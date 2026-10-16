"""Model -> reviewable, local-only EXE packet plan; never a hardware driver."""
from dataclasses import dataclass,field
from dsp408.model import DeviceModel,FILTER_TYPES,CROSS_TYPES,FIR_TYPES,FIR_WINDOWS
from dsp408.editor_profile import DETECTOR_TYPES,Q_VALUES,SINE_FREQUENCIES
from dsp408.source_codec import (encode_payload,encode_global,frame,gain_raw,frequency_raw,
                                frequency_hz,q_raw,ratio_raw,quantize,choice_raw,fir_chunks)
from dsp408.editor_tx_research import source_gain_db


@dataclass
class Packet:
    command:int
    payload:bytes
    path:str
    notes:list=field(default_factory=list)

    def record(self,address):
        return {'command':f'0x{self.command:02X}','payload_hex':self.payload.hex(' '),
                'frame_hex':frame(self.command,self.payload,address).hex(' '),
                'path':self.path,'notes':self.notes}


@dataclass
class Plan:
    packets:list=field(default_factory=list)
    blocked:list=field(default_factory=list)
    local_only:list=field(default_factory=list)

    def record(self,address=1):
        return {'scope':'EXE V1.12 source profile, offline only; NOT a hardware upload script',
                'hardware_verified':False,'address':address,'packets':[p.record(address) for p in self.packets],
                'blocked':self.blocked,'local_only':self.local_only}


def ascii_name(name):
    try:raw=name.encode('ascii')
    except UnicodeEncodeError as e:raise ValueError('Only ASCII names have an unambiguous eight-byte source representation') from e
    if len(raw)>8 or b'\0' in raw:raise ValueError('Source name requires at most eight ASCII bytes, without NUL')
    return raw.ljust(8,b'\0')


def plan_changes(before,after,*,raw_state=None,full=False):
    """Unknown co-fields MUST come from explicit raw_state, never guessed defaults.

    Quantization is an explicit local policy (nearest source position); it is
    reported, does not change JSON or claim the vendor's inverse rounding.
    """
    before=DeviceModel.from_dict(before).to_dict();after=DeviceModel.from_dict(after).to_dict()
    return _plan_validated_changes(before,after,raw_state=raw_state,full=full)


def _plan_validated_changes(before,after,*,raw_state=None,full=False):
    """Internal planner for independent, already validated model snapshots.

    Public plan_changes validates both inputs. USB prepare has already projected
    and validated its before model, and must validate wanted before entering here.
    This does not bypass opcode, co-field, authorization or write-arm checks.
    """
    plan=Plan();old=before['inputs']+before['outputs'];new=after['inputs']+after['outputs']
    def changed(a,b):return full or a!=b
    for ch,(a,b) in enumerate(zip(old,new)):
        prefix=f'channel[{ch}]'
        seed=raw_state['channels'][ch] if raw_state else None
        def emit(command,path,notes=None,**fields):
            plan.packets.append(Packet(command,encode_payload(command,ch,**fields),prefix+'.'+path,notes or []))
        def attempt(path,action):
            try:action()
            except (ValueError,KeyError,OverflowError) as e:plan.blocked.append({'path':prefix+'.'+path,'reason':str(e)})
        def require_seed():
            if seed is None:raise ValueError('Requires imported raw state to preserve unknown co-fields')
            return seed
        def preserve(section,key,raw_key,convert,raw_fields):
            if raw_fields is not None and not full and a[section][key]==b[section][key]:return raw_fields[raw_key]
            return convert(b[section][key])
        for key,opcode,field_name,convert in (
            ('gain',0x34,'gain_raw',gain_raw),('delay_ms',0x38,'delay_raw',lambda x:quantize(x,96,high=65280)),
            ('mute',0x35,'flag_raw',int),('polarity_inverted',0x36,'flag_raw',int),('name',0x3D,'name_bytes',ascii_name)):
            if changed(a[key],b[key]):
                def simple(key=key,opcode=opcode,field_name=field_name,convert=convert):
                    raw=convert(b[key]);notes=[]
                    display=source_gain_db(raw) if key=='gain' else raw/96 if key=='delay_ms' else b[key]
                    if display!=b[key]:notes.append({'requested':b[key],'represented':display})
                    if key=='gain' and raw==0:notes.append('MCU raw0 forces zero result; source label -60dB is not finite attenuation proof')
                    emit(opcode,key,notes,**{field_name:raw})
                attempt(key,simple)
        for band,(fa,fb) in enumerate(zip(a['filters'],b['filters'])):
            if changed(fa,fb) or changed(a['eq_bypass'],b['eq_bypass']):
                def peq():
                    s=seed['peq'][band] if seed else None
                    def field(key,raw_key,convert):
                        return s[raw_key] if s and not full and fa[key]==fb[key] else convert(fb[key])
                    kind=field('kind','type_raw',lambda v:choice_raw(v,FILTER_TYPES))
                    f=field('frequency','frequency_position_raw',frequency_raw);q=field('q','q_index_raw',q_raw)
                    g=field('gain','gain_raw',lambda v:quantize(v,10,120,0,240))
                    emit(0x33,f'filters[{band}]',[{'requested_frequency':fb['frequency'],'represented_frequency':frequency_hz(f) if f<=300 else None,
                         'requested_q':fb['q'],'represented_q':Q_VALUES[q] if q<len(Q_VALUES) else None,'requested_gain':fb['gain'],'represented_gain':(g-120)/10}],
                         band_index=band,gain_raw=g,frequency_position_raw=f,q_index_raw=q,type_raw=kind,
                         bypass_raw=int(b['eq_bypass'] or not fb['enabled']))
                attempt(f'filters[{band}]',peq)
        if ch<4:
            if changed(a['gate'],b['gate']):
                g=b['gate']
                def gate():
                    raw=dict(zip(('attack_raw','release_raw','hold_raw','threshold_raw'),seed['gate_words_raw'])) if seed else None
                    emit(0x3E,'gate',**{rk:preserve('gate',k,rk,cv,raw) for k,rk,cv in (
                        ('attack_ms','attack_raw',lambda v:quantize(v-1,high=998)),('release_ms','release_raw',lambda v:quantize(v-1,low=9,high=2999)),
                        ('hold_ms','hold_raw',lambda v:quantize(v-1,low=9,high=998)),('threshold','threshold_raw',lambda v:quantize(v,2,180,0,180)))})
                attempt('gate',gate)
            if changed(a['compressor'],b['compressor']):
                def comp():
                    d=b['compressor'];s=require_seed()['compressor']
                    ratio=s['ratio_raw'] if not full and all(a['compressor'][k]==d[k] for k in ('ratio','ratio_limit')) else ratio_raw(d['ratio'],d['ratio_limit'])
                    emit(0x30,'compressor',ratio_raw=ratio,unknown_byte=s['unknown_byte'],**{rk:preserve('compressor',k,rk,cv,s) for k,rk,cv in (
                        ('attack_ms','attack_raw',lambda v:quantize(v-1,high=998)),('release_ms','release_raw',lambda v:quantize(v-1,low=9,high=2999)),
                        ('knee','knee_raw',lambda v:quantize(v,high=12)),('threshold','threshold_raw',lambda v:quantize(v,2,180,0,220)),
                        ('detector_frequency','detector_frequency_position_raw',frequency_raw),('detector_type','detector_type_raw',lambda v:choice_raw(v,DETECTOR_TYPES)))})
                attempt('compressor',comp)
            if changed(a['fir']['bypass'],b['fir']['bypass']):
                attempt('fir.bypass',lambda:emit(0x4F,'fir.bypass',flag_raw=int(b['fir']['bypass'])))
            if changed(a['fir']['mode'],b['fir']['mode']) or any(changed(a['fir'][k],b['fir'][k]) for k in ('window','taps','hpf_hz','lpf_hz')):
                plan.local_only.append({'path':prefix+'.fir.design','reason':'MCU4B input design returns without designing; import4E is separate'})
        else:
            d=b['limiter']
            if any(changed(a['limiter'][k],d[k]) for k in ('ratio','ratio_limit','attack_ms','release_ms','knee','threshold')):
                def limit():
                    raw=dict(zip(('ratio_raw','attack_raw','release_raw','knee_raw','threshold_raw'),seed['limiter_words_raw'])) if seed else None
                    ratio=raw['ratio_raw'] if raw and not full and all(a['limiter'][k]==d[k] for k in ('ratio','ratio_limit')) else ratio_raw(d['ratio'],d['ratio_limit'])
                    emit(0x3F,'limiter',ratio_raw=ratio,**{rk:preserve('limiter',k,rk,cv,raw) for k,rk,cv in (
                        ('attack_ms','attack_raw',lambda v:quantize(v-1,high=998)),('release_ms','release_raw',lambda v:quantize(v-1,low=9,high=2999)),
                        ('knee','knee_raw',lambda v:quantize(v,high=12)),('threshold','threshold_raw',lambda v:quantize(v,2,180,0,220)))})
                attempt('limiter',limit)
            if changed(a['limiter'],d):
                for k in ('detector_frequency','detector_type'):
                    if a['limiter'][k]!=d[k]:plan.local_only.append({'path':prefix+'.limiter.'+k,'reason':'No detector field in LIMIT payload'})
            if changed(a['crossover_mode'],b['crossover_mode']):
                attempt('crossover_mode',lambda:emit(0x4C,'crossover_mode',processing_mode_raw=choice_raw(b['crossover_mode'],['IIR','FIR'])))
            for side,opcode in (('hpf',0x32),('lpf',0x31)):
                keys=[side+k for k in ('_hz','_type','_bypass')]
                if any(changed(a[k],b[k]) for k in keys):
                    def cross(side=side,opcode=opcode):
                        s=require_seed();aux=s['iir_'+('hp' if side=='hpf' else 'lp')+'_aux_raw']
                        rawside='hp' if side=='hpf' else 'lp'
                        frequency=s['iir_'+rawside+'_frequency_position_raw'] if not full and a[side+'_hz']==b[side+'_hz'] else frequency_raw(b[side+'_hz'])
                        typ=s['iir_'+rawside+'_type_raw'] if not full and all(a[side+k]==b[side+k] for k in ('_type','_bypass')) else (0 if b[side+'_bypass'] else choice_raw(b[side+'_type'],CROSS_TYPES)+1)
                        emit(opcode,side,frequency_position_raw=frequency,type_raw=typ,aux_raw=aux)
                    attempt(side,cross)
            designkeys=('mode','window','taps','hpf_hz','lpf_hz','bypass')
            if any(changed(a['fir'][k],b['fir'][k]) for k in designkeys):
                def design():
                    f=b['fir'];s=require_seed();type_changed=full or any(a['fir'][k]!=f[k] for k in ('mode','bypass'))
                    kind=(0 if f['bypass'] else choice_raw(f['mode'],FIR_TYPES)) if type_changed else s['fir_type_raw']
                    tap=(f['taps']-256)//32 if kind in (1,2,3) and (type_changed or changed(a['fir']['taps'],f['taps'])) else s['fir_tap_parameter_raw']
                    def field(key,raw_key,convert):
                        return s[raw_key] if not full and a['fir'][key]==f[key] else convert(f[key])
                    from dsp408.source_codec import fir_frequency_raw
                    emit(0x4B,'fir.design',['FIR synthesis remains MCU-side; local formula research is not bit-identical'],
                         type_raw=kind,window_raw=field('window','fir_window_raw',lambda v:choice_raw(v,FIR_WINDOWS)),
                         hp_frequency_position_raw=field('hpf_hz','fir_hp_frequency_position_raw',lambda v:fir_frequency_raw(v,'hp')),
                         lp_frequency_position_raw=field('lpf_hz','fir_lp_frequency_position_raw',lambda v:fir_frequency_raw(v,'lp')),tap_parameter_raw=tap)
                attempt('fir.design',design)
            out=ch-4
            if changed(before['routing'][out],after['routing'][out]):
                def routing():
                    if seed and seed['routing_raw']>255:raise ValueError('Unknown high routing bits cannot fit the one-byte MATRIX setter')
                    preserved=seed['routing_raw']&0xf0 if seed else 0
                    emit(0x3A,'routing',routing_mask_raw=preserved|sum(1<<i for i,v in enumerate(after['routing'][out]) if v))
                attempt('routing',routing)
            for inp,(ga,gb) in enumerate(zip(before['routing_gains'][out],after['routing_gains'][out])):
                if changed(ga,gb):attempt(f'mix[{inp}]',lambda inp=inp,gb=gb:emit(0x41,f'mix[{inp}]',input_index=inp,mix_gain_raw=gain_raw(gb)))
        # A full rebuild includes existing coefficient arrays, but an empty
        # array on both sides is not a deletion request. Never invent a clear
        # command when replacing an existing array with an empty one.
        if changed(a['fir']['coefficients'],b['fir']['coefficients']) and (a['fir']['coefficients'] or b['fir']['coefficients']):
            def coefficients():
                if not b['fir']['coefficients']:raise ValueError('Removing FIR locally has no established coefficient deletion command')
                for payload in fir_chunks(ch,b['fir']['coefficients']):
                    plan.packets.append(Packet(0x4E,payload,prefix+'.fir.coefficients',['Chunk plan only; EEPROM persistence/lifecycle not established']))
            attempt('fir.coefficients',coefficients)
        if changed(a['fir']['name'],b['fir']['name']):
            attempt('fir.name',lambda:emit(0x5B,'fir.name',name_bytes=ascii_name(b['fir']['name'])))
        if a['fir']['path']!=b['fir']['path']:plan.local_only.append({'path':prefix+'.fir.path','reason':'Local file path is not a DSP parameter'})
        if a['deq']!=b['deq']:plan.blocked.append({'path':prefix+'.deq','reason':'Hidden DEQ profile not enabled; raw state preserved'})
        for section in (('limiter',) if ch<4 else ('gate','compressor')):
            if a[section]!=b[section]:plan.local_only.append({'path':prefix+'.'+section,'reason':'Not applicable to this channel group'})
        if ch<4:
            for k in ('hpf_hz','lpf_hz','hpf_type','lpf_type','hpf_bypass','lpf_bypass','crossover_mode'):
                if a[k]!=b[k]:plan.local_only.append({'path':prefix+'.'+k,'reason':'Output crossover only'})
    if before['links']!=after['links']:plan.blocked.append({'path':'links','reason':'Local selection booleans are not MCU root Link masks; no invented mask conversion'})
    for k,v in after['settings'].items():
        if before['settings'][k]!=v:
            if k in ('input_select','output_select','test_tone','sine_hz'):continue
            target=plan.local_only if k in ('ip','device_id','delay_unit') else plan.blocked
            target.append({'path':'settings.'+k,'reason':'Local display/target setting' if target is plan.local_only else 'WORK_MODE fields not yet mapped to these controls'})
    for key,group in (('input_select',0),('output_select',1)):
        if changed(before['settings'][key],after['settings'][key]):
            payload=encode_global(0x4D,group_raw=group,selection_raw=choice_raw(after['settings'][key],['ANALOG','AES / EBU']))
            plan.packets.append(Packet(0x4D,payload,'settings.'+key))
    if any(changed(before['settings'][key],after['settings'][key]) for key in ('test_tone','sine_hz')):
        try:
            payload=encode_global(0x39,mode_raw=choice_raw(after['settings']['test_tone'],['ANALOG INPUT','PINK NOISE','WHITE NOISE','SINE']),
                                  sine_frequency_index_raw=choice_raw(after['settings']['sine_hz'],SINE_FREQUENCIES))
            plan.packets.append(Packet(0x39,payload,'settings.test_tone',['No audio generated locally; source sine table has 31 discrete choices']))
        except ValueError as e:plan.blocked.append({'path':'settings.test_tone','reason':str(e)})
    return plan
