"""Correlated P02 EEPROM read candidate. No I/O, staging or parameter writes."""
import hashlib
from dsp408.source_codec import frame
from dsp408.wire_research import decode_editor_frame
from dsp408.editor_state_research import StateBlockAssembler

SLOT = 2
RECORD_BYTES = 1556
START_ADDRESS = 1605
REFERENCE_SHA256 = 'deabbc06b4330d4fb6e414e8ff4bad1a46b2fc774b1070ec85728c12b9fcf52a'
REFERENCE_NAME = b'4+2 AES       '
READ_BLOCKS = tuple((START_ADDRESS+i*50, min(50, RECORD_BYTES-i*50)) for i in range(32))
CERTIFICATE_KEYS = ('method', 'slot', 'state_sha256', 'reference_sha256',
                    'current_before_sha256', 'current_after_sha256',
                    'active_slot_before', 'active_slot_after', 'catalog_before_hex',
                    'catalog_after_hex', 'name_raw_hex', 'fir_bank_read')


class EepromPresetReview:
    def __init__(self, state, metadata):
        self.before = bytes(state)
        if len(self.before) != RECORD_BYTES:
            raise ValueError('EEPROM preview requires a complete current state')
        markers = metadata.get('catalog_markers', [])
        if (len(markers) != 19 or any(type(v) is not int or not 0 <= v <= 255 for v in markers)
                or markers[SLOT-1] != 255):
            raise ValueError('Fresh P02 catalog differs from the observed stored profile')
        self.catalog = bytes(markers)
        names = metadata.get('names_raw_hex', {})
        self.name = bytes.fromhex(names.get(SLOT-1, names.get(str(SLOT-1), '')))
        self.active = metadata.get('active_slot_raw')
        if self.name != REFERENCE_NAME or type(self.active) is not int or not 0 <= self.active <= 19:
            raise ValueError('Fresh P02 name or active slot differs from the observed profile')
        self.record = bytearray()
        self.after = StateBlockAssembler(layout='common-prefix1556')
        self.catalog_after = None
        self.steps = [(0x19, address.to_bytes(2, 'little')+bytes((count,)), 0x19, 'EEPROM parameters')
                      for address, count in READ_BLOCKS]
        self.steps += [(0x14, b'', 0x14, 'verify active slot'),
                       (0x22, b'', 0x22, 'verify catalog'),
                       (0x29, b'\1', 0x29, 'verify stored name')]
        self.steps += [(0x27, bytes((i,)), 0x24, 'verify current parameters') for i in range(32)]
        self.position = 0
        self.outstanding = False
        self.complete = False

    @property
    def proposal(self):
        if self.complete:
            return None
        op, payload, _, _ = self.steps[self.position]
        return frame(op, payload)

    @property
    def phase(self):
        return 'complete' if self.complete else self.steps[self.position][3]

    def feed(self, direction, raw):
        if self.complete:
            raise ValueError('EEPROM preview already complete')
        packet = decode_editor_frame(raw)
        op, data, response, phase = self.steps[self.position]
        if direction == 'tx':
            if self.outstanding or packet.raw != self.proposal:
                raise ValueError('EEPROM TX differs from the pending read')
            self.outstanding = True
            return False
        if direction != 'rx' or packet.address_bytes != b'\1\0' or not self.outstanding:
            raise ValueError('Unrequested EEPROM response or wrong address')
        if packet.command == 1 and not packet.data:
            return False
        if packet.command != response:
            raise ValueError('Unexpected EEPROM preview response')
        body = packet.data
        if phase == 'EEPROM parameters':
            if len(body) != data[2]:
                raise ValueError('EEPROM response length differs from the requested count')
            self.record.extend(body)
            if self.position == 31:
                if len(self.record) != RECORD_BYTES or self.record[2:16] != self.name:
                    raise ValueError('EEPROM P02 record or name incomplete')
                if hashlib.sha256(self.record).hexdigest() != REFERENCE_SHA256:
                    raise ValueError('EEPROM P02 differs from the captured stored reference; no snapshot published')
        elif phase == 'verify active slot':
            if body != bytes((self.active,)):
                raise ValueError('Active slot changed during EEPROM preview; no restore attempted')
        elif phase == 'verify catalog':
            if body != self.catalog:
                raise ValueError('Preset catalog changed during EEPROM preview')
            self.catalog_after = body
        elif phase == 'verify stored name':
            if body != b'\1'+self.name:
                raise ValueError('Stored P02 name changed during EEPROM preview')
        else:
            index = data[0]
            if len(body) != (7 if index == 31 else 51) or body[0] != index:
                raise ValueError('Current-state block index or length differs')
            self.after.add(body)
            if index == 31 and self.after.data() != self.before:
                raise ValueError('Current raw state changed during EEPROM preview; no restore attempted')
        self.position += 1
        self.outstanding = False
        self.complete = self.position == len(self.steps)
        return True

    def result(self):
        if not self.complete:
            raise ValueError('EEPROM preview incomplete or preservation checks failed')
        return {'scope': 'Direct EEPROM P02 parameters; host readback, not audio/persistence certification',
                'method': 'EEPROM19', 'slot': SLOT, 'state_hex': bytes(self.record).hex(),
                'state_sha256': hashlib.sha256(self.record).hexdigest(),
                'reference_sha256': REFERENCE_SHA256, 'name_raw_hex': self.name.hex(),
                'current_before_sha256': hashlib.sha256(self.before).hexdigest(),
                'current_after_sha256': hashlib.sha256(self.after.data()).hexdigest(),
                'active_slot_before': self.active, 'active_slot_after': self.active,
                'catalog_before_hex': self.catalog.hex(), 'catalog_after_hex': self.catalog_after.hex(),
                'complete': True, 'current_state_unchanged': True, 'fir_bank_read': False}
