"""Bounded offline replay of USB Control host journals, with raw RX evidence.

No device discovery, transport, requests or vendor execution. A host journal
can confirm sampled byte effects, not independent capture, audio or EEPROM.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from dsp408.editor_tx_research import decode_tx_payload, FAMILIES
from dsp408.editor_rx_research import decode_telemetry_payload
from dsp408.source_session import SourceDocument
from dsp408.startup_research import StartupReview
from dsp408.wire_research import decode_editor_frame

LEGACY_COMMANDS=frozenset((0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x38,0x3A,0x3E,0x3F,0x41))
BYPASS_COMMANDS=LEGACY_COMMANDS|{0x4F}
MODE_COMMANDS=BYPASS_COMMANDS|{0x4C}
NAMED_COMMANDS=MODE_COMMANDS|{0x3D}
COMMANDS=NAMED_COMMANDS|{0x5B}
MAX_BYTES=32*1024*1024
MAX_RECORDS=200000


def parameter_path(packet):
    info=decode_tx_payload(packet.command,packet.data)
    op=packet.command
    name={0x30:'compressor',0x31:'lpf',0x32:'hpf',0x34:'gain',0x35:'mute',
          0x36:'polarity_inverted',0x38:'delay_ms',0x3A:'routing',0x3D:'name',0x5B:'fir.name',0x3E:'gate',0x3F:'limiter',0x4C:'crossover_mode',0x4F:'fir.bypass'}.get(op)
    if op==0x4F and (len(packet.data)!=2 or packet.data[0]>=4 or packet.data[1] not in (0,1)):
        raise ValueError('FIR bypass scope requires IN A-D and a boolean flag')
    if op==0x4C and (len(packet.data)!=2 or packet.data[0] not in range(4,12) or packet.data[1] not in (0,1)):
        raise ValueError('Crossover mode scope requires OUT1-8 and a boolean mode')
    if op==0x33:name=f"filters[{info['fields']['band_index']}]"
    if op==0x41:name=f"mix[{info['fields']['input_index']}]"
    return f"channel[{info['channel_index']}].{name}",info


def inspect(path):
    with Path(path).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    return inspect_bytes(raw)


def inspect_bytes(raw):
    if len(raw)>MAX_BYTES:raise ValueError('Parameter journal limit:32 MiB')
    lines=raw.splitlines()
    if not lines or len(lines)>MAX_RECORDS:raise ValueError('Empty journal or record limit exceeded')
    report={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'records':len(lines),
            'scope':'Host journal byte replay only; no independent USBPcap, audio or persistence certification',
            'hardware_certified':False,'startup_verified':False,'structural_valid':True,
            'closed':False,'session_error':None,'issues':[],
            'checked_blocks':0,'affected_groups':0,'full_scans':0,'telemetry_replies':0}
    startup=StartupReview(transport='usb',layout='common-prefix1556',device_address=1)
    doc=None;intent=None;awaiting=None;boundary=False;ended=False;released=COMMANDS
    dirty=set();paths=set();ops=set();scan=set();last_sent=None
    latest={};samples={};all_paths=set();counts=Counter();confirmed=Counter();full_paths=Counter()
    last_setter_index=None;last_full_index=None

    def require(condition,message):
        if not condition:raise ValueError(message)

    def bytes_field(row,key,size=None):
        value=row.get(key)
        require(isinstance(value,str),'Missing hexadecimal field '+key)
        require(len(value)<=MAX_BYTES,'Hexadecimal field exceeds bounds')
        result=bytes.fromhex(value)
        if size is not None:require(len(result)==size,'Wrong length: '+key)
        return result

    for index,line in enumerate(lines):
        try:
            require(len(line)<=16384,'Record exceeds16 KiB')
            row=json.loads(line)
            require(isinstance(row,dict),'Record must be an object')
            require(type(row.get('index')) is int and row['index']==index,'Journal index discontinuity')
            require(type(row.get('time_ns')) is int and row['time_ns']>=0,'Invalid record timestamp')
            require(not ended,'Records after session_finished')
            kind=row.get('kind')
            if index==0:require(kind=='session_started','Missing session_started')
            if kind=='session_started':
                require(index==0,'Duplicate session_started')
                require(row.get('commands') in (sorted(COMMANDS),sorted(NAMED_COMMANDS),sorted(MODE_COMMANDS),sorted(BYPASS_COMMANDS),sorted(LEGACY_COMMANDS)),
                        'Unexpected released command scope')
                released=frozenset(row['commands'])
            elif kind=='physical_address_scope':
                target=row.get('target_id')
                require(type(target) is int and 1<=target<=250 and row.get('internal_planner_id')==1,'Invalid physical address scope')
                report['physical_target_id']=target
            elif kind in ('tx_intent','setter_intent'):
                require(intent is None,'Second intent before TX completion')
                packet=decode_editor_frame(bytes_field(row,'frame_hex'))
                require(packet.address_bytes==b'\0\1','Wrong TX address')
                setter=kind=='setter_intent'
                require(setter==(packet.command in released),'Intent classification mismatch')
                if setter:require(doc is not None,'Setter before authenticated baseline')
                intent=(packet,setter)
            elif kind=='tx_completed':
                packet=decode_editor_frame(bytes_field(row,'frame_hex'))
                require(intent is not None and packet.raw==intent[0].raw,'TX completion lacks matching intent')
                require(type(row.get('setter')) is bool and row['setter']==intent[1],'TX setter flag mismatch')
                setter=intent[1];intent=None
                if doc is None:
                    startup.feed('tx',packet.raw)
                elif packet.command==0x11:
                    require(not packet.data and (awaiting is None or awaiting[0]=='telemetry'),'Invalid disconnect boundary')
                    awaiting=None;boundary=False
                else:
                    require(awaiting is None,'TX while a response is outstanding')
                    if setter:
                        from dsp408.channel_link import apply_parameter
                        path,info=parameter_path(packet);before=bytes(doc.data);apply_parameter(doc,packet.raw)
                        delta={i//50 for i,(a,b) in enumerate(zip(before,doc.data)) if a!=b}
                        require(bool(delta),'Setter has no expected byte effect')
                        dirty.update(delta);paths.add(path);ops.add(packet.command);scan.clear()
                        latest[path]=info;all_paths.add(path);counts[packet.command]+=1
                        samples[path]=samples.get(path,0)+1
                        last_sent=(packet,path,index);last_setter_index=index
                        awaiting=('setter',None)
                    elif packet.command==0x27:
                        require(len(packet.data)==1 and packet.data[0]<32,'Invalid read block request')
                        awaiting=('block',packet.data[0])
                    else:
                        require(packet.command==0x40 and not packet.data,'Unreleased post-startup TX')
                        awaiting=('telemetry',None)
            elif kind=='rx_report':
                bus=bytes_field(row,'report_hex',64)
                packet=decode_editor_frame(bus[:bus[4]+8])
                require(packet.address_bytes==b'\1\0','Wrong RX address')
                if doc is None:
                    require(packet.command==startup.response or (packet.command==1 and not packet.data),
                            'Unexpected response during guarded startup')
                    if packet.command==0x10:require(packet.data==b'\x33','Unexpected hello')
                    if packet.command==0x13:require(packet.data==b'FIR408 V0115P','Unexpected identity')
                    startup.feed('rx',packet.raw)
                elif awaiting and awaiting[0]=='block':
                    block=awaiting[1];size=min(50,1556-block*50)
                    require(packet.command==0x24 and size+1<=len(packet.data)<=51 and
                            (block==31 or len(packet.data)==51) and packet.data[0]==block,'Uncorrelated or malformed block')
                    require(packet.data[1:1+size]==bytes(doc.data[block*50:block*50+size]),'Readback byte mismatch')
                    dirty.discard(block);scan.add(block);report['checked_blocks']+=1;awaiting=None
                elif awaiting and awaiting[0]=='setter':
                    require(packet.command==1 and not packet.data,'Setter reply is not empty01')
                    awaiting=None
                elif packet.command==1 and not packet.data:
                    require(boundary or (awaiting and awaiting[0]=='telemetry'),'Unrequested empty01')
                    boundary=False  # Never confirms a telemetry poll or byte effect.
                else:
                    require(awaiting is not None and awaiting[0]=='telemetry' and packet.command==0x40,
                            'Unrequested telemetry or unexpected RX')
                    decode_telemetry_payload(packet.data)
                    report['telemetry_replies']+=1;awaiting=None
            elif kind=='control_baseline':
                require(doc is None and startup.phase=='complete_candidate','Baseline before complete startup')
                state=bytes_field(row,'state_hex',1556)
                require(state==startup.trace.configuration.data(),'Baseline differs from correlated startup RX24')
                require(row.get('identity')=='FIR408 V0115P' and row.get('source_families')==sorted(released),
                        'Baseline metadata differs from observed scope')
                candidate=SourceDocument(state)
                from dsp408.channel_link import validate_group_state
                validate_group_state(state)
                doc=candidate;report['startup_verified']=True;boundary=True
                report['baseline_sha256']=hashlib.sha256(state).hexdigest()
            elif kind=='parameter_sent':
                require(last_sent is not None and awaiting is None,'Sent record precedes completion reply')
                require(bytes_field(row,'frame_hex')==last_sent[0].raw and row.get('path')==last_sent[1],
                        'Sent metadata differs from raw setter')
                last_sent=None
            elif kind=='parameter_timing':
                require(row.get('path') in all_paths,'Timing record lacks known parameter')
            elif kind in ('parameter_verified','full_scan_verified'):
                require(doc is not None and awaiting is None and not dirty,'Confirmation without all changed blocks')
                require(bytes_field(row,'state_hex',1556)==bytes(doc.data),'Confirmation state differs from replay')
                if kind=='parameter_verified':
                    require(paths and row.get('paths')==sorted(paths) and row.get('commands')==sorted(ops),
                            'Confirmation paths/commands differ from raw setters')
                    report['affected_groups']+=1
                    for path in paths:confirmed[path]+=1
                    paths.clear();ops.clear()
                else:
                    require(scan==set(range(32)),'Full scan lacks32 correlated blocks since last setter')
                    require(last_setter_index is not None and last_full_index!=last_setter_index,'Duplicate/no-op full scan')
                    report['full_scans']+=1;last_full_index=last_setter_index
                    for path in latest:full_paths[path]+=1
                    scan.clear()
            elif kind=='readback_mismatch':
                require(doc is not None,'Mismatch without baseline')
                report['issues'].append({'index':index,'reason':'Application reported readback mismatch'})
            elif kind=='control_failed':
                report['session_error']=str(row.get('error','Control failed'))
            elif kind=='session_finished':
                require(intent is None,'Session ended with incomplete TX intent')
                report['closed']=True;report['session_error']=row.get('error');ended=True
            else:raise ValueError('Unknown journal record kind')
        except (ValueError,TypeError,KeyError,IndexError) as error:
            report['structural_valid']=False
            report['issues'].append({'index':index,'reason':str(error)})
            break
    report['setter_counts']={f'{op:02X}':count for op,count in sorted(counts.items())}
    report['functions']=[{'path':path,'family':latest[path]['family'],'command':latest[path]['command'],
        'channel_index':latest[path]['channel_index'],'sent_count':samples[path],
        'affected_final_groups':confirmed[path],'full_scans_covering_path':full_paths[path],
        'last_sent_fields':latest[path]['fields'],'last_sent_source_previews':latest[path]['source_previews']}
        for path in sorted(samples)]
    report['missing_command_samples']=[{'command':f'{op:02X}','family':FAMILIES[op]} for op in sorted(released-counts.keys())]
    report['pending_at_end']=None if awaiting is None else {'kind':awaiting[0],'block':awaiting[1]}
    report['unverified_dirty_blocks']=sorted(dirty)
    report['status']=('invalid_journal_prefix_only' if not report['structural_valid'] or report['issues'] else
                      'failed_session_prefix_only' if report['session_error'] else
                      'validated_closed' if report['closed'] else 'validated_open_prefix')
    return report
