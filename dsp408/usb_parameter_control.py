"""Serialized USB control for the audited FIR408 V0115P protocol.

Parameters, presets, PRS, FIR and device utilities share one transport owner.
Each operation has a bounded request policy and explicit confirmation where
required. FIR activation checks verified storage; imports use typed transactions.
Password commands and sensitive replies are redacted. There is no unrestricted
raw-frame API, automatic retry or automatic restoration after a failed write.
"""
from pathlib import Path
from threading import Event, Lock
import time
from uuid import uuid4

from PySide6.QtCore import QThread, Signal
from dsp408.model import DeviceModel
from dsp408.source_session import SourceDocument, project_state
from dsp408.source_bindings import _plan_validated_changes
from dsp408.source_codec import frame
from dsp408.usb_read import HidReadPort, validate_read_request, read_bus_frame
from dsp408.usb_journal import DurableJournal
from dsp408.control_fir_refresh import FirRefreshMixin

PARAMETERS = frozenset((0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x38, 0x3A, 0x3D, 0x3E, 0x3F, 0x41, 0x4C, 0x4F, 0x5B))
from dsp408.app_paths import JOURNAL_DIRECTORY


def state_model(raw):
    if len(raw) != 1556: raise ValueError('Control requires the complete 1556-byte state')
    doc = SourceDocument(raw)
    channels = doc.decoded()['channels']
    from dsp408.channel_link import validate_group_state
    validate_group_state(raw)
    model, issues = project_state(doc, DeviceModel().to_dict(), strict=False)
    if issues: raise ValueError('Control unavailable: raw values cannot be represented by the UI')
    return doc, model


def prepare(raw, wanted, fir_bank=None):
    """Reuse audited encoders, preserving raw co-fields; reject partial plans."""
    doc, model = state_model(raw)
    wanted=DeviceModel.from_dict(wanted).to_dict()
    if wanted.get('device_link_masks')!=model.to_dict().get('device_link_masks'):
        raise ValueError('Change Link groups through the separate Link review')
    from dsp408.channel_link import validate_wanted_groups,masks
    validate_wanted_groups(wanted,masks(raw))
    # Display units do not travel to the DSP.
    model.settings['delay_unit'] = wanted['settings']['delay_unit']
    plan = _plan_validated_changes(model.to_dict(), wanted, raw_state=doc.decoded())
    if plan.blocked or plan.local_only:
        raise ValueError('Unsupported control change: ' + str(plan.blocked + plan.local_only))
    packets = []
    for p in plan.packets:
        if p.command not in PARAMETERS: raise ValueError(f'0x{p.command:02X} is not released for USB control')
        if p.command==0x3D:
            from dsp408.channel_names import encode_channel_name
            encode_channel_name(wanted['inputs' if p.payload[0]<4 else 'outputs'][p.payload[0] if p.payload[0]<4 else p.payload[0]-4]['name'])
        if p.command==0x5B:
            from dsp408.channel_names import encode_fir_name
            encode_fir_name((wanted['inputs']+wanted['outputs'])[p.payload[0]]['fir']['name'])
        raw_frame = frame(p.command, p.payload)
        before = bytes(doc.data)
        if p.command==0x4F:
            from dsp408.fir_usb_import import FIR_IMPORT_AUTHORIZED,prepare_input_fir
            if not FIR_IMPORT_AUTHORIZED:raise ValueError('FIR bypass authorization revoked')
            if p.payload[0]>=4 or p.payload[1] not in (0,1):raise ValueError('Only input FIR bypass is released')
            if not p.payload[1]:
                if fir_bank is None:raise ValueError('Read complete FIR storage before activation')
                from dsp408.channel_link import masks,self_mask,validate_input_activation
                if masks(before)==tuple(self_mask(i) for i in range(12)):
                    prepare_input_fir(before,fir_bank,p.payload[0],None,False)
                else:validate_input_activation(before,fir_bank,p.payload[0])
        from dsp408.channel_link import apply_parameter
        apply_parameter(doc,raw_frame)
        if p.command==0x4C:
            from dsp408.fir_usb_import import resource_usage
            resource_usage(bytes(doc.data))
        if doc.data != before: packets.append((raw_frame, p.path))
    return packets, bytes(doc.data)


class ParameterPolicy:
    def __init__(self): self.armed = None;self.preset_armed=None;self.prs_permit=None;self.prs_index=0;self.prs_armed=None;self.startup_fir=None;self.utility_armed=None

    def arm_utility(self,request):
        from dsp408.device_utilities import validate_utility
        validate_utility(request)
        if any(x is not None for x in (self.armed,self.preset_armed,self.prs_permit,self.startup_fir,self.utility_armed)):
            raise ValueError('Another USB operation is armed')
        self.utility_armed=request.packet

    def begin_fir_startup(self,*,source_display=False):
        from dsp408.usb_control_startup import StartupFirWindow,SourceStartupFirWindow
        if type(source_display) is not bool:raise ValueError('Explicit FIR strategy required')
        if self.utility_armed is not None or self.startup_fir is not None or self.armed is not None or self.preset_armed is not None or self.prs_permit is not None:
            raise ValueError('Another USB operation is armed')
        self.startup_fir=SourceStartupFirWindow() if source_display else StartupFirWindow()

    def observe_fir_startup(self,raw):
        from dsp408.usb_control_startup import SourceStartupFirWindow
        if not isinstance(self.startup_fir,SourceStartupFirWindow):raise ValueError('No source FIR startup window')
        self.startup_fir.observe(raw)

    def arm_fir_startup(self,raw):
        if self.startup_fir is None:raise ValueError('No startup FIR window')
        self.startup_fir.arm(raw)

    def complete_fir_startup(self):
        if self.startup_fir is None:raise ValueError('No startup FIR window')
        self.startup_fir.complete();self.startup_fir=None

    def end_fir_startup(self):self.startup_fir=None

    def begin_prs_import(self,permit):
        from dsp408.usb_transaction_permit import verify_permit
        verify_permit(permit,reconstruct=True)
        if self.utility_armed is not None or self.startup_fir is not None or self.armed is not None or self.preset_armed is not None or self.prs_permit is not None:
            raise ValueError('Another USB operation is armed')
        self.prs_permit=permit;self.prs_index=0

    def arm_prs_request(self,raw,permit):
        from dsp408.usb_transaction_permit import verify_permit
        verify_permit(permit)
        if permit is not self.prs_permit or self.prs_armed is not None or self.prs_index>=len(permit.requests):
            raise ValueError('PRS request outside active transaction')
        if raw!=permit.requests[self.prs_index]:raise ValueError('PRS request is not the next exact frame')
        self.prs_armed=bytes(raw)

    def end_prs_import(self):
        self.prs_permit=None;self.prs_armed=None;self.prs_index=0

    def complete_prs_import(self,permit):
        from dsp408.usb_transaction_permit import verify_permit
        verify_permit(permit)
        if permit is not self.prs_permit or self.prs_armed is not None or self.prs_index!=len(permit.requests):
            raise ValueError('PRS transaction did not consume the complete exact plan')

    def arm_preset_request(self,raw,slot,target=None):
        from dsp408.preset_recall import checked_slot,eeprom_requests,check_target
        checked_slot(slot)
        if self.utility_armed is not None or self.startup_fir is not None or self.armed is not None or self.preset_armed is not None or self.prs_permit is not None:raise ValueError('Another USB operation is armed')
        if raw not in eeprom_requests(slot):
            if raw!=frame(0x20,bytes((slot,))) or target is None:raise ValueError('Request outside selected preset')
            check_target(slot,*target)
        self.preset_armed=bytes(raw)

    def arm_store_request(self,raw,slot,context):
        from dsp408.preset_store import validate_store_context,encode_name
        validate_store_context(slot,context)
        if self.utility_armed is not None or self.startup_fir is not None or self.armed is not None or self.preset_armed is not None or self.prs_permit is not None:raise ValueError('Another USB operation is armed')
        if raw!=frame(0x21,bytes((slot,))):
            if len(raw)!=23 or raw!=frame(0x26,raw[6:20]):raise ValueError('Store request outside scope')
            if encode_name(raw[6:20].decode('ascii'))!=raw[6:20]:raise ValueError('Name payload is not canonical ASCII14')
        self.preset_armed=bytes(raw)

    def arm(self, state, wanted, raw):
        packets, _ = prepare(state, wanted, getattr(self,'fir_bank',None))
        if self.utility_armed is not None or self.startup_fir is not None or self.armed is not None or self.preset_armed is not None or self.prs_permit is not None or raw not in [p[0] for p in packets]:
            raise ValueError('Setter must belong to the current validated model change')
        self.armed = bytes(raw)

    def validate(self, raw):
        if self.utility_armed is not None:
            if raw!=self.utility_armed:raise ValueError('Request differs from armed utility')
            self.utility_armed=None
            return raw[5]!=0x19
        if self.startup_fir is not None and len(raw)>5 and raw[5]==0x56:
            self.startup_fir.consume(raw);return False
        if self.prs_permit is not None:
            from dsp408.usb_transaction_permit import verify_permit
            verify_permit(self.prs_permit)
            if raw!=self.prs_armed:raise ValueError('Unarmed request during PRS import')
            self.prs_armed=None;self.prs_index+=1
            from dsp408.preset_bank import BankBackupPermit
            if type(self.prs_permit) is BankBackupPermit:return False
            from dsp408.preset_bank_restore import BankRestorePermit
            if type(self.prs_permit) is BankRestorePermit:return raw[5] not in (0x14,0x19,0x22,0x27,0x29,0x56)
            return raw[5] not in (0x14,0x22,0x27,0x56)
        if raw==self.preset_armed:
            self.preset_armed=None
            if raw[5] in (0x21,0x26):
                from dsp408.preset_store import PRESET_STORE_AUTHORIZED,BLOCK_REASON
                if not PRESET_STORE_AUTHORIZED:raise ValueError(BLOCK_REASON)
            return raw[5] in (0x20,0x21,0x26)
        if raw == self.armed:
            self.armed = None  # consume before I/O, including failures
            return True
        validate_read_request(raw)
        return False


class HidParameterPort(HidReadPort):
    def __init__(self, record, stop):
        super().__init__()
        self.policy, self.record, self.stop_event = ParameterPolicy(), record, stop
        self.redact_tails=False;self.secret_reply=None

    def arm_parameter(self, state, wanted, raw): self.policy.arm(state, wanted, raw)
    def arm_utility(self,request):self.policy.arm_utility(request)
    def cache_fir_bank(self,raw):self.policy.fir_bank=raw

    def arm_preset_request(self,raw,slot,target=None):self.policy.arm_preset_request(raw,slot,target)
    def arm_store_request(self,raw,slot,context):self.policy.arm_store_request(raw,slot,context)
    def begin_fir_startup(self,**kwargs):self.policy.begin_fir_startup(**kwargs)
    def observe_fir_startup(self,raw):self.policy.observe_fir_startup(raw)
    def arm_fir_startup(self,raw):self.policy.arm_fir_startup(raw)
    def complete_fir_startup(self):self.policy.complete_fir_startup()
    def end_fir_startup(self):self.policy.end_fir_startup()
    def begin_prs_import(self,permit):self.policy.begin_prs_import(permit)
    def arm_prs_request(self,raw,permit):self.policy.arm_prs_request(raw,permit)
    def end_prs_import(self):self.policy.end_prs_import()
    def complete_prs_import(self,permit):self.policy.complete_prs_import(permit)

    def write(self, raw):
        raw = bytes(raw)
        setter = self.policy.validate(raw)
        # Normal user disconnect still sends the captured empty11. Pending
        # reads/Recall/parameters remain cancelled; error paths never send11.
        if self.stop_event.is_set() and raw!=frame(0x11,b''):
            raise InterruptedError('USB operation cancelled before write')
        secret=raw[5] in (0x2D,0x2F)
        if secret:
            self.redact_tails=True;self.secret_reply=0x2D if raw[5]==0x2D else 1
        details={'command':raw[5],'password_redacted':True} if secret else {'frame_hex':raw.hex()}
        self.record({'kind': 'setter_intent' if setter else 'tx_intent', **details})
        if self.device.write(b'\0' + raw + bytes(64-len(raw))) != 65:
            raise OSError('Incomplete USB report; no retry')
        self.record({'kind': 'tx_completed', **details, 'setter': setter})

    def read(self, timeout_ms):
        raw = super().read(timeout_ms)
        if raw:
            if self.secret_reply is not None or (len(raw)>5 and raw[5] in (0x2D,0x2F)):
                packet=read_bus_frame(raw)
                self.redact_tails=True
                self.record({'kind':'rx_sensitive_reply','command':packet.command,'password_redacted':True})
                if (self.secret_reply==1 and packet.command==1 and not packet.data or
                    self.secret_reply==0x2D and packet.command==0x2D and packet.data in (b'\0\0',b'\0\1')):
                    self.secret_reply=None
            elif self.redact_tails:
                self.record({'kind':'rx_frame','frame_hex':read_bus_frame(raw).raw.hex(),'unused_tail_redacted':True})
            else:self.record({'kind': 'rx_report', 'report_hex': raw.hex()})
        return raw


class ParameterService:
    """One USB owner, latest desired state, one setter/read block per idle turn.

    Setters take priority over background verification. A setter is never
    followed by a blocking full-state round trip. An empty01 is only the common
    MCU completion reply; readback separately confirms byte effects.
    """
    def __init__(self, port, stop, *, record, configuration, confirmed, availability,
                 pending, status, log, clock=time.monotonic,preset_metadata=lambda _:None,
                 recall_progress=lambda _:None,recall_result=lambda _:None,utility_state=lambda _:None,
                 reply_decoder=read_bus_frame,allowed_commands=PARAMETERS,response_timeout=2.,medium='USB',
                 recall_class=None,store_class=None):
        if not frozenset(allowed_commands)<=PARAMETERS:raise ValueError('Unknown parameter command scope')
        if medium not in ('USB','Ethernet') or response_timeout not in (2.,5.):raise ValueError('Unknown control transport profile')
        self.reply_decoder=reply_decoder;self.allowed_commands=frozenset(allowed_commands)
        self.response_timeout=response_timeout;self.medium=medium
        self.recall_class=recall_class
        self.store_class=store_class
        self.port, self.stop, self.record, self.clock = port, stop, record, clock
        self.configuration, self.confirmed, self.availability = configuration, confirmed, availability
        self.pending, self.status, self.log = pending, status, log
        self.preset_metadata=preset_metadata;self.recall_progress=recall_progress;self.recall_result=recall_result
        self.recall_slot=None;self.recall_running=False;self.recall_failed=False
        self.store_request=None;self.prs_request=None
        self.lock = Lock()
        self.expected = None
        self.fir_bank = None
        self.wanted = None
        self.generation = self.sent_generation = 0
        self.confirmed_generation = 0
        self.ready = False
        self.last_send = 0.
        self.requested_at = 0.
        self.dirty_blocks = set()
        self.dirty_paths, self.dirty_commands = set(), set()
        self.scrub = None
        self.next_scrub = float('inf')
        self.startup_boundary = True
        self.startup_status_ack = False
        self.inflight = False
        self.planned_generation = -1
        self.packets = []
        from dsp408.usb_device_utilities import DeviceUtilities
        self.utilities=DeviceUtilities(self,utility_state)

    def observe_fir_bank(self,raw):
        if raw is not None and len(raw)!=65536:raise ValueError('Complete FIR bank required')
        self.fir_bank=None if raw is None else bytes(raw)
        cache=getattr(self.port,'cache_fir_bank',None)
        if cache is not None:cache(self.fir_bank)

    def observe_configuration(self, raw):
        self.configuration(bytes(raw))
        self.expected=bytes(raw)
        try: _, model = state_model(raw)
        except ValueError as e:
            self.status(self.medium+' control locked: ' + str(e)); self.availability(False); return
        with self.lock:
            self.expected, self.wanted = bytes(raw), model.to_dict()
            self.ready = True
        self.record({'kind': 'control_baseline', 'state_hex': bytes(raw).hex(),
                     'identity': 'FIR408 V0115P', 'source_families': sorted(self.allowed_commands)})
        self.availability(True)
        self.status(self.medium+' control · EXE/MCU families available for verification')

    def prepare_parameters(self,state,wanted):
        packets,expected=prepare(state,wanted,self.fir_bank)
        if any(raw[5] not in self.allowed_commands for raw,path in packets):
            raise ValueError('This parameter family is not released for '+self.medium+' control')
        return packets,expected

    def request(self, wanted, generation):
        if self.utilities.locked or self.utilities.busy:return False
        # All planning is repeated in the USB thread against its newest cache.
        wanted = DeviceModel.from_dict(wanted).to_dict()
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None or self.recall_running: return False
            self.prepare_parameters(self.expected, wanted)  # refuse unsupported/local-only changes before UI commit
            self.wanted, self.generation = wanted, generation
            self.requested_at = self.clock()
        return True

    def request_recall(self,slot):
        if self.utilities.locked or self.utilities.busy:return False
        from dsp408.preset_recall import checked_slot
        checked_slot(slot)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or self.expected is None or self.stop.is_set() or self.recall_failed or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None or self.recall_running:
                return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation:
                return False
            self.recall_slot=slot
        self.recall_progress({'busy':True,'slot':slot,'stage':'Preparing preset recall',
                              'done':0,'total':70,'waiting':True})
        return True

    def request_store(self,slot,name,confirmed_target):
        if self.utilities.locked or self.utilities.busy:return False
        from dsp408.preset_store import PRESET_STORE_AUTHORIZED,BLOCK_REASON,encode_name
        from dsp408.preset_recall import checked_slot
        if not PRESET_STORE_AUTHORIZED:raise ValueError(BLOCK_REASON)
        checked_slot(slot);encode_name(name)
        if not isinstance(confirmed_target,dict):raise ValueError('Confirmed Store destination required')
        with self.lock:
            if self.utilities.locked or self.utilities.busy or self.expected is None or self.stop.is_set() or self.recall_failed or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None or self.recall_running:
                return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation:return False
            self.store_request=(slot,name,dict(confirmed_target))
        self.recall_progress({'busy':True,'operation':'store','slot':slot,'stage':'Preparing preset Store',
                              'done':0,'total':168,'waiting':True})
        return True

    def request_prs_import(self,state,prs,bank=None):
        if self.utilities.locked or self.utilities.busy:return False
        from dsp408.prs_usb_import import PRS_IMPORT_AUTHORIZED,BLOCK_REASON,prepare_import
        if not PRS_IMPORT_AUTHORIZED:raise ValueError(BLOCK_REASON)
        if bank is None:permit,_=prepare_import(state,prs)
        else:
            from dsp408.prs_full_import import prepare_full_import
            permit,_=prepare_full_import(state,bank,prs)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected:return False
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'prs_import','stage':'Preparing PRS parameter import',
                              'done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_fir_trial(self,state):
        if self.utilities.locked or self.utilities.busy:return False
        from dsp408.fir_usb_trial import FIR_TRIAL_AUTHORIZED,BLOCK_REASON,prepare_fir_trial
        if not FIR_TRIAL_AUTHORIZED:raise ValueError(BLOCK_REASON)
        permit=prepare_fir_trial(state)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected:return False
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'fir_trial','stage':'Preparing IN A identity FIR256 trial',
                              'done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_input_fir(self,state,bank,channel,coefficients,bypass,clear=False):
        if self.utilities.locked or self.utilities.busy:return False
        from dsp408.fir_usb_import import FIR_IMPORT_AUTHORIZED,BLOCK_REASON,prepare_import
        if not FIR_IMPORT_AUTHORIZED:raise ValueError(BLOCK_REASON)
        permit=prepare_import(state,bank,channel,coefficients,bypass,clear)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected:return False
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'fir_import','stage':'Preparing input FIR',
                              'done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_output_fir(self,state,bank,channel,settings):
        from dsp408.output_fir import prepare_output_permit
        permit=prepare_output_permit(state,bank,channel,settings)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected:return False
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'output_fir','stage':'Preparing output crossover','done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_link(self,state,bank,selected,members):
        from dsp408.channel_link import prepare_link
        permit=prepare_link(state,bank,selected,members)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected:return False
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'channel_link','stage':'Preparing channel Link','done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_bank_backup(self,state,bank,catalog,active,names,destination,extended=False):
        from dsp408.preset_bank import prepare_backup
        permit=prepare_backup(state,bank,catalog,active,names,extended)
        destination=Path(destination)
        if destination.suffix.lower()!='.dspbank':raise ValueError('Use a .dspbank destination')
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected or permit.bank!=self.fir_bank:return False
            self.backup_destination=destination;self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'bank_backup','stage':'Preparing preset bank backup','done':0,'total':len(permit.requests),'waiting':False})
        return True

    def request_bank_restore(self,state,bank,catalog,active,names,records,banks,source):
        from dsp408.preset_bank_restore import prepare_restore
        permit=prepare_restore(state,bank,catalog,active,names,records,banks)
        with self.lock:
            if self.utilities.locked or self.utilities.busy or not self.ready or self.stop.is_set() or self.recall_failed or self.recall_running or self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:return False
            if self.inflight or self.dirty_blocks or self.generation!=self.confirmed_generation or permit.state!=self.expected or permit.bank!=self.fir_bank:return False
            self.restore_source=Path(source);self.restore_directory=JOURNAL_DIRECTORY/'bank-restore'
            self.prs_request=permit
        self.recall_progress({'busy':True,'operation':'bank_restore','stage':'Preparing backup before restore','done':0,'total':len(permit.requests),'waiting':False})
        return True

    def dispatch_recall(self):
        from dsp408.preset_recall import RecallOperation
        with self.lock:
            store=self.store_request;self.store_request=None
            prs=self.prs_request;self.prs_request=None
            slot=store[0] if store else self.recall_slot
            self.recall_running=True;self.recall_slot=None
        from dsp408.fir_usb_trial import FirTrialPermit
        from dsp408.fir_usb_import import InputFirPermit
        from dsp408.output_fir import OutputFirPermit,OutputFirOperation
        from dsp408.channel_link import LinkPermit,LinkOperation
        from dsp408.prs_full_import import FullPrsPermit,FullPrsOperation
        from dsp408.preset_bank import BankBackupPermit,BankBackupOperation
        from dsp408.preset_bank_restore import BankRestorePermit,BankRestoreOperation
        bank_backup=type(prs) is BankBackupPermit
        bank_restore=type(prs) is BankRestorePermit
        if not (bank_backup or bank_restore):self.utilities.invalidate_generator()
        full_prs=type(prs) is FullPrsPermit
        channel_link=type(prs) is LinkPermit
        output_fir=type(prs) is OutputFirPermit
        fir_import=type(prs) is InputFirPermit
        fir=type(prs) is FirTrialPermit
        action='Bank restore' if bank_restore else 'Bank backup' if bank_backup else 'Link' if channel_link else 'Output FIR' if output_fir else 'FIR import' if fir_import else 'FIR trial' if fir else 'PRS import' if prs else 'Store' if store else 'Recall'
        self.availability(False)
        try:
            if bank_restore:operation_class=BankRestoreOperation
            elif bank_backup:operation_class=BankBackupOperation
            elif full_prs:operation_class=FullPrsOperation
            elif channel_link:operation_class=LinkOperation
            elif output_fir:operation_class=OutputFirOperation
            elif fir_import:
                from dsp408.fir_usb_import import UsbInputFir
                operation_class=UsbInputFir
            elif fir:
                from dsp408.fir_usb_trial import UsbFirTrial
                operation_class=UsbFirTrial
            elif prs:
                from dsp408.prs_usb_import import UsbPrsImport
                operation_class=UsbPrsImport
            elif store:
                from dsp408.preset_store import StoreOperation
                operation_class=self.store_class or StoreOperation
            else:operation_class=self.recall_class or RecallOperation
            operation=operation_class(self.port,self.stop,record=self.record,log=self.log,
                                      progress=self.recall_progress,clock=self.clock,
                                      **({'reply_decoder':self.reply_decoder,'default_timeout':self.response_timeout} if self.medium=='Ethernet' else {}))
            if bank_backup:operation.destination=self.backup_destination
            if bank_restore:
                operation.source_path=self.restore_source;operation.backup_directory=self.restore_directory
            if prs:
                raw,result=operation.run_import(prs);metadata={}
            else:raw,metadata,result=operation.run(slot,self.expected,store[1],store[2]) if store else operation.run(slot)
            self.expected=raw
            self.observe_fir_bank(bytes.fromhex(result['bank_hex']) if result.get('bank_hex') is not None and (result.get('operation') in ('fir_import','output_fir','channel_link','bank_backup','bank_restore') or result.get('full_prs')) else None)
            self.scrub=None;self.next_scrub=float('inf');self.packets=[];self.planned_generation=-1
            self.dirty_blocks.clear();self.dirty_paths.clear();self.dirty_commands.clear()
            try:_,model=state_model(raw)
            except ValueError as error:
                self.ready=False;self.wanted=None;self.status(f'Preset {action} complete; channel control locked: '+str(error))
            else:
                self.wanted=model.to_dict();self.ready=True
                self.status('Preset bank restored · current configuration unchanged' if bank_restore else 'Preset bank backup saved · current configuration unchanged' if bank_backup else 'Configuration and FIR imported · full readback verified' if full_prs else 'Channel Link applied · parameters checked' if channel_link else 'Output FIR crossover applied · full bank and parameters verified' if output_fir else 'Input FIR complete · full bank and parameters verified' if fir_import else 'IN A FIR256 trial complete · parameters and full storage verified' if fir else 'PRS parameters imported · unchanged FIR verified' if prs else f'P{slot:02d} '+('saved' if store else 'loaded')+' · full parameter readback verified')
            if metadata:self.preset_metadata(metadata)
            if bank_restore:self.preset_metadata(result['metadata'])
            if not (bank_backup or bank_restore):self.configuration(raw);self.confirmed(raw,self.generation)
            # Publish readiness before completion closes the modal dialog.
            # Queued Qt signals must not expose a finished preset with stale
            # unavailable controls to the next user gesture.
            self.pending(False);self.availability(self.ready);self.recall_result(result)
        except Exception as error:
            self.ready=False;self.recall_failed=True;self.availability(False)
            self.recall_progress({'busy':False,'operation':'bank_restore' if bank_restore else 'bank_backup' if bank_backup else 'output_fir' if output_fir else 'fir_import' if fir_import else 'fir_trial' if fir else 'prs_import' if prs else 'store' if store else 'recall','slot':slot,'stage':action+' stopped · '+str(error),
                                  'done':0,'total':70,'waiting':False,'failed':True})
            self.record({'kind':'bank_restore_failed' if bank_restore else 'bank_backup_failed' if bank_backup else 'output_fir_failed' if output_fir else 'fir_import_failed' if fir_import else 'fir_trial_failed' if fir else 'prs_import_failed' if prs else 'preset_store_failed' if store else 'preset_recall_failed','slot':slot,'error':str(error)})
            raise RuntimeError('Preset '+action+' stopped; no retry or automatic restore. '+str(error)) from error
        finally:
            with self.lock:self.recall_running=False

    def receive(self, timeout=100):
        if self.stop.is_set(): raise InterruptedError(self.medium+' control cancelled')
        raw = self.port.read(timeout)
        if not raw: return None
        p = self.reply_decoder(raw)
        if not self.utilities.secret_active and p.command not in (0x2D,0x2F):self.log('rx', p.raw)
        return p

    def wait(self, command, block=None):
        # Only the first read-only status exchange may finish the TX12
        # boundary. Never carry its empty ACK into a setter acknowledgement.
        allow_startup_ack = self.startup_status_ack and command == 0x2C
        self.startup_status_ack = False
        deadline = self.clock() + self.response_timeout
        while self.clock() < deadline:
            p = self.receive()
            if p is None: continue
            if allow_startup_ack and p.command == 1 and not p.data:
                allow_startup_ack = False
                self.record({'kind':'startup_finish_acknowledged','scope':'delayed TX12 ACK before first read-only system status'})
                continue
            if p.command != command or (command == 1 and p.data) or (block is not None and (not p.data or p.data[0] != block)):
                raise ValueError('Unexpected response in serialized '+self.medium+' control')
            return p
        raise TimeoutError(self.medium+' control response timeout; no retry')

    def read_block(self, index):
        if self.stop.is_set(): raise InterruptedError(self.medium+' control cancelled')
        raw = frame(0x27, bytes((index,)))
        self.port.write(raw); self.log('tx', raw)
        p = self.wait(0x24, index)
        size = min(50, 1556-index*50)
        if not size+1 <= len(p.data) <= 51 or (index < 31 and len(p.data) != 51):
            raise ValueError('Configuration block length mismatch')
        expected = self.expected[index*50:index*50+size]
        if p.data[1:1+size] != expected:
            self.record({'kind': 'readback_mismatch', 'block': index,
                         'expected_hex': expected.hex(), 'actual_hex': p.data[1:].hex()})
            raise ValueError(f'DSP block {index} differs from requested state; writes stopped')

    def finish_startup_boundary(self,*,system_read=False):
        """Consume only the TX12 boundary; optional ACK belongs to status2C."""
        if not self.startup_boundary:return
        p=self.receive(1)
        if p is not None and (p.command!=1 or p.data):
            raise ValueError('Unexpected response at startup/control boundary')
        self.startup_status_ack=p is None and self.medium=='USB' and system_read
        self.startup_boundary=False

    def dispatch(self):
        if self.stop.is_set() or (not self.ready and self.recall_slot is None and self.store_request is None and self.prs_request is None): return
        try:
            # TX12 may leave one empty01; never treat it as a setter reply.
            self.finish_startup_boundary(system_read=self.utilities.requested is not None
                and self.utilities.requested.kind=='input_selection_read')
            if self.recall_slot is not None or self.store_request is not None or self.prs_request is not None:
                self.dispatch_recall();return
            if self.utilities.requested is not None:
                self.utilities.dispatch();return
            if self.utilities.locked:return
            with self.lock:
                wanted, generation, requested_at = self.wanted, self.generation, self.requested_at
            # Idle telemetry/readback never recompiles an unchanged full model.
            # A new generation supersedes every unsent older packet.
            if generation != self.planned_generation:
                self.packets, _ = self.prepare_parameters(self.expected, wanted)
                self.planned_generation = generation
            packets = self.packets
            if packets:
                if self.clock()-self.last_send < .025: return
                raw, path = packets[0]
                before = self.expected
                from dsp408.channel_link import apply_parameter
                doc = SourceDocument(before); apply_parameter(doc,raw)
                expected = bytes(doc.data)
                self.scrub = None
                self.port.arm_parameter(before, wanted, raw)
                if self.stop.is_set(): raise InterruptedError(self.medium+' setter cancelled')
                self.inflight = True
                write_start = self.clock()
                self.port.write(raw); self.log('tx', raw)
                self.wait(1)
                self.packets.pop(0)
                with self.lock: self.expected = expected
                self.dirty_blocks.update(i//50 for i,(a,b) in enumerate(zip(before,expected)) if a != b)
                self.dirty_paths.add(path); self.dirty_commands.add(raw[5])
                self.inflight = False
                self.sent_generation = generation
                self.last_send = self.clock()
                self.next_scrub = self.last_send + .7
                self.pending(True)
                self.record({'kind': 'parameter_sent', 'generation': generation, 'path': path,
                             'frame_hex': raw.hex(), 'confirmation': self.medium+' write and empty01; byte readback pending'})
                self.record({'kind': 'parameter_timing', 'generation': generation, 'path': path,
                             'queue_delay_ms': round((write_start-requested_at)*1000,3),
                             'write_reply_ms': round((self.clock()-write_start)*1000,3)})
                return
            self.sent_generation = generation
            # New fader events can preempt between these individual block reads.
            if self.dirty_blocks and self.clock()-self.last_send >= .12:
                index = min(self.dirty_blocks)
                self.read_block(index); self.dirty_blocks.remove(index)
                if not self.dirty_blocks:
                    self.record({'kind': 'parameter_verified', 'generation': generation,
                                 'state_hex': self.expected.hex(), 'paths': sorted(self.dirty_paths),
                                 'commands': sorted(self.dirty_commands),
                                 'scope': 'final values in affected blocks; full scan follows; not every intermediate movement'})
                    self.dirty_paths.clear(); self.dirty_commands.clear()
                    self.confirmed(self.expected, generation); self.pending(False)
                    self.confirmed_generation = generation
                return
            if not self.dirty_blocks and generation != self.confirmed_generation:
                self.confirmed(self.expected, generation); self.pending(False)
                self.confirmed_generation = generation
            if self.clock() >= self.next_scrub:
                if self.scrub is None: self.scrub = list(range(32))
                self.read_block(self.scrub.pop(0))
                if not self.scrub:
                    self.record({'kind': 'full_scan_verified', 'generation': generation,
                                 'state_hex': self.expected.hex()})
                    self.scrub = None; self.next_scrub = float('inf')
        except Exception as e:
            with self.lock: self.ready = False
            self.availability(False)
            self.record({'kind': 'control_failed', 'error': str(e), 'state_unconfirmed': bool(self.dirty_blocks) or self.inflight or self.recall_failed})
            raise RuntimeError(self.medium+' control stopped; no retry or automatic restore. ' + str(e)) from e


def dispatch_with_input_status(service):
    """Refresh known input-selector read once per invalidation, same USB owner.

    Reuse the exact EEPROM18 utility and
    unchanged-state checks; no auto setter and no retry on unknown result.
    Queued edits/busy operations retain priority via the utility request guard.
    """
    if service.utilities.input_selection is None and not service.utilities.locked:
        from dsp408.device_utilities import input_selection_read_request
        service.utilities.request(input_selection_read_request())
    service.dispatch()


class UsbParameterWorker(FirRefreshMixin,QThread):
    status = Signal(str)
    configuration = Signal(bytes)
    confirmed = Signal(bytes, int)
    presetMetadata = Signal(object)
    telemetry = Signal(object)
    frameObserved = Signal(str, bytes)
    failed = Signal(str)
    available = Signal(bool)
    pending = Signal(bool)
    journalPath = Signal(str)
    firBank=Signal(bytes)
    firPreview=Signal(object)
    recallProgress=Signal(object)
    recallResult=Signal(object)
    utilityState=Signal(object)

    def __init__(self, parent=None, *, port_factory=HidParameterPort,device_id=1,fir_strategy='source-display'):
        if fir_strategy not in ('full','source-display'):raise ValueError('Unknown USB startup FIR strategy')
        super().__init__(parent)
        self.fir_strategy=fir_strategy
        self.stop_event, self.port_factory, self.service = Event(), port_factory, None
        from dsp408.device_address import checked_id
        self.device_id=checked_id(device_id)
        self.meter_poll_ms=100
        self.fir_read_requested=False

    def set_meter_poll_ms(self,value):
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms.')
        self.meter_poll_ms=value

    def stop(self): self.stop_event.set()

    def request_model(self, model, generation):
        return self.service is not None and self.service.request(model, generation)

    def request_utility(self,request):
        return self.service is not None and self.service.utilities.request(request)

    def request_recall(self,slot):
        return self.service is not None and self.service.request_recall(slot)
    def request_store(self,slot,name,confirmed_target):
        return self.service is not None and self.service.request_store(slot,name,confirmed_target)
    def request_fir_trial(self,state):
        return self.service is not None and self.service.request_fir_trial(state)

    def request_input_fir(self,state,bank,channel,coefficients,bypass,clear=False):
        return self.service is not None and self.service.request_input_fir(state,bank,channel,coefficients,bypass,clear)

    def request_prs_import(self,state,prs,bank=None):
        return self.service is not None and self.service.request_prs_import(state,prs,bank)

    def request_output_fir(self,*args):
        service=self.service
        return service is not None and service.request_output_fir(*args)

    def request_link(self,*args):
        return self.service is not None and self.service.request_link(*args)

    def request_bank_backup(self,*args):
        return self.service is not None and self.service.request_bank_backup(*args)

    def request_bank_restore(self,*args):
        return self.service is not None and self.service.request_bank_restore(*args)

    def idle(self):
        self.read_requested_fir()
        dispatch_with_input_status(self.service)

    def unlock_startup(self,payload):
        """Wait without polling DSP; UI may queue only an explicit unlock."""
        service=self.service
        service.utilities.authentication_pending=True
        service.utilities.observe_system(payload)
        self.status.emit('USB · processor locked · unlock in SETUP')
        while not self.stop_event.is_set():
            if service.utilities.authenticate_startup():return service.utilities.last_system_frame
            self.stop_event.wait(.05)
        return False

    def run(self):
        journal = None
        try:
            from dsp408.preset_store import PRESET_STORE_AUTHORIZED
            directory = JOURNAL_DIRECTORY
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / ('app-parameters-' + time.strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8] + '.ndjson')
            journal = DurableJournal(path, sync_each=False,max_bytes=128*1024*1024)
            journal.record({'kind': 'session_started', 'scope': 'Manual EXE/MCU parameter verification; not hardware certification',
                            'commands': sorted(PARAMETERS),'manual_preset_recall':True,
                            'manual_preset_store_authorized':PRESET_STORE_AUTHORIZED,
                            'control_startup_fir_strategy':'full bank0 sequential read' if self.fir_strategy=='full' else 'source sentinel skip/carry',
                            'meter_poll_ms':self.meter_poll_ms})
            self.journalPath.emit(str(path))
            port = self.port_factory(journal.record, self.stop_event)
            port.target_id=self.device_id
            journal.record({'kind':'physical_address_scope','target_id':self.device_id,'internal_planner_id':1})
            self.service = ParameterService(port, self.stop_event, record=journal.record,
                configuration=self.configuration.emit, confirmed=self.confirmed.emit,
                availability=self.available.emit, pending=self.pending.emit,
                status=self.status.emit, log=self.frameObserved.emit,
                preset_metadata=self.presetMetadata.emit,recall_progress=self.recallProgress.emit,
                recall_result=self.recallResult.emit,utility_state=self.utilityState.emit)
            from dsp408.usb_control_startup import run_control_session
            def bank_received(raw):
                self.service.observe_fir_bank(raw);self.firBank.emit(raw)
            run_control_session(port, self.stop_event, record=journal.record,fir_bank=bank_received,status=self.status.emit,
                fir_strategy=self.fir_strategy,fir_preview=self.firPreview.emit,
                system_status=self.service.utilities.observe_system,
                locked_startup=self.unlock_startup,
                configuration=self.service.observe_configuration, telemetry=self.telemetry.emit,
                log=self.frameObserved.emit, preset_metadata=self.presetMetadata.emit,
                between_polls=self.idle, idle_read_ms=10,
                poll_interval=lambda:self.meter_poll_ms/1000, poll_from_request=True)
            journal.record({'kind': 'session_finished', 'error': None})
        except Exception as e:
            self.available.emit(False); self.failed.emit(str(e))
            if journal is not None:
                try: journal.record({'kind': 'session_finished', 'error': str(e)})
                except OSError: pass
        finally:
            if journal is not None: journal.close()
