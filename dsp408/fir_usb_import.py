"""Manual IN FIR replacement/bypass with bounded transaction permits."""
from dataclasses import dataclass
import math
import struct
from dsp408.source_codec import frame, integer
from dsp408.source_session import SourceDocument
from dsp408.fir_upload_rehearsal import FirUploadPlan, FirUploadRehearsal, prepare_fir_upload

FIR_IMPORT_AUTHORIZED = True
BLOCK_REASON = 'FIR import and bypass require authorization in this profile'
# The release profile limits imported input filters to512 coefficients.
# This is a release limit, not a claim that EXE storage capacity equals DSP capacity.
INPUT_UPLOAD_LIMIT = 512


def resource_usage(state):
    """Reconstruct the pinned editor's active FIR tap accounting, not CPU percent."""
    channels = SourceDocument(state).decoded()['channels']
    used = 0
    for ch, row in enumerate(channels):
        if ch < 4:
            count = integer(row['fir_coefficient_count_raw'], 0, 2048)
            bypass = integer(row['fir_bypass_raw'], 0, 1)
            used += 0 if bypass else count
        else:
            mode = integer(row['crossover_processing_mode_raw'], 0, 1)
            typ = integer(row['fir_type_raw'], 0, 4)
            if mode and typ:
                count = integer(row['fir_tap_parameter_raw'], 0, 1024 if typ == 4 else 24)
                used += count if typ == 4 else 256 + 32*count
    if used > 4096:
        raise ValueError('Current configuration exceeds the confirmed editor FIR budget')
    return used


def available_input_taps(state, channel):
    integer(channel, 0, 3)
    from dsp408.channel_link import validate_group_state,members_for
    members=members_for(validate_group_state(state),channel)
    rows = SourceDocument(state).decoded()['channels']
    used = resource_usage(state)
    old=sum(0 if rows[i]['fir_bypass_raw'] else rows[i]['fir_coefficient_count_raw'] for i in members)
    return min(INPUT_UPLOAD_LIMIT, (4096-used+old)//len(members))


@dataclass(frozen=True)
class InputFirPlan(FirUploadPlan):
    coefficients: tuple | None
    bypass: bool
    clear: bool = False


def prepare_input_fir(state, bank, channel, coefficients, bypass, clear=False):
    integer(channel, 0, 3)
    if type(bypass) is not bool:
        raise ValueError('Explicit FIR bypass choice required')
    if type(clear) is not bool or (clear and (coefficients is not None or not bypass)):
        raise ValueError('Clear requires bypass and no coefficient upload')
    state, bank = bytes(state), bytes(bank)
    if len(state) != 1556 or len(bank) != 65536:
        raise ValueError('Fresh complete state and FIR bank required')
    available = available_input_taps(state, channel)
    from dsp408.channel_link import validate_group_state,members_for,mask_offset,self_mask
    masks=validate_group_state(state);members=members_for(masks,channel)
    # Pure independent shadow for existing per-record codec. Actual wire4E
    # resolves the group in9724 and applies/writes each member in its own loop.
    shadow=bytearray(state)
    for i in range(12):shadow[mask_offset(i):mask_offset(i)+2]=self_mask(i).to_bytes(2,'little')
    row = SourceDocument(state).decoded()['channels'][channel]
    count = row['fir_coefficient_count_raw']
    if coefficients is not None:
        values = tuple(coefficients)
        base = prepare_fir_upload(shadow, bank, channel, values)
        # Canonicalization always uses the actual binary32 transferred values.
        values = struct.unpack('<'+'f'*len(values), base.coefficient_bytes_le)
        if any(v > 50 for v in values):
            raise ValueError('Coefficient exceeds the confirmed editor upper guard of 50')
        count = len(values)
        if count > available:
            raise ValueError(f'Current FIR budget allows at most {available} coefficients on this input')
    else:
        values = None
        # Reuse explicit self-only Link validation without changing storage.
        prepare_fir_upload(shadow, bank, channel, [1.])
        base = FirUploadPlan(channel, state, bank, b'', (), state, bank, (), 0)
    if not bypass:
        if not 1 <= count <= available:
            raise ValueError(f'FIR activation needs 1..{available} coefficients')
        for member in members:
            raw = base.coefficient_bytes_le if values is not None else bank[member*8192:member*8192+count*4]
            if not all(math.isfinite(v) and v <= 50 for v in struct.unpack('<'+'f'*count, raw)):
                raise ValueError('Selected group does not contain valid finite FIR; import a file first')
    doc = SourceDocument(shadow)
    storage=bytearray(bank);sectors=();programmed=0
    if values is not None:
        for member in members:
            member_plan=prepare_fir_upload(bytes(doc.data),bytes(storage),member,values)
            for packet in member_plan.frames:
                if packet[5]==0x4E:doc.apply(packet)
            storage[:]=member_plan.expected_bank
            sectors+=member_plan.sector_indices;programmed+=member_plan.programmed_bytes
        chunks=tuple(raw for raw in base.frames if raw[5]==0x4E)
        frames=tuple(frame(0x58,s.to_bytes(2,'little')) for s in sectors)+chunks
    else:frames=()
    toggle = frame(0x4F, bytes((channel, int(bypass))))
    for member in members:doc.apply(frame(0x4F,bytes((member,int(bypass)))))
    frames+=(toggle,)
    if clear:
        sectors=tuple(s for m in members for s in (m*2,m*2+1))
        for member in members:storage[member*8192:member*8192+8192]=b'\xff'*8192
        frames=(toggle,)+tuple(frame(0x58,s.to_bytes(2,'little')) for s in sectors)
    for i in range(12):doc.data[mask_offset(i):mask_offset(i)+2]=masks[i].to_bytes(2,'little')
    resource_usage(bytes(doc.data));validate_group_state(bytes(doc.data))
    return InputFirPlan(channel, state, bank, base.coefficient_bytes_le,
                        frames, bytes(doc.data), bytes(storage),
                        sectors, programmed, values, bypass, clear)


@dataclass(frozen=True)
class InputFirPermit:
    plan: InputFirPlan
    requests: tuple

    @property
    def state(self): return self.plan.state


def prepare_import(state, bank, channel, coefficients, bypass, clear=False):
    plan = prepare_input_fir(state, bank, channel, coefficients, bypass, clear)
    states = tuple(frame(0x27, bytes((i,))) for i in range(32))
    banks = tuple(frame(0x56, b'\0'+i.to_bytes(2, 'little')) for i in range(1261))
    catalog = (frame(0x22, b''), frame(0x14, b''))
    mutes = tuple(frame(0x35, bytes((ch, 1))) for ch in range(12))
    final = []
    for ch in range(12):
        offset, bit = (1432, ch) if ch < 4 else (1434, ch-4)
        flag = (int.from_bytes(plan.state[offset:offset+2], 'little') >> bit) & 1
        final.append(frame(0x35, bytes((ch, flag))))
    return InputFirPermit(plan, catalog+states+banks+mutes+states+plan.frames+
                          states+banks+tuple(final)+states+catalog)


class InputFirRehearsal(FirUploadRehearsal):
    def run_plan(self,plan):
        self.clearing=plan.clear
        return super().run_plan(plan)

    def report(self, stage, waiting=False):
        if stage.startswith('FIR transfer step'):phase='Clear · bypass and erase selected input' if getattr(self,'clearing',False) else 'Transfer · erase, coefficients and activation'
        elif stage.startswith(('Checking count/type','Checking entire FIR')):phase='Verification · full FIR bank and parameters'
        elif stage.startswith(('Restoring original','Checking final','Checking unchanged')):phase='Finishing · restore Mute and verify final state'
        elif stage.startswith(('Temporarily muting','Checking all channels muted')):phase='Mute · preparing channel state'
        else:phase='Preflight · full FIR bank and parameters'
        self.progress({'busy':True,'operation':'fir_upload_rehearsal','stage':stage,
            'operation_phase':phase,'done':self.done,'total':self.TOTAL,
            'waiting':waiting,'hardware_enabled':False})

    def canonical_plan(self, plan):
        return prepare_input_fir(plan.state, plan.bank, plan.channel, plan.coefficients, plan.bypass,plan.clear)


class UsbInputFir(InputFirRehearsal):
    def check_port(self, port):
        if not FIR_IMPORT_AUTHORIZED: raise ValueError(BLOCK_REASON)

    def exchange(self, raw, *args, **kwargs):
        if not FIR_IMPORT_AUTHORIZED: raise ValueError(BLOCK_REASON)
        # Final4E performs the native loop's flash programming for all members.
        if raw[5]==0x4E and (raw[7]+1)*12>=int.from_bytes(raw[8:10],'little'):
            kwargs.setdefault('timeout',10.)
        self.port.arm_prs_request(raw, self.permit)
        return super().exchange(raw, *args, **kwargs)

    def run_import(self, permit):
        p = permit.plan
        if type(permit) is not InputFirPermit or permit != prepare_import(p.state, p.bank, p.channel, p.coefficients, p.bypass,p.clear):
            raise ValueError('Input FIR permit differs from canonical plan')
        self.check_port(self.port); self.permit = permit
        self.port.begin_prs_import(permit)
        original_record, original_progress = self.record, self.progress
        def record(event):
            event = dict(event)
            if event.get('kind') == 'fir_rehearsal_baseline':
                event.update(bypass=p.bypass, upload=p.coefficients is not None,
                             upload_limit=INPUT_UPLOAD_LIMIT)
                if p.clear:event['clear']=True
            if event.get('kind') == 'fir_rehearsal_verified': self.port.complete_prs_import(permit)
            if event.get('operation') == 'fir_upload_rehearsal': event['operation'] = 'fir_import'
            if event.get('kind', '').startswith('fir_rehearsal_'):
                event['kind'] = event['kind'].replace('fir_rehearsal_', 'fir_import_', 1)
            event['hardware_enabled'] = True; original_record(event)
        def progress(event):
            original_progress({**event, 'operation': 'fir_import', 'hardware_enabled': True, 'busy': True})
        self.record, self.progress = record, progress
        try:
            state, result = self.run_plan(p)
            return state, {**result, 'operation': 'fir_import', 'hardware_enabled': True,
                           'bank_hex': p.expected_bank.hex(), 'bypass': p.bypass,'clear':p.clear}
        finally:
            self.port.end_prs_import(); self.record, self.progress = original_record, original_progress
