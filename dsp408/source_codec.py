"""Pure EXE source-profile encoding, ONLY for files and local protocol tests.

No sockets, HID, transport discovery or permission to send. These are editor
V1.12 serializers, not capture-verified device commands. See SOURCE_SESSION_V12.
"""
import math
import struct
from functools import reduce
from operator import xor
from dsp408.editor_tx_research import decode_tx_payload
from dsp408.editor_profile import FREQUENCY_BASE,Q_VALUES,RATIO_VALUES


def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'Expected integer {low}..{high}')
    return value


def frame(command,payload,address=1):
    """TX builder490058, mode1. No USB report wrapper/direction assumptions."""
    integer(command,0,255);integer(address,0,255);payload=bytes(payload)
    if len(payload)>254:raise ValueError('One-byte source frame length exceeded')
    raw=bytes((16,2,0,address,len(payload)+1,command))+payload+b'\x10\x03'
    return raw+bytes((reduce(xor,raw,0),))


def encode_global(command,**fields):
    keys=('mode_raw','sine_frequency_index_raw') if command==0x39 else ('group_raw','selection_raw') if command==0x4D else None
    if keys is None or set(fields)!=set(keys):raise ValueError('No audited global payload or mismatched fields')
    return bytes(integer(fields[k],0,255) for k in keys)


def encode_payload(command,channel,**fields):
    integer(channel,0,11)
    def values(names,bits=16):
        return [integer(fields.pop(n),0,(1<<bits)-1) for n in names.split()]
    def words(names):return struct.pack('<'+'H'*len(names.split()),*values(names))
    if command==0x3B:
        raw=bytes((channel,*values('link_mask_raw',8)))
    elif command in (0x34,0x38):
        raw=bytes((channel,))+words({0x34:'gain_raw',0x38:'delay_raw',0x3B:'link_mask_raw'}[command])
    elif command in (0x35,0x36,0x4C,0x4F,0x3A):
        key={0x4C:'processing_mode_raw',0x3A:'routing_mask_raw'}.get(command,'flag_raw')
        raw=bytes((channel,*values(key,8)))
    elif command==0x41:
        raw=bytes((channel,*values('input_index',8)))+words('mix_gain_raw')
    elif command==0x33:
        raw=bytes((channel,*values('band_index',8)))+words('gain_raw frequency_position_raw')+bytes(values('q_index_raw type_raw bypass_raw',8))
    elif command in (0x31,0x32):
        raw=bytes((channel,))+words('frequency_position_raw')+bytes(values('type_raw aux_raw',8))
    elif command==0x30:
        raw=bytes((channel,))+words('ratio_raw attack_raw release_raw knee_raw threshold_raw detector_frequency_position_raw')+bytes(values('unknown_byte detector_type_raw',8))
    elif command in (0x3E,0x3F):
        raw=bytes((channel,))+words('attack_raw release_raw hold_raw threshold_raw' if command==0x3E else 'ratio_raw attack_raw release_raw knee_raw threshold_raw')
    elif command==0x4B:
        raw=bytes((channel,*values('type_raw window_raw',8)))+words('hp_frequency_position_raw lp_frequency_position_raw tap_parameter_raw')
    elif command in (0x3D,0x5B):
        name=fields.pop('name_bytes')
        if not isinstance(name,bytes) or len(name)!=8:raise ValueError('Name must have exactly eight explicit bytes')
        raw=bytes((channel,))+name
    elif command==0x4E:
        block=values('block_index',8)[0];total=values('total_parameter_raw')[0]
        coefficients=fields.pop('coefficient_words_be')
        raw=bytes((channel,block))+struct.pack('<H',total)+b''.join(struct.pack('>I',integer(v,0,0xffffffff)) for v in coefficients)
    else:raise ValueError('No audited encoder for this command')
    if fields:raise ValueError('Unexpected fields: '+', '.join(fields))
    if command in (0x3D,0x5B):pass  # EXE-only names; opaque encoding
    elif command==0x4F:
        if channel>=4:raise ValueError('Source input FIR bypass is IN only')
    else:decode_tx_payload(command,raw)
    return raw


def quantize(value,scale=1,offset=0,low=0,high=65535):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Expected finite engineering value')
    raw=math.floor(value*scale+offset+0.5)
    return integer(raw,low,high)


def gain_raw(db):
    if isinstance(db,bool) or not isinstance(db,(float,int)) or not -60<=db<=12:raise ValueError('Gain outside editor profile')
    return quantize(db,2,120,0,80) if db<=-20 else quantize(db,10,280,80,400)


def frequency_raw(hz):
    if isinstance(hz,bool) or not isinstance(hz,(float,int)) or not math.isfinite(hz) or hz<=0:raise ValueError('Frequency must be positive finite')
    return quantize(170+math.log(hz/1000,FREQUENCY_BASE),low=0,high=300)


def frequency_hz(raw):return 1000*FREQUENCY_BASE**(integer(raw,0,300)-170)


def fir_frequency_raw(hz,side):
    """OUT design sliders in exact TFMMAIN, not general PEQ/IIR frequency range."""
    if side not in ('hp','lp'):raise ValueError('FIR side must be hp/lp')
    raw=frequency_raw(hz)
    low,high=(88,299) if side=='hp' else (89,300)
    if not low<=raw<=high:raise ValueError(f'FIR {side} outside source editor raw profile {low}..{high}')
    return raw


def choice_raw(value,choices):
    if value not in choices:raise ValueError('No exact source enum/table choice for '+str(value))
    return choices.index(value)


def q_raw(value):
    if not .4<=value<=128:raise ValueError('Q outside source table')
    return min(range(len(Q_VALUES)),key=lambda i:abs(math.log(Q_VALUES[i]/value)))


def ratio_raw(value,limit):
    return 15 if limit else choice_raw(value,RATIO_VALUES)


def fir_chunks(channel,coefficients):
    """EXT4E active-buffer chunk plan ONLY; no persistence/start/finish claims."""
    integer(channel,0,11);total=len(coefficients)
    if not 1<=total<=(2048 if channel<4 else 1024):raise ValueError('FIR count outside documented storage profile')
    words=[]
    for value in coefficients:
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('FIR requires finite coefficients')
        try:raw=struct.pack('>f',value)
        except (OverflowError,struct.error) as e:raise ValueError('Coefficient outside binary32') from e
        if not math.isfinite(struct.unpack('>f',raw)[0]):raise ValueError('Coefficient outside finite binary32')
        words.append(int.from_bytes(raw,'big'))
    return [encode_payload(0x4E,channel,block_index=i//12,total_parameter_raw=total,coefficient_words_be=words[i:i+12]) for i in range(0,total,12)]
