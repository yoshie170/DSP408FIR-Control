"""Bounded offline classic-PCAP/USBPcap reader. No device handles or commands.

Container reference: https://desowin.org/usbpcap/captureformat.html
USB bus payloads do not contain the Windows synthetic Report ID byte.
"""
import hashlib
import struct
from collections import Counter

from dsp408.wire_research import decode_editor_frame
from dsp408.startup_research import StartupReview

MAX_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 200000


def read_capture(raw, *, bus, device):
    """Explicit bus/device selection; retain payload/tails and raw status values."""
    if not 0 <= bus <= 65535 or not 0 <= device <= 65535:
        raise ValueError('Invalid explicit bus/device')
    raw = bytes(raw)
    if len(raw) > MAX_BYTES or len(raw) < 24:
        raise ValueError('Capture size must be 24 bytes..32 MiB')
    if raw[:4] != bytes.fromhex('d4c3b2a1'):
        raise ValueError('Only little-endian microsecond classic PCAP is supported')
    _, major, minor, _, _, snaplen, linktype = struct.unpack_from('<IHHIIII', raw)
    if (major, minor, linktype) != (2, 4, 249) or not snaplen:
        raise ValueError('Expected PCAP2.4 LINKTYPE_USBPCAP249')
    pos = 24; records = 0; events = []; statuses = Counter(); endpoints = Counter()
    first = last = None; selected = 0; descriptors = []
    while pos < len(raw):
        if len(raw) - pos < 16:
            raise ValueError('Truncated PCAP record header')
        sec, usec, size, original = struct.unpack_from('<IIII', raw, pos); pos += 16
        if size != original or size > snaplen or pos + size > len(raw) or usec >= 1000000:
            raise ValueError('Truncated or invalid PCAP record')
        packet = raw[pos:pos + size]; pos += size; records += 1
        if records > MAX_RECORDS:
            raise ValueError('Capture record limit exceeded')
        if len(packet) < 27:
            raise ValueError('Truncated USBPcap header')
        h, irp, status, function, info, rb, rd, ep, transfer, count = struct.unpack_from('<HQIHBHHBBI', packet)
        if h < 27 or h > len(packet) or count != len(packet) - h:
            raise ValueError('Invalid USBPcap header/data length')
        timestamp = sec + usec / 1000000
        if first is None: first = timestamp
        last = timestamp
        if (rb, rd) != (bus, device): continue
        selected += 1
        payload = packet[h:]; completion = bool(info & 1)
        if completion: statuses[f'0x{status:08X}'] += 1
        if transfer == 2 and payload:
            descriptors.append({'record': records, 'endpoint': ep, 'info': info,
                                'control_stage': packet[27] if h >= 28 else None,
                                'payload_hex': payload.hex()})
        # OUT data at submission, IN data at completion. Never count both URBs.
        if transfer != 1 or not payload or bool(ep & 128) != completion: continue
        if completion and status: continue
        endpoints[f'0x{ep:02X}'] += 1
        if len(payload) < 5:
            raise ValueError(f'Record{records}: incomplete DSP payload')
        try: frame = decode_editor_frame(payload[:payload[4] + 8])
        except ValueError as e: raise ValueError(f'Record{records}: {e}') from e
        events.append({'record': records, 'time_seconds': timestamp - first,
                       'direction': 'rx' if ep & 128 else 'tx', 'endpoint': ep,
                       'irp_id_hex': f'{irp:016x}', 'bus_payload_bytes': len(payload),
                       'command': f'0x{frame.command:02X}', 'frame_hex': frame.raw.hex(),
                       'tail_hex': payload[len(frame.raw):].hex()})
    return {'capture_sha256': hashlib.sha256(raw).hexdigest(), 'capture_bytes': len(raw),
            'records': records, 'selected_records': selected, 'bus': bus, 'device': device,
            'duration_seconds': last - first if first is not None else 0,
            'completion_status_counts': dict(statuses), 'endpoint_data_counts': dict(endpoints),
            'control_records': descriptors, 'events': events}


def review_capture(raw, *, bus, device, device_address, layout):
    result = read_capture(raw, bus=bus, device=device)
    sessions = []; active = None; errors = []; counts = Counter()
    for event in result['events']:
        direction = event['direction']; frame = bytes.fromhex(event['frame_hex'])
        command = decode_editor_frame(frame).command
        counts[f'{direction}:{command:02X}'] += 1
        if direction == 'tx' and command == 0x10:
            if active is not None:
                errors.append({'record': event['record'], 'error': 'New hello before prior startup completed'})
            active = StartupReview(transport='usb', layout=layout, device_address=device_address)
        if active is None: continue
        try: active.feed(direction, frame)
        except ValueError as e:
            errors.append({'record': event['record'], 'phase': active.phase, 'error': str(e)})
            sessions.append(active.report()); active = None; continue
        if active.phase in ('complete_candidate', 'blocked', 'failed', 'rejected'):
            report = active.report(); report['last_capture_record'] = event['record']
            sessions.append(report); active = None
    if active is not None:
        sessions.append(active.report())
        errors.append({'error': 'Capture ended during startup'})
    result.update({'command_counts': dict(counts), 'startups': sessions, 'startup_errors': errors,
                   'scope': 'Captured USB startup/read traffic only; no write/audio certification',
                   'hardware_writes_enabled': False})
    return result
