"""Explicit P19 Store/Recall trial plan and correlator; no I/O in this module.

Restricted to the observed P02 parameter profile and fresh all-FF FIR banks.
Not a general preset writer or an emulator of processing/persistence.
"""
import hashlib
from dsp408.source_codec import frame
from dsp408.wire_research import decode_editor_frame
from dsp408.editor_state_research import StateBlockAssembler
from dsp408.editor_rx_research import FirAreaAssembler
from dsp408.eeprom_preset import REFERENCE_SHA256,REFERENCE_NAME

TARGET_SLOT=19
RETURN_SLOT=2


def eeprom_blocks(slot):
    if type(slot) is not int or slot not in (2,19):raise ValueError('Trial permits P02 and P19 EEPROM only')
    start=slot*1580-1555
    return tuple((start+50*i,50 if i<31 else 6) for i in range(32))


class PresetRoundtripReview:
    def __init__(self,current,metadata):
        self.before=bytes(current)
        if hashlib.sha256(self.before).hexdigest()!=REFERENCE_SHA256:raise ValueError('Current state differs from the confirmed P02 profile')
        if metadata.get('active_slot_raw')!=2:raise ValueError('Trial starts only with active P02')
        markers=metadata.get('catalog_markers',[])
        if len(markers)!=19 or any(type(v) is not int or not 0<=v<=255 for v in markers):raise ValueError('Fresh catalog required')
        if markers[1]!=255 or markers[18]!=0:raise ValueError('P02 must be stored and P19 empty before any write')
        names=metadata.get('names_raw_hex',{})
        if bytes.fromhex(names.get(1,names.get('1','')))!=REFERENCE_NAME:raise ValueError('Fresh P02 name differs')
        self.catalog=bytes(markers);changed=bytearray(self.catalog);changed[18]=255;self.after_catalog=bytes(changed)
        self.minus=bytearray(self.before)
        if self.minus[146:148]!=b'\x18\x01':raise ValueError('IN A is not the verified0dB baseline')
        self.minus[146:148]=b'\x0e\x01';self.minus=bytes(self.minus)
        self.steps=[];self.position=0;self.outstanding=False;self.complete=False
        self.buffers={};self.banks={};self.states={};self.write_count=0
        def add(op,data,reply,label,kind,key,expected=None):
            self.steps.append((op,data,reply,label,kind,key,expected))
        def record(slot,key):
            self.buffers[key]=bytearray()
            for address,count in eeprom_blocks(slot):add(0x19,address.to_bytes(2,'little')+bytes((count,)),0x19,key,'record',key,count)
        def bank(slot,key):
            self.banks[key]=FirAreaAssembler(selector=slot)
            for i in range(1261):add(0x56,bytes((slot,))+i.to_bytes(2,'little'),0x56,key,'bank',key,i)
        def verify(key,slot,catalog,state):
            add(0x14,b'',0x14,key,'exact','active',bytes((slot,)))
            add(0x22,b'',0x22,key,'exact','catalog',catalog)
            self.states[key]=StateBlockAssembler(layout='common-prefix1556')
            for i in range(32):add(0x27,bytes((i,)),0x24,key,'state',key,(i,state))
        def mutation(op,data,label):add(op,data,1,label,'mutation',label,b'')
        record(2,'before_P02');record(19,'before_P19')
        for slot in (0,2,19):bank(slot,'before_FIR_'+str(slot))
        verify('ready',2,self.catalog,self.before)
        mutation(0x21,b'\x13','Store P19')
        record(19,'stored_P19')
        add(0x29,b'\x12',0x29,'stored P19 name','exact','name',b'\x12'+REFERENCE_NAME)
        verify('stored',19,self.after_catalog,self.before);bank(19,'stored_FIR_19')
        mutation(0x34,b'\x00\x0e\x01','IN A -1 dB probe')
        verify('minus1',19,self.after_catalog,self.minus)
        mutation(0x20,b'\x13','Recall P19')
        verify('recalled',19,self.after_catalog,self.before);bank(0,'recalled_FIR_0')
        mutation(0x20,b'\x02','Return to P02')
        verify('returned',2,self.after_catalog,self.before);bank(0,'returned_FIR_0')

    @property
    def proposal(self):
        if self.complete:return None
        op,data,*_=self.steps[self.position];return frame(op,data)

    @property
    def phase(self):return 'complete' if self.complete else self.steps[self.position][3]

    @property
    def timeout_seconds(self):
        op=self.steps[self.position][0]
        return 50. if op==0x20 else 10. if op==0x21 else 2.

    def feed(self,direction,raw):
        if self.complete:raise ValueError('Preset trial already complete')
        p=decode_editor_frame(raw);op,data,reply,label,kind,key,expected=self.steps[self.position]
        if direction=='tx':
            if self.outstanding or p.raw!=self.proposal:raise ValueError('Preset trial TX differs from pending step')
            self.outstanding=True
            if kind=='mutation':self.write_count+=1
            return False
        if direction!='rx' or p.address_bytes!=b'\x01\x00' or not self.outstanding:raise ValueError('Unrequested preset trial response')
        if p.command==1 and not p.data and reply!=1:return False
        if p.command!=reply:raise ValueError('Unexpected preset trial response')
        body=p.data
        if kind in ('exact','mutation'):
            if body!=expected:raise ValueError('Preset trial verification differs: '+label+' / '+key)
        elif kind=='record':
            if len(body)!=expected:raise ValueError('Preset EEPROM count differs')
            self.buffers[key].extend(body)
            if len(self.buffers[key])==1556:
                r=bytes(self.buffers[key])
                if key=='before_P02' and r!=self.before:raise ValueError('Stored P02 differs from the confirmed return state')
                if key=='before_P19' and (r[0]!=0 or r[1]!=self.before[1]):raise ValueError('P19 empty marker or preserved header differs')
                if key=='stored_P19' and r!=self.before:raise ValueError('Stored P19 differs from current parameters')
        elif kind=='bank':
            i=expected
            if len(body)!=(19 if i==1260 else 55) or body[:3]!=bytes((self.banks[key].selector,))+i.to_bytes(2,'big'):raise ValueError('FIR bank/index/extent differs')
            self.banks[key].add(body)
            if i==1260 and self.banks[key].data()!=b'\xff'*65536:raise ValueError('Trial requires fresh all-FF FIR banks: '+key)
        else:
            i,wanted=expected
            if len(body)!=(7 if i==31 else 51) or body[0]!=i:raise ValueError('Current-state block differs')
            self.states[key].add(body)
            if i==31 and self.states[key].data()!=wanted:raise ValueError('Current state differs: '+key+'; no automatic restore')
        self.position+=1;self.outstanding=False;self.complete=self.position==len(self.steps)
        return True

    def result(self):
        if not self.complete:raise ValueError('Preset roundtrip incomplete')
        return {'scope':'P19 Store/Recall, IN A -1dB probe, planned return P02; host verification only',
                'complete':True,'target_slot':19,'return_slot':2,'mutating_commands':self.write_count,
                'before_sha256':hashlib.sha256(self.before).hexdigest(),
                'stored_sha256':hashlib.sha256(self.buffers['stored_P19']).hexdigest(),
                'returned_sha256':hashlib.sha256(self.states['returned'].data()).hexdigest(),
                'fir_banks_all_ff_verified':sorted(self.banks),
                'catalog_before_hex':self.catalog.hex(),'catalog_after_hex':self.after_catalog.hex(),
                'target_slot_created':True,'audio_verified':False,'power_cycle_persistence_verified':False}
