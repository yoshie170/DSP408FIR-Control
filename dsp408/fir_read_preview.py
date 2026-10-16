"""Read-only IN preview from covered raw bytes, never sentinel-generated data."""
import hashlib,math,struct
from dsp408.source_session import SourceDocument


def input_preview(state,area,bootstrap):
    channels=SourceDocument(state).decoded()['channels'];inputs=[]
    for index in range(4):
        count=channels[index]['fir_coefficient_count_raw'];raw=b'';status='invalid_count'
        if 1<=count<=2048:
            try:
                first=area.received_bytes(index*8192,4)
                if first==b'\xff'*4:raw=first;status='empty_marker'
                else:
                    raw=area.received_bytes(index*8192,count*4)
                    status='received' if all(math.isfinite(v) for v in struct.unpack('<'+'f'*count,raw)) else 'empty_or_nonfinite'
            except ValueError:status='not_received'
        inputs.append({'channel':index,'count':count,'status':status,'coefficient_bytes_le_hex':raw.hex()})
    return {'mode':'source-skip-raw-input','scope':'Read-only FIR preview from received bytes; incomplete raw storage bank',
            'raw_bank_complete':False,'state_sha256':hashlib.sha256(state).hexdigest(),
            'received_blocks':list(area.received_blocks),'inputs':inputs,
            'source_bootstrap':bootstrap.report()}


def coefficients(preview,state,index):
    if not preview or not 0<=index<4 or preview['state_sha256']!=hashlib.sha256(state).hexdigest():return []
    entry=preview['inputs'][index]
    count=SourceDocument(state).decoded()['channels'][index]['fir_coefficient_count_raw']
    if entry['status']!='received' or entry['count']!=count or not 1<=count<=2048:return []
    raw=bytes.fromhex(entry['coefficient_bytes_le_hex'])
    if len(raw)!=count*4:return []
    values=struct.unpack('<'+'f'*count,raw)
    return list(values) if all(math.isfinite(v) for v in values) else []


def advance_preview(preview,before,after,*,allow_input_bypass=False):
    """Retain received IN bytes after verified scalar-only state updates.

    The exact delta must replay from the released scalar encoders, excluding
    FIR bypass unless explicitly permitting verified IN bypass-on (which keeps
    storage unchanged). Activation still requires the complete bank. Unknown
    co-field/coefficient/global changes invalidate the preview.
    """
    if not preview or before is None or preview['state_sha256']!=hashlib.sha256(before).hexdigest():return None
    if before==after:return preview
    from dsp408.usb_parameter_control import state_model,prepare
    try:
        _,wanted=state_model(after);packets,expected=prepare(before,wanted.to_dict())
        if expected!=after:return None
        if any(raw[5]==0x4F and not (allow_input_bypass and raw[6]<4 and raw[7]==1) for raw,path in packets):return None
    except (ValueError,TypeError):return None
    from copy import deepcopy
    result=deepcopy(preview);result.setdefault('origin_state_sha256',result['state_sha256'])
    result['state_sha256']=hashlib.sha256(after).hexdigest()
    return result
