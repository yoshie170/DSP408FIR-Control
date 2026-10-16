"""Audited utility payloads and local editing lock. No hardware I/O here.

39 source selection; 2F password+lock; 2D subtype0 authentication. PTS and
vendor fallback passwords are intentionally outside this application profile.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import secrets
from dsp408.editor_profile import SINE_FREQUENCIES
from dsp408.source_codec import frame

SOURCE_NAMES = ('ANALOG INPUT', 'PINK NOISE', 'WHITE NOISE', 'SINE')
INPUT_SELECTIONS=('ANALOG','AES / EBU')


def password_bytes(password):
    if not isinstance(password, str) or len(password) != 4:
        raise ValueError('Use a four-character password (A–Z, 0–9).')
    password = password.upper()
    if len(password) != 4 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for c in password):
        raise ValueError('Use a four-character password (A–Z, 0–9).')
    return password.encode('ascii')


@dataclass(frozen=True)
class UtilityRequest:
    kind: str
    packet: bytes = field(repr=False)
    source: str | None = None
    frequency: float | None = None
    device_id: int | None = None
    device_ip: str | None = None
    before: bytes | None = None

def device_settings_read_request():return UtilityRequest('device_settings_read',frame(0x19,b'\x11\0\x08'))

def device_setting_request(kind,value,before):
    before=bytes(before)
    if len(before)!=8:raise ValueError('Fresh device settings read required')
    if kind=='device_id':
        from dsp408.device_address import checked_id
        value=checked_id(value)
        return UtilityRequest(kind,frame(0x15,bytes((value,))),device_id=value,before=before)
    if kind=='device_ip':
        from dsp408.connection_profile import target_profile
        from ipaddress import IPv4Address
        ip=target_profile(value,1)['ip']
        # Native B8 requires destinationFD even in an established session.
        # Release on the single-device USB owner only, never Ethernet broadcast.
        return UtilityRequest(kind,frame(0xB8,IPv4Address(ip).packed,address=253),device_ip=ip,before=before)
    raise ValueError('Unknown device setting')


def generator_request(source, frequency):
    if source not in SOURCE_NAMES or isinstance(frequency, bool) or frequency not in SINE_FREQUENCIES:
        raise ValueError('Choose a source and a supported sine frequency.')
    return UtilityRequest('generator', frame(0x39, bytes((SOURCE_NAMES.index(source), SINE_FREQUENCIES.index(frequency)))), source, frequency)


def input_selection_request(source):
    if source not in INPUT_SELECTIONS:raise ValueError('Choose Analog or AES / EBU.')
    return UtilityRequest('input_selection',frame(0x4D,bytes((0,INPUT_SELECTIONS.index(source)))),source)


def input_selection_read_request():
    # MCU94D6 stores the input selector at EEPROM18. Read exactly this byte;
    # adjacent password/status locations and arbitrary EEPROM remain excluded.
    return UtilityRequest('input_selection_read',frame(0x19,b'\x12\0\1'))


def lock_request(password):
    return UtilityRequest('lock', frame(0x2F, password_bytes(password) + b'\x01'))


def unlock_request(password):
    return UtilityRequest('unlock', frame(0x2D, b'\x00' + password_bytes(password)))


def validate_utility(request):
    if type(request) is not UtilityRequest or type(request.packet) is not bytes:
        raise ValueError('A typed utility request is required.')
    from dsp408.wire_research import decode_editor_frame
    packet = decode_editor_frame(request.packet)
    if packet.address_bytes != (b'\0\xfd' if request.kind=='device_ip' else b'\0\1'):
        raise ValueError('Unexpected device address.')
    if request.kind=='device_settings_read':expected=device_settings_read_request()
    elif request.kind in ('device_id','device_ip'):expected=device_setting_request(request.kind,request.device_id if request.kind=='device_id' else request.device_ip,request.before)
    elif request.kind == 'generator':
        expected = generator_request(request.source, request.frequency)
    elif request.kind=='input_selection':expected=input_selection_request(request.source)
    elif request.kind=='input_selection_read':expected=input_selection_read_request()
    elif request.kind == 'lock' and packet.command == 0x2F and len(packet.data) == 5 and packet.data[-1] == 1:
        expected = lock_request(packet.data[:4].decode('ascii'))
    elif request.kind == 'unlock' and packet.command == 0x2D and len(packet.data) == 5 and packet.data[0] == 0:
        expected = unlock_request(packet.data[1:].decode('ascii'))
    else:
        raise ValueError('Utility request is outside the supported profile.')
    if expected != request:
        raise ValueError('Utility fields differ from the serialized request.')
    return packet


def system_lock(payload):
    payload = bytes(payload)
    if (len(payload) != 7 or payload[0] or payload[5] not in (0, 1)
            or payload[6] not in (0, 1) or payload[5] and not payload[6]):
        raise ValueError('Device requires a different authorization mode.')
    # RX2C byte6 comes from EEPROM address12 in B106/B10C.
    return bool(payload[6])


def session_lock(payload,authenticated=False):
    """The MCU's current access flag is independent of saved protection."""
    system_lock(payload)  # Validate the complete known ordinary-lock profile.
    return bool(payload[5])


class EditingLock:
    """Session-only DEMO lock; secrets never enter presets or configuration."""
    def __init__(self):
        self._salt = self._digest = None

    @property
    def locked(self):
        return self._digest is not None

    def lock(self, password):
        if self.locked:
            raise ValueError('Editing is already locked.')
        raw = password_bytes(password)
        self._salt = secrets.token_bytes(16)
        self._digest = hashlib.pbkdf2_hmac('sha256', raw, self._salt, 120000)

    def unlock(self, password):
        raw = password_bytes(password)
        if not self.locked:
            return True
        if not hmac.compare_digest(self._digest, hashlib.pbkdf2_hmac('sha256', raw, self._salt, 120000)):
            return False
        self._salt = self._digest = None
        return True
