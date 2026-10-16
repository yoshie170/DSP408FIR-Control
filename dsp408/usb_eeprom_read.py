"""Manual P02 EEPROM read; no staging or parameter setters."""
import time
from pathlib import Path
from threading import Event
from uuid import uuid4
from PySide6.QtCore import QThread, Signal
from dsp408.wire_research import decode_editor_frame
from dsp408.usb_read import run_read_session, read_bus_frame, validate_read_request
from dsp408.usb_fir_read import HidFirReadPort
from dsp408.usb_journal import DurableJournal
from dsp408.eeprom_preset import EepromPresetReview, READ_BLOCKS, CERTIFICATE_KEYS

# Diagnostic profile: P02 EEPROM19, addresses1605..3160 only.
EEPROM_READ_AUTHORIZED = True
BLOCK_REASON = 'P02 EEPROM read is disabled by the permission profile'
from dsp408.app_paths import JOURNAL_DIRECTORY


def validate_eeprom_read_request(raw):
    """Exact frame scope; not an authorization to open a device."""
    packet = decode_editor_frame(raw)
    if packet.command != 0x19:
        return validate_read_request(raw)
    if (packet.address_bytes != b'\0\1' or len(packet.data) != 3
            or (int.from_bytes(packet.data[:2], 'little'), packet.data[2]) not in READ_BLOCKS):
        raise ValueError('EEPROM read permits only the 32 exact P02 address/count pairs')
    return packet


class HidEepromReadPort(HidFirReadPort):
    validate_request = staticmethod(validate_eeprom_read_request)

    def open(self):
        if not EEPROM_READ_AUTHORIZED:
            raise ValueError(BLOCK_REASON)
        super().open()

    def write(self, raw):
        if not EEPROM_READ_AUTHORIZED:
            raise ValueError(BLOCK_REASON)
        super().write(raw)


class EepromReadService:
    def __init__(self, port, stop, *, record, status, log, configuration, preset_metadata, snapshot,
                 clock=time.monotonic):
        self.port = port; self.stop = stop; self.record = record; self.status = status; self.log = log
        self.configuration = configuration; self.preset_metadata = preset_metadata
        self.snapshot = snapshot; self.clock = clock
        self.metadata = None; self.review = None; self.done = False

    def observe_metadata(self, metadata):
        self.metadata = metadata
        self.preset_metadata(metadata)

    def observe_configuration(self, state):
        self.review = EepromPresetReview(state, self.metadata or {})
        self.configuration(state)

    def observe_frame(self, direction, raw):
        if direction == 'rx':
            packet = decode_editor_frame(raw)
            if packet.command == 0x24:
                body = packet.data
                if not body or body[0] > 31 or len(body) != (7 if body[0] == 31 else 51):
                    raise ValueError('Current-state block size differs from MCU50/6')
        self.log(direction, raw)

    def dispatch(self):
        if self.done or self.review is None:
            return
        self.done = True
        review = self.review
        while not review.complete:
            if self.stop.is_set():
                raise InterruptedError('P02 EEPROM read cancelled before the next request')
            raw = review.proposal
            self.status(f'USB P02 EEPROM · {review.phase} · {review.position}/{len(review.steps)}')
            validate_eeprom_read_request(raw)
            self.port.write(raw); self.log('tx', raw); review.feed('tx', raw)
            deadline = self.clock()+2.
            while True:
                if self.stop.is_set():
                    raise InterruptedError('P02 EEPROM read cancelled while waiting')
                if self.clock() >= deadline:
                    raise TimeoutError('P02 EEPROM response timeout · '+review.phase)
                report = self.port.read(100)
                if not report:
                    continue
                packet = read_bus_frame(report); self.observe_frame('rx', packet.raw)
                if review.feed('rx', packet.raw):
                    break
        result = review.result()
        self.record({'kind': 'eeprom_preview_complete', **{k: result[k] for k in CERTIFICATE_KEYS}})
        self.snapshot(result)
        self.status('USB P02 EEPROM read complete · current parameters, active slot and catalog unchanged')


class UsbEepromReadWorker(QThread):
    status = Signal(str); configuration = Signal(bytes); presetMetadata = Signal(object)
    telemetry = Signal(object); frameObserved = Signal(str, bytes); failed = Signal(str)
    snapshot = Signal(object); journalPath = Signal(str)

    def __init__(self, parent=None, *, port_factory=HidEepromReadPort):
        super().__init__(parent)
        self.stop_event = Event(); self.port_factory = port_factory

    def stop(self):
        self.stop_event.set()

    def run(self):
        journal = None
        try:
            if self.port_factory is HidEepromReadPort and not EEPROM_READ_AUTHORIZED:
                raise ValueError(BLOCK_REASON)
            JOURNAL_DIRECTORY.mkdir(parents=True, exist_ok=True)
            path = JOURNAL_DIRECTORY/('app-eeprom-read-P02-'+time.strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:8]+'.ndjson')
            journal = DurableJournal(path, sync_each=False)
            self.journalPath.emit(str(path))
            journal.record({'kind': 'session_started', 'scope': 'P02 EEPROM19 parameter read; captured startup; no staging or setters'})
            port = self.port_factory(journal.record, self.stop_event)
            service = EepromReadService(port, self.stop_event, record=journal.record, status=self.status.emit,
                                        log=self.frameObserved.emit, configuration=self.configuration.emit,
                                        preset_metadata=self.presetMetadata.emit, snapshot=self.snapshot.emit)
            run_read_session(port, self.stop_event, status=self.status.emit, configuration=service.observe_configuration,
                             preset_metadata=service.observe_metadata, telemetry=self.telemetry.emit, log=service.observe_frame,
                             strict_startup=True, request_validator=validate_eeprom_read_request, between_polls=service.dispatch)
            journal.record({'kind': 'session_finished', 'error': None, 'cancelled': self.stop_event.is_set()})
        except Exception as error:
            self.failed.emit(str(error))
            if journal is not None:
                try: journal.record({'kind': 'session_finished', 'error': str(error)})
                except OSError: pass
        finally:
            if journal is not None:
                journal.close()
