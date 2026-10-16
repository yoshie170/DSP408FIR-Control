"""Explicit OUT crossover design: MCU synthesis4B, never local coefficient upload."""
from dataclasses import dataclass
from dsp408.source_codec import frame,encode_payload,fir_frequency_raw,integer
from dsp408.source_session import SourceDocument
from dsp408.model import FIR_TYPES,FIR_WINDOWS
from dsp408.fir_usb_import import resource_usage
from dsp408.fir_upload_rehearsal import FirUploadPlan,FirUploadRehearsal

OUTPUT_FIR_AUTHORIZED=True


@dataclass(frozen=True)
class OutputFirPlan(FirUploadPlan):
    settings:tuple


@dataclass(frozen=True)
class OutputFirPermit:
    plan:OutputFirPlan
    requests:tuple
    @property
    def state(self):return self.plan.state


def prepare_output_fir(state,bank,channel,settings):
    if not OUTPUT_FIR_AUTHORIZED:raise ValueError('Output FIR design is disabled')
    integer(channel,4,11);state,bank=bytes(state),bytes(bank)
    if len(state)!=1556 or len(bank)!=65536:raise ValueError('Complete current state and FIR bank required')
    from dsp408.usb_parameter_control import state_model
    from dsp408.channel_link import validate_group_state,members_for,mask_offset,self_mask
    masks=validate_group_state(state);members=members_for(masks,channel)
    state_model(state)  # Complete representability and canonical native groups.
    if not isinstance(settings,dict) or set(settings)!={'mode','window','hpf_hz','lpf_hz','taps'}:
        raise ValueError('Complete output FIR draft required')
    mode=settings['mode'];window=settings['window'];taps=settings['taps']
    if mode not in FIR_TYPES[:4] or window not in FIR_WINDOWS:raise ValueError('Choose a generated output FIR type/window')
    if type(taps) is not int or taps not in range(256,1025,32):raise ValueError('Output design uses256..1024 taps in steps of32')
    doc=SourceDocument(state);row=doc.decoded()['channels'][channel]
    if row['crossover_processing_mode_raw']!=1:raise ValueError('Select FIR crossover mode before applying its design')
    kind=FIR_TYPES.index(mode)
    if kind:
        hp=fir_frequency_raw(settings['hpf_hz'],'hp') if kind in (2,3) else row['fir_hp_frequency_position_raw']
        lp=fir_frequency_raw(settings['lpf_hz'],'lp') if kind in (1,3) else row['fir_lp_frequency_position_raw']
        win=FIR_WINDOWS.index(window);tap=(taps-256)//32
    else:
        # Bypass ignores these fields in MCU9A62. Preserve opaque/inactive values.
        hp=row['fir_hp_frequency_position_raw'];lp=row['fir_lp_frequency_position_raw']
        win=row['fir_window_raw'];tap=row['fir_tap_parameter_raw']
    raw=frame(0x4B,encode_payload(0x4B,channel,type_raw=kind,window_raw=win,
        hp_frequency_position_raw=hp,lp_frequency_position_raw=lp,tap_parameter_raw=tap))
    for i in range(12):doc.data[mask_offset(i):mask_offset(i)+2]=self_mask(i).to_bytes(2,'little')
    for member in members:doc.apply(frame(0x4B,bytes((member,))+raw[7:-3]))
    for i in range(12):doc.data[mask_offset(i):mask_offset(i)+2]=masks[i].to_bytes(2,'little')
    expected=bytes(doc.data);resource_usage(expected);validate_group_state(expected)
    storage=bytearray(bank);sectors=tuple(m+4 for m in members) if kind else ()
    for sector in sectors:storage[sector*4096:sector*4096+4096]=b'\xff'*4096
    expected_bank=bytes(storage)
    return OutputFirPlan(channel,state,bank,b'',(raw,),expected,expected_bank,
        sectors,0,tuple((key,settings[key]) for key in ('mode','window','hpf_hz','lpf_hz','taps')))


def prepare_output_permit(state,bank,channel,settings):
    plan=prepare_output_fir(state,bank,channel,settings)
    states=tuple(frame(0x27,bytes((i,))) for i in range(32))
    banks=tuple(frame(0x56,b'\0'+i.to_bytes(2,'little')) for i in range(1261))
    catalog=(frame(0x22,b''),frame(0x14,b''))
    mutes=tuple(frame(0x35,bytes((i,1))) for i in range(12));final=[]
    for i in range(12):
        offset,bit=(1432,i) if i<4 else (1434,i-4)
        flag=(int.from_bytes(plan.state[offset:offset+2],'little')>>bit)&1
        final.append(frame(0x35,bytes((i,flag))))
    return OutputFirPermit(plan,catalog+states+banks+mutes+states+plan.frames+states+banks+tuple(final)+states+catalog)


class OutputFirOperation(FirUploadRehearsal):
    def check_port(self,port):
        if not OUTPUT_FIR_AUTHORIZED:raise ValueError('Output FIR design is disabled')
    def canonical_plan(self,plan):
        return prepare_output_fir(plan.state,plan.bank,plan.channel,dict(plan.settings))
    def exchange(self,raw,*args,**kwargs):
        if raw[5]==0x4B:kwargs.setdefault('timeout',10.) # Native synthesis for every linked OUT.
        self.check_port(self.port);self.port.arm_prs_request(raw,self.permit)
        return super().exchange(raw,*args,**kwargs)
    def run_import(self,permit):
        if type(permit) is not OutputFirPermit:raise ValueError('Typed output design required')
        p=permit.plan
        if permit!=prepare_output_permit(p.state,p.bank,p.channel,dict(p.settings)):
            raise ValueError('Output FIR permit differs from canonical plan')
        self.permit=permit;self.port.begin_prs_import(permit)
        record,progress=self.record,self.progress
        def record_output(event):
            event=dict(event)
            if event.get('kind')=='fir_rehearsal_verified':self.port.complete_prs_import(permit)
            if event.get('kind','').startswith('fir_rehearsal_'):event['kind']=event['kind'].replace('fir_rehearsal_','output_fir_',1)
            if event.get('operation')=='fir_upload_rehearsal':event['operation']='output_fir'
            event['hardware_enabled']=True;record(event)
        self.record=record_output
        self.progress=lambda event:progress({**event,'operation':'output_fir','hardware_enabled':True,'busy':True})
        try:
            state,result=self.run_plan(p)
            return state,{**result,'operation':'output_fir','hardware_enabled':True,'bank_hex':p.expected_bank.hex()}
        finally:
            self.port.end_prs_import();self.record,self.progress=record,progress
