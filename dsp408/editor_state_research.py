"""Offline V1.12 editor configuration layout. Not a verified device codec.

Source: RX24 -> 0x484334, getters/setters and bulk serializers; stage10 audit.
No transport, model application, encoder or device compatibility inference.
Unknown values stay raw, including hidden DEQ and the final eight words.
Stage11 MCU correlation identifies Mute, Link and output crossover fields.
"""
import struct

STATE_SIZE = 1572
LEGACY_PREFIX_SIZE = 1556
LAYOUT_SIZES = {'editor1572': STATE_SIZE, 'common-prefix1556': LEGACY_PREFIX_SIZE}


def decode_state(data, *, layout='editor1572'):
    data = bytes(data)
    if layout not in LAYOUT_SIZES:
        raise ValueError('Unknown explicit state layout')
    expected = LAYOUT_SIZES[layout]
    if len(data) != expected:
        raise ValueError(f'Source layout {layout} requires exactly {expected} bytes; no inferred padding/version conversion')
    def words(offset, count):
        return list(struct.unpack_from('<'+'H'*count, data, offset))
    def peq(offset, count, mask):
        result = []
        for band in range(count):
            gain, frequency, q, kind = struct.unpack_from('<HHBB', data, offset+6*band)
            result.append({'band_index': band, 'gain_raw': gain, 'frequency_position_raw': frequency,
                           'q_index_raw': q, 'type_raw': kind, 'bypass_mask_bit': bool(mask & (1 << band))})
        return result
    input_masks = words(1436, 4); output_masks = words(1444, 8)
    input_mute, output_mute = words(1432, 2)
    channels = []
    for index in range(12):
        is_input = index < 4
        base = 16+index*138 if is_input else 568+(index-4)*108
        channel = {'channel_index': index, 'group': 'IN' if is_input else 'OUT',
                   'record_offset': base, 'name_bytes_hex': data[base:base+8].hex()}
        if is_input:
            deq = []
            for band in range(3):
                start = base+16+16*band
                deq.append({'prefix_bytes_raw': list(data[start:start+2]),
                            'words_raw': words(start+2, 6),
                            'suffix_bytes_raw': list(data[start+14:start+16])})
            mask = input_masks[index]
            channel.update(gate_words_raw=words(base+8, 4), hidden_deq_raw=deq,
                           peq=peq(base+64, 8, mask),
                           compressor=dict(zip(('ratio_raw', 'attack_raw', 'release_raw', 'knee_raw',
                                                'threshold_raw', 'detector_frequency_position_raw'), words(base+112, 6)),
                                           unknown_byte=data[base+124], detector_type_raw=data[base+125]),
                           unknown_words_126_128=words(base+126, 2),
                           fir_coefficient_count_raw=words(base+126, 1)[0],
                           fir_bypass_raw=words(base+128, 1)[0],
                           gain_raw=words(base+130, 1)[0], polarity_raw=words(base+132, 1)[0],
                           delay_raw=words(base+134, 1)[0], link_mask_raw=words(base+136, 1)[0])
        else:
            mask = output_masks[index-4]
            channel.update(routing_raw=words(base+8, 1)[0], mix_words_raw=words(base+10, 4),
                           crossover_words_raw=words(base+18, 3),
                           crossover_bytes_raw=list(data[base+24:base+30]),
                           fir_design_words_raw=words(base+30, 3), peq=peq(base+36, 9, mask),
                           crossover_processing_mode_raw=words(base+18, 1)[0],
                           iir_hp_frequency_position_raw=words(base+20, 1)[0],
                           iir_lp_frequency_position_raw=words(base+22, 1)[0],
                           iir_hp_type_raw=data[base+24], iir_lp_type_raw=data[base+25],
                           iir_hp_aux_raw=data[base+26], iir_lp_aux_raw=data[base+27],
                           fir_type_raw=data[base+28], fir_window_raw=data[base+29],
                           fir_hp_frequency_position_raw=words(base+30, 1)[0],
                           fir_lp_frequency_position_raw=words(base+32, 1)[0],
                           fir_tap_parameter_raw=words(base+34, 1)[0],
                           limiter_words_raw=words(base+90, 5), gain_raw=words(base+100, 1)[0],
                           polarity_raw=words(base+102, 1)[0], delay_raw=words(base+104, 1)[0],
                           link_mask_raw=words(base+106, 1)[0])
        local_index = index if is_input else index-4
        channel['mute_mask_bit'] = bool((input_mute if is_input else output_mute) & (1 << local_index))
        channel['peq_bypass_mask_raw'] = mask
        channel['peq_bypass_unknown_bits'] = mask & ~((1 << (8 if is_input else 9))-1)
        channels.append(channel)
    return {'profile': 'editor-v1.12-source-only', 'layout': layout, 'size': len(data),
            'hardware_verified': False, 'header_opaque_hex': data[:2].hex(),
            'configuration_name_bytes_hex': data[2:16].hex(), 'channels': channels,
            'input_mute_mask_raw': input_mute, 'output_mute_mask_raw': output_mute,
            'unknown_input_mute_bits': input_mute & 0xFFF0, 'unknown_output_mute_bits': output_mute & 0xFF00,
            'fir_name_bytes_hex': [data[1460+8*i:1468+8*i].hex() for i in range(12)],
            'extension_unknown_words': words(1556, 8) if layout=='editor1572' else None,
            'extension_status': 'present_semantics_unknown' if layout=='editor1572' else 'absent_not_fabricated'}


class StateBlockAssembler:
    """Explicit one-session RX24/RX28 payload collector, no I/O or requests.

    Index byte plus 50-byte stride. Require every block before decode. Retain
    last-block padding, reject changed duplicates. Caller owns session lifetime
    and direction/opcode validation. Completeness is stricter than vendor code.
    """
    def __init__(self, *, layout='editor1572'):
        if layout not in LAYOUT_SIZES:
            raise ValueError('Unknown explicit state layout')
        self.layout = layout
        self.size = LAYOUT_SIZES[layout]
        self._blocks = {}

    def add(self, payload):
        payload = bytes(payload)
        if not payload:
            raise ValueError('Missing configuration block index')
        index = payload[0]; body = payload[1:]
        last_size = self.size-1550
        if index > 31 or not (len(body) == 50 if index < 31 else last_size <= len(body) <= 50):
            raise ValueError('Invalid configuration block index or source stride length')
        if index in self._blocks and self._blocks[index] != body:
            raise ValueError('Changed duplicate configuration block; reset session explicitly')
        self._blocks[index] = body

    @property
    def missing_blocks(self):
        return tuple(index for index in range(32) if index not in self._blocks)

    @property
    def final_padding(self):
        return self._blocks.get(31, b'')[self.size-1550:]

    def data(self):
        if self.missing_blocks:
            raise ValueError('Configuration read incomplete')
        return b''.join(self._blocks[index] for index in range(32))[:self.size]

    def decode(self):
        return decode_state(self.data(), layout=self.layout)
