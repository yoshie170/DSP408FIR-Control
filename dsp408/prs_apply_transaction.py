"""PRS parameter transaction rehearsal. Only explicit offline ports accepted.

Not connected to USB Control. No FIR setters, preset Store/Recall, staging,
retry or automatic unmute/restore after failure. Numeric FIR is out of scope.
"""
import hashlib
from dsp408.preset_recall import RecallOperation
from dsp408.prs import validate, BODY_START, FIR_START
from dsp408.prs_apply_review import review
from dsp408.source_codec import frame
from dsp408.source_session import SourceDocument

# Relative order of constructors in480C1C; PEQ is sent after ordinary IN/OUT
# fields for every channel, then FIR names. Audited by audit_prs_sequence.py.
IN_ORDER = (0x3D, 0x3E, 0x30, 0x34, 0x36, 0x38)
OUT_ORDER = (0x3D, 0x3A, 0x41, 0x32, 0x31, 0x3F, 0x34, 0x36, 0x38)


def ordered_packets(report):
    if not report['source_plan_complete']:
        raise ValueError('PRS parameters/FIR cannot be reproduced completely: ' + str(report['blockers'])[:800])
    result = []
    for row in report['packets']:
        op = int(row['command'], 16)
        payload = bytes.fromhex(row['payload_hex'])
        if op == 0x35:
            continue  # The final mask comes from the PRS, after verification.
        if op == 0x26:
            key = (-1, 0, 0)
        elif op == 0x33:
            key = (12 + payload[0], 0, payload[1])
        elif op == 0x5B:
            key = (24 + payload[0], 0, 0)
        else:
            order = IN_ORDER if payload[0] < 4 else OUT_ORDER
            key = (payload[0], order.index(op), 0)
        result.append((key, op, payload, row['path']))
    return [(op, payload, path) for _, op, payload, path in sorted(result)]


def muted(state):
    doc = SourceDocument(state)
    for ch in range(12):
        doc.apply(frame(0x35, bytes((ch, 1))))
    return bytes(doc.data)


class PrsApplyRehearsal(RecallOperation):
    def __init__(self, port, stop, **kwargs):
        self.check_port(port)
        super().__init__(port, stop, **kwargs)

    def check_port(self,port):
        if getattr(port,'offline_only',None) is not True:
            raise ValueError('PRS transaction is offline only; physical ports are blocked')

    def report(self, stage, waiting=False):
        self.progress({'busy': True, 'operation': 'prs_rehearsal', 'stage': stage,
                       'done': self.done, 'total': self.TOTAL, 'waiting': waiting,
                       'hardware_enabled': False})

    def state(self, stage):
        data = bytearray()
        for i in range(32):
            body = self.exchange(frame(0x27, bytes((i,))), 0x24, stage)
            if len(body) != (7 if i == 31 else 51) or body[0] != i:
                raise ValueError('PRS state response index/extent differs')
            data.extend(body[1:])
        return bytes(data)

    def bank(self, stage):
        data = bytearray()
        for i in range(1261):
            body = self.exchange(frame(0x56, b'\0' + i.to_bytes(2, 'little')), 0x56, stage)
            if len(body) != (19 if i == 1260 else 55) or body[:3] != b'\0' + i.to_bytes(2, 'big'):
                raise ValueError('PRS FIR bank/block/extent differs')
            data.extend(body[3:])
        return bytes(data)

    def run(self, confirmed_state, confirmed_bank, prs):
        self.check_port(self.port)
        confirmed_state = bytes(confirmed_state); confirmed_bank = bytes(confirmed_bank)
        prs = validate(bytes(prs))
        if confirmed_bank != b'\xff' * 65536:
            raise ValueError('PRS rehearsal currently supports unchanged all-FF FIR banks only')
        report = review(confirmed_state, confirmed_bank, prs)
        packets = ordered_packets(report)
        # Initial hardware profile is deliberately restricted to observed FF
        # storage. Identical numeric banks alone do not certify parameter import.
        if confirmed_bank != b'\xff' * 65536:
            raise ValueError('PRS rehearsal currently supports unchanged all-FF FIR banks only')
        mutations = bool(report['packets'])
        self.TOTAL = 2 + 32 + 1261 + (24 + len(packets) + 32 * 3 + 1261 if mutations else 0) + 2
        catalog = self.exchange(frame(0x22, b''), 0x22, 'Checking preset catalog')
        active = self.exchange(frame(0x14, b''), 0x14, 'Checking active slot')
        if len(catalog) != 19 or len(active) != 1 or not 1 <= active[0] <= 19:
            raise ValueError('PRS catalog/active slot differs')
        current = self.state('Reading current parameters')
        if current != confirmed_state:
            raise ValueError('Current parameters changed after review; no mutation')
        bank = self.bank('Reading complete current FIR')
        if bank != confirmed_bank:
            raise ValueError('Current FIR changed after review; no mutation')
        expected = current[:2] + prs[BODY_START:FIR_START]
        self.record({'kind': 'prs_rehearsal_baseline', 'state_hex': current.hex(),
                     'bank_hex': bank.hex(), 'catalog_hex': catalog.hex(), 'active_slot': active[0],
                     'prs_sha256': hashlib.sha256(prs).hexdigest(), 'hardware_enabled': False})
        if mutations:
            # Recording intent must succeed BEFORE each mutation, including Mute.
            def send(op, payload, path):
                raw = frame(op, payload)
                self.record({'kind': 'setter_intent', 'operation': 'prs_rehearsal',
                             'path': path, 'frame_hex': raw.hex(), 'hardware_enabled': False})
                reply = active + payload if op == 0x26 else None
                self.exchange(raw, 1, path, expected_payload=reply)
            for ch in range(12):
                send(0x35, bytes((ch, 1)), 'Temporarily muting channel ' + str(ch))
            if self.state('Checking all channels muted') != muted(current):
                raise ValueError('Mute readback differs; no parameter import')
            for op, payload, path in packets:
                send(op, payload, path)
            if self.state('Verifying parameters before unmute') != muted(expected):
                raise ValueError('PRS parameter readback differs; channels remain muted')
            if self.bank('Verifying unchanged FIR before unmute') != bank:
                raise ValueError('FIR changed during parameter import; channels remain muted')
            # Target masks, not pre-import masks; matches manufacturer final35.
            for ch in range(12):
                offset, bit = (1432, ch) if ch < 4 else (1434, ch - 4)
                flag = (int.from_bytes(expected[offset:offset + 2], 'little') >> bit) & 1
                send(0x35, bytes((ch, flag)), 'Applying target Mute channel ' + str(ch))
            if self.state('Checking final parameters') != expected:
                raise ValueError('Final PRS state differs; no automatic restore')
        if self.exchange(frame(0x22, b''), 0x22, 'Checking unchanged catalog') != catalog:
            raise ValueError('PRS catalog changed')
        if self.exchange(frame(0x14, b''), 0x14, 'Checking unchanged active slot') != active:
            raise ValueError('PRS active slot changed')
        result = {'operation': 'prs_rehearsal', 'hardware_enabled': False,
                  'parameters_verified': True, 'fir_bank_unchanged': True,
                  'state_sha256': hashlib.sha256(expected).hexdigest(),
                  'audio_verified': False, 'power_cycle_persistence_verified': False,
                  'done': self.done, 'total': self.TOTAL}
        self.record({'kind': 'prs_rehearsal_verified', **result})
        self.progress({'busy': False, 'stage': 'Offline rehearsal complete', **result})
        return expected, result
