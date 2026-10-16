"""Historical offline staging plan; shared RAM side effect excludes live preview."""
from dsp408.source_codec import frame


def preview_plan(slot,marker):
    if type(slot) is not int or not 1<=slot<=19:raise ValueError('Stored preview slot must be1..19; factory0 is separate')
    if type(marker) is not int or not 1<=marker<=255:raise ValueError('Nonzero stored-prefix marker required; absent slots fall back to defaults')
    return {'scope':'Offline source plan only; not authorized for device transmission',
        'slot':slot,'name_index':slot-1,'marker_raw':marker,
        'physical_staging_allowed':False,'shared_parameter_ram':'0x200003a0',
        'stage_frame_hex':frame(0x24,bytes((slot,))).hex(),
        'state_frames_hex':[frame(0x28,bytes((i,))).hex() for i in range(32)],
        'fir_selector':slot,'fir_frame_count':1261,
        'fir_first_frame_hex':frame(0x56,bytes((slot,0,0))).hex(),
        'fir_last_frame_hex':frame(0x56,bytes((slot,))+b'\xec\x04').hex(),
        'state_bytes':1556,'final_state_block_bytes':6,
        'limits':['TX24 overwrites shared current parameter RAM used by RX24/RX28; not a separate preview buffer',
                  'No Recall20 does not establish unchanged parameter state or audio; physical staging blocked',
                  'Markers do not certify complete preset/FIR integrity',
                  'TX25 upload1572/current and staged reads1556 discrepancy remains',
                  'Store21,Recall20,delete/factory23 and name26 are outside this plan']}
