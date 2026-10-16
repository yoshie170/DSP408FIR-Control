"""Complete PRS configuration/FIR transaction through exact typed bulk requests.

No raw state upload, staging, Store/Recall, retry or automatic recovery. File
padding is not flash padding: predict actual MCU page writes independently.
"""
from dataclasses import dataclass
import hashlib
import struct
from dsp408.prs import validate,from_bytes,fir_areas,BODY_START,FIR_START,FIR_END
from dsp408.source_session import SourceDocument,project_state
from dsp408.source_bindings import plan_changes
from dsp408.source_codec import frame,encode_payload
from dsp408.prs_apply_transaction import PrsApplyRehearsal
from dsp408.channel_link import muted
from dsp408.fir_upload_rehearsal import prepare_fir_upload
from dsp408.fir_usb_import import resource_usage
from dsp408.model import DeviceModel


@dataclass(frozen=True)
class FullPrsPermit:
    state:bytes
    bank:bytes
    prs:bytes
    frames:tuple
    expected_state:bytes
    expected_bank:bytes
    bank_known:bytes
    requests:tuple


def mute_flag(state,ch):
    offset,bit=(1432,ch) if ch<4 else (1434,ch-4)
    return (int.from_bytes(state[offset:offset+2],'little')>>bit)&1


def prepare_full_import(state,bank,prs):
    state,bank,prs=bytes(state),bytes(bank),validate(bytes(prs))
    if len(state)!=1556 or len(bank)!=65536:raise ValueError('Complete current parameters and FIR required')
    from dsp408.channel_link import validate_group_state,masks,self_mask,mask_offset,topology,prepare_link
    validate_group_state(state)
    target=state[:2]+prs[BODY_START:FIR_START]
    validate_group_state(target)
    resource_usage(target)
    wanted=from_bytes(prs)
    doc=SourceDocument(state);actual=bank;known=bytearray(b'\1'*65536);frames=[];paths=[];fir_channels=[]
    rows=SourceDocument(target).decoded()['channels']
    def add(raw,path):
        frames.append(raw);paths.append(path)
        if raw[5]==0x3B:
            at=mask_offset(raw[6]);doc.data[at:at+2]=raw[7].to_bytes(2,'little')
        elif raw[5]!=0x58:doc.apply(raw)
    # Shrink owner masks before making followers independent. These changes
    # add only a channel's own bit, so native3B copies no later channel/storage.
    for ch,value in enumerate(masks(state)):
        if value!=self_mask(ch):add(frame(0x3B,bytes((ch,self_mask(ch)))),f'channels[{ch}].link')
    # Temporarily disable active FIR allocation, while all audio is muted. This
    # avoids an intermediate old+new resource total exceeding the final budget.
    for ch,row in enumerate(doc.decoded()['channels']):
        if ch<4 and not row['fir_bypass_raw']:add(frame(0x4F,bytes((ch,1))),f'inputs[{ch}].fir.bypass')
        if ch>=4 and row['crossover_processing_mode_raw']:add(frame(0x4C,bytes((ch,0))),f'outputs[{ch-4}].crossover_mode')
    for ch,(offset,capacity,count,values) in enumerate(fir_areas(target,prs[FIR_START:FIR_END])):
        if ch>=4 and rows[ch]['fir_type_raw']==4 and not 0<=count<=capacity:
            raise ValueError('PRS External OUT count exceeds1024 even when inactive')
        if ch>=4 and rows[ch]['fir_type_raw']!=4:
            # The OEM generated design is reconstructed by4B. Its flash area
            # is erased; never upload a locally calculated crossover preview.
            if actual[offset:offset+capacity*4]!=b'\xff'*(capacity*4):
                add(frame(0x58,(offset//4096).to_bytes(2,'little')),f'channels[{ch}].fir.clear')
                actual=actual[:offset]+b'\xff'*(capacity*4)+actual[offset+capacity*4:];fir_channels.append(ch)
            continue
        current=doc.decoded()['channels'][ch]
        old_count=current['fir_coefficient_count_raw'] if ch<4 else current['fir_tap_parameter_raw']
        old=actual[offset:offset+capacity*4]
        if values:
            prefix=struct.pack('<'+str(count)+'f',*values)
            if old_count==count and old[:count*4]==prefix and (ch<4 or current['fir_type_raw']==4):continue
            if ch<4 and len(values)>512:raise ValueError('PRS input FIR exceeds512 taps per input')
            plan=prepare_fir_upload(bytes(doc.data),actual,ch,values)
            for raw in plan.frames:add(raw,f'channels[{ch}].fir.coefficients')
            actual=plan.expected_bank;fir_channels.append(ch)
        else:
            # Marker means an identity, not NaNs to transmit. If the retained
            # count differs, use the confirmed4E count effect then erase, like
            # the OEM marker branch. Never fabricate a dedicated count setter.
            if old_count!=count:
                if not 1<=count<=(512 if ch<4 else 1024):raise ValueError('PRS empty FIR count cannot be reproduced within the supported profile')
                plan=prepare_fir_upload(bytes(doc.data),actual,ch,(1.0,)+(0.0,)*(count-1))
                for raw in plan.frames:add(raw,f'channels[{ch}].fir.count')
                actual=plan.expected_bank;old=actual[offset:offset+capacity*4]
            if old!=b'\xff'*(capacity*4):
                for sector in range(offset//4096,(offset+capacity*4)//4096):add(frame(0x58,sector.to_bytes(2,'little')),f'channels[{ch}].fir.clear')
                actual=actual[:offset]+b'\xff'*(capacity*4)+actual[offset+capacity*4:];fir_channels.append(ch)
    before,issues=project_state(doc,DeviceModel().to_dict(),strict=False)
    if issues:raise ValueError('Current PRS projection unsupported: '+str(issues[:3]))
    a,b=before.to_dict(),wanted.to_dict()
    a['settings']['delay_unit']=b['settings']['delay_unit']
    for old,new in zip(a['inputs']+a['outputs'],b['inputs']+b['outputs']):
        old['fir']['coefficients']=new['fir']['coefficients']=[]
        old['fir']['path']=new['fir']['path']=''
    plan=plan_changes(a,b,raw_state=doc.decoded())
    if plan.blocked or plan.local_only:raise ValueError('PRS contains unsupported changes: '+str(plan.blocked+plan.local_only)[:700])
    supported={0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x38,0x3A,0x3D,0x3E,0x3F,0x41,0x5B,0x4B,0x4C,0x4F}
    def output_design(ch):
        r=rows[ch]
        return frame(0x4B,encode_payload(0x4B,ch,type_raw=r['fir_type_raw'],window_raw=r['fir_window_raw'],hp_frequency_position_raw=r['fir_hp_frequency_position_raw'],lp_frequency_position_raw=r['fir_lp_frequency_position_raw'],tap_parameter_raw=r['fir_tap_parameter_raw']))
    # Ordinary fields first; restore FIR allocation only after counts/designs.
    late=[];designed=set()
    for p in plan.packets:
        if p.command not in supported:raise ValueError('Unsupported PRS command '+hex(p.command))
        if p.command in (0x4F,0x4C):late.append((frame(p.command,p.payload),p.path));continue
        if p.command==0x35:continue
        if p.command==0x4B:
            ch=p.payload[0];raw=output_design(ch);designed.add(ch)
            if rows[ch]['fir_type_raw'] in (1,2,3):
                off=32768+(ch-4)*4096;actual=actual[:off]+b'\xff'*4096+actual[off+4096:]
            add(raw,p.path)
        else:add(frame(p.command,p.payload),p.path)
    for ch in range(4,12):
        off=32768+(ch-4)*4096
        if rows[ch]['fir_type_raw'] in (1,2,3) and ch not in designed and actual[off:off+4096]!=b'\xff'*4096:
            add(output_design(ch),f'outputs[{ch-4}].fir.design');actual=actual[:off]+b'\xff'*4096+actual[off+4096:]
    for raw,path in late:add(raw,path)
    # Build the final native groups only after every independent channel has
    # the target fields/FIR. Reject conflicting FIR prefixes within a group;
    # native Link always copies the lowest member's stored coefficients.
    target_areas=fir_areas(target,prs[FIR_START:FIR_END])
    for group in topology(masks(target)):
        if len(group)<2:continue
        source=group[0]
        if any(target_areas[t][3]!=target_areas[source][3] for t in group):raise ValueError('PRS linked channels contain different FIR coefficients')
        p=prepare_link(bytes(doc.data),actual,source,group)
        frames.extend(p.frames);paths.extend(f'channels[{source}].link' for _ in p.frames)
        doc=SourceDocument(p.expected_state);actual=p.expected_bank
        known=bytearray(a&b for a,b in zip(known,p.bank_known))
    # Link copies FIR names; their dedicated name setter permits independent
    # labels, so restore target labels after the native copies.
    for ch in range(12):
        at=1460+8*ch
        if doc.data[at:at+8]!=target[at:at+8]:add(frame(0x5B,bytes((ch,))+target[at:at+8]),f'channels[{ch}].fir.name')
    # A successful native storage prediction alone is insufficient if a source
    # quirk (notably Link's literal0x0FFFFFFF) would lose requested numeric taps.
    # Reject that file before I/O rather than certifying the wrong FIR prefix.
    for offset,capacity,count,values in target_areas:
        if values and actual[offset:offset+count*4]!=struct.pack('<'+str(count)+'f',*values):
            raise ValueError('Native Link cannot reproduce the requested FIR coefficient prefix')
    name=target[2:16]
    if bytes(doc.data[2:16])!=name:
        from dsp408.preset_store import encode_name
        if encode_name(name.decode('ascii'))!=name:raise ValueError('PRS configuration name requires printable ASCII14')
        frames.insert(0,frame(0x26,name));paths.insert(0,'preset.name');doc.data[2:16]=name
    # Mute is deliberately held until the full state and bank match.
    from dsp408.channel_link import set_mute
    for ch in range(12):
        off,bit=(1432,ch) if ch<4 else (1434,ch-4)
        doc.data[:]=set_mute(bytes(doc.data),ch,bool(int.from_bytes(target[off:off+2],'little')&(1<<bit)))
    residual=[i for i,(x,y) in enumerate(zip(doc.data,target)) if x!=y]
    if residual:raise ValueError('PRS has unrepresented parameter bytes: '+str(residual[:40]))
    # A genuinely identical configuration needs no disable/re-enable writes.
    if target==state and all(not k or a==b for a,b,k in zip(actual,bank,known)):
        frames=[];paths=[];actual=bank;known=bytearray(b'\1'*65536)
    states=tuple(frame(0x27,bytes((i,))) for i in range(32))
    banks=tuple(frame(0x56,b'\0'+i.to_bytes(2,'little')) for i in range(1261))
    cat=(frame(0x22,b''),frame(0x14,b''))
    final=tuple(frame(0x35,bytes((ch,mute_flag(target,ch)))) for ch in range(12))
    mutations=target!=state or actual!=bank
    requests=cat+states+banks+((tuple(frame(0x35,bytes((ch,1))) for ch in range(12))+states+tuple(frames)+states+banks+final+states) if mutations else ())+cat
    permit=FullPrsPermit(state,bank,prs,tuple(frames),target,actual,bytes(known),requests)
    packets=[{'command':hex(raw[5]),'payload_hex':raw[6:-3].hex(),'path':path} for raw,path in zip(frames,paths)]
    return permit,{'source_plan_complete':True,'blockers':[],'packets':packets,'fir_channels':sorted(set(fir_channels)),
        'fir_different_bytes':sum(x!=y for x,y in zip(bank,actual)),'residual_parameter_offsets':[],
        'scope':'Full PRS configuration and FIR','hardware_enabled':True}


class FullPrsOperation(PrsApplyRehearsal):
    def check_port(self,port):
        from dsp408.prs_usb_import import PRS_IMPORT_AUTHORIZED
        if not PRS_IMPORT_AUTHORIZED:raise ValueError('PRS import authorization disabled')
    def report(self,stage,waiting=False):
        self.progress({'busy':True,'operation':'prs_import','stage':stage,'done':self.done,'total':self.TOTAL,'waiting':waiting})
    def exchange(self,raw,*args,**kwargs):
        self.check_port(self.port);self.port.arm_prs_request(raw,self.permit)
        return super().exchange(raw,*args,**kwargs)
    def run_import(self,permit):
        if type(permit) is not FullPrsPermit or prepare_full_import(permit.state,permit.bank,permit.prs)[0]!=permit:raise ValueError('Full PRS permit differs from canonical plan')
        self.permit=permit;self.TOTAL=len(permit.requests);self.port.begin_prs_import(permit)
        try:
            cat=self.exchange(frame(0x22,b''),0x22,'Checking preset catalog')
            active=self.exchange(frame(0x14,b''),0x14,'Checking active slot')
            if len(cat)!=19 or len(active)!=1 or not 1<=active[0]<=19:raise ValueError('Invalid PRS catalog/slot')
            if self.state('Reading current parameters')!=permit.state:raise ValueError('Parameters changed since PRS review')
            if self.bank('Reading complete current FIR')!=permit.bank:raise ValueError('FIR changed since PRS review')
            self.record({'kind':'prs_full_baseline','state_hex':permit.state.hex(),'bank_hex':permit.bank.hex(),'catalog_hex':cat.hex(),'active_slot':active[0],'prs_sha256':hashlib.sha256(permit.prs).hexdigest(),'prs_hex':permit.prs.hex()})
            def send(raw,path):
                self.record({'kind':'setter_intent','operation':'prs_import','path':path,'frame_hex':raw.hex()})
                self.exchange(raw,1,path,expected_payload=active+raw[6:-3] if raw[5]==0x26 else None,
                              **({'timeout':10.} if raw[5]==0x3B else {}))
            actual=permit.bank
            if permit.state!=permit.expected_state or permit.bank!=permit.expected_bank:
                for ch in range(12):send(frame(0x35,bytes((ch,1))),'Temporarily muting channels')
                if self.state('Checking Mute')!=muted(permit.state):raise ValueError('Mute readback differs; import stopped')
                for raw in permit.frames:send(raw,'Applying PRS configuration and FIR')
                if self.state('Verifying parameters before unmute')!=muted(permit.expected_state):raise ValueError('PRS parameters differ; channels remain muted')
                actual=self.bank('Verifying complete FIR before unmute')
                if any(k and a!=b for a,b,k in zip(actual,permit.expected_bank,permit.bank_known)):raise ValueError('PRS FIR differs; channels remain muted')
                for ch in range(12):
                    send(frame(0x35,bytes((ch,mute_flag(permit.expected_state,ch)))),'Applying target Mute')
                if self.state('Checking final parameters')!=permit.expected_state:raise ValueError('Final PRS state differs')
            if self.exchange(frame(0x22,b''),0x22,'Checking catalog')!=cat:raise ValueError('PRS catalog changed')
            if self.exchange(frame(0x14,b''),0x14,'Checking active slot')!=active:raise ValueError('PRS slot changed')
            self.port.complete_prs_import(permit)
            result={'operation':'prs_import','full_prs':True,'hardware_enabled':True,'parameters_verified':True,'bank_hex':actual.hex(),
                'fir_bank_unchanged':permit.bank==actual,'unpredicted_unused_padding_bytes':permit.bank_known.count(0),'state_sha256':hashlib.sha256(permit.expected_state).hexdigest(),
                'bank_sha256':hashlib.sha256(actual).hexdigest(),'done':self.done,'total':self.TOTAL,'audio_verified':False,'power_cycle_persistence_verified':False}
            self.record({'kind':'prs_full_verified',**result});self.progress({'busy':True,**result})
            return permit.expected_state,result
        finally:self.port.end_prs_import()
