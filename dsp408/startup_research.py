"""Review explicit offline startup frames. Suggestions are data, never sent.

Source EXE V1.12 / MCU1.15, see PROTOCOL_COMPATIBILITY_V14.md. This intentionally
requires response correlation and all blocks even where the original does not.
It cannot establish hardware identity, audio state or acknowledgement of writes.
"""
from dsp408.source_codec import frame,integer
from dsp408.wire_research import decode_editor_frame
from dsp408.trace_research import OfflineReadTrace
from dsp408.editor_rx_research import decode_fir_read_payload
from dsp408.fir_bootstrap_research import FirBootstrapReview,FirReconstructionBoundary


def retry_action(transport,*,retries_remaining,exhausted_waits=0,command):
    """One *observed* timeout, no clock. R retransmits, then source failure policy."""
    if transport not in ('usb','ethernet'):raise ValueError('Explicit usb/ethernet profile required')
    integer(retries_remaining,0,255);integer(exhausted_waits,0,255);integer(command,0,255)
    if retries_remaining: return {'action':'retry','retries_remaining':retries_remaining-1,'exhausted_waits':0}
    if transport=='usb' and command!=5 and exhausted_waits<4:
        return {'action':'wait','retries_remaining':0,'exhausted_waits':exhausted_waits+1}
    return {'action':'failed','retries_remaining':0,'exhausted_waits':exhausted_waits}


class StartupReview:
    def __init__(self,*,transport,layout,device_address,full_fir=False):
        if type(full_fir) is not bool:raise ValueError('Explicit full FIR strategy required')
        self.full_fir=full_fir
        if transport not in ('usb','ethernet'):raise ValueError('Explicit usb/ethernet profile required')
        self.trace=OfflineReadTrace(layout=layout,device_address=device_address)
        self.transport=transport;self.address=device_address;self.phase='hello';self.outstanding=None
        self.recognized=False;self.identity_hex=None;self.active_slot_raw=None;self.names={}
        self.notes=[];self.history=[];self.exhausted_waits=0;self.retry_due=False
        self.fir_bootstrap=None
        self.fir_boundary_error=None
        self.uncorrelated_rx_count=0
        self.timeout_ms=100 if transport=='usb' else 4000;self.retry_limit=3
        self._suggest(0x10,b'',0x10)

    def resume_authenticated_system(self,raw,*,accepted=False):
        """Continue after an explicit accepted password and actual RX2C read."""
        previous=self.trace.latest_system_status
        if (accepted is not True or self.phase!='blocked' or not self.recognized
                or previous is None or previous.flag0_raw or previous.flag5_raw!=1
                or previous.flag6_raw!=1):
            raise ValueError('No ordinary locked startup awaiting authentication')
        packet=decode_editor_frame(raw)
        from dsp408.device_utilities import system_lock
        if packet.command!=0x2C:raise ValueError('Authentication continuation requires system readback')
        system_lock(packet.data)
        if packet.data[5]:raise ValueError('Processor still requires authentication')
        # These are the actual final TX2C/RX2C of the authenticated callback,
        # not a manufactured response or a second HELLO resetting the session.
        tx=frame(0x2C,b'',self.address)
        self.trace.feed('tx',tx);self.trace.feed('rx',packet.raw)
        self.history.extend([{'direction':'tx','frame_hex':tx.hex(),'phase':'authenticated_system'},
                             {'direction':'rx','frame_hex':packet.raw.hex(),'phase':'authenticated_system'}])
        self.phase='catalog';self._suggest(0x22,b'',0x22)

    def _suggest(self,command,payload,response):
        self.proposal=frame(command,payload,self.address);self.response=response
        self.outstanding=None;self.retries_remaining=self.retry_limit;self.exhausted_waits=0;self.retry_due=False

    def timeout(self):
        if self.outstanding is None or self.phase in ('blocked','failed','rejected','complete_candidate','cancelled'):
            raise ValueError('No pending startup response to time out')
        if self.retry_due:raise ValueError('Observe the suggested retransmission before another timeout')
        result=retry_action(self.transport,retries_remaining=self.retries_remaining,
                            exhausted_waits=self.exhausted_waits,command=decode_editor_frame(self.outstanding).command)
        self.retries_remaining=result['retries_remaining'];self.exhausted_waits=result['exhausted_waits']
        self.retry_due=result['action']=='retry'
        if result['action']=='failed':self.phase='failed';self.proposal=None
        self.history.append({'timeout':result['action'],'source_timeout_ms':self.timeout_ms})
        return result

    def cancel(self):
        self.phase='cancelled';self.proposal=None;self.outstanding=None;self.retry_due=False

    def feed(self,direction,raw):
        packet=decode_editor_frame(raw)
        if direction not in ('tx','rx'):raise ValueError('Explicit tx/rx direction required')
        if packet.address_bytes[1 if direction=='tx' else 0]!=self.address:
            raise ValueError('Frame address differs from explicit source address')
        if direction=='tx':
            if self.phase in ('blocked','failed','rejected','cancelled','complete_candidate'):
                raise ValueError('No startup suggestion in this terminal phase')
            if packet.raw!=self.proposal:raise ValueError('TX differs from current offline startup suggestion')
            if self.outstanding is not None and not self.retry_due:raise ValueError('Duplicate TX without an observed retry timeout')
            self.trace.feed(direction,raw);self.outstanding=packet.raw;self.retry_due=False
            self.history.append({'direction':'tx','frame_hex':packet.raw.hex(),'phase':self.phase})
            if self.phase=='finish':self.phase='complete_candidate';self.proposal=None;self.outstanding=None
            elif self.phase=='reject_identity':self.phase='rejected';self.proposal=None;self.outstanding=None
            return {'advanced':False,'phase':self.phase,'hardware_verified':False}
        # Validate known raw response types even when they cannot advance startup.
        if packet.command in (1,2,0x40):
            event=self.trace.feed(direction,raw);event['advanced']=False;return event
        if self.outstanding is None or packet.command!=self.response:
            # Uncorrelated24/56 must not contaminate the active collection.
            self.uncorrelated_rx_count+=1
            self.notes.append({'command':f'0x{packet.command:02X}','reason':'Uncorrelated response; startup not advanced'})
            return {'advanced':False,'phase':self.phase,'hardware_verified':False}
        payload=packet.data;phase=self.phase
        def extent(size):
            if len(payload)!=size:raise ValueError(f'Source startup profile needs exactly{size} payload bytes')
        if phase=='hello':
            extent(1)
            if payload!=b'\x33':self.notes.append({'reason':'MCU source emits33; EXE hello handler does not test its value','payload_hex':payload.hex()})
            self.trace.feed(direction,raw);self.phase='identity';self.timeout_ms=5000;self.retry_limit=1
            self._suggest(0x13,b'',0x13)
        elif phase=='identity':
            extent(13);self.trace.feed(direction,raw);self.identity_hex=payload.hex()
            self.recognized=payload[:6]==b'FIR408' and payload[:11]==b'FIR408 V011'
            if not self.recognized:self.phase='reject_identity';self._suggest(0x11,b'',None)
            else:
                self.phase='system';self.timeout_ms=1000 if self.transport=='usb' else 5000
                self._suggest(0x2C,b'',0x2C)
        elif phase=='system':
            extent(7);self.trace.feed(direction,raw);s=self.trace.latest_system_status
            if s.flag0_raw and s.word3_be_raw>=s.word1_be_raw:
                self.phase='blocked';self.proposal=None;self.outstanding=None
                self.notes.append({'reason':'Source enters modal operation state7; raw counter/flag semantics not assumed'})
            elif s.flag5_raw:
                self.phase='blocked';self.proposal=None;self.outstanding=None
                self.notes.append({'reason':'Source enters modal operation state8; auth/lock continuation not reconstructed'})
            else:self.phase='catalog';self._suggest(0x22,b'',0x22)
        elif phase=='catalog':
            extent(19);self.trace.feed(direction,raw);self.phase='active_slot';self._suggest(0x14,b'',0x14)
        elif phase=='active_slot':
            extent(1);self.trace.feed(direction,raw);self.active_slot_raw=payload[0]
            self.phase='names';self._suggest(0x29,b'\0',0x29)
        elif phase=='names':
            extent(15);index=decode_editor_frame(self.outstanding).data[0]
            if payload[0]!=index:raise ValueError('Preset name index differs from pending request')
            self.trace.feed(direction,raw);self.names[index]=payload[1:].hex()
            if index<18:self._suggest(0x29,bytes((index+1,)),0x29)
            else:
                self.phase='fir';self.trace.begin_fir_area_read(0)
                self.fir_bootstrap=None if self.full_fir else FirBootstrapReview()
                self._suggest(0x56,b'\0\0\0',0x56)
        elif phase=='fir':
            # Exact-device USB capture: TX index LE, RX index BE.
            chunk=decode_fir_read_payload(payload);index=int.from_bytes(decode_editor_frame(self.outstanding).data[1:],'little')
            if chunk.selector_byte!=0 or chunk.block_index!=index:raise ValueError('FIR block differs from pending source request')
            try:next_block=(index+1 if index<1260 else None) if self.full_fir else self.fir_bootstrap.add(payload)
            except FirReconstructionBoundary as e:
                self.fir_boundary_error=str(e)
                self.trace.feed(direction,raw)
                self.phase='blocked';self.proposal=None;self.outstanding=None
                self.notes.append({'reason':str(e),'block':index})
                self.history.append({'direction':'rx','frame_hex':packet.raw.hex(),'from_phase':phase,'phase':self.phase})
                return {'advanced':False,'phase':self.phase,'hardware_verified':False}
            self.trace.feed(direction,raw)
            if next_block is not None:self._suggest(0x56,b'\0'+next_block.to_bytes(2,'little'),0x56)
            else:
                self.phase='configuration';self.trace.begin_configuration_read();self._suggest(0x27,b'\0',0x24)
        elif phase=='configuration':
            index=decode_editor_frame(self.outstanding).data[0]
            if not payload or payload[0]!=index:raise ValueError('Configuration block differs from pending request')
            self.trace.feed(direction,raw)
            if index<31:self._suggest(0x27,bytes((index+1,)),0x24)
            else:
                if self.trace.configuration.missing_blocks:raise ValueError('All32 configuration blocks required')
                self.phase='finish';self._suggest(0x12,b'',None)
        else:raise ValueError('Unsupported startup phase')
        self.history.append({'direction':'rx','frame_hex':packet.raw.hex(),'from_phase':phase,'phase':self.phase})
        return {'advanced':True,'phase':self.phase,'hardware_verified':False}

    def restart_full_fir_after_boundary(self):
        """Discard sparse collection after the known source reconstruction limit.

        This proposes only existing full-read frames. No implicit retry on
        malformed/corrupt replies, no reconstruction into a raw bank.
        """
        if self.full_fir or self.phase!='blocked' or not self.fir_boundary_error:
            raise ValueError('No source FIR boundary requiring a full read')
        self.full_fir=True;self.fir_bootstrap=None
        if not self.trace.fir_area.missing_blocks:
            self.phase='configuration';self.trace.begin_configuration_read();self._suggest(0x27,b'\0',0x24)
            return 'use complete raw bank already received'
        self.trace.begin_fir_area_read(0);self.phase='fir';self._suggest(0x56,b'\0\0\0',0x56)
        return 'discard sparse read and read full raw bank'

    def report(self):
        result=self.trace.report()
        result.update({'scope':'offline source startup review; suggestions never transmitted',
            'transport_profile':self.transport,'startup_phase':self.phase,'source_prefix_recognized':self.recognized,
            'fir_read_strategy':'all raw blocks' if self.full_fir else 'source sentinel skip/carry',
            'identity_payload_hex':self.identity_hex,'active_slot_raw':self.active_slot_raw,
            'preset_names_raw_hex':self.names,'startup_candidate_complete':self.phase=='complete_candidate',
            'suggested_tx_frame_hex':self.proposal.hex() if self.proposal else None,
            'waiting_for_rx':self.outstanding is not None,'retry_due':self.retry_due,
            'source_timeout_ms':self.timeout_ms,'retries_remaining':self.retries_remaining,
            'uncorrelated_response_count':self.uncorrelated_rx_count,
            'observed_valid_rx_count':self.trace.rx_count+self.uncorrelated_rx_count,
            'usb_exhausted_waits':self.exhausted_waits,'notes':self.notes,'history':self.history,
            'source_fir_bootstrap':self.fir_bootstrap.report() if self.fir_bootstrap else None})
        return result
