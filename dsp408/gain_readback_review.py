"""Pure comparison of the exact IN A 0/-1/0 readback sample. No transport."""
from dsp408.editor_state_research import decode_state


def compare_gain_readbacks(baseline, minus1, restored):
    states = [bytes(s) for s in (baseline, minus1, restored)]
    decoded = [decode_state(s, layout='common-prefix1556') for s in states]
    def changes(before, after):
        return [{'offset': i, 'before': a, 'after': b}
                for i, (a, b) in enumerate(zip(before, after)) if a != b]
    minus_changes = changes(states[0], states[1])
    restore_changes = changes(states[0], states[2])
    gains = [d['channels'][0]['gain_raw'] for d in decoded]
    checks = {'baseline_in_a_raw280': gains[0] == 280,
              'minus1_in_a_raw270': gains[1] == 270,
              'restored_in_a_raw280': gains[2] == 280,
              'minus1_changes_only_in_a_gain_bytes': bool(minus_changes) and all(
                  change['offset'] in (146, 147) for change in minus_changes),
              'restored_prefix_identical_to_baseline': not restore_changes}
    return {'scope': 'Pure raw-prefix comparison; caller must authenticate journals and provenance',
            'checks': checks, 'sample_readback_checks_match': all(checks.values()),
            'input_a_gain_raw_sequence': gains,
            'minus1_byte_changes': minus_changes, 'restored_byte_changes': restore_changes,
            'our_parameter_write_tested': False, 'hardware_write_unlock_allowed': False,
            'limits': ['Only IN A and sampled raw280/270/280, not other channels/ranges',
                       'Snapshots after separate TX10 startups, not continuous monitoring',
                       'No audio/EEPROM/power-cycle/global/active-FIR verification',
                       'Prefix equality and source frames do not authorize our application to send setters']}
