"""Pure readback coverage diagnostics. No projection, encoder or device access."""
from dataclasses import asdict
import hashlib
from dsp408.editor_state_research import decode_state
from dsp408.link_research import resolve_link_mask

GLOBAL_OFFSETS={'generator_mode_raw':1556,'sine_index_raw':1558,
                'unknown_word_1560':1560,'input_select_raw':1562,'output_select_raw':1564}


def audit_readback(data,*,layout):
    data=bytes(data);raw=decode_state(data,layout=layout)
    globals_={key:{'offset':offset,'available':offset+2<=len(data),
                   'raw':int.from_bytes(data[offset:offset+2],'little') if offset+2<=len(data) else None}
              for key,offset in GLOBAL_OFFSETS.items()}
    masks=[c['link_mask_raw'] for c in raw['channels']]
    links=[];fir=[]
    for ch,c in enumerate(raw['channels']):
        resolved=resolve_link_mask(masks,ch)
        links.append({'channel':ch,'stored_mask_raw':masks[ch],**asdict(resolved),
                      'source_grouped':len(resolved.members)>1,
                      'topology_unambiguous':not resolved.used_fallback and not resolved.unknown_bits
                          and ch in resolved.members,
                      'ui_checkbox_equivalent':False,'hardware_fanout_verified':False})
        if ch<4:
            fir.append({'channel':ch,'count_raw':c['fir_coefficient_count_raw'],
                        'bypass_raw':c['fir_bypass_raw'],'coefficient_data_available':False,
                        'active_audio_verified':False})
        else:
            fir.append({'channel':ch,'processing_mode_raw':c['crossover_processing_mode_raw'],
                        'type_raw':c['fir_type_raw'],'tap_parameter_raw':c['fir_tap_parameter_raw'],
                        'coefficient_data_available':False,'active_audio_verified':False})
    return {'scope':'offline raw state coverage; no writes or hardware certification',
            'layout':layout,'state_bytes':len(data),'state_sha256':hashlib.sha256(data).hexdigest(),
            'global_fields':globals_,'link_resolutions':links,'fir_configuration':fir,
            'hardware_write_unlock_allowed':False,
            'blockers':['No capture-confirmed parameter setters or post-write state/audio verification',
                        'Readback size1556 omits globals and extra copy masks',
                        'Link fanout/copy/persistence effects not physically verified',
                        'State prefix does not contain active FIR coefficient data',
                        'Preset upload1572 vs read1556 discrepancy remains unresolved',
                        'No universal write ACK; RX01/RX02 cannot certify application']}
