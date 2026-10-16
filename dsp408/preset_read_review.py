"""Offline replay of the dedicated P02 journal and preservation certificate."""
import json,hashlib
from dsp408.startup_research import StartupReview
from dsp408.preset_preview import PresetPreviewReview
from dsp408.usb_preset_read import validate_preset_read_request
from dsp408.usb_read import read_bus_frame,IDENTITY


def inspect_bytes(raw):
    raw=bytes(raw)
    if not raw or len(raw)>32*1024*1024 or not raw.endswith(b'\n'):raise ValueError('Invalid/incomplete P02 journal file')
    rows=raw.splitlines()
    if len(rows)>200000:raise ValueError('P02 journal record limit')
    start=StartupReview(transport='usb',layout='common-prefix1556',device_address=1,full_fir=True)
    preview=None;intent=None;poll=False;closing=False;closed=False;error=None;issues=[];bank0=False;result=None
    for index,line in enumerate(rows):
        try:
            if len(line)>16384:raise ValueError('P02 journal line limit')
            row=json.loads(line)
            if not isinstance(row,dict) or type(row.get('index')) is not int or row['index']!=index:raise ValueError('Record index differs')
            if closed:raise ValueError('Records after session end')
            kind=row['kind']
            if index==0:
                if kind!='session_started':raise ValueError('Missing session start')
                continue
            if kind=='tx_intent':
                if closing or intent is not None:raise ValueError('TX after close or overlapping intent')
                intent=bytes.fromhex(row['frame_hex']);validate_preset_read_request(intent)
            elif kind=='tx_completed':
                raw_tx=bytes.fromhex(row['frame_hex'])
                if intent is None or raw_tx!=intent:raise ValueError('TX completion differs')
                p=validate_preset_read_request(raw_tx);intent=None
                if p.command==0x11 and start.recognized:closing=True;poll=False
                elif start.phase!='complete_candidate':start.feed('tx',raw_tx)
                elif preview is not None and not preview.complete:preview.feed('tx',raw_tx)
                elif preview is None:
                    if not bank0:raise ValueError('P02 preview before bank0 certificate')
                    metadata={'active_slot_raw':start.active_slot_raw,'names_raw_hex':start.names,
                        'catalog_markers':list(start.trace.latest_preset_catalog.marker_bytes)}
                    preview=PresetPreviewReview(start.trace.configuration.data(),metadata);preview.feed('tx',raw_tx)
                elif result is not None and p.command==0x40 and not poll:poll=True
                else:raise ValueError('Unexpected post-preview TX')
            elif kind=='rx_report':
                p=read_bus_frame(bytes.fromhex(row['report_hex']))
                if start.phase!='complete_candidate':
                    if p.command!=start.response and not (p.command==1 and not p.data):raise ValueError('Unexpected startup response')
                    if p.command==0x10 and p.data!=b'\x33':raise ValueError('Hello differs')
                    if p.command==0x13 and p.data!=IDENTITY:raise ValueError('Identity differs')
                    start.feed('rx',p.raw)
                elif preview is not None and not preview.complete:preview.feed('rx',p.raw)
                elif p.command==0x40 and poll and len(p.data)==42:poll=False
                elif p.command!=1 or p.data:raise ValueError('Unrequested post-preview RX')
            elif kind=='fir_bank_complete':
                if bank0 or start.phase!='complete_candidate':raise ValueError('Premature/duplicate bank0 certificate')
                bank=start.trace.fir_area.data()
                if (row.get('selector'),row.get('bytes'),row.get('blocks'),row.get('sha256'))!=(0,65536,1261,hashlib.sha256(bank).hexdigest()):raise ValueError('Bank0 certificate differs')
                bank0=True
            elif kind=='preset_preview_complete':
                if result is not None or preview is None or not preview.complete:raise ValueError('P02 certificate without complete correlated read')
                candidate=preview.result()
                for key in ('slot','state_sha256','fir_bank_sha256','current_before_sha256','current_after_sha256','active_slot_before','active_slot_after'):
                    if row.get(key)!=candidate[key]:raise ValueError('P02 certificate differs: '+key)
                result=candidate
            elif kind=='session_finished':
                closed=True;error=row.get('error')
                if not error and (intent is not None or poll):raise ValueError('Healthy finish with incomplete transaction')
            else:raise ValueError('Unexpected P02 journal event')
        except (ValueError,TypeError,KeyError,IndexError) as failure:issues.append({'index':index,'reason':str(failure)});break
    status=('invalid_prefix' if issues else 'failed_prefix' if error else 'cancelled_before_complete' if closing and result is None else
            'validated_closed' if closed else 'validated_open_prefix')
    return {'scope':'Offline host P02 read replay; not audio/EEPROM certification','status':status,'issues':issues,
        'session_error':error,'records':len(rows),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
        'startup_complete':start.phase=='complete_candidate','bank0_complete':bank0,
        'preset_preview':result if not issues else None,'pending_intent':intent is not None}
