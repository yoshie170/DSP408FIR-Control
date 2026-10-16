"""Confirmed Ethernet startup, reused by CLI and manual app connection."""
import hashlib,socket,time
from ipaddress import IPv4Address
from dsp408.ethernet_stream import EthernetFrames,ObservedEthernetGreeting,EDITOR_TCP_PORT
from dsp408.source_codec import frame
from dsp408.startup_research import StartupReview
from dsp408.wire_research import decode_editor_frame


def validate_request(raw):
    p=decode_editor_frame(raw)
    valid=(p.command in (0x10,0x11,0x12,0x13,0x2C,0x22,0x14,0x40) and not p.data or
           p.command==0x29 and len(p.data)==1 and p.data[0]<=18 or
           p.command==0x27 and len(p.data)==1 and p.data[0]<=31 or
           p.command==0x56 and len(p.data)==3 and p.data[0]==0 and int.from_bytes(p.data[1:],'little')<=1260)
    if p.address_bytes!=b'\0\1' or not valid:raise ValueError('Outside confirmed Ethernet read profile (DSP ID 1)')
    return p


def read_snapshot(host,record,*,source_ip=None,request_gap_ms=0,connect=socket.create_connection,clock=time.monotonic,sleep=time.sleep,status=lambda _:None,
                  stop=None,session=None,frame_observed=lambda *args:None,fir_strategy='full',locked_startup=None):
    def cancelled():
        if stop is not None and stop.is_set():raise InterruptedError('Ethernet connection cancelled')
    cancelled()
    if fir_strategy not in ('full','source-display'):raise ValueError('Explicit full or source-display FIR strategy required')
    if type(request_gap_ms) is not int or not 0<=request_gap_ms<=250:
        raise ValueError('Diagnostic request gap must be an integer from 0 to 250 ms')
    request_gap=request_gap_ms/1000
    address=IPv4Address(host)
    if address.is_unspecified or address.is_multicast or address.is_loopback or address==IPv4Address('255.255.255.255'):
        raise ValueError('Explicit unicast DSP IPv4 required')
    source=IPv4Address(source_ip) if source_ip is not None else None
    if source is not None and (source.is_unspecified or source.is_multicast or source.is_loopback or source==IPv4Address('255.255.255.255') or source==address):
        raise ValueError('Explicit distinct unicast PC source IPv4 required')
    review=StartupReview(transport='ethernet',layout='common-prefix1556',device_address=1,full_fir=fir_strategy=='full')
    decoder=EthernetFrames();greeting=ObservedEthernetGreeting(host);queued=[];steps=0;started=clock();previous_reply=None
    authentication_seconds=0.;authenticated=False
    record({'kind':'started','host':str(address),'port':EDITOR_TCP_PORT,'profile':'full-current-read-v70' if fir_strategy=='full' else 'source-display-read-v99','source_ip':str(source) if source else None,**({'request_gap_ms':request_gap_ms} if request_gap_ms else {})})
    status('Opening TCP · '+str(address)+':9761'+(' · source '+str(source) if source else ''))
    try:
        connection=connect((str(address),EDITOR_TCP_PORT),timeout=4,**({'source_address':(str(source),0)} if source else {}))
    except (TimeoutError,OSError) as error:
        raise ConnectionError(f'TCP connection failed before DSP commands: {error}') from error
    with connection as stream:
        record({'kind':'tcp_connected','local_address':stream.getsockname() if hasattr(stream,'getsockname') else None})
        def send(raw):
            validate_request(raw)
            record({'kind':'tx_intent','frame_hex':raw.hex()})
            if stop is not None:stream.settimeout(4)
            stream.sendall(raw);record({'kind':'tx_completed','frame_hex':raw.hex()})
            frame_observed('tx',raw)
        while review.phase!='complete_candidate':
            cancelled()
            limit=1320 if fir_strategy=='full' else 2640
            if steps>=limit or clock()-started-authentication_seconds>(180 if fir_strategy=='full' else 360)+limit*request_gap:raise TimeoutError('Ethernet startup bound exceeded; no retry')
            if review.phase in ('blocked','failed','rejected'):raise ValueError('Startup stopped: '+str(review.notes))
            raw=review.proposal
            if raw is None:raise ValueError('No validated startup request')
            packet=decode_editor_frame(raw)
            if packet.command==0x56:
                block=int.from_bytes(packet.data[1:],'little')
                if fir_strategy=='source-display' or block%64==0 or block==1260:status(f'FIR {block}/1261')
            else:status(review.phase)
            if steps and request_gap:sleep(request_gap)
            send(raw);review.feed('tx',raw);steps+=1
            if review.phase=='complete_candidate':break
            deadline=clock()+5;acks=0;duplicates=0;retries=0
            while True:
                cancelled()
                if clock()>=deadline:raise TimeoutError('Ethernet response deadline exceeded during '+review.phase)
                if not queued:
                    stream.settimeout(max(.001,min(.1,deadline-clock()) if stop is not None else deadline-clock()))
                    try:chunk=stream.recv(4096)
                    except TimeoutError:
                        cancelled()
                        if getattr(stream,'physical_pending',False) and clock()<deadline:continue
                        if stop is not None and clock()<deadline:continue
                        retryable=packet.command in (0x2C,0x22,0x14,0x29,0x56,0x27)
                        detail=f'{review.phase}, TX 0x{packet.command:02X}, payload {packet.data.hex()}'
                        if packet.command==0x56:detail+=f', FIR block {int.from_bytes(packet.data[1:],"little")}'
                        if not retryable or retries or decoder.pending or getattr(stream,'physical_pending',False):
                            raise TimeoutError('Ethernet response timeout: '+detail)
                        action=review.timeout()
                        if action['action']!='retry':raise TimeoutError('Ethernet source retry exhausted: '+detail)
                        retries=1
                        record({'kind':'read_retry','phase':review.phase,'frame_hex':raw.hex(),'attempt':1})
                        status('Read retry · '+detail);send(raw);review.feed('tx',raw)
                        deadline=clock()+5;continue
                    if not chunk:
                        decoder.finish();raise ConnectionError('DSP closed TCP during startup')
                    record({'kind':'rx_chunk','hex':chunk.hex()})
                    for decoded in decoder.feed(chunk):
                        frame_observed('rx',decoded.raw)
                        if greeting.accept(decoded):
                            record({'kind':'observed_greeting','frame_hex':decoded.raw.hex(),'advances_startup':False})
                        else:queued.append(decoded)
                    if not queued:continue
                reply=queued.pop(0)
                if reply.address_bytes!=b'\1\0':raise ValueError('Reply address differs from actual Ethernet identity')
                if previous_reply is not None and reply.raw==previous_reply:
                    duplicates+=1
                    if duplicates>4:raise ValueError('Too many duplicate Ethernet replies')
                    record({'kind':'duplicate_reply','frame_hex':reply.raw.hex(),'advances_startup':False})
                    continue
                if reply.command==1 and not reply.data and acks<4:
                    acks+=1;continue
                if reply.command!=review.response:
                    record({'kind':'uncorrelated_reply','phase':review.phase,'expected_command':review.response,'frame_hex':reply.raw.hex()})
                    raise ValueError(f'Uncorrelated Ethernet startup reply during {review.phase}: expected 0x{review.response:02X}, got 0x{reply.command:02X}')
                if review.phase=='hello' and reply.data!=b'\x33':raise ValueError('Unexpected hello')
                if review.phase=='identity' and reply.data!=b'FIR408 V0115P':raise ValueError('Unsupported identity')
                review.feed('rx',reply.raw);previous_reply=reply.raw
                if review.phase=='blocked' and reply.command==0x2C and locked_startup is not None:
                    from dsp408.device_utilities import system_lock
                    if not system_lock(reply.data) or reply.data[5]!=1:
                        raise ValueError('Device requires an unsupported authorization mode')
                    if queued or decoder.pending:raise ValueError('Unexpected data before Ethernet authentication')
                    waiting=clock()
                    actual_status=locked_startup(stream,reply.data,record)
                    authentication_seconds+=clock()-waiting
                    if not actual_status:raise InterruptedError('Ethernet authentication cancelled')
                    cancelled()
                    review.resume_authenticated_system(actual_status,accepted=True)
                    authenticated=True;previous_reply=bytes(actual_status)
                if fir_strategy=='source-display' and review.phase=='blocked' and review.fir_boundary_error:
                    action=review.restart_full_fir_after_boundary()
                    record({'kind':'fir_display_boundary','reason':review.fir_boundary_error,'action':action})
                    status('Reading complete FIR bank…' if review.phase=='fir' else 'configuration')
                break
        state=bytes(review.trace.configuration.data())
        full_bank=not review.trace.fir_area.missing_blocks
        bank=bytes(review.trace.fir_area.data()) if full_bank else None
        if len(state)!=1556 or (full_bank and len(bank)!=65536) or queued or decoder.pending:
            raise ValueError('Incomplete state/bank or unexpected trailing data')
        result={'kind':'snapshot_complete' if full_bank else 'fir_display_snapshot_complete','identity':'FIR408 V0115P','state_hex':state.hex(),
                'state_sha256':hashlib.sha256(state).hexdigest(),'steps':steps,
                'active_slot_raw':review.active_slot_raw,'names_raw_hex':review.names,
                'elapsed_seconds':round(clock()-started,3),'setters_sent':authenticated}
        if authenticated:
            result.update(authentication_performed=True,authentication_seconds=round(authentication_seconds,3))
        if full_bank:
            result.update(bank_hex=bank.hex(),bank_sha256=hashlib.sha256(bank).hexdigest())
        else:
            if fir_strategy!='source-display' or review.fir_bootstrap is None or not review.fir_bootstrap.complete:
                raise ValueError('Incomplete source FIR display read')
            from dsp408.fir_read_preview import input_preview
            result['fir_preview']=input_preview(state,review.trace.fir_area,review.fir_bootstrap)
        if session is not None:
            cancelled()
            metadata={'active_slot_raw':review.active_slot_raw,'names_raw_hex':dict(review.names),
                      'catalog_markers':list(review.trace.latest_preset_catalog.marker_bytes)}
            system=review.trace.latest_system_status
            metadata['system_payload_hex']=(bytes((system.flag0_raw,))+system.word1_be_raw.to_bytes(2,'big')+
                system.word3_be_raw.to_bytes(2,'big')+bytes((system.flag5_raw,system.flag6_raw))).hex()
            record(result)
            summary=session(stream,result,metadata,send)
            send(frame(0x11,b''))
            details={'setters_sent':False}
            if isinstance(summary,dict) and type(summary.get('setter_count')) is int:
                details={'setters_sent':summary['setter_count']>0,'setter_count':summary['setter_count'],
                         'state_unconfirmed':bool(summary.get('state_unconfirmed'))}
            record({'kind':'session_finished','reason':'manual_disconnect',**details})
            return result
        send(frame(0x11,b''))
        record(result);return result

