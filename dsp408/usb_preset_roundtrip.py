"""Manual P19 trial worker, explicitly approved by the user on 2026-10-12."""
import time
from pathlib import Path
from threading import Event
from uuid import uuid4
from PySide6.QtCore import QThread,Signal
from dsp408.preset_roundtrip import PresetRoundtripReview,eeprom_blocks
from dsp408.wire_research import decode_editor_frame
from dsp408.usb_read import run_read_session,read_bus_frame,validate_read_request
from dsp408.usb_fir_read import HidFirReadPort
from dsp408.usb_journal import DurableJournal

PRESET_ROUNDTRIP_AUTHORIZED=True
BLOCK_REASON='P19 Store/Recall trial prepared; destination-slot approval required'
from dsp408.app_paths import JOURNAL_DIRECTORY


def validate_trial_request(raw):
    p=decode_editor_frame(raw)
    if p.address_bytes!=b'\x00\x01':raise ValueError('Wrong preset trial device address')
    if p.command==0x19:
        if len(p.data)!=3 or (int.from_bytes(p.data[:2],'little'),p.data[2]) not in eeprom_blocks(2)+eeprom_blocks(19):raise ValueError('EEPROM outside P02/P19 trial')
    elif p.command==0x56:
        if len(p.data)!=3 or p.data[0] not in (0,2,19) or int.from_bytes(p.data[1:],'little')>1260:raise ValueError('FIR read outside trial banks')
    elif p.command==0x20:
        if p.data not in (b'\x02',b'\x13'):raise ValueError('Recall outside P02/P19 trial')
    elif p.command==0x21:
        if p.data!=b'\x13':raise ValueError('Store permits P19 only')
    elif p.command==0x34:
        if p.data!=b'\x00\x0e\x01':raise ValueError('Trial permits only IN A -1dB probe')
    else:return validate_read_request(raw)
    return p


class HidPresetRoundtripPort(HidFirReadPort):
    validate_request=staticmethod(validate_trial_request)
    def open(self):
        if not PRESET_ROUNDTRIP_AUTHORIZED:raise ValueError(BLOCK_REASON)
        super().open()
    def write(self,raw):
        if not PRESET_ROUNDTRIP_AUTHORIZED:raise ValueError(BLOCK_REASON)
        super().write(raw)


class PresetTrialService:
    def __init__(self,port,stop,*,record,status,log,configuration,preset_metadata,result,clock=time.monotonic):
        self.port=port;self.stop=stop;self.record=record;self.status=status;self.log=log
        self.configuration=configuration;self.preset_metadata=preset_metadata;self.result=result;self.clock=clock
        self.metadata=None;self.review=None;self.done=False
    def observe_metadata(self,value):self.metadata=value;self.preset_metadata(value)
    def observe_configuration(self,raw):
        self.review=PresetRoundtripReview(raw,self.metadata or {});self.configuration(raw)
    def observe_frame(self,direction,raw):
        if direction=='rx':
            p=decode_editor_frame(raw)
            if p.command==0x24 and (not p.data or p.data[0]>31 or len(p.data)!=(7 if p.data[0]==31 else 51)):raise ValueError('Current block extent differs')
        self.log(direction,raw)
    def dispatch(self):
        if self.done or self.review is None:return
        self.done=True;r=self.review
        while not r.complete:
            if self.stop.is_set():raise InterruptedError('Preset trial cancelled; no automatic restore')
            step=r.steps[r.position]
            raw=r.proposal;validate_trial_request(raw)
            if r.position%32==0 or r.steps[r.position][4]=='mutation':self.status(f'P19 trial · {r.phase} · {r.position}/{len(r.steps)}')
            if r.steps[r.position][4]=='mutation':
                self.record({'kind':'setter_intent','frame_hex':raw.hex(),'phase':r.phase,'trial_step':r.position})
            self.port.write(raw);self.log('tx',raw);deadline=self.clock()+r.timeout_seconds;r.feed('tx',raw)
            while True:
                if self.stop.is_set():raise InterruptedError('Preset trial cancelled while waiting; DSP may retain the last action')
                if self.clock()>=deadline:raise TimeoutError('Preset trial response timeout: '+r.phase+'; no retry or automatic restore')
                report=self.port.read(100)
                if not report:continue
                p=read_bus_frame(report);self.observe_frame('rx',p.raw)
                if r.feed('rx',p.raw):
                    # Publish actual fully verified states, never desired values.
                    if step[4]=='state' and step[6][0]==31:
                        key=step[5]
                        catalog=r.catalog if key=='ready' else r.after_catalog
                        names=dict(self.metadata['names_raw_hex'])
                        if key!='ready':names[18]=r.before[2:16].hex()
                        self.metadata={**self.metadata,'active_slot_raw':2 if key in ('ready','returned') else 19,
                                       'catalog_markers':list(catalog),'names_raw_hex':names}
                        self.preset_metadata(self.metadata);self.configuration(r.states[key].data())
                    break
        value=r.result();self.record({'kind':'preset_roundtrip_complete',**value})
        metadata={**self.metadata,'active_slot_raw':2,'catalog_markers':list(r.after_catalog),
                  'names_raw_hex':{**self.metadata['names_raw_hex'],18:r.before[2:16].hex()}}
        self.preset_metadata(metadata);self.configuration(r.before);self.result(value)
        self.status('P19 Store/Recall complete · IN A restored by Recall · P02 active · parameters and FIR verified')


class UsbPresetRoundtripWorker(QThread):
    status=Signal(str);configuration=Signal(bytes);presetMetadata=Signal(object);telemetry=Signal(object)
    frameObserved=Signal(str,bytes);failed=Signal(str);result=Signal(object);journalPath=Signal(str)
    def __init__(self,parent=None,*,port_factory=HidPresetRoundtripPort):
        super().__init__(parent);self.stop_event=Event();self.port_factory=port_factory
    def stop(self):self.stop_event.set()
    def run(self):
        journal=None
        try:
            if self.port_factory is HidPresetRoundtripPort and not PRESET_ROUNDTRIP_AUTHORIZED:raise ValueError(BLOCK_REASON)
            JOURNAL_DIRECTORY.mkdir(parents=True,exist_ok=True)
            path=JOURNAL_DIRECTORY/('app-preset-roundtrip-P19-'+time.strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:8]+'.ndjson')
            journal=DurableJournal(path,sync_each=False);self.journalPath.emit(str(path))
            journal.record({'kind':'session_started','scope':'Manual P19 Store/Recall trial; four explicit mutations; no staging/rename/upload'})
            port=self.port_factory(journal.record,self.stop_event)
            s=PresetTrialService(port,self.stop_event,record=journal.record,status=self.status.emit,log=self.frameObserved.emit,
                                 configuration=self.configuration.emit,preset_metadata=self.presetMetadata.emit,result=self.result.emit)
            run_read_session(port,self.stop_event,status=self.status.emit,configuration=s.observe_configuration,
                preset_metadata=s.observe_metadata,telemetry=self.telemetry.emit,log=s.observe_frame,
                strict_startup=True,request_validator=validate_trial_request,between_polls=s.dispatch)
            journal.record({'kind':'session_finished','error':None,'cancelled':self.stop_event.is_set()})
        except Exception as error:
            self.failed.emit(str(error))
            if journal is not None:
                try:journal.record({'kind':'session_finished','error':str(error)})
                except OSError:pass
        finally:
            if journal is not None:journal.close()
