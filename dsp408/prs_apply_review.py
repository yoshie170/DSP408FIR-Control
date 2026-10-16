"""Exact-byte, offline review of applying PRS parameters to a read snapshot.

No port, worker, policy token or hardware authorization. FIR differences and
unrepresented bytes are blockers, never replaced with guessed values.
"""
import hashlib

from dsp408.model import DeviceModel
from dsp408.prs import validate, from_bytes, BODY_START, FIR_START, FIR_END
from dsp408.source_session import SourceDocument, project_state
from dsp408.source_bindings import plan_changes, Packet
from dsp408.source_codec import frame


def review(current_state, current_fir, prs_bytes):
    current_state = bytes(current_state)
    current_fir = bytes(current_fir)
    target = validate(bytes(prs_bytes))
    if len(current_state) != 1556 or len(current_fir) != 65536:
        raise ValueError('Review requires complete 1556-byte parameters and 65536-byte FIR snapshot')
    doc = SourceDocument(current_state)
    before, issues = project_state(doc, DeviceModel().to_dict(), strict=False)
    wanted = from_bytes(target)
    blockers = list(issues)
    for label, channels in [('current', doc.decoded()['channels']),
                            ('target', SourceDocument(current_state[:2] + target[BODY_START:FIR_START]).decoded()['channels'])]:
        if any(c['link_mask_raw'] != 1 << (i if i < 4 else i - 4) for i, c in enumerate(channels)):
            blockers.append({'path': label + '.links', 'reason': 'Grouped Link semantics are not reproduced by this review'})
    plan = plan_changes(before.to_dict(), wanted.to_dict(), raw_state=doc.decoded())
    blockers.extend(plan.blocked)
    blockers.extend(plan.local_only)
    # This reducer intentionally covers ordinary parameter commands only.
    # Numeric FIR design/import and global operations need separate verification.
    supported = {0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x38,
                 0x3A, 0x3D, 0x3E, 0x3F, 0x41, 0x5B}
    packets = []
    for packet in plan.packets:
        if packet.command not in supported:
            blockers.append({'path': packet.path, 'reason': 'Separate FIR/global operation required'})
            continue
        try:
            doc.apply(frame(packet.command, packet.payload))
            packets.append(packet)
        except ValueError as error:
            blockers.append({'path': packet.path, 'reason': str(error)})
    target_name = target[BODY_START:BODY_START + 14]
    if current_state[2:16] != target_name:
        if any(b < 32 or b > 126 for b in target_name):
            blockers.append({'path': 'preset.name', 'reason': 'Name requires canonical printable ASCII bytes'})
        else:
            packets.append(Packet(0x26, target_name, 'preset.name'))
            doc.data[2:16] = target_name  # Source-audited name-only RAM effect.
    expected = current_state[:2] + target[BODY_START:FIR_START]
    residual = [i for i, (a, b) in enumerate(zip(doc.data, expected)) if a != b]
    if residual:
        blockers.append({'path': 'raw.parameters', 'reason': 'Not all target bytes are represented by the packet plan',
                         'offsets': residual})
    fir_differences = sum(a != b for a, b in zip(current_fir, target[FIR_START:FIR_END]))
    if fir_differences:
        blockers.append({'path': 'fir.bank', 'reason': 'FIR bank differs; parameter-only plan cannot reproduce this PRS',
                         'different_bytes': fir_differences})
    return {'scope': 'Offline PRS parameter review only; no hardware upload or authorization',
            'hardware_enabled': False, 'source_plan_complete': not blockers,
            'current_state_sha256': hashlib.sha256(current_state).hexdigest(),
            'target_state_sha256': hashlib.sha256(expected).hexdigest(),
            'prs_sha256': hashlib.sha256(target).hexdigest(),
            'fir_different_bytes': fir_differences, 'residual_parameter_offsets': residual,
            'packets': [p.record(1) for p in packets], 'blockers': blockers,
            'limits': ['Raw equality is not audio, EEPROM persistence or physical FIR verification',
                       'No temporary mute or automatic restore is inferred from this plan']}
