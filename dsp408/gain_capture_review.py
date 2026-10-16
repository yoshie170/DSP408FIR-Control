"""Offline evidence checklist for the approved manufacturer IN A gain test.

Reads existing frames only. A matching report never unlocks our transport.
Full correlated reads before, between and after the two setters are required
to establish the observed byte-field effect; ACK alone is insufficient.
"""
import hashlib

from dsp408.editor_state_research import StateBlockAssembler, decode_state
from dsp408.editor_tx_research import source_gain_db
from dsp408.source_codec import frame, encode_payload
from dsp408.usbpcap_research import review_capture
from dsp408.wire_research import decode_editor_frame


def observe_gain_frames(events):
    """Describe arbitrary captured gain sequences without treating ACK as effect.

    Repeats are retained. A source conversion is an interpretation of observed
    bytes; agreement with UI/readback must be established independently.
    """
    observations = []
    pending = None
    for event in events:
        packet = decode_editor_frame(bytes.fromhex(event['frame_hex']))
        if event['direction'] == 'tx' and packet.command == 0x34:
            item = {'record': event['record'], 'time_seconds': event['time_seconds'],
                    'payload_hex': packet.data.hex(), 'frame_hex': packet.raw.hex(),
                    'channel': None, 'gain_raw': None, 'source_interpreted_db': None,
                    'source_serializer_matches': False, 'following_empty_rx01': None}
            if len(packet.data) == 3:
                channel = packet.data[0]
                value = int.from_bytes(packet.data[1:], 'little')
                item.update(channel=channel, gain_raw=value, source_interpreted_db=source_gain_db(value))
                try:
                    item['source_serializer_matches'] = packet.raw == frame(
                        0x34, encode_payload(0x34, channel, gain_raw=value), 1)
                except ValueError:
                    pass
            observations.append(item)
            pending = item
        elif event['direction'] == 'tx' and (packet.command != 0x40 or not allowed_read(packet)):
            pending = None  # In particular TX12 can produce its own empty RX01.
        elif pending is not None and event['direction'] == 'rx' and packet.command == 1 and not packet.data:
            pending['following_empty_rx01'] = {'record': event['record'],
                'elapsed_ms': (event['time_seconds'] - pending['time_seconds']) * 1000}
            pending = None
    runs = []
    for item in observations:
        key = (item['channel'], item['gain_raw'])
        if runs and (runs[-1]['channel'], runs[-1]['gain_raw']) == key:
            runs[-1]['observed_count'] += 1
            runs[-1]['last_record'] = item['record']
        else:
            runs.append({'channel': item['channel'], 'gain_raw': item['gain_raw'],
                         'source_interpreted_db': item['source_interpreted_db'],
                         'first_record': item['record'], 'last_record': item['record'], 'observed_count': 1})
    return {'scope': 'Observed TX gain bytes; source dB interpretation, no post-write verification',
            'count': len(observations), 'observations': observations, 'adjacent_value_runs': runs,
            'all_source_serializer_frames_match': bool(observations) and all(
                o['source_serializer_matches'] for o in observations),
            'channels_observed': sorted({o['channel'] for o in observations if o['channel'] is not None}),
            'following_empty_rx01_count': sum(o['following_empty_rx01'] is not None for o in observations),
            'parameter_application_verified_by_this_transcript': False,
            'limits': ['Repeated TXs are observations, not a requirement for our future driver',
                       'A following empty RX01 has no channel/value/transaction identifier; never a universal ACK',
                       'UI-reported final gain is not a full post-write raw readback']}


def allowed_read(packet):
    op, payload = packet.command, packet.data
    if op in (0x10, 0x11, 0x12, 0x13, 0x2C, 0x22, 0x14, 0x40):
        return not payload
    if op == 0x29:
        return len(payload) == 1 and payload[0] <= 18
    if op == 0x27:
        return len(payload) == 1 and payload[0] <= 31
    if op == 0x56:
        return len(payload) == 3 and payload[0] == 0 and int.from_bytes(payload[1:], 'little') in (
            0, 157, 315, 472, 630, 708, 787, 866, 945, 1024, 1102, 1181)
    return False


def analyze_gain_capture(raw, *, bus, device):
    capture = review_capture(raw, bus=bus, device=device, device_address=1,
                             layout='common-prefix1556')
    setters = []
    unexpected = []
    errors = []
    snapshots = []
    assembler = None
    pending = None
    snapshot_stage = None
    snapshot_start = None
    identities = []
    previous_time = -1
    for event in capture['events']:
        packet = decode_editor_frame(bytes.fromhex(event['frame_hex']))
        direction = event['direction']
        record = event['record']
        if direction == 'rx' and packet.command == 0x13:
            identities.append(packet.data.hex())
        if event['time_seconds'] < previous_time:
            errors.append({'record': record, 'reason': 'Nonmonotonic capture time'})
        previous_time = event['time_seconds']
        if (packet.address_bytes != (b'\0\1' if direction == 'tx' else b'\1\0')
                or event['bus_payload_bytes'] != 64
                or event['endpoint'] != (2 if direction == 'tx' else 0x81)):
            errors.append({'record': record, 'reason': 'Frame/container differs from exact USB profile'})
        if direction == 'tx' and packet.command == 0x34:
            setters.append({'record': record, 'time_seconds': event['time_seconds'],
                            'payload_hex': packet.data.hex(), 'frame_hex': packet.raw.hex()})
            if assembler is not None:
                errors.append({'record': record, 'reason': 'Gain changed during configuration read'})
            continue
        if direction == 'tx' and not allowed_read(packet):
            unexpected.append({'record': record, 'command': f'0x{packet.command:02X}',
                               'payload_hex': packet.data.hex()})
        if direction == 'tx' and packet.command == 0x27:
            if len(packet.data) != 1 or packet.data[0] > 31:
                errors.append({'record': record, 'reason': 'Invalid configuration request'})
                continue
            index = packet.data[0]
            if pending is not None:
                errors.append({'record': record, 'reason': 'New read before pending block response'})
            if index == 0:
                if assembler is not None:
                    errors.append({'record': record, 'reason': 'Configuration read restarted before completion'})
                assembler = StateBlockAssembler(layout='common-prefix1556')
                snapshot_stage = len(setters)
                snapshot_start = record
            if assembler is None or index != assembler.missing_blocks[0]:
                errors.append({'record': record, 'reason': 'Configuration blocks must be requested in order0..31'})
            pending = index
        elif direction == 'rx' and packet.command == 0x24:
            if assembler is None or pending is None or not packet.data or packet.data[0] != pending:
                errors.append({'record': record, 'reason': 'Uncorrelated configuration response'})
                continue
            try:
                assembler.add(packet.data)
            except ValueError as exc:
                errors.append({'record': record, 'reason': str(exc)})
                assembler = None
                pending = None
                continue
            pending = None
            if not assembler.missing_blocks:
                data = assembler.data()
                snapshots.append({'start_record': snapshot_start, 'end_record': record,
                                  'setter_count': snapshot_stage, 'data': data,
                                  'state_sha256': hashlib.sha256(data).hexdigest(),
                                  'input_a_gain_raw': decode_state(data, layout='common-prefix1556')['channels'][0]['gain_raw']})
                assembler = None
    if assembler is not None or pending is not None:
        errors.append({'reason': 'Capture ends during configuration read'})

    expected_frames = [frame(0x34, b'\0\x0e\x01').hex(), frame(0x34, b'\0\x18\x01').hex()]
    cycle = [s['frame_hex'] for s in setters] == expected_frames
    stages = {i: [s for s in snapshots if s['setter_count'] == i] for i in range(3)}
    # All repeated observations of each stage must agree; do not cherry-pick.
    stable = all(len({s['state_sha256'] for s in group}) <= 1 for group in stages.values())
    before = stages[0][-1] if stages[0] else None
    lower = stages[1][-1] if stages[1] else None
    restored = stages[2][-1] if stages[2] else None
    first_setter_record = setters[0]['record'] if setters else float('inf')
    valid_starts = [s for s in capture['startups']
                    if s['startup_candidate_complete'] and s['identity_payload_hex'] == b'FIR408 V0115P'.hex()
                    and s.get('last_capture_record', float('inf')) < first_setter_record]
    authenticated = bool(before and any(s['configuration_candidate_sha256'] == before['state_sha256']
                                       for s in valid_starts))
    deltas = []
    if before and lower:
        deltas = [{'offset': i, 'before': a, 'after': b}
                  for i, (a, b) in enumerate(zip(before['data'], lower['data'])) if a != b]
    gain_only = bool(before and lower and before['input_a_gain_raw'] == 280
                     and lower['input_a_gain_raw'] == 270 and deltas
                     and all(d['offset'] in (146, 147) for d in deltas))
    identical_restore = bool(before and restored and before['data'] == restored['data'])
    checks = {
        'complete_exact_firmware_startup_before_test': authenticated,
        'all_observed_identities_match_exact_firmware': bool(identities) and all(
            value == b'FIR408 V0115P'.hex() for value in identities),
        'exact_two_setter_frames_in_order': cycle,
        'no_other_or_unrecognized_tx': not unexpected,
        'three_correlated_configuration_stages': bool(before and lower and restored),
        'repeated_stage_snapshots_agree': stable,
        'gain_minus1_changes_only_gain_bytes': gain_only,
        'restored_prefix_identical_to_baseline': identical_restore,
        'no_read_or_container_errors': not errors and not capture['startup_errors'],
        'no_failed_usb_completions': all(key == '0x00000000' for key in capture['completion_status_counts']),
    }
    matches = all(checks.values())
    return {'scope': 'Offline checklist for manufacturer-editor gain0/-1/0 capture; not upload approval',
            'capture_sha256': capture['capture_sha256'], 'capture_bytes': capture['capture_bytes'],
            'bus': bus, 'device': device, 'checks': checks,
            'parameter_prefix_evidence_matches': matches,
            'hardware_write_unlock_allowed': False, 'hardware_commands_sent': 0,
            'setters': setters, 'expected_source_frames': expected_frames,
            'observed_identity_payloads_hex': identities,
            'unexpected_tx': unexpected, 'read_errors': errors,
            'startup_errors': capture['startup_errors'],
            'completion_status_counts': capture['completion_status_counts'],
            'snapshots': [{k: v for k, v in s.items() if k != 'data'} for s in snapshots],
            'minus1_byte_changes': deltas,
            'gain_frame_observations': observe_gain_frames(capture['events']),
            'missing_evidence': [key for key, passed in checks.items() if not passed],
            'limits': ['Empty RX01/RX02 is never treated as setter confirmation',
                       'Only captured1556 prefix is compared; globals/active FIR/EEPROM/audio effects remain unknown',
                       'Capture selection and provenance are supplied by the user; analysis cannot attest how file was obtained',
                       'Matching evidence applies only to these two frames and does not unlock our application'],
            }
