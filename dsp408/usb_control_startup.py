"""Manual USB startup: manufacturer FIR display read or explicit complete bank.

Uses exact56 bank0/block0..1260 TX/RX captured in the real FIR trial.
No new setters or arbitrary read API; ordinary read/gain policies stay strict.
"""
import hashlib
from dsp408.usb_read import run_read_session, validate_read_request
from dsp408.usb_fir_read import validate_fir_read_request


class StartupFirWindow:
    def __init__(self): self.next_block=0; self.armed=None

    def arm(self, raw):
        packet=validate_fir_read_request(raw)
        if packet.command!=0x56 or self.armed is not None:
            raise ValueError('Startup FIR requires one current-bank request')
        if int.from_bytes(packet.data[1:],'little')!=self.next_block or self.next_block>=1261:
            raise ValueError('Startup FIR request is not the next block')
        self.armed=bytes(raw)

    def consume(self, raw):
        if self.armed is None or bytes(raw)!=self.armed:
            raise ValueError('Unarmed startup FIR request')
        self.armed=None; self.next_block+=1

    def complete(self):
        if self.armed is not None or self.next_block!=1261:
            raise ValueError('Startup FIR read is incomplete')


class SourceStartupFirWindow(StartupFirWindow):
    """A next request is permitted only after the actual prior RX56."""
    def __init__(self):
        super().__init__()
        from dsp408.fir_bootstrap_research import FirBootstrapReview
        self.bootstrap=FirBootstrapReview();self.waiting=None;self.received=set();self.fallback=False

    def arm(self,raw):
        if self.waiting is not None or self.next_block is None:
            raise ValueError('Source FIR requires its pending reply before the next request')
        super().arm(raw)

    def consume(self,raw):
        previous=self.next_block;super().consume(raw)
        self.waiting=previous;self.next_block=None

    def observe(self,raw):
        from dsp408.wire_research import decode_editor_frame
        from dsp408.editor_rx_research import decode_fir_read_payload
        from dsp408.fir_bootstrap_research import FirReconstructionBoundary
        packet=decode_editor_frame(raw);chunk=decode_fir_read_payload(packet.data)
        if (packet.address_bytes!=b'\1\0' or packet.command!=0x56 or self.waiting is None
                or chunk.selector_byte!=0 or chunk.block_index!=self.waiting
                or len(packet.data)!=(19 if self.waiting==1260 else 55)):
            raise ValueError('Source FIR reply differs from the pending request')
        index=self.waiting;self.received.add(index)
        if self.fallback:self.next_block=index+1 if index<1260 else None
        else:
            try:self.next_block=self.bootstrap.add(packet.data)
            except FirReconstructionBoundary:
                self.fallback=True
                if len(self.received)!=1261:self.next_block=0;self.received.clear()
        self.waiting=None

    def complete(self):
        if (self.armed is not None or self.waiting is not None or self.next_block is not None
                or not (len(self.received)==1261 if self.fallback else self.bootstrap.complete)):
            raise ValueError('Source FIR read is incomplete')


def run_control_session(port, stop, *, record, fir_bank, fir_preview=None,fir_strategy='full', **callbacks):
    """Same USB owner; firmware identity and correlated replies checked by runner."""
    if fir_strategy not in ('full','source-display'):raise ValueError('Unknown USB startup FIR strategy')
    source=fir_strategy=='source-display'
    if source and fir_preview is None:raise ValueError('Source startup requires a separate preview receiver')
    publish_configuration=callbacks.pop('configuration')
    def begin():
        if source:port.begin_fir_startup(source_display=True)
        else:port.begin_fir_startup()
    begin()
    authenticate=callbacks.pop('locked_startup',None)
    if authenticate is not None:
        def unlock_before_fir(payload):
            # Authentication occurs at SYSTEM, before any FIR block is armed.
            # Keep the utility and FIR capabilities mutually exclusive.
            port.end_fir_startup()
            accepted=False
            try:
                accepted=authenticate(payload)
                return accepted
            finally:
                if accepted and not stop.is_set():begin()
        callbacks['locked_startup']=unlock_before_fir
    received_state=[]
    def validate(raw):
        packet=validate_fir_read_request(raw)
        if packet.command==0x56:port.arm_fir_startup(raw)
        else:validate_read_request(raw)
        return packet
    def complete(bank):
        if len(received_state)!=1 or len(received_state[0])!=1556:
            raise ValueError('Control startup parameters are incomplete')
        port.complete_fir_startup()
        record({'kind':'control_startup_fir_complete','selector':0,'blocks':1261,
                'bytes':len(bank),'sha256':hashlib.sha256(bank).hexdigest(),
                'raw_hex':bank.hex(),'state_hex':received_state[0].hex(),
                'state_sha256':hashlib.sha256(received_state[0]).hexdigest()})
        fir_bank(bank)
        publish_configuration(received_state[0])
    def complete_preview(preview):
        if len(received_state)!=1 or len(received_state[0])!=1556:
            raise ValueError('Source startup parameters are incomplete')
        port.complete_fir_startup()
        state=received_state[0]
        record({'kind':'control_startup_fir_preview','selector':0,
                'state_hex':state.hex(),'state_sha256':hashlib.sha256(state).hexdigest(),
                'fir_preview':preview,'raw_bank_complete':False})
        fir_preview(preview);publish_configuration(state)
    try:
        run_read_session(port,stop,full_fir=not source,request_validator=validate,
                         fir_bank=complete,configuration=lambda raw:received_state.append(bytes(raw)),
                         fir_preview=complete_preview if source else None,
                         startup_fir_reply=port.observe_fir_startup if source else None,
                         strict_startup=True,**callbacks)
    finally:
        port.end_fir_startup()
