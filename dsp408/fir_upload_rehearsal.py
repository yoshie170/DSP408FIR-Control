"""Source-derived numeric FIR transaction, restricted to explicit offline ports.

No worker/controller integration or permission to use HID. Full raw flash
comparison is a storage predicate, not proof of audio or power-cycle behavior.
"""
from dataclasses import dataclass
import hashlib
import struct
from dsp408.source_codec import fir_chunks, frame, integer
from dsp408.source_session import SourceDocument
from dsp408.prs_apply_transaction import PrsApplyRehearsal
from dsp408.channel_link import muted
from dsp408.link_research import resolve_link_mask

FF_BANK = b'\xff' * 65536


@dataclass(frozen=True)
class FirUploadPlan:
    channel: int
    state: bytes
    bank: bytes
    coefficient_bytes_le: bytes
    frames: tuple
    expected_state: bytes
    expected_bank: bytes
    sector_indices: tuple
    programmed_bytes: int


def prepare_fir_upload(state, bank, channel, coefficients):
    """Offline storage plan; does not authorize uploads or certify DSP resources."""
    integer(channel, 0, 11)
    state, bank = bytes(state), bytes(bank)
    doc = SourceDocument(state)
    if len(state) != 1556:
        raise ValueError('FIR plan requires explicit 1556-byte current state')
    if len(bank) != 65536:
        raise ValueError('FIR plan requires an explicit complete 65536-byte bank')
    channels = doc.decoded()['channels']
    masks = [row['link_mask_raw'] for row in channels]
    resolution = resolve_link_mask(masks, channel)
    if resolution.members != (channel,) or resolution.used_fallback or resolution.unknown_bits:
        raise ValueError('FIR upload requires an explicit self-only Link mask')
    if any(masks[ch] != 1 << (ch if ch<4 else ch-4) for ch in range(12)):
        raise ValueError('FIR profile refuses linked or ambiguous channel groups')
    coefficients = tuple(coefficients)
    payloads = fir_chunks(channel, coefficients)
    coefficient_bytes = b''.join(payload[4:] for payload in payloads)
    words = struct.unpack('>' + 'I' * len(coefficients), coefficient_bytes)
    coefficients_le = struct.pack('<' + 'I' * len(words), *words)
    offset = channel * 8192 if channel < 4 else 32768 + (channel-4) * 4096
    capacity = 8192 if channel < 4 else 4096
    sectors = tuple(range(offset // 4096, (offset + capacity) // 4096))
    erases = tuple(frame(0x58, sector.to_bytes(2, 'little')) for sector in sectors)
    chunks = tuple(frame(0x4E, payload) for payload in payloads)
    for raw in chunks:
        doc.apply(raw)
    # MCU9724 zero-fills RAM to2048 words; CA9A programs ceil(count/64)
    # full256-byte pages. Explicit58 erases the entire selected storage area.
    programmed = ((len(coefficients) + 63) // 64) * 256
    area = coefficients_le + b'\0' * (programmed-len(coefficients_le)) + b'\xff' * (capacity-programmed)
    expected_bank = bank[:offset] + area + bank[offset+capacity:]
    return FirUploadPlan(channel, state, bank, coefficients_le, erases + chunks,
                         bytes(doc.data), expected_bank, sectors, programmed)


class FirUploadRehearsal(PrsApplyRehearsal):
    def canonical_plan(self, plan):
        return prepare_fir_upload(plan.state, plan.bank, plan.channel,
                    struct.unpack('<' + 'f' * (len(plan.coefficient_bytes_le)//4), plan.coefficient_bytes_le))

    def report(self, stage, waiting=False):
        self.progress({'busy': True, 'operation': 'fir_upload_rehearsal',
                       'stage': stage, 'done': self.done, 'total': self.TOTAL,
                       'waiting': waiting, 'hardware_enabled': False})

    def run_plan(self, plan):
        self.check_port(self.port)
        canonical = self.canonical_plan(plan)
        if canonical != plan:
            raise ValueError('FIR plan differs from canonical source plan')
        self.TOTAL = 2678 + len(plan.frames)
        catalog = self.exchange(frame(0x22, b''), 0x22, 'Checking preset catalog')
        active = self.exchange(frame(0x14, b''), 0x14, 'Checking active slot')
        if len(catalog) != 19 or len(active) != 1 or not 1 <= active[0] <= 19:
            raise ValueError('FIR catalog/active slot differs')
        if self.state('Reading current parameters') != plan.state:
            raise ValueError('Current parameters changed after FIR review; no mutation')
        if self.bank('Reading complete current FIR') != plan.bank:
            raise ValueError('Current bank changed after FIR review; no mutation')
        self.record({'kind': 'fir_rehearsal_baseline', 'state_hex': plan.state.hex(),
                     'bank_hex': plan.bank.hex(), 'catalog_hex': catalog.hex(),
                     'active_slot': active[0], 'channel': plan.channel,
                     'coefficient_bytes_le_hex': plan.coefficient_bytes_le.hex(),
                     'hardware_enabled': False})

        def send(raw, path):
            self.record({'kind': 'setter_intent', 'operation': 'fir_upload_rehearsal',
                         'path': path, 'frame_hex': raw.hex(), 'hardware_enabled': False})
            self.exchange(raw, 1, path)

        for ch in range(12):
            send(frame(0x35, bytes((ch, 1))), 'Temporarily muting channel ' + str(ch))
        if self.state('Checking all channels muted') != muted(plan.state):
            raise ValueError('Mute readback differs; no FIR transfer')
        for i, raw in enumerate(plan.frames):
            send(raw, 'FIR transfer step ' + str(i))
        if self.state('Checking count/type before unmute') != muted(plan.expected_state):
            raise ValueError('FIR parameter readback differs; no automatic unmute')
        if self.bank('Checking entire FIR bank before unmute') != plan.expected_bank:
            raise ValueError('FIR storage readback differs; no automatic unmute')
        for ch in range(12):
            offset, bit = (1432, ch) if ch < 4 else (1434, ch-4)
            flag = (int.from_bytes(plan.state[offset:offset+2], 'little') >> bit) & 1
            send(frame(0x35, bytes((ch, flag))), 'Restoring original Mute channel ' + str(ch))
        if self.state('Checking final parameters') != plan.expected_state:
            raise ValueError('Final FIR parameters differ; no automatic restore')
        if self.exchange(frame(0x22, b''), 0x22, 'Checking unchanged catalog') != catalog:
            raise ValueError('FIR preset catalog changed')
        if self.exchange(frame(0x14, b''), 0x14, 'Checking unchanged active slot') != active:
            raise ValueError('FIR active slot changed')
        result = {'operation': 'fir_upload_rehearsal', 'hardware_enabled': False,
                  'channel': plan.channel, 'parameters_verified': True,
                  'storage_matches_source_prediction': True,
                  'state_sha256': hashlib.sha256(plan.expected_state).hexdigest(),
                  'bank_sha256': hashlib.sha256(plan.expected_bank).hexdigest(),
                  'audio_verified': False, 'power_cycle_persistence_verified': False,
                  'done': self.done, 'total': self.TOTAL}
        self.record({'kind': 'fir_rehearsal_verified', **result})
        self.progress({'busy': False, **result})
        return plan.expected_state, result
