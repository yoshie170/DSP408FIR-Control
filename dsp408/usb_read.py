"""Explicit USB session: captured startup and telemetry only. No parameter API.

Device access occurs only in run_read_session after the user's Connect action.
The pure validator also guards every byte handed to the HID writer.
"""
import sys
import time
from threading import Event

from PySide6.QtCore import QThread, Signal
from dsp408.source_codec import frame
from dsp408.startup_research import StartupReview
from dsp408.wire_research import decode_editor_frame
from dsp408.editor_rx_research import decode_telemetry_payload

VID, PID = 0x0168, 0x0821
IDENTITY = b'FIR408 V0115P'
CAPTURED_FIR_BLOCKS = (0, 157, 315, 472, 630, 708, 787, 866, 945, 1024, 1102, 1181)


def validate_read_request(raw):
    packet = decode_editor_frame(raw)
    if packet.address_bytes != b'\0\1':
        raise ValueError('USB read profile permits only captured device address1')
    op, payload = packet.command, packet.data
    empty = (0x10, 0x11, 0x12, 0x13, 0x2C, 0x22, 0x14, 0x40)
    valid = (op in empty and not payload or
             op == 0x29 and len(payload) == 1 and payload[0] <= 18 or
             op == 0x27 and len(payload) == 1 and payload[0] <= 31 or
             op == 0x56 and len(payload) == 3 and payload[0] == 0 and
             int.from_bytes(payload[1:], 'little') in CAPTURED_FIR_BLOCKS)
    if not valid: raise ValueError('Command/values outside exact captured USB read profile')
    return packet


def read_bus_frame(payload):
    payload = bytes(payload)
    if len(payload) != 64: raise ValueError('Expected64-byte unnumbered HIDAPI input report')
    packet = decode_editor_frame(payload[:payload[4] + 8])
    if packet.address_bytes != b'\1\0': raise ValueError('Unexpected USB response address')
    return packet


class HidReadPort:
    """HIDAPI uses ID00 on write; strips it from unnumbered Windows reads."""
    def __init__(self): self.device = None;self.target_id=1;self.startup_fir=None

    def begin_fir_startup(self,*,source_display=False):
        from dsp408.usb_control_startup import StartupFirWindow,SourceStartupFirWindow
        if type(source_display) is not bool:raise ValueError('Explicit FIR strategy required')
        if self.startup_fir is not None:raise ValueError('USB startup window already open')
        self.startup_fir=SourceStartupFirWindow() if source_display else StartupFirWindow()
    def arm_fir_startup(self,raw):
        if self.startup_fir is None:raise ValueError('No USB startup FIR window')
        self.startup_fir.arm(raw)
    def observe_fir_startup(self,raw):
        if self.startup_fir is None:raise ValueError('No USB startup FIR window')
        self.startup_fir.observe(raw)
    def complete_fir_startup(self):
        if self.startup_fir is None:raise ValueError('No USB startup FIR window')
        self.startup_fir.complete();self.startup_fir=None
    def end_fir_startup(self):self.startup_fir=None

    def open(self):
        if sys.platform != 'win32': raise OSError('This captured USB profile is Windows only')
        try: import hid
        except ImportError as e:
            raise OSError('Install USB support: .\\.venv\\Scripts\\python.exe -m pip install -r requirements-usb.txt') from e
        candidates = [d for d in hid.enumerate(VID, PID)
                      if d.get('vendor_id') == VID and d.get('product_id') == PID]
        if not candidates: raise OSError('FIR DSP408 USB not found. Power on and connect USB; close the original editor.')
        if len(candidates) != 1: raise OSError('Multiple matching HID interfaces/devices; disconnect other DSP units before connecting')
        self.device = hid.device()
        try: self.device.open_path(candidates[0]['path'])
        except Exception:
            self.close(); raise
        from dsp408.device_address import AddressedHid
        self.device=AddressedHid(self.device,self.target_id,getattr(self,'record',lambda _:None))

    def write(self, raw):
        if self.startup_fir is not None and len(raw)>5 and raw[5]==0x56:self.startup_fir.consume(raw)
        else:validate_read_request(raw)
        report = b'\0' + bytes(raw) + bytes(64 - len(raw))
        if self.device.write(report) != 65: raise OSError('Incomplete USB output report')

    def read(self, timeout_ms): return bytes(self.device.read(64, timeout_ms))

    def close(self):
        if self.device is not None:
            try: self.device.close()
            finally: self.device = None


def run_read_session(port, stop, *, status, configuration, telemetry, log,
                     clock=time.monotonic, max_seconds=None, preset_metadata=None,
                     between_polls=None, strict_startup=False, idle_read_ms=100,
                     full_fir=False, request_validator=validate_read_request, fir_bank=None,system_status=None,
                     poll_interval=.3, poll_from_request=False, locked_startup=None,
                     fir_preview=None,startup_fir_reply=None):
    """Blocking worker routine; fake ports/clocks run the same path in tests.

    Fail closed on timeout/mismatch. No retries, discovery commands or write
    parameters in the default read profile. An explicit separate control worker
    can supply a service at idle poll boundaries; ordinary Connect never does.
    Firmware identity must match before post-identity reads.
    """
    def interval():
        value=poll_interval() if callable(poll_interval) else poll_interval
        if value not in (.1,.3):raise ValueError('Meter polling must be 100 or 300 ms')
        return value
    interval()  # Reject unsupported local policy before opening any port.
    started = False; recognized = False; healthy = True
    review = StartupReview(transport='usb', layout='common-prefix1556', device_address=1,full_fir=full_fir)
    start = clock()

    def send(raw):
        nonlocal started
        request_validator(raw)
        port.write(raw); started = True; log('tx', bytes(raw))

    def receive(timeout=100):
        payload = port.read(timeout)
        if not payload: return None
        packet = read_bus_frame(payload); log('rx', packet.raw); return packet

    try:
        if stop.is_set(): return
        status('Opening USB HID'); port.open()
        if stop.is_set(): return
        while review.phase != 'complete_candidate' and not stop.is_set():
            if max_seconds is not None and clock() - start >= max_seconds: return
            if review.phase in ('blocked', 'failed', 'rejected'):
                raise ValueError('Device stopped synchronization: ' + str(review.notes))
            raw = review.proposal
            if raw is None: raise ValueError('Missing validated startup request')
            if full_fir and review.phase=='fir':
                block=int.from_bytes(decode_editor_frame(raw).data[1:],'little')
                if block%32==0 or block==1260:status(f'USB FIR raw read · {block}/1261 blocks · {block*100/1261:.0f}%')
            else:status('USB synchronization · ' + review.phase)
            if stop.is_set(): return
            # Captured hello is not side-effect-free: it initializes the session.
            # The Connect button is the explicit user action authorizing it.
            send(raw); review.feed('tx', raw)
            if review.phase == 'complete_candidate': break
            deadline = clock() + (5.0 if review.phase == 'identity' else 2.0)
            while not stop.is_set():
                if clock() >= deadline: raise TimeoutError('USB response timeout during ' + review.phase)
                packet = receive()
                if packet is None: continue
                if strict_startup:
                    if packet.command != review.response and not (packet.command == 1 and not packet.data):
                        raise ValueError('Unexpected response during guarded USB startup')
                    if packet.command == 0x10 and packet.data != b'\x33':
                        raise ValueError('USB hello differs from exact capture')
                if review.phase == 'identity' and packet.command == 0x13:
                    if packet.data != IDENTITY: raise ValueError('USB firmware identity differs from captured FIR408 V0115P')
                    recognized = True
                event = review.feed('rx', packet.raw)
                if packet.command==0x56 and startup_fir_reply is not None:
                    startup_fir_reply(packet.raw)
                if system_status is not None and packet.command==0x2C and event.get('advanced'):
                    system_status(packet.data)
                if review.phase == 'blocked':
                    if fir_preview is not None and review.fir_boundary_error:
                        review.restart_full_fir_after_boundary()
                        status('USB synchronization · reading complete FIR bank')
                        break
                    from dsp408.device_utilities import system_lock
                    if (locked_startup is None or packet.command!=0x2C
                            or not system_lock(packet.data) or packet.data[5]!=1):
                        raise ValueError('Device requires an unsupported modal operation')
                    authenticated_status=locked_startup(packet.data)
                    if not authenticated_status:return
                    review.resume_authenticated_system(authenticated_status,accepted=True)
                    break
                if event.get('advanced'): break
        if stop.is_set(): return
        if preset_metadata is not None:
            preset_metadata({'active_slot_raw':review.active_slot_raw,
                             'names_raw_hex':dict(review.names),
                             'catalog_markers':list(review.trace.latest_preset_catalog.marker_bytes)})
        configuration(bytes(review.trace.configuration.data()))
        if fir_bank is not None and not review.trace.fir_area.missing_blocks:
            fir_bank(review.trace.fir_area.data())
        elif fir_preview is not None:
            from dsp408.fir_read_preview import input_preview
            if review.fir_bootstrap is None or not review.fir_bootstrap.complete:raise ValueError('Incomplete source FIR preview')
            fir_preview(input_preview(review.trace.configuration.data(),review.trace.fir_area,review.fir_bootstrap))
        status('USB · read connected · FIR408 V0115P')
        next_poll = clock(); deadline = None
        while not stop.is_set():
            if max_seconds is not None and clock() - start >= max_seconds: return
            now = clock()
            if deadline is None and between_polls is not None:
                between_polls()
                if stop.is_set(): return
                now = clock()
            if deadline is None and now >= next_poll:
                sent_at=now
                send(frame(0x40, b'')); deadline = now + 2.0
            # Wake for the next query rather than sleeping an extra full HID
            # read interval. Never overlap queries or catch up with a burst.
            wait_ms=100
            if deadline is None:
                wait_ms=max(1,min(idle_read_ms,int(max(0,next_poll-now)*1000))) if poll_from_request else idle_read_ms
            packet = receive(wait_ms)
            if packet is not None:
                if packet.command == 0x40:
                    if deadline is None: raise ValueError('Unrequested USB telemetry response')
                    if len(packet.data) != 42: raise ValueError('USB telemetry size differs from captured42-byte profile')
                    telemetry(decode_telemetry_payload(packet.data)); deadline = None
                    next_poll = max(clock(),sent_at+interval()) if poll_from_request else clock()+interval()
                elif packet.command != 1 or packet.data:
                    raise ValueError('Unexpected response after USB startup')
            if deadline is not None and clock() >= deadline: raise TimeoutError('USB telemetry response timeout')
    except Exception:
        healthy = False; raise
    finally:
        # Only normal user disconnect sends the captured session-close command.
        # On malformed traffic, wrong identity or device error, just close HID.
        try:
            if started and recognized and healthy: send(frame(0x11, b''))
        finally: port.close()


class UsbReadWorker(QThread):
    status = Signal(str)
    configuration = Signal(bytes)
    presetMetadata = Signal(object)
    telemetry = Signal(object)
    frameObserved = Signal(str, bytes)
    failed = Signal(str)
    firPreview=Signal(object);firBank=Signal(bytes)

    def __init__(self, parent=None, *, port_factory=HidReadPort,device_id=1):
        super().__init__(parent); self.stop_event = Event(); self.port_factory = port_factory
        from dsp408.device_address import checked_id
        self.device_id=checked_id(device_id)
        self.meter_poll_ms=300

    def set_meter_poll_ms(self,value):
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms.')
        self.meter_poll_ms=value

    def stop(self): self.stop_event.set()

    def run(self):
        try:
            port=self.port_factory()
            if isinstance(port,HidReadPort) or hasattr(port,'target_id'):port.target_id=self.device_id
            elif self.device_id!=1:raise ValueError('Custom transport does not implement physical DSP addressing')
            from dsp408.usb_control_startup import run_control_session
            run_control_session(port, self.stop_event,record=lambda _:None,fir_strategy='source-display',
                             fir_bank=self.firBank.emit,fir_preview=self.firPreview.emit,status=self.status.emit,
                             configuration=self.configuration.emit, telemetry=self.telemetry.emit,
                             log=self.frameObserved.emit, preset_metadata=self.presetMetadata.emit,
                             poll_interval=lambda:self.meter_poll_ms/1000)
        except Exception as e: self.failed.emit(str(e))
