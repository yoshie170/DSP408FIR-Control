"""Offline comparison with a source-layout readback. Never grants write permission.

The caller authenticates the journal. SourceDocument is a byte-field reducer,
not an MCU/DSP emulator. Unknown model placeholders are never actual readings.
"""
from copy import deepcopy
import hashlib

from dsp408.model import DeviceModel
from dsp408.readback_audit import audit_readback
from dsp408.source_bindings import plan_changes
from dsp408.source_codec import frame
from dsp408.source_session import SourceDocument, project_state

GLOBAL_KEYS = ('input_select', 'output_select', 'test_tone', 'sine_hz')


def differences(before, after, path=''):
    """Leaf differences, with coefficient arrays kept as one bounded record."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [d for key in before for d in differences(before[key], after[key],
                 f'{path}.{key}' if path else key)]
    if isinstance(before, list) and isinstance(after, list) and not path.endswith('coefficients'):
        return [d for i, (a, b) in enumerate(zip(before, after))
                for d in differences(a, b, f'{path}[{i}]')]
    return [{'path': path, 'baseline_projection': before, 'requested': after}]


def review_configuration(target, state, *, layout='common-prefix1556'):
    if layout != 'common-prefix1556':
        raise ValueError('Review requires the exact captured1556 layout')
    state = bytes(state)
    document = SourceDocument(state, layout, origin='offline readback comparison')
    baseline, issues = project_state(document, DeviceModel().to_dict())
    before = baseline.to_dict()
    desired = DeviceModel.from_dict(deepcopy(target)).to_dict()
    planning = deepcopy(desired)
    excluded = []
    unavailable = []

    def exclude(obj, old, key, path, reason, *, unknown=True):
        if obj[key] != old[key]:
            excluded.append({'path': path, 'requested': obj[key],
                             'actual': None if unknown else old[key], 'reason': reason})
        obj[key] = deepcopy(old[key])

    for key in GLOBAL_KEYS:
        path = 'settings.' + key
        unavailable.append({'path': path, 'actual': None, 'requested': desired['settings'][key],
                            'reason': 'Outside captured1556; DEMO default is not a readback'})
        exclude(planning['settings'], before['settings'], key, path, 'Global baseline unavailable')
    exclude(planning, before, 'links', 'links', 'Local Link checkboxes are not MCU masks')
    for ch, (new, old) in enumerate(zip(planning['inputs'] + planning['outputs'],
                                       before['inputs'] + before['outputs'])):
        prefix = f'channel[{ch}]'
        unavailable.append({'path': prefix + '.fir.coefficients', 'actual': None,
                            'requested_count': len(new['fir']['coefficients']),
                            'reason': 'Active FIR coefficients absent from state prefix; empty JSON is not a clear request'})
        exclude(new['fir'], old['fir'], 'coefficients', prefix + '.fir.coefficients',
                'FIR lifecycle and active coefficient baseline unavailable')
        # Input design is local only; output design remains a source proposal,
        # but active audio/MCU synthesis and conditional tap fields are unknown.
        for key in ('mode', 'window', 'taps', 'hpf_hz', 'lpf_hz'):
            exclude(new['fir'], old['fir'], key, prefix + '.fir.' + key,
                    'Input design is local only' if ch < 4 else 'FIR synthesis/lifecycle not verified')
        if ch >= 4:
            exclude(new['fir'], old['fir'], 'bypass', prefix + '.fir.bypass',
                    'Output FIR bypass uses compound design command; deferred')
        exclude(new, old, 'deq', prefix + '.deq', 'Hidden DEQ has no established active readback')

    plan = plan_changes(before, planning, raw_state=document.decoded())
    reduced = SourceDocument(state, layout, origin='offline trial copy')
    candidates = []
    refused = list(plan.blocked)
    for packet in plan.packets:
        record = packet.record(1)  # Address from exact captured profile, not local target ID.
        record['capture_verified_setter'] = False
        record['hardware_send_allowed'] = False
        if issues:
            # Conservative until issue-to-compound-field coverage is exhaustive.
            # A fallback projection must never be treated as a real baseline.
            record['trial_applied'] = False
            refused.append({'path': packet.path, 'reason': 'Projection has unsupported fields; trial refused'})
        else:
            try:
                trial = SourceDocument(bytes(reduced.data), layout, origin='offline isolated packet trial')
                trial.apply(frame(packet.command, packet.payload, 1))
                reduced = trial
                record['trial_applied'] = True
            except ValueError as exc:
                record['trial_applied'] = False
                refused.append({'path': packet.path, 'reason': str(exc)})
        candidates.append(record)
    represented, represented_issues = project_state(reduced, before)
    deltas = [{'offset': i, 'before': a, 'after': b}
              for i, (a, b) in enumerate(zip(state, reduced.data)) if a != b]
    return {
        'scope': 'Offline raw-state review only; caller must authenticate journal, source setters remain unverified',
        'hardware_write_unlock_allowed': False, 'hardware_commands_sent': 0,
        'captured_address': 1, 'local_target_device_id': desired['settings']['device_id'],
        'state_sha256': hashlib.sha256(state).hexdigest(),
        'trial_state_sha256': hashlib.sha256(reduced.data).hexdigest(),
        'projection_issues': issues, 'trial_projection_issues': represented_issues,
        'unavailable_fields': unavailable, 'excluded_changes': excluded,
        'source_packets': candidates, 'blocked': refused, 'local_only': plan.local_only,
        'requested_differences': differences(before, desired),
        'represented_differences': differences(before, represented.to_dict()),
        'representation_residuals': differences(represented.to_dict(), planning),
        'raw_byte_changes': deltas, 'coverage': audit_readback(state, layout=layout),
        'limits': ['All setter frames are EXE-source proposals, never device write approval',
                   'Trial only changes local byte fields; no DSP/audio/EEPROM/ACK simulation',
                   'Unchanged unprojected fields are placeholders, not verified equivalence',
                   'Any projection issue conservatively refuses all packet trials',
                   'Captured state may be stale; reconnect/readback required before any future write',
                   'Local nearest quantization is not a measured vendor inverse conversion'],
    }
