"""In-memory protocol exercise. No USB/Ethernet I/O or vendor code execution.

Applies packet byte fields to a local source-layout document, NOT a DSP emulator.
No simulated acknowledgement is accepted as evidence of a physical write.
"""
import json
import struct
import hashlib
from pathlib import Path
from dsp408.editor_state_research import decode_state,StateBlockAssembler
from dsp408.editor_tx_research import decode_tx_payload,source_gain_db
from dsp408.source_bindings import plan_changes
from dsp408.source_codec import frame,frequency_hz
from dsp408.wire_research import decode_editor_frame
from dsp408.model import DeviceModel,FILTER_TYPES,CROSS_TYPES,FIR_TYPES,FIR_WINDOWS
from dsp408.editor_profile import Q_VALUES,RATIO_VALUES,DETECTOR_TYPES,SINE_FREQUENCIES


class SourceDocument:
    def __init__(self,data,layout='common-prefix1556',*,origin='explicit local file'):
        decode_state(data,layout=layout)
        self.data=bytearray(data);self.layout=layout;self.origin=origin;self.coefficients={}
        self.original_sha256=hashlib.sha256(data).hexdigest()
        self._fir_pending={}
        self.global_fields={}

    def decoded(self):return decode_state(self.data,layout=self.layout)

    def apply(self,packet):
        """Mutates document fields only; processing/persistence are not simulated."""
        f=decode_editor_frame(packet);op=f.command;p=f.data
        if op in (0x39,0x4D):
            decode_tx_payload(op,p)
            if op==0x39:
                if p[0]>3 or p[1]>=len(SINE_FREQUENCIES):raise ValueError('Global generator value outside source profile')
                self.global_fields['test_tone']=['ANALOG INPUT','PINK NOISE','WHITE NOISE','SINE'][p[0]]
                self.global_fields['sine_hz']=SINE_FREQUENCIES[p[1]]
            else:
                if p[0]>1 or p[1]>1:raise ValueError('Global I/O selector outside source profile')
                self.global_fields['input_select' if p[0]==0 else 'output_select']=['ANALOG','AES / EBU'][p[1]]
            return
        if op in (0x3D,0x5B):
            if len(p)!=9 or p[0]>=12:raise ValueError('Name payload extent')
        elif op==0x4F:
            if len(p)!=2 or p[0]>=4:raise ValueError('Input FIR bypass payload extent')
        else:decode_tx_payload(op,p)
        ch=p[0];is_input=ch<4;base=16+138*ch if is_input else 568+108*(ch-4)
        # Link resolver/copy scope is not reproduced by this document reducer.
        group=self.decoded()['channels'][:4] if is_input else self.decoded()['channels'][4:]
        if op not in (0x3D,0x5B,0x3A,0x41) and any(c['link_mask_raw'] not in (0,1<<i) for i,c in enumerate(group)):
            raise ValueError('Linked raw state requires MCU resolver/copy semantics; local reducer refuses')
        def put(relative,data):self.data[base+relative:base+relative+len(data)]=data
        def mask(offset,bit,flag):
            raw=int.from_bytes(self.data[offset:offset+2],'little');raw=raw|(1<<bit) if flag else raw&~(1<<bit)
            self.data[offset:offset+2]=struct.pack('<H',raw)
        if op==0x34:put(130 if is_input else 100,p[1:3])
        elif op==0x38:put(134 if is_input else 104,p[1:3])
        elif op==0x36:put(132 if is_input else 102,bytes((p[1],0)))
        elif op==0x35:mask(1432 if is_input else 1434,ch if is_input else ch-4,p[1])
        elif op==0x33:
            put((64 if is_input else 36)+6*p[1],p[2:8])
            mask((1436+2*ch) if is_input else (1444+2*(ch-4)),p[1],p[8])
        elif op==0x30:put(112,p[1:])
        elif op==0x3E:put(8,p[1:])
        elif op==0x3F:put(90,p[1:])
        elif op in (0x31,0x32):
            side=0 if op==0x32 else 1
            put(20+2*side,p[1:3]);put(24+side,p[3:4]);put(26+side,p[4:5])
        elif op==0x4B:
            if is_input:raise ValueError('Input4B does not design filters in audited MCU')
            put(28,p[1:3]);put(30,p[3:])
        elif op==0x4C:put(18,bytes((p[1],0)))
        elif op==0x3A:put(8,bytes((p[1],0)))
        elif op==0x41:put(10+2*p[1],p[2:4])
        elif op==0x3D:put(0,p[1:])
        elif op==0x5B:self.data[1460+8*ch:1468+8*ch]=p[1:]
        elif op==0x4F:put(128,bytes((p[1],0)))
        elif op==0x4E:
            block=p[1];total=int.from_bytes(p[2:4],'little')
            if block==0 and ch not in self._fir_pending:self._fir_pending[ch]=(total,{})
            if ch not in self._fir_pending or self._fir_pending[ch][0]!=total:raise ValueError('FIR local transfer must start with block0 and consistent total')
            blocks=self._fir_pending[ch][1]
            if block in blocks and blocks[block]!=p[4:]:raise ValueError('Conflicting FIR duplicate')
            blocks[block]=p[4:]
            count=(total+11)//12
            if all(i in blocks for i in range(count)):
                raw=b''.join(blocks[i] for i in range(count));self.coefficients[ch]=list(struct.unpack('>'+'f'*total,raw));del self._fir_pending[ch]
                # MCU9396 called on the final4E chunk: input count at126;
                # output type becomes External(4) and relative34 is the count.
                # Storage/DSP side effects remain outside this document reducer.
                if is_input:put(126,struct.pack('<H',total))
                else:put(28,b'\x04');put(34,struct.pack('<H',total))
        else:raise ValueError('No local document reducer for this family')

    def read_blocks(self):
        return [bytes((i,))+bytes(self.data[50*i:50*i+50]) for i in range(32)]


def project_state(document,previous,*,strict=True):
    """Project confirmed fields to model; unknown/unrepresentable fields retained raw.

    No silently guessed enum conversion. Each unsupported field has a report.
    The model is built and validated before the caller may replace UI state.
    strict=False validates once at the end and rejects invalid numeric states
    atomically. Interactive control uses this path; diagnostic imports retain
    the default per-field validation/reporting of unrepresentable values.
    """
    result=DeviceModel.from_dict(previous);issues=[];raw=document.decoded()
    if hasattr(result,'device_link_masks'):del result.device_link_masks
    original_links=result.links[:];result.links=[False]*12
    def apply(ch,key,value,band=-1):
        parts=key.split('.');obj=result.channels[ch]
        if parts[0]=='filters':obj=obj.filters[band];parts=parts[1:]
        for part in parts[:-1]:obj=getattr(obj,part)
        previous_value=getattr(obj,parts[-1]);setattr(obj,parts[-1],value)
        try:
            if strict:result.validate()
        except (ValueError,TypeError) as e:
            setattr(obj,parts[-1],previous_value)
            issues.append({'path':f'channel[{ch}].{key}','reason':str(e),'raw_preserved':True})
    def selected(raw_value,choices,path):
        if not 0<=raw_value<len(choices):raise ValueError('Unknown '+path+' enum '+str(raw_value))
        return choices[raw_value]
    for ch,s in enumerate(raw['channels']):
        def safe(fn,path):
            try:fn()
            except ValueError as e:issues.append({'path':f'channel[{ch}].{path}','reason':str(e),'raw_preserved':True})
        def gain():
            g=source_gain_db(s['gain_raw'])
            if g is None:raise ValueError('Gain outside source profile')
            apply(ch,'gain',g)
        safe(gain,'gain');apply(ch,'mute',s['mute_mask_bit']);apply(ch,'delay_ms',s['delay_raw']/96)
        if s['polarity_raw'] in (0,1):apply(ch,'polarity_inverted',bool(s['polarity_raw']))
        else:issues.append({'path':f'channel[{ch}].polarity','reason':'Unknown non-boolean raw polarity','raw_preserved':True})
        def name():
            try:value=bytes.fromhex(s['name_bytes_hex']).split(b'\0',1)[0].decode('ascii')
            except UnicodeDecodeError as e:raise ValueError('Unknown manufacturer name codepage') from e
            if value:apply(ch,'name',value)
        safe(name,'name')
        def fir_name():
            try:value=bytes.fromhex(raw['fir_name_bytes_hex'][ch]).split(b'\0',1)[0].decode('ascii')
            except UnicodeDecodeError as e:raise ValueError('Unknown manufacturer FIR name codepage') from e
            apply(ch,'fir.name',value)
        safe(fir_name,'fir.name')
        apply(ch,'eq_bypass',False)
        for band,p in enumerate(s['peq']):
            safe(lambda p=p,band=band:apply(ch,'filters.frequency',frequency_hz(p['frequency_position_raw']),band),f'filters[{band}].frequency')
            apply(ch,'filters.gain',(p['gain_raw']-120)/10,band)
            safe(lambda p=p,band=band:apply(ch,'filters.q',selected(p['q_index_raw'],Q_VALUES,'Q'),band),f'filters[{band}].q')
            apply(ch,'filters.enabled',not p['bypass_mask_bit'],band)
            safe(lambda p=p,band=band:apply(ch,'filters.kind',selected(p['type_raw'],FILTER_TYPES,'PEQ type'),band),f'filters[{band}].kind')
        def dynamics(section,words):
            ratio,attack,release,knee,threshold=words
            apply(ch,section+'.ratio_limit',ratio==15)
            if ratio<15:apply(ch,section+'.ratio',selected(ratio,RATIO_VALUES,'ratio'))
            elif ratio!=15:raise ValueError('Unknown ratio position')
            for key,value in (('attack_ms',attack+1),('release_ms',release+1),('knee',knee),('threshold',(threshold-180)/2)):
                apply(ch,section+'.'+key,value)
        if ch<4:
            attack,release,hold,threshold=s['gate_words_raw']
            for key,value in (('attack_ms',attack+1),('release_ms',release+1),('hold_ms',hold+1),('threshold',(threshold-180)/2)):
                apply(ch,'gate.'+key,value)
            c=s['compressor']
            safe(lambda:dynamics('compressor',[c[k] for k in ('ratio_raw','attack_raw','release_raw','knee_raw','threshold_raw')]),'compressor')
            safe(lambda:apply(ch,'compressor.detector_frequency',frequency_hz(c['detector_frequency_position_raw'])),'detector_frequency')
            safe(lambda:apply(ch,'compressor.detector_type',selected(c['detector_type_raw'],DETECTOR_TYPES,'detector')),'detector_type')
            value=s['fir_bypass_raw']
            if value in (0,1):apply(ch,'fir.bypass',bool(value))
            else:issues.append({'path':f'channel[{ch}].fir.bypass','reason':'Unknown non-boolean FIR bypass','raw_preserved':True})
        else:
            safe(lambda:dynamics('limiter',s['limiter_words_raw']),'limiter')
            safe(lambda:apply(ch,'crossover_mode',selected(s['crossover_processing_mode_raw'],['IIR','FIR'],'processing')),'crossover_mode')
            for side in ('hp','lp'):
                type_raw=s['iir_'+side+'_type_raw'];key='hpf' if side=='hp' else 'lpf'
                apply(ch,key+'_bypass',type_raw==0)
                if type_raw:safe(lambda type_raw=type_raw,key=key:apply(ch,key+'_type',selected(type_raw-1,CROSS_TYPES,'IIR')) ,key+'_type')
                safe(lambda side=side,key=key:apply(ch,key+'_hz',frequency_hz(s['iir_'+side+'_frequency_position_raw'])),key+'_hz')
            for i,value in enumerate(s['mix_words_raw']):
                g=source_gain_db(value)
                if g is None or g>0:issues.append({'path':f'routing_gains[{ch-4}][{i}]','reason':'Mix outside model profile','raw_preserved':True})
                else:result.routing_gains[ch-4][i]=g
            if s['routing_raw']&~15:issues.append({'path':f'routing[{ch-4}]','reason':'Unknown high routing bits retained','raw_preserved':True})
            result.routing[ch-4]=[bool(s['routing_raw']&(1<<i)) for i in range(4)]
            typ=s['fir_type_raw'];apply(ch,'fir.bypass',typ==0)
            safe(lambda:apply(ch,'fir.mode',selected(typ,FIR_TYPES,'FIR')),'fir.mode')
            safe(lambda:apply(ch,'fir.window',selected(s['fir_window_raw'],FIR_WINDOWS,'FIR window')),'fir.window')
            for side in ('hp','lp'):
                safe(lambda side=side:apply(ch,'fir.'+('hpf_hz' if side=='hp' else 'lpf_hz'),frequency_hz(s['fir_'+side+'_frequency_position_raw'])),'fir.frequency')
            if typ in (1,2,3):apply(ch,'fir.taps',256+32*s['fir_tap_parameter_raw'])
        if ch in document.coefficients:apply(ch,'fir.coefficients',document.coefficients[ch])
    result.settings.update(document.global_fields)
    result.links=original_links;result.validate()
    from dsp408.channel_link import masks,topology
    try:
        from dsp408.channel_link import self_mask
        values=masks(document.data);topology(values)
        if any(v!=self_mask(i) for i,v in enumerate(values)):result.device_link_masks=values
    except ValueError:pass
    return result,issues


class LocalSourceSession:
    def __init__(self,snapshot,document=None):
        self.active=True;self.previous=snapshot;self.entries=[];self.total_packets=0;self.sequence=0;self.latest=None;self.pending={}
        if document is None:
            # Explicitly synthetic unknown bytes/type fields, NOT manufacturer defaults.
            fixture=bytearray(1556)
            for ch in range(12):
                base=16+138*ch if ch<4 else 568+108*(ch-4)
                struct.pack_into('<H',fixture,base+(136 if ch<4 else 106),1<<(ch if ch<4 else ch-4))
            document=SourceDocument(fixture,origin='synthetic fixture; independent own-bit masks, opaque co-fields zero, known values from model')
            plan=plan_changes(snapshot,snapshot,raw_state=document.decoded(),full=True)
            for p in plan.packets:
                document.apply(frame(p.command,p.payload,snapshot['settings']['device_id']))
            self.initial_issues=plan.blocked
        else:self.initial_issues=[]
        self.document=document

    def observe(self,snapshot):
        plan=plan_changes(self.previous,snapshot,raw_state=self.document.decoded())
        self.previous=snapshot
        if not (plan.packets or plan.blocked or plan.local_only):return
        self.sequence+=1;address=snapshot['settings']['device_id']
        record=plan.record(address);record['sequence']=self.sequence;record['origin']=self.document.origin
        record['local_apply_errors']=[]
        for p in plan.packets:
            try:
                self.document.apply(frame(p.command,p.payload,address))
                self.pending.pop(p.path,None)
            except ValueError as e:record['local_apply_errors'].append({'path':p.path,'reason':str(e)})
        for error in record['blocked']+record['local_apply_errors']:self.pending[error['path']]=error
        self.total_packets+=len(plan.packets);self.entries.append(record);self.entries=self.entries[-200:];self.latest=record

    def report(self):
        return {'scope':'LOCAL SOURCE TEST — no physical I/O', 'hardware_verified':False,'active':self.active,
                'origin':self.document.origin,'total_packets':self.total_packets,'retained_batches':len(self.entries),
                'initial_issues':self.initial_issues,'projection_issues':getattr(self,'projection_issues',[]),
                'pending':list(self.pending.values()),'entries':self.entries,'state':self.document.decoded(),
                'raw_state_hex':bytes(self.document.data).hex(),'state_sha256':hashlib.sha256(self.document.data).hexdigest(),
                'original_sha256':self.document.original_sha256,
                'global_fields_from_local_tx':self.document.global_fields,
                'fir_coefficients_from_local_tx':self.document.coefficients}

    def readback(self,previous):
        collector=StateBlockAssembler(layout=self.document.layout)
        # Exercises actual block decoder, including strict completeness.
        for payload in reversed(self.document.read_blocks()):collector.add(payload)
        document=SourceDocument(collector.data(),self.document.layout,origin=self.document.origin)
        document.coefficients=self.document.coefficients.copy()
        document.global_fields=self.document.global_fields.copy()
        return project_state(document,previous)

    def save(self,path):
        destination=Path(path);temporary=destination.with_name(destination.name+'.tmp')
        try:
            temporary.write_text(json.dumps(self.report(),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            temporary.replace(destination)
        finally:
            if temporary.exists():temporary.unlink()
