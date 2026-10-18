"""Explicit full bank0 read. No FIR/preset setters permitted.

TX56 selector0 + blockLE16, RX56 selector0 + blockBE16 +52/16 bytes.
MCU1.15 B00E/B036 and B036+28: flash address selector<<16 +52*block;
1261 blocks cover exactly65536 bytes. No sentinel skip or synthesized words.
"""
import hashlib,time
from threading import Event
from uuid import uuid4
from PySide6.QtCore import QThread,Signal
from dsp408.wire_research import decode_editor_frame
from dsp408.usb_read import HidReadPort,validate_read_request,run_read_session
from dsp408.usb_journal import DurableJournal

from dsp408.app_paths import JOURNAL_DIRECTORY


def validate_fir_read_request(raw):
    p=decode_editor_frame(raw)
    if p.command!=0x56:return validate_read_request(raw)
    if p.address_bytes!=b'\0\1' or len(p.data)!=3 or p.data[0]!=0 or int.from_bytes(p.data[1:],'little')>1260:
        raise ValueError('Full FIR read allows only current bank0, blocks0..1260, address1')
    return p


class HidFirReadPort(HidReadPort):
    validate_request=staticmethod(validate_fir_read_request)
    def __init__(self,record,stop):
        super().__init__();self.record=record;self.stop_event=stop
    def write(self,raw):
        p=self.validate_request(raw)
        if self.stop_event.is_set() and p.command!=0x11:raise InterruptedError('FIR read cancelled before transmission')
        self.record({'kind':'tx_intent','frame_hex':bytes(raw).hex()})
        if self.stop_event.is_set() and p.command!=0x11:raise InterruptedError('FIR read cancelled before transmission')
        report=b'\0'+bytes(raw)+bytes(64-len(raw))
        if self.device.write(report)!=65:raise OSError('Incomplete USB output report; no retransmission')
        self.record({'kind':'tx_completed','frame_hex':bytes(raw).hex()})
    def read(self,timeout_ms):
        raw=super().read(timeout_ms)
        if raw:self.record({'kind':'rx_report','report_hex':raw.hex()})
        return raw


class UsbFirReadWorker(QThread):
    status=Signal(str);configuration=Signal(bytes);presetMetadata=Signal(object)
    telemetry=Signal(object);frameObserved=Signal(str,bytes);failed=Signal(str)
    firBank=Signal(bytes);journalPath=Signal(str)
    def __init__(self,parent=None,*,port_factory=HidFirReadPort):
        super().__init__(parent);self.stop_event=Event();self.port_factory=port_factory
    def stop(self):self.stop_event.set()
    def run(self):
        journal=None
        try:
            directory=JOURNAL_DIRECTORY;directory.mkdir(parents=True,exist_ok=True)
            path=directory/('app-fir-read-'+time.strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:8]+'.ndjson')
            journal=DurableJournal(path,sync_each=False);self.journalPath.emit(str(path))
            journal.record({'kind':'session_started','scope':'Manual full raw FIR bank0 read; no parameter/preset/FIR setters'})
            def complete(raw):
                journal.record({'kind':'fir_bank_complete','bytes':len(raw),'blocks':1261,'selector':0,
                                'sha256':hashlib.sha256(raw).hexdigest()})
                self.firBank.emit(raw)
            run_read_session(self.port_factory(journal.record,self.stop_event),self.stop_event,
                status=self.status.emit,configuration=self.configuration.emit,telemetry=self.telemetry.emit,
                log=self.frameObserved.emit,preset_metadata=self.presetMetadata.emit,strict_startup=True,
                full_fir=True,request_validator=validate_fir_read_request,fir_bank=complete)
            journal.record({'kind':'session_finished','error':None,'cancelled':self.stop_event.is_set()})
        except Exception as error:
            self.failed.emit(str(error))
            if journal is not None:
                try:journal.record({'kind':'session_finished','error':str(error)})
                except OSError:pass
        finally:
            if journal is not None:journal.close()
