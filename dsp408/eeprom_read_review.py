"""Offline replay of direct EEPROM P02 reads and preservation evidence."""
import hashlib, json
from dsp408.startup_research import StartupReview
from dsp408.eeprom_preset import EepromPresetReview, CERTIFICATE_KEYS
from dsp408.usb_eeprom_read import validate_eeprom_read_request
from dsp408.usb_read import read_bus_frame, IDENTITY


def inspect_bytes(raw):
    raw = bytes(raw)
    if not raw or len(raw) > 32*1024*1024 or not raw.endswith(b'\n'):
        raise ValueError('Invalid/incomplete EEPROM journal')
    lines = raw.splitlines()
    if len(lines) > 200000:
        raise ValueError('EEPROM journal record limit')
    startup = StartupReview(transport='usb', layout='common-prefix1556', device_address=1)
    review = None; result = None; intent = None; polling = False; closing = False; closed = False
    error = None; issues = []; cancelled = False
    for index, line in enumerate(lines):
        try:
            if len(line) > 16384:
                raise ValueError('EEPROM journal line limit')
            row = json.loads(line)
            if not isinstance(row, dict) or type(row.get('index')) is not int or row['index'] != index:
                raise ValueError('Record index differs')
            if closed:
                raise ValueError('Records after session end')
            kind = row['kind']
            if index == 0:
                if kind != 'session_started':
                    raise ValueError('Missing EEPROM session start')
                continue
            if kind == 'tx_intent':
                if closing or intent is not None:
                    raise ValueError('TX after close or overlapping intent')
                intent = bytes.fromhex(row['frame_hex']); validate_eeprom_read_request(intent)
            elif kind == 'tx_completed':
                packet = validate_eeprom_read_request(bytes.fromhex(row['frame_hex']))
                if intent is None or packet.raw != intent:
                    raise ValueError('TX completion differs')
                intent = None
                if packet.command == 0x11 and startup.recognized:
                    closing = True; polling = False
                elif startup.phase != 'complete_candidate':
                    startup.feed('tx', packet.raw)
                elif review is not None and not review.complete:
                    review.feed('tx', packet.raw)
                elif review is None:
                    metadata = {'active_slot_raw': startup.active_slot_raw, 'names_raw_hex': startup.names,
                                'catalog_markers': list(startup.trace.latest_preset_catalog.marker_bytes)}
                    review = EepromPresetReview(startup.trace.configuration.data(), metadata)
                    review.feed('tx', packet.raw)
                elif result is not None and packet.command == 0x40 and not polling:
                    polling = True
                else:
                    raise ValueError('Unexpected post-EEPROM TX')
            elif kind == 'rx_report':
                packet = read_bus_frame(bytes.fromhex(row['report_hex']))
                if closing:
                    raise ValueError('RX after session close')
                if packet.command == 0x24:
                    body = packet.data
                    if not body or body[0] > 31 or len(body) != (7 if body[0] == 31 else 51):
                        raise ValueError('Current-state block size differs from MCU50/6')
                if startup.phase != 'complete_candidate':
                    if packet.command != startup.response and not (packet.command == 1 and not packet.data):
                        raise ValueError('Unexpected EEPROM startup response')
                    if packet.command == 0x10 and packet.data != b'\x33':
                        raise ValueError('Hello differs')
                    if packet.command == 0x13 and packet.data != IDENTITY:
                        raise ValueError('Identity differs')
                    startup.feed('rx', packet.raw)
                elif review is not None and not review.complete:
                    review.feed('rx', packet.raw)
                elif packet.command == 0x40 and polling and len(packet.data) == 42:
                    polling = False
                elif packet.command != 1 or packet.data:
                    raise ValueError('Unrequested post-EEPROM response')
            elif kind == 'eeprom_preview_complete':
                if result is not None or review is None or not review.complete:
                    raise ValueError('EEPROM certificate without complete correlated read')
                candidate = review.result()
                for key in CERTIFICATE_KEYS:
                    if row.get(key) != candidate[key] or type(row.get(key)) is not type(candidate[key]):
                        raise ValueError('EEPROM certificate differs: '+key)
                result = candidate
            elif kind == 'session_finished':
                closed = True; error = row.get('error'); cancelled = row.get('cancelled') is True
                if not error and (intent is not None or polling):
                    raise ValueError('Healthy finish with pending transaction')
                if not error and not closing and (not cancelled or result is not None):
                    raise ValueError('Healthy finish without session close')
            else:
                raise ValueError('Unexpected EEPROM journal event')
        except (ValueError, TypeError, KeyError, IndexError) as failure:
            issues.append({'index': index, 'reason': str(failure)}); break
    status = ('invalid_prefix' if issues else 'failed_prefix' if error else
              'cancelled_before_complete' if (closing or cancelled) and result is None else
              'validated_closed' if closed else 'validated_open_prefix')
    return {'scope': 'Offline EEPROM P02 host replay, not audio/persistence certification',
            'status': status, 'issues': issues, 'session_error': error, 'records': len(lines), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'startup_complete': startup.phase == 'complete_candidate',
            'eeprom_preset': result if not issues else None, 'pending_intent': intent is not None}
