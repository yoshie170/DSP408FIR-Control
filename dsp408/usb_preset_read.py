"""Offline P02 research; physical staging blocked after the shared-RAM finding."""
import hashlib,time
from threading import Event
from uuid import uuid4
from PySide6.QtCore import QThread,Signal
from dsp408.wire_research import decode_editor_frame
from dsp408.usb_read import run_read_session,read_bus_frame
from dsp408.usb_fir_read import HidFirReadPort,validate_fir_read_request
from dsp408.usb_journal import DurableJournal
from dsp408.preset_preview import PresetPreviewReview,SLOT,LIVE_PREVIEW_BLOCK_REASON

from dsp408.app_paths import JOURNAL_DIRECTORY


def validate_preset_read_request(raw):
    """Offline historical frame scope only; this grants no physical permission."""
    p=decode_editor_frame(raw)
    if p.address_bytes!=b'\0\1':raise ValueError('Preset read requires address1')
    if p.command==0x24 and p.data==bytes((SLOT,)):return p
    if p.command==0x28 and len(p.data)==1 and p.data[0]<32:return p
    if p.command==0x56 and len(p.data)==3 and p.data[0]==SLOT and int.from_bytes(p.data[1:],'little')<=1260:return p
    return validate_fir_read_request(raw)


class HidPresetReadPort(HidFirReadPort):
    validate_request=staticmethod(validate_preset_read_request)
    def open(self):
        raise ValueError(LIVE_PREVIEW_BLOCK_REASON)
    def write(self,raw):
        raise ValueError(LIVE_PREVIEW_BLOCK_REASON)


class PresetReadService:
    def __init__(self,port,stop,*,record,status,log,configuration,preset_metadata,snapshot,clock=time.monotonic):
        self.port=port;self.stop=stop;self.record=record;self.status=status;self.log=log;self.configuration=configuration
        self.preset_metadata=preset_metadata;self.snapshot=snapshot;self.clock=clock
        self.metadata=None;self.review=None;self.done=False
    def observe_metadata(self,m):self.metadata=m;self.preset_metadata(m)
    def observe_configuration(self,state):
        self.review=PresetPreviewReview(state,self.metadata or {})
        self.configuration(state)
    def dispatch(self):
        if self.done or self.review is None:return
        self.done=True;r=self.review
        while not r.complete:
            if self.stop.is_set():raise InterruptedError('P02 preview cancelled before next request')
            raw=r.proposal
            if r.position%32==0:self.status(f'USB P02 preview · {r.phase} · {r.position}/{len(r.steps)}')
            validate_preset_read_request(raw);self.port.write(raw);self.log('tx',raw);r.feed('tx',raw)
            deadline=self.clock()+2.
            while True:
                if self.stop.is_set():raise InterruptedError('P02 preview cancelled while waiting')
                if self.clock()>=deadline:raise TimeoutError('P02 preview response timeout · '+r.phase)
                report=self.port.read(100)
                if not report:continue
                p=read_bus_frame(report);self.log('rx',p.raw)
                if r.feed('rx',p.raw):break
        result=r.result()
        self.record({'kind':'preset_preview_complete',**{k:result[k] for k in ('slot','state_sha256','fir_bank_sha256',
            'current_before_sha256','current_after_sha256','active_slot_before','active_slot_after')}})
        self.snapshot(result);self.status('USB P02 preview complete · current state and active slot unchanged')


class UsbPresetReadWorker(QThread):
    status=Signal(str);configuration=Signal(bytes);presetMetadata=Signal(object);telemetry=Signal(object)
    frameObserved=Signal(str,bytes);failed=Signal(str);firBank=Signal(bytes);snapshot=Signal(object);journalPath=Signal(str)
    def __init__(self,parent=None,*,port_factory=HidPresetReadPort):
        super().__init__(parent);self.stop_event=Event();self.port_factory=port_factory
    def stop(self):self.stop_event.set()
    def run(self):
        journal=None
        try:
            if self.port_factory is HidPresetReadPort:raise ValueError(LIVE_PREVIEW_BLOCK_REASON)
            JOURNAL_DIRECTORY.mkdir(parents=True,exist_ok=True)
            path=JOURNAL_DIRECTORY/('app-preset-read-P02-'+time.strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:8]+'.ndjson')
            journal=DurableJournal(path,sync_each=False);self.journalPath.emit(str(path))
            journal.record({'kind':'session_started','scope':'Manual P02 preview, bank0 startup and stored bank2; no Store/Recall'})
            port=self.port_factory(journal.record,self.stop_event)
            service=PresetReadService(port,self.stop_event,record=journal.record,status=self.status.emit,log=self.frameObserved.emit,
                configuration=self.configuration.emit,preset_metadata=self.presetMetadata.emit,snapshot=self.snapshot.emit)
            def bank0(raw):
                journal.record({'kind':'fir_bank_complete','selector':0,'bytes':len(raw),'blocks':1261,'sha256':hashlib.sha256(raw).hexdigest()})
                self.firBank.emit(raw)
            run_read_session(port,self.stop_event,status=self.status.emit,configuration=service.observe_configuration,
                preset_metadata=service.observe_metadata,telemetry=self.telemetry.emit,log=self.frameObserved.emit,
                strict_startup=True,full_fir=True,request_validator=validate_preset_read_request,fir_bank=bank0,
                between_polls=service.dispatch)
            journal.record({'kind':'session_finished','error':None,'cancelled':self.stop_event.is_set()})
        except Exception as error:
            self.failed.emit(str(error))
            if journal is not None:
                try:journal.record({'kind':'session_finished','error':str(error)})
                except OSError:pass
        finally:
            if journal is not None:journal.close()
