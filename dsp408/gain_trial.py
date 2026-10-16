"""Original isolated CLI IN A 0/-1/0 trial, separate from normal USB read.

The later explicit app gain mode reuses constants and baseline validation,
not this one-shot routine or its transport policy.

Only two exact, captured setters are permitted, once each and in order. A fresh
correlated snapshot is required to arm either. Fake ports exercise this routine
offline; successful simulation is not hardware verification or authorization.
"""
import hashlib
import time
from threading import Event

from dsp408.editor_state_research import StateBlockAssembler, decode_state
from dsp408.gain_readback_review import compare_gain_readbacks
from dsp408.source_codec import frame
from dsp408.startup_research import StartupReview
from dsp408.usb_read import HidReadPort, IDENTITY, read_bus_frame, validate_read_request


BASELINE_SHA256 = '04249c3bdaaf389a68ad579e1f29a82b2c0405207880627a6e084c37b851abed'
MINUS1 = bytes.fromhex('100200010434000e0110033f')
RESTORE0 = bytes.fromhex('100200010434001801100329')


def validate_baseline(state):
    state = bytes(state)
    decoded = decode_state(state, layout='common-prefix1556')
    if decoded['channels'][0]['gain_raw'] != 280:
        raise ValueError('IN A baseline must be raw280 / 0.0 dB')
    for channel in decoded['channels']:
        index = channel['channel_index']
        if channel['link_mask_raw'] != 1 << (index if index < 4 else index - 4):
            raise ValueError('Independent self-only raw Link masks required on all channels')
    if hashlib.sha256(state).hexdigest() != BASELINE_SHA256:
        raise ValueError('Fresh baseline differs from the exact verified stage28 configuration')
    return state


def expected_minus1(baseline):
    result = bytearray(validate_baseline(baseline))
    result[146:148] = (270).to_bytes(2, 'little')
    return bytes(result)


class TrialPolicy:
    """One-shot arming, separate from the unchanged ordinary read allowlist."""
    def __init__(self):
        self.baseline = None
        self.step = 0
        self.armed = None

    def arm(self, state):
        if self.armed is not None:
            raise ValueError('Trial already armed; no duplicate setters')
        if self.step == 0:
            self.baseline = validate_baseline(state)
            self.armed = MINUS1
        elif self.step == 1 and bytes(state) == expected_minus1(self.baseline):
            self.armed = RESTORE0
        else:
            raise ValueError('Restore requires exact minus1 readback; trial cannot be reused')

    def validate(self, raw):
        raw = bytes(raw)
        if raw in (MINUS1, RESTORE0):
            if raw != self.armed:
                raise ValueError('Setter not armed for this exact one-shot trial stage')
            # Consume BEFORE I/O: a short/failed write must not be retried.
            self.armed = None
            self.step += 1
            return
        validate_read_request(raw)


class HidGainTrialPort(HidReadPort):
    """Explicit separate adapter, never selected by ordinary Connect USB."""
    def __init__(self):
        super().__init__()
        self.policy = TrialPolicy()

    def arm(self, state):
        self.policy.arm(state)

    def write(self, raw):
        self.policy.validate(raw)
        report = b'\0' + bytes(raw) + bytes(64 - len(raw))
        if self.device.write(report) != 65:
            raise OSError('Incomplete USB output report; setter will not be retried')


class GainTrialError(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(report['error'])


def run_gain_trial(port, *, authorized=False, record, stop=None, clock=time.monotonic):
    """Blocking explicit trial; record must durably save each event before return.

    No retries/reconnects, no automatic restoration after a failure. At most two
    setters. Any failure closes HID without further TX (including session close).
    Readback equality covers only 1556 bytes, not audio/globals/active FIR/EEPROM.
    """
    if authorized is not True:
        raise PermissionError('Separate explicit consent for our isolated gain trial required')
    stop = stop if stop is not None else Event()
    policy = TrialPolicy()
    report = {'scope': 'Isolated IN A 0/-1/0 trial; common-prefix1556 only',
              'hardware_write_unlock_allowed': False, 'status': 'not_started',
              'setter_attempts': 0, 'setter_transmissions_completed': 0,
              'restore_verified': False, 'snapshots': {}, 'error': None}

    def check_stop():
        if stop.is_set():
            raise InterruptedError('Gain trial cancelled; no further commands')

    def send(raw):
        check_stop()
        policy.validate(raw)
        record({'kind': 'tx_intent', 'frame_hex': raw.hex()})
        check_stop()  # Cancellation may arrive while the journal is flushed.
        if raw in (MINUS1, RESTORE0):
            report['setter_attempts'] += 1
        port.write(raw)
        if raw in (MINUS1, RESTORE0):
            report['setter_transmissions_completed'] += 1
        record({'kind': 'tx_completed', 'frame_hex': raw.hex()})

    def receive():
        check_stop()
        payload = port.read(100)
        if not payload:
            return None
        # Preserve malformed input too; validation failures must remain reviewable.
        record({'kind': 'rx_report', 'report_hex': bytes(payload).hex()})
        return read_bus_frame(payload)

    def wait_packet(seconds=2.0):
        deadline = clock() + seconds
        while clock() < deadline:
            packet = receive()
            if packet is not None:
                return packet
        raise TimeoutError('Gain trial response timeout; no retransmission')

    def snapshot(label, data):
        state = bytes(data)
        report['snapshots'][label] = {'state_hex': state.hex(),
                                     'sha256': hashlib.sha256(state).hexdigest()}
        record({'kind': 'snapshot', 'label': label, **report['snapshots'][label]})
        return state

    def read_configuration(label):
        collection = StateBlockAssembler(layout='common-prefix1556')
        for index in range(32):
            send(frame(0x27, bytes((index,))))
            packet = wait_packet()
            if packet.command != 0x24 or not packet.data or packet.data[0] != index:
                raise ValueError('Unexpected or uncorrelated configuration response')
            collection.add(packet.data)
        return snapshot(label, collection.data())

    def gain(state, raw):
        # Two independent guards: routine and physical adapter.
        policy.arm(state)
        port.arm(state)
        send(raw)
        packet = wait_packet()
        if packet.command != 1 or packet.data:
            raise ValueError('Expected sampled empty RX01 after gain; effect remains unverified')
        record({'kind': 'empty_rx01_observed', 'effect_verified': False})

    def quiet_boundary():
        # TX12's empty RX01 was seen in the vendor capture, but not in every app
        # read. Do not require/invent it or confuse it with a gain response.
        deadline = clock() + 2.0
        count = 0
        while clock() < deadline:
            packet = receive()
            if packet is None:
                record({'kind': 'quiet_read_boundary', 'optional_empty_rx01': count})
                return
            if packet.command != 1 or packet.data or count:
                raise ValueError('Unexpected response at pre-write boundary')
            count += 1
        raise TimeoutError('No quiet pre-write boundary')

    try:
        record({'kind': 'trial_started', 'expected_identity_hex': IDENTITY.hex(),
                'expected_baseline_sha256': BASELINE_SHA256,
                'setter_frames_hex': [MINUS1.hex(), RESTORE0.hex()],
                'hardware_write_unlock_allowed': False})
        check_stop()
        port.open()
        report['status'] = 'startup'
        review = StartupReview(transport='usb', layout='common-prefix1556', device_address=1)
        while review.phase != 'complete_candidate':
            if review.phase in ('blocked', 'failed', 'rejected') or review.proposal is None:
                raise ValueError('Trial startup stopped: ' + review.phase)
            send(review.proposal)
            review.feed('tx', review.proposal)
            if review.phase == 'complete_candidate':
                break
            packet = wait_packet(5.0 if review.phase == 'identity' else 2.0)
            if packet.command != review.response:
                raise ValueError('Unexpected response during trial startup')
            if packet.command == 0x10 and packet.data != b'\x33':
                raise ValueError('Hello differs from exact-device capture')
            if packet.command == 0x13 and packet.data != IDENTITY:
                raise ValueError('Firmware identity differs from captured FIR408 V0115P')
            review.feed('rx', packet.raw)
        baseline = snapshot('startup_baseline', review.trace.configuration.data())
        validate_baseline(baseline)
        quiet_boundary()
        # This same-handle refresh sequence is a new physical trial, not already
        # certified by the separate-session manufacturer readbacks in stage28.
        stable = read_configuration('stable_baseline')
        if stable != baseline:
            raise ValueError('Configuration changed before gain; refusing setter')
        quiet_boundary()
        report['status'] = 'minus1'
        gain(stable, MINUS1)
        minus1 = read_configuration('minus1')
        if minus1 != expected_minus1(baseline):
            raise ValueError('Minus1 full-prefix mismatch; refusing automatic restore')
        quiet_boundary()
        report['status'] = 'restore0'
        gain(minus1, RESTORE0)
        restored = read_configuration('restored')
        comparison = compare_gain_readbacks(baseline, minus1, restored)
        report['comparison'] = comparison
        if not comparison['sample_readback_checks_match']:
            raise ValueError('Restored prefix differs from baseline')
        report['restore_verified'] = True
        quiet_boundary()
        send(frame(0x11, b''))
        report['status'] = 'completed_prefix_verified'
    except (Exception, KeyboardInterrupt) as error:
        report['status'] = 'aborted'
        report['error'] = str(error) or type(error).__name__
    finally:
        try:
            port.close()
        except Exception as error:
            report['status'] = 'aborted'
            report['error'] = (report['error'] or '') + ' HID close failed: ' + str(error)
    report['manual_recovery_required'] = report['setter_attempts'] > 0 and not report['restore_verified']
    try:
        record({'kind': 'trial_finished', 'report': report})
    except Exception as error:
        report['status'] = 'aborted'
        report['error'] = (report['error'] or '') + ' Journal write failed: ' + str(error)
    if report['status'] != 'completed_prefix_verified':
        raise GainTrialError(report)
    return report
