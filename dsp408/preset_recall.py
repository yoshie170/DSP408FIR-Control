"""User-confirmed native Recall20 with fresh EEPROM and complete readback.

No Store, upload, staging, FIR coefficient encoding or automatic recovery.
"""
import hashlib
import time
from dsp408.source_codec import frame
from dsp408.usb_read import read_bus_frame


def checked_slot(slot):
    if type(slot) is not int or not 1<=slot<=19:
        raise ValueError('Recall permits stored P01-P19 only; default slot0 is blocked')
    return slot


def eeprom_requests(slot):
    start=checked_slot(slot)*1580-1555
    return tuple(frame(0x19,(start+50*i).to_bytes(2,'little')+bytes((50 if i<31 else 6,))) for i in range(32))


def check_target(slot,raw,catalog,name):
    checked_slot(slot)
    if len(catalog)!=19 or catalog[slot-1]!=255 or len(raw)!=1556 or raw[0]!=255:
        raise ValueError('Preset must be stored in the fresh catalog and EEPROM')
    if len(name)!=14 or raw[2:16]!=name:
        raise ValueError('Stored preset name differs from the fresh catalog')


class RecallOperation:
    TOTAL=70

    def __init__(self,port,stop,*,record,log,progress,clock=time.monotonic,
                 reply_decoder=read_bus_frame,default_timeout=2.):
        self.port=port;self.stop=stop;self.record=record;self.log=log
        self.progress=progress;self.clock=clock;self.done=0;self.slot=None
        self.reply_decoder=reply_decoder;self.default_timeout=default_timeout

    def report(self,stage,waiting=False):
        self.progress({'busy':True,'slot':self.slot,'stage':stage,'done':self.done,
                       'total':self.TOTAL,'waiting':waiting})

    def exchange(self,raw,reply,stage,*,arm=False,target=None,timeout=None,expected_payload=None):
        if self.stop.is_set():raise InterruptedError('Preset recall cancelled; no automatic restore')
        self.report(stage,reply==1)
        if arm:self.port.arm_preset_request(raw,self.slot,target)
        self.port.write(raw);self.log('tx',raw);deadline=self.clock()+(self.default_timeout if timeout is None else timeout)
        while self.clock()<deadline:
            if self.stop.is_set():raise InterruptedError('Preset recall cancelled; DSP may retain the last action')
            report=self.port.read(100)
            if not report:continue
            packet=self.reply_decoder(report);self.log('rx',packet.raw)
            if packet.address_bytes!=b'\x01\x00':raise ValueError('Preset response address differs')
            if packet.command==1 and not packet.data and reply!=1:continue
            if packet.command!=reply or (reply==1 and packet.data!=(b'' if expected_payload is None else expected_payload)):
                raise ValueError('Unexpected response during preset recall')
            self.done+=1;self.report(stage)
            return packet.data
        raise TimeoutError('Preset recall timeout: '+stage+'; no retry or automatic restore')

    def run(self,slot):
        self.slot=checked_slot(slot)
        catalog=self.exchange(frame(0x22,b''),0x22,'Checking stored presets')
        if len(catalog)!=19 or catalog[slot-1]!=255:raise ValueError('Selected preset is empty or catalog differs')
        named=self.exchange(frame(0x29,bytes((slot-1,))),0x29,'Reading preset name')
        if len(named)!=15 or named[0]!=slot-1:raise ValueError('Preset name response differs')
        saved=bytearray()
        for raw in eeprom_requests(slot):
            body=self.exchange(raw,0x19,'Reading stored parameters',arm=True)
            if len(body)!=raw[8]:raise ValueError('Stored parameter block extent differs')
            saved.extend(body)
        saved=bytes(saved);check_target(slot,saved,catalog,named[1:])
        # Persist the fresh target bytes before the one native mutation.
        self.record({'kind':'setter_intent','operation':'preset_recall','slot':slot,
                     'frame_hex':frame(0x20,bytes((slot,))).hex(),'target_state_hex':saved.hex(),
                     'catalog_hex':catalog.hex(),'name_hex':named[1:].hex()})
        self.exchange(frame(0x20,bytes((slot,))),1,'Waiting for DSP Recall',arm=True,
                      target=(saved,catalog,named[1:]),timeout=50.)
        active=self.exchange(frame(0x14,b''),0x14,'Checking active preset')
        if active!=bytes((slot,)):raise ValueError('DSP active slot differs after Recall')
        after=self.exchange(frame(0x22,b''),0x22,'Checking preset catalog')
        if after!=catalog:raise ValueError('Preset catalog changed during Recall')
        name=self.exchange(frame(0x29,bytes((slot-1,))),0x29,'Checking preset name')
        if name!=named:raise ValueError('Preset name changed during Recall')
        current=bytearray()
        for i in range(32):
            body=self.exchange(frame(0x27,bytes((i,))),0x24,'Verifying loaded parameters')
            if len(body)!=(7 if i==31 else 51) or body[0]!=i:
                raise ValueError('Recall state block index or extent differs')
            current.extend(body[1:])
        current=bytes(current)
        if current!=saved:raise ValueError('Loaded parameters differ from stored preset; no automatic restore')
        result={'slot':slot,'state_sha256':hashlib.sha256(current).hexdigest(),
                'parameters_verified':True,'fir_bank_read':False,'audio_verified':False,
                'power_cycle_persistence_verified':False}
        self.record({'kind':'preset_recall_verified',**result,'state_hex':current.hex()})
        self.progress({'busy':True,'slot':slot,'stage':'Preset loaded · parameters verified',
                       'done':self.TOTAL,'total':self.TOTAL,'waiting':False})
        return current,{'active_slot_raw':slot,'catalog_markers':list(after),
                        'name_index':slot-1,'name_raw_hex':name[1:].hex()},result
