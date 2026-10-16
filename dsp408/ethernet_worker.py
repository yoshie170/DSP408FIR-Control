"""Manual direct Ethernet read session. No setters or HID adaptation/padding."""
import socket,time
from pathlib import Path
from threading import Event
from PySide6.QtCore import QThread,Signal
from dsp408.ethernet_read import read_snapshot
from dsp408.ethernet_stream import EthernetFrames
from dsp408.source_codec import frame
from dsp408.editor_rx_research import decode_telemetry_payload
from dsp408.usb_journal import DurableJournal


def wait_finish_ack(stream,stop,*,record,log,clock=time.monotonic):
    """The serialized TX12 boundary only: MCU AF1E/AF46 emits empty RX01.

    Actual successful Ethernet sessions contain this reply before their first
    RX40. Never enqueue40 behind an unacknowledged12 or use01 as a setter ACK.
    """
    decoder=EthernetFrames();deadline=clock()+5
    while True:
        if stop.is_set():raise InterruptedError('Ethernet connection cancelled before startup acknowledgement')
        if clock()>=deadline:raise TimeoutError('Ethernet startup acknowledgement timeout after TX12; no retry')
        stream.settimeout(max(.001,min(.1,deadline-clock())))
        try:chunk=stream.recv(4096)
        except TimeoutError:continue
        if not chunk:
            decoder.finish();raise ConnectionError('DSP closed Ethernet before startup acknowledgement')
        record({'kind':'rx_chunk','hex':chunk.hex()})
        packets=decoder.feed(chunk)
        if not packets:continue
        if len(packets)!=1 or decoder.pending:raise ValueError('Unexpected data after Ethernet startup acknowledgement')
        p=packets[0]
        if p.address_bytes!=b'\1\0' or p.command!=1 or p.data:
            raise ValueError('Expected empty RX01 after Ethernet TX12')
        log('rx',p.raw)
        record({'kind':'startup_finish_acknowledged','frame_hex':p.raw.hex(),'setters_sent':False})
        return


def poll_levels(stream,stop,send,*,record,telemetry,log,clock=time.monotonic,poll_ms=100):
    def interval():
        value=poll_ms() if callable(poll_ms) else poll_ms
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms polling')
        return value/1000
    interval()
    decoder=EthernetFrames();next_poll=clock()
    while not stop.is_set():
        remaining=next_poll-clock()
        if remaining>0 and stop.wait(remaining):return
        if stop.is_set():return
        sent_at=clock();send(frame(0x40,b''));deadline=sent_at+5;acks=0;packets=[]
        while not stop.is_set():
            if clock()>=deadline:raise TimeoutError('Ethernet meter response timeout; no retry')
            stream.settimeout(max(.001,min(.1,deadline-clock())))
            try:chunk=stream.recv(4096)
            except TimeoutError:continue
            if not chunk:
                decoder.finish();raise ConnectionError('DSP closed Ethernet connection')
            record({'kind':'rx_chunk','hex':chunk.hex()})
            packets.extend(decoder.feed(chunk))
            accepted=None
            while packets:
                p=packets.pop(0)
                if p.address_bytes!=b'\1\0':raise ValueError('Unexpected Ethernet meter address')
                if p.command==1 and not p.data and acks<4:acks+=1;log('rx',p.raw);continue
                if p.command!=0x40 or len(p.data)!=42:raise ValueError('Unexpected Ethernet meter reply; expected RX40/42 bytes')
                if accepted is not None:raise ValueError('Unrequested extra Ethernet meter reply')
                accepted=p
            if accepted is not None:
                if decoder.pending:raise ValueError('Unexpected partial frame after Ethernet meter reply')
                value=decode_telemetry_payload(accepted.data);log('rx',accepted.raw)
                telemetry(value);next_poll=max(clock(),sent_at+interval());break


class EthernetReadWorker(QThread):
    control_writes_allowed=False
    status=Signal(str);configuration=Signal(bytes);firBank=Signal(bytes)
    firPreview=Signal(object)
    presetMetadata=Signal(object);telemetry=Signal(object);frameObserved=Signal(str,bytes)
    journalPath=Signal(str);failed=Signal(str)

    def __init__(self,host,source_ip,parent=None,*,poll_ms=100,connect=socket.create_connection,
                 directory=None,clock=time.monotonic,fir_strategy='full',device_id=1):
        if type(poll_ms) is not int or poll_ms not in (100,300):raise ValueError('Choose 100 or 300 ms polling')
        if fir_strategy not in ('full','source-display'):raise ValueError('Unknown Ethernet FIR strategy')
        super().__init__(parent);self.host=host;self.source_ip=source_ip;self.poll_ms=poll_ms
        from dsp408.device_address import AddressedStream,checked_id
        self.device_id=checked_id(device_id)
        self.connect_factory=lambda *a,**kw:AddressedStream(connect(*a,**kw),self.device_id,getattr(self,'address_record',lambda _:None))
        self.clock=clock;self.stop_event=Event()
        self.fir_strategy=fir_strategy
        from dsp408.app_paths import JOURNAL_DIRECTORY
        self.directory=Path(directory) if directory is not None else JOURNAL_DIRECTORY

    def stop(self):self.stop_event.set()

    def set_meter_poll_ms(self,value):
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms.')
        self.poll_ms=value

    def live_session(self,stream,result,metadata,send,record):
        if self.stop_event.is_set():raise InterruptedError('Ethernet connection cancelled before startup acknowledgement')
        self.status.emit('Ethernet synchronization · finish_ack')
        wait_finish_ack(stream,self.stop_event,record=record,log=self.frameObserved.emit,clock=self.clock)
        if self.stop_event.is_set():return
        self.presetMetadata.emit(metadata)
        if 'bank_hex' in result:self.firBank.emit(bytes.fromhex(result['bank_hex']))
        else:self.firPreview.emit(result['fir_preview'])
        self.configuration.emit(bytes.fromhex(result['state_hex']))
        self.status.emit('Ethernet · read connected · FIR408 V0115P')
        poll_levels(stream,self.stop_event,send,record=record,telemetry=self.telemetry.emit,
                    log=self.frameObserved.emit,clock=self.clock,poll_ms=lambda:self.poll_ms)

    def run(self):
        journal=None
        try:
            self.directory.mkdir(parents=True,exist_ok=True)
            path=self.directory/('ethernet-session-'+str(time.time_ns())+'.ndjson')
            journal=DurableJournal(path,sync_each=False,max_bytes=(128 if self.control_writes_allowed else 32)*1024*1024);self.journalPath.emit(str(path))
            journal.record({'kind':'physical_address_scope','target_id':self.device_id,'internal_planner_id':1})
            def record(event):
                journal.record(event)
                if event['kind'] in ('snapshot_complete','fir_display_snapshot_complete','startup_finish_acknowledged','ethernet_control_started','control_baseline'):
                    # Sync the complete startup certificate before publishing any live state.
                    import os
                    os.fsync(journal.stream.fileno())
            def progress(value):
                if value.startswith('FIR '):
                    block=int(value.split()[1].split('/')[0]);value=f'Reading FIR · {block*100/1261:.0f}%'
                self.status.emit('Ethernet synchronization · '+value)
            self.address_record=record
            def connected(stream,result,metadata,send):
                return self.live_session(stream,result,metadata,send,record)
            read_snapshot(self.host,record,source_ip=self.source_ip,connect=self.connect_factory,
                          clock=self.clock,status=progress,stop=self.stop_event,session=connected,
                          frame_observed=self.frameObserved.emit,fir_strategy=self.fir_strategy,
                          locked_startup=getattr(self,'unlock_startup',None))
        except InterruptedError:
            if journal is not None:
                try:journal.record({'kind':'cancelled','setters_sent':None if self.control_writes_allowed else False})
                except OSError as error:self.failed.emit('Cannot record Ethernet cancellation: '+str(error))
        except Exception as error:
            if journal is not None:
                try:journal.record({'kind':'failed','error':str(error),'setters_sent':None if self.control_writes_allowed else False})
                except OSError:pass
            self.failed.emit(str(error))
        finally:
            if journal is not None:
                try:journal.close()
                except OSError as error:self.failed.emit('Cannot finish Ethernet journal: '+str(error))
