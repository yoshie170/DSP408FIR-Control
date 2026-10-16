"""Inspect explicitly supplied TX payloads offline. No encoder, transport or apply.

Layouts: hash-audited V1.12 EXE and MCU1.15/1.15P case correlation. Source-profile
limits below are inspection constraints, not proof of device range validation.
Raw values are preserved. See docs/PROTOCOL_PARAMETERS_V11.md.
"""
import math
import struct

FAMILIES={0x30:'COMP',0x31:'LOW_PASS',0x32:'HIGH_PASS',0x33:'PEQ',0x34:'GAIN',
          0x35:'MUTE',0x36:'POLARITY',0x38:'DELAY',0x3A:'MATRIX',0x3B:'LINK',
          0x3D:'CHANNEL_NAME',0x3E:'GATE',0x3F:'LIMIT',0x41:'MIX',0x4B:'FIR_DESIGN',0x4C:'CROSSOVER_MODE',
          0x4E:'EXT_FIR',0x4F:'INPUT_FIR_BYPASS',0x5B:'FIR_NAME',0x39:'WORK_MODE',0x4D:'IO_SELECT'}
SIZES={0x30:15,0x31:5,0x32:5,0x33:9,0x34:3,0x35:2,0x36:2,0x38:3,
       0x3A:2,0x3B:2,0x3D:9,0x3E:9,0x3F:11,0x41:4,0x4B:9,0x4C:2,0x4F:2,0x5B:9}


def source_gain_db(raw):
    """Editor display conversion only; raw0 is separately zeroed by MCU math."""
    if not 0<=raw<=400:
        return None
    return raw/2-60 if raw<=80 else raw/10-28


def decode_tx_payload(command, payload):
    payload=bytes(payload)
    if command not in FAMILIES:
        raise ValueError('Unsupported source-audited TX family')
    if command in (0x39,0x4D):
        if len(payload)!=2:raise ValueError('Global TX requires two bytes')
        return {'scope':'Offline global TX source profile; no device verification','hardware_verified':False,
                'command':f'0x{command:02X}','family':FAMILIES[command], 'raw_payload_hex':payload.hex(),
                'fields':{'mode_raw':payload[0],'sine_frequency_index_raw':payload[1]} if command==0x39 else
                         {'group_raw':payload[0],'selection_raw':payload[1]}}
    if not payload or not 0<=payload[0]<12:
        raise ValueError('Missing/outside source-profile channel index')
    if command in SIZES and len(payload)!=SIZES[command]:
        raise ValueError('TX payload size differs from audited source layout')
    channel=payload[0];is_input=channel<4
    if command in (0x30,0x3E,0x4F) and not is_input or command in (0x31,0x32,0x3A,0x3F,0x41,0x4C) and is_input:
        raise ValueError('TX family is outside the audited IN/OUT source profile')
    def word(offset):return int.from_bytes(payload[offset:offset+2],'little')
    fields={};previews={}
    if command==0x3B:fields={'link_mask_raw':payload[1]}
    elif command in (0x34,0x38):
        value=word(1)
        fields[ {0x34:'gain_raw',0x38:'delay_raw',0x3B:'link_mask_raw'}[command] ]=value
        if command==0x34:
            previews={'editor_gain_db':source_gain_db(value),'mcu_forces_zero_result':value==0}
        elif command==0x38:
            previews={'editor_delay_ms':value/96}
    elif command in (0x35,0x36,0x4C,0x4F):
        fields={'flag_raw' if command!=0x4C else 'processing_mode_raw':payload[1]}
    elif command in (0x3D,0x5B):
        fields={'name_bytes_hex':payload[1:].hex()}
    elif command==0x3A:
        fields={'routing_mask_raw':payload[1]}
    elif command==0x41:
        if payload[1]>=4:
            raise ValueError('Mix input index outside four audited inputs')
        fields={'input_index':payload[1],'mix_gain_raw':word(2)}
        previews={'editor_gain_scale_db':source_gain_db(word(2))}
    elif command==0x33:
        if payload[1]>=(8 if is_input else 9):
            raise ValueError('PEQ band index outside audited group')
        fields={'band_index':payload[1],'gain_raw':word(2),'frequency_position_raw':word(4),
                'q_index_raw':payload[6],'type_raw':payload[7],'bypass_raw':payload[8]}
    elif command in (0x31,0x32):
        fields={'frequency_position_raw':word(1),'type_raw':payload[3],'aux_raw':payload[4]}
    elif command==0x30:
        fields=dict(zip(('ratio_raw','attack_raw','release_raw','knee_raw','threshold_raw','detector_frequency_position_raw'),
                        struct.unpack_from('<6H',payload,1)))
        fields.update(unknown_byte=payload[13],detector_type_raw=payload[14])
    elif command in (0x3E,0x3F):
        fields={'parameter_words_raw':list(struct.unpack_from('<'+'H'*(4 if command==0x3E else 5),payload,1))}
    elif command==0x4B:
        fields={'type_raw':payload[1],'window_raw':payload[2],
                'hp_frequency_position_raw':word(3),'lp_frequency_position_raw':word(5),'tap_parameter_raw':word(7)}
        previews={'mcu_path':'input_returns_before_output_design_loop' if is_input else 'output_design_loop'}
    elif command==0x4E:
        if len(payload)<8 or (len(payload)-4)%4:
            raise ValueError('External FIR requires header4 and complete coefficient words')
        block=payload[1];total=word(2);count=(len(payload)-4)//4
        remaining=total-12*block
        if remaining<=0 or count!=min(12,remaining):
            raise ValueError('FIR block extent differs from audited constructor/MCU chunk logic')
        words=list(struct.unpack_from('>'+'I'*count,payload,4))
        values=[struct.unpack('>f',struct.pack('>I',value))[0] for value in words]
        fields={'block_index':block,'total_parameter_raw':total,'coefficient_words_be':words,
                'coefficient_values':[v if math.isfinite(v) else None for v in values],
                'nonfinite_indices':[i for i,v in enumerate(values) if not math.isfinite(v)]}
    return {'scope':'Offline TX source interpretation; no device or direction verification',
            'hardware_verified':False,'command':f'0x{command:02X}','family':FAMILIES[command],
            'channel_index':channel,'group':'IN' if is_input else 'OUT','raw_payload_hex':payload.hex(),
            'fields':fields,'source_previews':previews}
