"""Replay an existing P19 trial journal offline; never opens a device."""
import hashlib,json
from dsp408.startup_research import StartupReview
from dsp408.preset_roundtrip import PresetRoundtripReview
from dsp408.usb_preset_roundtrip import validate_trial_request
from dsp408.usb_read import read_bus_frame,IDENTITY


def inspect_bytes(raw):
    if not raw or len(raw)>32*1024*1024 or not raw.endswith(b'\n'):raise ValueError('Invalid preset trial journal size/tail')
    lines=raw.splitlines()
    if len(lines)>200000:raise ValueError('Trial record limit')
    startup=StartupReview(transport='usb',layout='common-prefix1556',device_address=1)
    r=None;result=None;intent=None;setter=None;polling=False;closing=False;closed=False;error=None;issues=[];mutations=0
    for index,line in enumerate(lines):
        try:
            if len(line)>16384:raise ValueError('Trial line limit')
            row=json.loads(line)
            if not isinstance(row,dict):raise ValueError('Trial record must be an object')
            if type(row.get('index')) is not int or row['index']!=index:raise ValueError('Trial record index differs')
            if closed:raise ValueError('Record after session finish')
            kind=row['kind']
            if index==0:
                if kind!='session_started':raise ValueError('Missing trial session start')
                continue
            if kind=='setter_intent':
                packet=validate_trial_request(bytes.fromhex(row['frame_hex']))
                if r is None or r.complete or setter is not None or intent is not None or r.steps[r.position][4]!='mutation':raise ValueError('Unexpected mutating intent')
                if packet.raw!=r.proposal or row.get('trial_step')!=r.position or row.get('phase')!=r.phase:raise ValueError('Mutating intent differs')
                setter=packet.raw
            elif kind=='tx_intent':
                if closing or intent is not None:raise ValueError('Overlapping TX or TX after close')
                intent=validate_trial_request(bytes.fromhex(row['frame_hex'])).raw
            elif kind=='tx_completed':
                p=validate_trial_request(bytes.fromhex(row['frame_hex']))
                if intent!=p.raw:raise ValueError('TX completion differs from durable intent')
                intent=None
                if p.command==0x11 and startup.recognized:closing=True;polling=False
                elif startup.phase!='complete_candidate':startup.feed('tx',p.raw)
                elif r is None or not r.complete:
                    if r is None:r=PresetRoundtripReview(startup.trace.configuration.data(),
                        {'active_slot_raw':startup.active_slot_raw,'names_raw_hex':startup.names,
                         'catalog_markers':list(startup.trace.latest_preset_catalog.marker_bytes)})
                    if r.steps[r.position][4]=='mutation':
                        if setter!=p.raw:raise ValueError('Mutation without matching synced setter intent')
                        setter=None;mutations+=1
                    elif setter is not None:raise ValueError('Read replaces pending mutation')
                    r.feed('tx',p.raw)
                elif result is not None and p.command==0x40 and not polling:polling=True
                else:raise ValueError('Unexpected post-trial TX')
            elif kind=='rx_report':
                p=read_bus_frame(bytes.fromhex(row['report_hex']))
                if closing:raise ValueError('RX after session close')
                if p.command==0x24 and (not p.data or p.data[0]>31 or len(p.data)!=(7 if p.data[0]==31 else 51)):raise ValueError('Current block extent differs')
                if startup.phase!='complete_candidate':
                    if p.command!=startup.response and not (p.command==1 and not p.data):raise ValueError('Unexpected startup RX')
                    if p.command==0x10 and p.data!=b'\x33':raise ValueError('Hello differs')
                    if p.command==0x13 and p.data!=IDENTITY:raise ValueError('Device identity differs')
                    startup.feed('rx',p.raw)
                elif r is not None and not r.complete:r.feed('rx',p.raw)
                elif p.command==0x40 and polling and len(p.data)==42:polling=False
                elif p.command!=1 or p.data:raise ValueError('Unexpected post-trial RX')
            elif kind=='preset_roundtrip_complete':
                if result is not None or r is None or not r.complete:raise ValueError('Trial certificate before verification')
                expected=r.result()
                if any(row.get(k)!=v or type(row.get(k)) is not type(v) for k,v in expected.items()):raise ValueError('Trial certificate differs')
                result=expected
            elif kind=='session_finished':
                closed=True;error=row.get('error')
                if not error and (intent is not None or setter is not None or polling):raise ValueError('Healthy finish with pending request')
                if not error and not closing:raise ValueError('Healthy finish without close')
            else:raise ValueError('Unknown trial journal event')
        except (ValueError,TypeError,KeyError,IndexError) as failure:
            issues.append({'index':index,'reason':str(failure)});break
    status='invalid_prefix' if issues else 'failed_prefix' if error else 'validated_closed' if closed else 'validated_open_prefix'
    return {'scope':'Offline P19 host trial replay; not audio or power-cycle proof','status':status,
            'issues':issues,'error':error,'records':len(lines),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'trial':result if not issues else None,'mutating_tx_completed':mutations,
            'pending_request':intent is not None or setter is not None or (r is not None and r.outstanding)}
