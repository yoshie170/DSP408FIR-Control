"""Explicit app mode: only captured IN A -1/0 dB with complete readback.

No generic dispatcher, queue of arbitrary frames, gain range extension, linked
channels or optimistic model changes. Normal read adapter stays read-only.
"""
import math
from pathlib import Path
from queue import Queue, Empty
from threading import Event, Lock
import time
from uuid import uuid4

from PySide6.QtCore import QThread, Signal
from dsp408.gain_trial import BASELINE_SHA256, MINUS1, RESTORE0, validate_baseline
from dsp408.editor_state_research import StateBlockAssembler
from dsp408.source_codec import frame
from dsp408.usb_journal import DurableJournal
from dsp408.usb_read import HidReadPort, read_bus_frame, run_read_session, validate_read_request


def verified_state(state):
    """Recognize only the two exact observed prefixes, including self Link masks."""
    state = bytes(state)
    if len(state) != 1556 or int.from_bytes(state[146:148], 'little') not in (270, 280):
        raise ValueError('Only verified IN A -1.0 / 0.0 dB prefixes are writable')
    baseline = bytearray(state)
    baseline[146:148] = (280).to_bytes(2, 'little')
    validate_baseline(baseline)
    return state


def target_frame(gain):
    if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not math.isfinite(gain) or gain not in (-1, 0):
        raise ValueError('Hardware gain permits only IN A -1.0 or 0.0 dB')
    return MINUS1 if gain == -1 else RESTORE0


class GainPolicy:
    def __init__(self): self.armed = None

    def arm(self, state, gain):
        verified_state(state)
        if self.armed is not None: raise ValueError('Previous gain still armed')
        self.armed = target_frame(gain)

    def validate(self, raw):
        if raw in (MINUS1, RESTORE0):
            if raw != self.armed: raise ValueError('IN A gain write requires a fresh verified readback')
            self.armed = None  # Consume before I/O; no retries even on failure.
        else:
            validate_read_request(raw)


class HidGainControlPort(HidReadPort):
    def __init__(self, record, stop):
        super().__init__()
        self.policy = GainPolicy()
        self.record, self.stop_event = record, stop

    def arm_gain(self, state, gain): self.policy.arm(state, gain)

    def write(self, raw):
        self.policy.validate(bytes(raw))
        self.record({'kind': 'tx_intent', 'frame_hex': bytes(raw).hex()})
        # Normal session close after the user's Stop is still permitted. Gain
        # always checks cancellation after the durable intent flush as well.
        if raw in (MINUS1, RESTORE0) and self.stop_event.is_set():
            raise InterruptedError('Gain cancelled before transmission')
        report = b'\0' + bytes(raw) + bytes(64-len(raw))
        if self.device.write(report) != 65:
            raise OSError('Incomplete USB output report; no retransmission')
        self.record({'kind': 'tx_completed', 'frame_hex': bytes(raw).hex()})

    def read(self, timeout_ms):
        raw = super().read(timeout_ms)
        if raw: self.record({'kind': 'rx_report', 'report_hex': raw.hex()})
        return raw


class GainService:
    """Runs only in the USB thread between completed telemetry polls."""
    def __init__(self, port, stop, *, record, configuration, availability, busy, status, log, clock=time.monotonic):
        self.port, self.stop = port, stop
        self.record, self.configuration, self.availability = record, configuration, availability
        self.busy, self.status, self.log, self.clock = busy, status, log, clock
        self.queue, self.lock = Queue(maxsize=1), Lock()
        self.pending = False
        self.ready = False

    def observe_configuration(self, state):
        self.configuration(bytes(state))
        try: verified_state(state)
        except ValueError: self.ready = False
        else: self.ready = True
        self.availability(self.ready)

    def request(self, gain):
        target_frame(gain)
        with self.lock:
            if self.stop.is_set() or not self.ready or self.pending: return False
            self.pending = True
            self.queue.put_nowait(gain)
        return True

    def check_stop(self):
        if self.stop.is_set(): raise InterruptedError('USB gain operation cancelled')

    def send_read(self, raw):
        self.check_stop()
        validate_read_request(raw)
        self.port.write(raw)
        self.log('tx', raw)

    def receive(self):
        self.check_stop()
        raw = self.port.read(100)
        if not raw: return None
        packet = read_bus_frame(raw)
        self.log('rx', packet.raw)
        return packet

    def wait_packet(self):
        deadline = self.clock() + 2.
        while self.clock() < deadline:
            packet = self.receive()
            if packet is not None: return packet
        raise TimeoutError('USB gain readback timeout; no retry')

    def quiet(self):
        deadline, empty = self.clock() + 2., 0
        while self.clock() < deadline:
            packet = self.receive()
            if packet is None: return
            if packet.command != 1 or packet.data or empty:
                raise ValueError('Unexpected USB response at gain boundary')
            empty += 1
        raise TimeoutError('No quiet gain boundary')

    def read_state(self, label):
        collection = StateBlockAssembler(layout='common-prefix1556')
        for index in range(32):
            self.send_read(frame(0x27, bytes((index,))))
            packet = self.wait_packet()
            if packet.command != 0x24 or not packet.data or packet.data[0] != index:
                raise ValueError('Uncorrelated USB gain configuration response')
            collection.add(packet.data)
        state = collection.data()
        self.record({'kind': 'gain_snapshot', 'label': label, 'state_hex': state.hex()})
        return state

    def dispatch(self):
        try: gain = self.queue.get_nowait()
        except Empty: return
        attempted = False
        self.busy(True)
        self.status('USB · checking fresh IN A gain baseline')
        try:
            self.quiet()
            before = verified_state(self.read_state('before'))
            self.observe_configuration(before)
            raw = target_frame(gain)
            if before[146:148] != raw[7:9]:
                expected = bytearray(before)
                expected[146:148] = raw[7:9]
                self.quiet()
                self.check_stop()
                self.port.arm_gain(before, gain)
                self.record({'kind': 'gain_requested', 'gain_db': gain})
                self.check_stop()
                attempted = True
                self.port.write(raw)
                self.log('tx', raw)
                packet = self.wait_packet()
                if packet.command != 1 or packet.data:
                    raise ValueError('Gain response differs from sampled empty01')
                after = self.read_state('after')
                if after != bytes(expected):
                    raise ValueError('Full gain readback differs from expected1556-byte prefix')
                self.observe_configuration(after)
                attempted = False  # The requested value is now confirmed.
                self.quiet()
            self.record({'kind': 'gain_confirmed', 'gain_db': gain})
            self.status(f'USB · IN A {gain:.1f} dB confirmed by full readback')
        except Exception as error:
            self.ready = False
            self.availability(False)
            message = ('IN A write state unconfirmed; check IN A in the original editor after disconnect. '
                       if attempted else 'USB gain operation stopped. ')
            try: self.record({'kind': 'gain_failed', 'error': str(error), 'state_unconfirmed': attempted})
            except OSError: pass
            raise RuntimeError(message + str(error)) from error
        finally:
            with self.lock: self.pending = False
            self.busy(False)


class UsbGainWorker(QThread):
    status = Signal(str)
    configuration = Signal(bytes)
    presetMetadata = Signal(object)
    telemetry = Signal(object)
    frameObserved = Signal(str, bytes)
    failed = Signal(str)
    gainAvailable = Signal(bool)
    gainBusy = Signal(bool)
    journalPath = Signal(str)

    def __init__(self, parent=None, *, port_factory=HidGainControlPort, journal_factory=DurableJournal):
        super().__init__(parent)
        self.stop_event = Event()
        self.port_factory, self.journal_factory = port_factory, journal_factory
        self.service = None

    def stop(self): self.stop_event.set()

    def request_gain(self, gain):
        return self.service is not None and self.service.request(gain)

    def run(self):
        journal = None
        try:
            from dsp408.app_paths import JOURNAL_DIRECTORY
            directory = JOURNAL_DIRECTORY
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / ('app-in-a-gain-' + time.strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8] + '.ndjson')
            journal = self.journal_factory(path)
            journal.record({'kind': 'session_started', 'scope': 'App USB, only explicit IN A -1/0 dB requests',
                            'expected_baseline_sha256': BASELINE_SHA256})
            self.journalPath.emit(str(path))
            port = self.port_factory(journal.record, self.stop_event)
            self.service = GainService(port, self.stop_event, record=journal.record,
                                       configuration=self.configuration.emit, availability=self.gainAvailable.emit,
                                       busy=self.gainBusy.emit, status=self.status.emit, log=self.frameObserved.emit)
            run_read_session(port, self.stop_event, status=self.status.emit,
                             configuration=self.service.observe_configuration,
                             telemetry=self.telemetry.emit, log=self.frameObserved.emit,
                             preset_metadata=self.presetMetadata.emit, between_polls=self.service.dispatch,
                             strict_startup=True)
            journal.record({'kind': 'session_finished', 'error': None})
        except Exception as error:
            self.gainAvailable.emit(False)
            self.failed.emit(str(error))
            if journal is not None:
                try: journal.record({'kind': 'session_finished', 'error': str(error)})
                except OSError: pass
        finally:
            if journal is not None: journal.close()
