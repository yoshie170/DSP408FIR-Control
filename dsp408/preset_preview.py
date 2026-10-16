"""Offline P02 correlation and unchanged-state guard; physical staging blocked."""
import hashlib
from dsp408.source_codec import frame
from dsp408.wire_research import decode_editor_frame
from dsp408.editor_state_research import StateBlockAssembler
from dsp408.editor_rx_research import FirAreaAssembler
from dsp408.fir_bank import describe_bank

SLOT=2
LIVE_PREVIEW_BLOCK_REASON='Preset staging blocked: it overwrites the current parameter RAM'


class PresetPreviewReview:
    def __init__(self,state,metadata):
        self.before=bytes(state)
        if len(self.before)!=1556:raise ValueError('Preset preview needs a complete current state')
        markers=metadata.get('catalog_markers',[]);names=metadata.get('names_raw_hex',{})
        if len(markers)!=19 or markers[SLOT-1]!=255:raise ValueError('P02 stored marker differs from observed FF profile')
        self.name=bytes.fromhex(names.get(SLOT-1,names.get(str(SLOT-1),'')))
        self.active=metadata.get('active_slot_raw')
        if len(self.name)!=14 or type(self.active) is not int or not 0<=self.active<=19:raise ValueError('Preset catalog/name/active slot incomplete')
        self.staged=StateBlockAssembler(layout='common-prefix1556')
        self.bank=FirAreaAssembler(selector=SLOT);self.after=StateBlockAssembler(layout='common-prefix1556')
        self.position=0;self.outstanding=False;self.complete=False
        self.steps=[(0x24,bytes((SLOT,)),1,'stage')]
        self.steps += [(0x28,bytes((i,)),0x28,'parameters') for i in range(32)]
        self.steps += [(0x56,bytes((SLOT,))+i.to_bytes(2,'little'),0x56,'stored FIR') for i in range(1261)]
        self.steps += [(0x14,b'',0x14,'verify active slot')]
        self.steps += [(0x27,bytes((i,)),0x24,'verify current state') for i in range(32)]
    @property
    def proposal(self):
        if self.complete:return None
        op,p,_,_=self.steps[self.position];return frame(op,p)
    @property
    def phase(self):return 'complete' if self.complete else self.steps[self.position][3]
    def feed(self,direction,raw):
        if self.complete:raise ValueError('Preview already complete')
        p=decode_editor_frame(raw);op,data,response,phase=self.steps[self.position]
        if direction=='tx':
            if self.outstanding or p.raw!=self.proposal:raise ValueError('Preset TX differs from pending preview step')
            self.outstanding=True;return False
        if direction!='rx' or p.address_bytes!=b'\1\0' or not self.outstanding:raise ValueError('Preset response without pending request or wrong address')
        if p.command==1 and not p.data and response!=1:return False
        if p.command!=response:raise ValueError('Unexpected preset preview response')
        if phase=='stage':
            if p.data:raise ValueError('Preset staging expects empty source01 shape')
        elif phase in ('parameters','verify current state'):
            index=data[0]
            if len(p.data)!=(7 if index==31 else 51) or p.data[0]!=index:raise ValueError('Preset/current block index or exact50/6-byte body differs')
            assembler=self.staged if phase=='parameters' else self.after
            assembler.add(p.data)
            if index==31:
                if phase=='parameters' and assembler.data()[2:16]!=self.name:raise ValueError('Staged P02 name differs from freshly read catalog')
                if phase=='verify current state' and assembler.data()!=self.before:raise ValueError('Current raw state changed during preset preview; no restore attempted')
        elif phase=='stored FIR':
            index=int.from_bytes(data[1:],'little')
            if len(p.data)!=(19 if index==1260 else 55) or p.data[:3]!=bytes((SLOT,))+index.to_bytes(2,'big'):
                raise ValueError('Stored FIR selector/index/length differs')
            self.bank.add(p.data)
        else:
            if p.data!=bytes((self.active,)):raise ValueError('Active preset index changed during preview; no restore attempted')
        self.position+=1;self.outstanding=False;self.complete=self.position==len(self.steps)
        return True
    def result(self):
        if not self.complete:raise ValueError('Preset snapshot incomplete or not verified')
        state=self.staged.data();bank=self.bank.data();r=describe_bank(bank);r['selector']=SLOT
        return {'scope':'Read-only stored P02 preview; host readback, not audio/persistence certification',
            'slot':SLOT,'name_raw_hex':self.name.hex(),'state_hex':state.hex(),'fir_bank_hex':bank.hex(),
            'state_sha256':hashlib.sha256(state).hexdigest(),'fir_bank_sha256':r['sha256'],
            'current_before_sha256':hashlib.sha256(self.before).hexdigest(),
            'current_after_sha256':hashlib.sha256(self.after.data()).hexdigest(),
            'active_slot_before':self.active,'active_slot_after':self.active,
            'complete':True,'current_state_unchanged':True,'fir_bank':r}
