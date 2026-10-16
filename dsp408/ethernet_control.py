"""Manual native TCP control: channel parameters, typed input source and Recall."""
import time
from PySide6.QtCore import Signal
from dsp408.ethernet_worker import EthernetReadWorker,wait_finish_ack
from dsp408.ethernet_stream import EthernetFrames
from dsp408.wire_research import decode_editor_frame
from dsp408.source_codec import frame
from dsp408.editor_rx_research import decode_telemetry_payload
from dsp408.usb_parameter_control import ParameterService,ParameterPolicy,PARAMETERS,dispatch_with_input_status
from dsp408.preset_recall import RecallOperation,checked_slot,eeprom_requests
from dsp408.preset_store import StoreOperation,encode_name
from dsp408.device_utilities import validate_utility
from dsp408.control_fir_refresh import FirRefreshMixin

CHANNEL_COMMANDS=frozenset((0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x38,0x3A,0x3E,0x3F,0x41))


def native_reply(raw):
    p=decode_editor_frame(raw)
    if p.address_bytes!=b'\1\0':raise ValueError('Unexpected Ethernet control response address')
    return p


class EthernetParameterPort:
    """One outstanding request, canonical one-shot setter arm, strict native RX."""
    def __init__(self,stream,stop,record,*,input_and_recall=False,full_control=False):
        self.stream,self.stop,self.record=stream,stop,record
        self.policy=ParameterPolicy();self.decoder=EthernetFrames();self.pending=None;self.failed=False
        self.setter_count=0
        self.input_and_recall=input_and_recall;self.recall_requests=None;self.recall_index=0
        self.full_control=full_control;self.ack_payload=b'';self.active_slot=None;self.secret_rx=False;self.fir_selector=0

    def arm_utility(self,request):
        validate_utility(request)
        allowed=('input_selection','input_selection_read','generator','lock','unlock','device_settings_read','device_id') if self.full_control else ('input_selection','input_selection_read')
        if not self.input_and_recall or request.kind not in allowed:
            raise ValueError('Ethernet utility not released')
        if self.failed or self.pending is not None or self.recall_requests is not None:
            raise ValueError('Another Ethernet operation is pending')
        self.policy.arm_utility(request)

    def cache_fir_bank(self,raw):self.policy.fir_bank=raw
    def begin_fir_startup(self):
        if not self.full_control or self.pending is not None or self.recall_requests is not None or self.failed:raise ValueError('FIR read unavailable')
        self.policy.begin_fir_startup()
    def arm_fir_startup(self,raw):self.policy.arm_fir_startup(raw)
    def complete_fir_startup(self):self.policy.complete_fir_startup()
    def end_fir_startup(self):self.policy.end_fir_startup()
    def begin_prs_import(self,permit):
        if not self.full_control or self.pending is not None or self.recall_requests is not None or self.failed:raise ValueError('Bulk transaction unavailable')
        self.policy.begin_prs_import(permit)
    def arm_prs_request(self,raw,permit):self.policy.arm_prs_request(raw,permit)
    def complete_prs_import(self,permit):self.policy.complete_prs_import(permit)
    def end_prs_import(self):self.policy.end_prs_import()

    def begin_store(self,slot,baseline,name):
        if not self.full_control:raise ValueError('Ethernet Store not released')
        desired=encode_name(name);self.begin_recall(slot)
        states=tuple(frame(0x27,bytes((i,))) for i in range(32));stored=eeprom_requests(slot)
        self.recall_requests=(frame(0x22,b''),frame(0x14,b''),frame(0x29,bytes((slot-1,))),*stored,*states,
            *((frame(0x26,desired),*states) if baseline[2:16]!=desired else ()),frame(0x21,bytes((slot,))),
            *stored,frame(0x29,bytes((slot-1,))),frame(0x22,b''),frame(0x14,b''),*states)

    def arm_store_request(self,raw,slot,context):
        if not self.full_control or self.recall_requests is None or slot!=self.recall_slot or self.pending is not None or self.failed:
            raise ValueError('No active Ethernet Store')
        if self.recall_index>=len(self.recall_requests) or self.recall_requests[self.recall_index]!=raw:
            raise ValueError('Outside ordered Ethernet Store')
        self.policy.arm_store_request(raw,slot,context)

    def begin_recall(self,slot):
        checked_slot(slot)
        if not self.input_and_recall or self.failed or self.pending is not None or self.recall_requests is not None:
            raise ValueError('Ethernet Recall unavailable')
        if any(x is not None for x in (self.policy.armed,self.policy.utility_armed,self.policy.preset_armed,self.policy.prs_permit,self.policy.startup_fir)):
            raise ValueError('Another Ethernet operation is armed')
        catalog=frame(0x22,b'');name=frame(0x29,bytes((slot-1,)))
        self.recall_requests=(catalog,name,*eeprom_requests(slot),frame(0x20,bytes((slot,))),
                              frame(0x14,b''),catalog,name,*(frame(0x27,bytes((i,))) for i in range(32)))
        self.recall_index=0;self.recall_slot=slot

    def arm_preset_request(self,raw,slot,target=None):
        if self.failed or self.pending is not None or self.recall_requests is None or slot!=self.recall_slot:
            raise ValueError('No active Ethernet Recall')
        if self.recall_index>=len(self.recall_requests) or raw!=self.recall_requests[self.recall_index]:
            raise ValueError('Outside ordered Ethernet Recall')
        self.policy.arm_preset_request(raw,slot,target)

    def complete_recall(self):
        if self.pending is not None or self.recall_requests is None or self.recall_index!=len(self.recall_requests):
            raise ValueError('Incomplete Ethernet Recall')
        self.recall_requests=None

    def arm_parameter(self,state,wanted,raw):
        if self.failed or self.pending is not None or self.recall_requests is not None:raise ValueError('Ethernet control request still outstanding')
        if decode_editor_frame(raw).command not in (PARAMETERS if self.full_control else CHANNEL_COMMANDS):raise ValueError('Ethernet family not released')
        self.policy.arm(state,wanted,raw)

    def write(self,raw):
        try:
            if self.failed or self.pending is not None:raise ValueError('Ethernet control request still outstanding')
            if self.stop.is_set():raise InterruptedError('Ethernet control cancelled before send')
            raw=bytes(raw);p=decode_editor_frame(raw)
            if p.address_bytes!=b'\0\1':raise ValueError('Ethernet control requires DSP ID1')
            self.ack_payload=b''
            setter=p.command in (PARAMETERS if self.full_control else CHANNEL_COMMANDS)
            if self.policy.prs_permit is not None:
                setter=self.policy.validate(raw)
                expected=self.bulk_reply(p)
            elif self.full_control and p.command==0x56 and self.policy.startup_fir is not None:
                self.policy.validate(raw);setter=False;expected=(0x56,int.from_bytes(p.data[1:],'little'))
            elif self.recall_requests is not None:
                if self.recall_index>=len(self.recall_requests) or raw!=self.recall_requests[self.recall_index]:
                    raise ValueError('Outside ordered Ethernet Recall')
                if p.command in (0x19,0x20,0x21,0x26):
                    if self.policy.preset_armed!=raw:raise ValueError('Unarmed Ethernet Recall request')
                    setter=self.policy.validate(raw)
                expected=self.bulk_reply(p)
            elif self.input_and_recall and p.command in (0x19,0x4D,0x39,0x2F,0x2D,0x15):
                if self.policy.utility_armed!=raw:raise ValueError('Unarmed Ethernet input source operation')
                setter=self.policy.validate(raw);expected=(0x2D if p.command==0x2D else 1 if setter else 0x19,p.data[-1] if p.command==0x19 else None)
            elif self.input_and_recall and p.command==0x2C and not p.data:
                if self.policy.armed is not None or self.policy.utility_armed is not None:raise ValueError('Another operation armed')
                expected=(0x2C,None)
            elif setter:
                if self.policy.armed!=raw:raise ValueError('Unarmed Ethernet setter')
                self.policy.validate(raw)
                expected=(1,None)
            elif p.command==0x27 and len(p.data)==1 and p.data[0]<=31:
                if self.policy.armed is not None:raise ValueError('Setter already armed')
                expected=(0x24,p.data[0])
            elif p.command==0x40 and not p.data:
                if self.policy.armed is not None:raise ValueError('Setter already armed')
                expected=(0x40,None)
            else:raise ValueError('Outside Ethernet channel control profile')
            self.pending=expected
            if p.command==0x56:self.fir_selector=p.data[0]
            # DurableJournal syncs setter_intent before sendall. Arm is consumed
            # before this point, even if the journal or socket subsequently fails.
            secret=p.command in (0x2D,0x2F)
            if secret:self.secret_rx=True
            details={'command':p.command,'password_redacted':True} if secret else {'frame_hex':raw.hex()}
            self.record({'kind':'setter_intent' if setter else 'tx_intent',**details,'transport':'ethernet'})
            self.stream.settimeout(4);self.stream.sendall(raw)
            if setter:self.setter_count+=1
            self.record({'kind':'tx_completed',**details,'setter':setter,'transport':'ethernet'})
        except Exception:
            self.failed=True;raise

    def bulk_reply(self,p):
        if p.command==0x26:
            if type(self.active_slot) is not int or not 1<=self.active_slot<=19:raise ValueError('Fresh active slot required for name ACK')
            self.ack_payload=bytes((self.active_slot,))+p.data
        if p.command==0x27:return (0x24,p.data[0])
        if p.command==0x29:return (0x29,p.data[0])
        if p.command==0x19:return (0x19,p.data[-1])
        if p.command==0x25:return (0x25,p.data[0])
        if p.command==0x56:return (0x56,int.from_bytes(p.data[1:],'little'))
        if p.command in (0x22,0x14):return (p.command,None)
        return (1,None)

    def read(self,timeout_ms):
        if self.failed:raise ValueError('Ethernet control port failed')
        if self.stop.is_set():raise InterruptedError('Ethernet control cancelled')
        if self.pending is None:raise ValueError('No outstanding Ethernet request')
        try:
            self.stream.settimeout(max(.001,min(.1,timeout_ms/1000)))
            try:chunk=self.stream.recv(4096)
            except TimeoutError:return b''
            if not chunk:
                self.decoder.finish();raise ConnectionError('DSP closed Ethernet control')
            self.record({'kind':'rx_sensitive_chunk','password_redacted':True} if self.secret_rx else {'kind':'rx_chunk','hex':chunk.hex()})
            packets=self.decoder.feed(chunk)
            if not packets:return b''
            if len(packets)!=1 or self.decoder.pending:raise ValueError('Unrequested trailing Ethernet control data')
            p=native_reply(packets[0].raw);op,index=self.pending
            if p.command!=op:raise ValueError('Ethernet control response differs from pending command')
            if op==1 and p.data!=self.ack_payload:raise ValueError('Ethernet setter ACK payload differs')
            if op==0x2D and p.data not in (b'\0\0',b'\0\1'):raise ValueError('Unexpected Ethernet authentication response')
            if op==0x40 and len(p.data)!=42:raise ValueError('Ethernet meter reply must have42 payload bytes')
            if op==0x24 and (len(p.data)!=1+min(50,1556-index*50) or p.data[0]!=index):
                raise ValueError('Ethernet readback index or extent mismatch')
            if op==0x2C and len(p.data)!=7:raise ValueError('Ethernet system reply extent mismatch')
            if op==0x19 and len(p.data)!=(index if index is not None else 1):raise ValueError('Ethernet EEPROM reply extent mismatch')
            if op==0x22 and len(p.data)!=19:raise ValueError('Ethernet catalog extent mismatch')
            if op==0x29 and (len(p.data)!=15 or p.data[0]!=index):raise ValueError('Ethernet preset name mismatch')
            if op==0x25 and p.data!=bytes((index,)):raise ValueError('Ethernet preset write acknowledgment mismatch')
            if op==0x14 and len(p.data)!=1:raise ValueError('Ethernet active preset extent mismatch')
            if op==0x14:self.active_slot=p.data[0]
            if op==0x56 and (len(p.data)!=(19 if index==1260 else 55) or p.data[:3]!=bytes((self.fir_selector,))+index.to_bytes(2,'big')):
                raise ValueError('Ethernet FIR bank/index/extent mismatch')
            if self.recall_requests is not None:self.recall_index+=1
            self.pending=None;return p.raw
        except Exception:
            self.failed=True;raise


class EthernetRecallOperation(RecallOperation):
    def __init__(self,*args,**kwargs):
        kwargs.setdefault('reply_decoder',native_reply);kwargs.setdefault('default_timeout',5.)
        super().__init__(*args,**kwargs)

    def run(self,slot):
        self.port.begin_recall(slot)
        try:
            result=super().run(slot)
            self.port.complete_recall()
            return result
        except Exception:
            self.port.failed=True
            raise


class EthernetStoreOperation(StoreOperation):
    def run(self,slot,baseline,name,confirmed_target):
        self.port.begin_store(slot,baseline,name)
        try:
            result=super().run(slot,baseline,name,confirmed_target)
            self.port.complete_recall();return result
        except Exception:
            self.port.failed=True;raise


def control_loop(service,port,stop,*,telemetry,clock=time.monotonic,poll_ms=lambda:100,input_status=False,auxiliary=lambda:None):
    next_poll=clock()
    while not stop.is_set():
        # Same latest-value planner/readback as USB, between complete meter
        # transactions. No socket access from the GUI thread or catch-up burst.
        auxiliary()
        if input_status:dispatch_with_input_status(service)
        else:service.dispatch()
        if stop.is_set():return
        if clock()>=next_poll:
            sent=clock();raw=frame(0x40,b'');port.write(raw);service.log('tx',raw)
            deadline=sent+5
            while not stop.is_set():
                if clock()>=deadline:raise TimeoutError('Ethernet meter response timeout; no retry')
                p=service.receive(100)
                if p is not None:
                    if p.command!=0x40 or len(p.data)!=42:raise ValueError('Unexpected Ethernet meter reply')
                    telemetry(decode_telemetry_payload(p.data));break
            next_poll=max(clock(),sent+poll_ms()/1000)
        if not stop.is_set():stop.wait(.01)


class EthernetControlWorker(FirRefreshMixin,EthernetReadWorker):
    control_writes_allowed=True
    available=Signal(bool);pending=Signal(bool);confirmed=Signal(bytes,int)
    utilityState=Signal(object);recallProgress=Signal(object);recallResult=Signal(object)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.service=None;self.fir_read_requested=False

    def set_meter_poll_ms(self,value):
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms.')
        self.poll_ms=value

    def request_model(self,model,generation):
        return self.service is not None and self.service.request(model,generation)

    def request_utility(self,request):
        validate_utility(request)
        return self.service is not None and self.service.utilities.request(request)

    def request_recall(self,slot):
        return self.service is not None and self.service.request_recall(slot)

    def request_store(self,slot,name,confirmed_target):
        return self.service is not None and self.service.request_store(slot,name,confirmed_target)

    def request_input_fir(self,*args,**kwargs):
        return self.service is not None and self.service.request_input_fir(*args,**kwargs)

    def request_prs_import(self,*args):
        return self.service is not None and self.service.request_prs_import(*args)

    def request_output_fir(self,*args):
        service=self.service
        return service is not None and service.request_output_fir(*args)

    def request_link(self,*args):
        return self.service is not None and self.service.request_link(*args)

    def request_bank_backup(self,*args):
        return self.service is not None and self.service.request_bank_backup(*args)

    def request_bank_restore(self,*args):
        return self.service is not None and self.service.request_bank_restore(*args)

    def make_service(self,stream,record):
        port=EthernetParameterPort(stream,self.stop_event,record,input_and_recall=True,full_control=True)
        service=ParameterService(port,self.stop_event,record=record,
            configuration=self.configuration.emit,confirmed=self.confirmed.emit,
            availability=self.available.emit,pending=self.pending.emit,status=self.status.emit,
            log=self.frameObserved.emit,clock=self.clock,reply_decoder=native_reply,
            allowed_commands=PARAMETERS,response_timeout=5.,medium='Ethernet',
            utility_state=self.utilityState.emit,preset_metadata=self.presetMetadata.emit,
            recall_progress=self.recallProgress.emit,recall_result=self.recallResult.emit,
            recall_class=EthernetRecallOperation,store_class=EthernetStoreOperation)
        service.startup_boundary=False
        return service

    def unlock_startup(self,stream,payload,record):
        # One TCP owner throughout authentication and the remaining startup.
        self.service=self.make_service(stream,record)
        utilities=self.service.utilities
        utilities.authentication_pending=True;utilities.observe_system(payload)
        self.status.emit('Ethernet · processor locked · unlock in SETUP')
        while not self.stop_event.is_set():
            if utilities.authenticate_startup():
                # The last complete validated RX2C ends the sensitive exchange.
                self.service.port.secret_rx=False
                record({'kind':'authentication_system_verified','frame_hex':utilities.last_system_frame.hex()})
                return utilities.last_system_frame
            self.stop_event.wait(.05)
        return False

    def run(self):
        try:super().run()
        finally:
            if self.service is not None:self.service.ready=False
            self.available.emit(False);self.service=None

    def live_session(self,stream,result,metadata,send,record):
        if self.stop_event.is_set():raise InterruptedError('Ethernet control cancelled before startup acknowledgement')
        self.status.emit('Ethernet synchronization · finish_ack')
        wait_finish_ack(stream,self.stop_event,record=record,log=self.frameObserved.emit,clock=self.clock)
        if self.stop_event.is_set():return
        record({'kind':'ethernet_control_started','commands':sorted(PARAMETERS),
                'identity':'FIR408 V0115P','manual_input_selection':True,'manual_preset_recall':True,
                'manual_preset_store':True,'typed_fir_prs':True,'typed_utilities':True})
        if self.service is None:self.service=self.make_service(stream,record)
        port=self.service.port
        if port.stream is not stream or port.pending is not None or port.decoder.pending:
            raise ValueError('Ethernet authentication did not end at a complete response')
        try:
            self.service.utilities.observe_system(bytes.fromhex(metadata['system_payload_hex']))
            self.presetMetadata.emit(metadata)
            if 'bank_hex' in result:
                bank=bytes.fromhex(result['bank_hex']);self.service.observe_fir_bank(bank);self.firBank.emit(bank)
            else:self.firPreview.emit(result['fir_preview'])
            self.service.observe_configuration(bytes.fromhex(result['state_hex']))
            control_loop(self.service,port,self.stop_event,telemetry=self.telemetry.emit,
                         clock=self.clock,poll_ms=lambda:self.poll_ms,input_status=True,auxiliary=self.read_requested_fir)
            if port.pending is not None:raise InterruptedError('Ethernet control cancelled with a pending reply')
            return {'setter_count':port.setter_count,
                    'state_unconfirmed':bool(self.service.dirty_blocks) or self.service.inflight or self.service.generation!=self.service.confirmed_generation}
        except Exception as error:
            if self.stop_event.is_set():raise InterruptedError('Ethernet control cancelled; pending state may be unconfirmed') from error
            raise
        finally:
            self.service.ready=False;self.available.emit(False);self.service=None
