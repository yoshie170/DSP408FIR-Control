"""State with audited editor frequency domain; no wire encoding lives here."""
from dataclasses import dataclass, field, asdict, fields
from copy import copy,deepcopy
from pathlib import Path
import json
import math
from dsp408.editor_profile import FREQUENCY_MIN,FREQUENCY_MAX,DETECTOR_TYPES,DEQ_LIMITS

FILTER_TYPES = ['Bell', 'Low shelf', 'High shelf', 'Low pass 6', 'Low pass 12', 'High pass 6', 'High pass 12', 'All pass 1', 'All pass 2']
LEGACY_FILTER_TYPES = ['Low cut','High cut','Band pass']
DEQ_TYPES = ['Parameter EQ','Full Band','Low Shelf','High Shelf']
DEQ_MODES = ['Cut Above','Boost Above','Cut Below','Boost Below']
CROSS_TYPES = [f'{kind} -{slope}' for slope in range(6,49,6) for kind in ('BW','BL','LR') if kind != 'LR' or slope in (12,24,36,48)]
FIR_WINDOWS = ['RECT','BARTLETT','HANNING','HAMMING','BLACKMAN','SINE','SINC','NUTTALL','KAISER','BLACK-NU','HARRIS']
FIR_TYPES = ['BYPASS','LOW PASS','HIGH PASS','BAND PASS','External FIR']

@dataclass
class Filter:
    enabled: bool = True
    kind: str = 'Bell'
    frequency: float = 1000.0
    gain: float = 0.0
    q: float = 1.0

@dataclass
class Gate:
    threshold: float = -90.0
    hold_ms: float = 100.0
    attack_ms: float = 1.0
    release_ms: float = 100.0

@dataclass
class Dynamics:
    threshold: float = 20.0
    ratio: float = 1.0
    knee: float = 0.0
    attack_ms: float = 10.0
    release_ms: float = 100.0
    ratio_limit: bool = False
    detector_frequency: float = 1000.0
    detector_type: str = 'Bypass'

@dataclass
class FIR:
    name: str = ''
    bypass: bool = True
    mode: str = 'BYPASS'
    window: str = 'KAISER'
    taps: int = 512
    hpf_hz: float = 150.0
    lpf_hz: float = 20000.0
    path: str = ''
    coefficients: list[float] = field(default_factory=list)

@dataclass
class DynamicEQ:
    bypass: bool = True
    kind: str = 'Parameter EQ'
    mode: str = 'Cut Above'
    threshold: float = 20.0
    ratio: float = 1.0
    attack_ms: float = 51.0
    release_ms: float = 500.0
    gain: float = 6.0
    frequency: float = 1000.0
    q: float = 3.0

@dataclass
class Channel:
    name: str
    gain: float = 0.0
    mute: bool = False
    polarity_inverted: bool = False
    delay_ms: float = 0.0
    hpf_hz: float = 20.0
    lpf_hz: float = 20000.0
    hpf_type: str = 'BW -12'
    lpf_type: str = 'BW -12'
    hpf_bypass: bool = True
    lpf_bypass: bool = True
    crossover_mode: str = 'IIR'
    filters: list[Filter] = field(default_factory=lambda: [Filter(frequency=f) for f in (31.5,63,125,250,500,1000,2000,5000,10000)])
    eq_bypass: bool = False
    deq: list[DynamicEQ] = field(default_factory=lambda:[DynamicEQ() for _ in range(3)])
    gate: Gate = field(default_factory=Gate)
    compressor: Dynamics = field(default_factory=Dynamics)
    limiter: Dynamics = field(default_factory=Dynamics)
    fir: FIR = field(default_factory=FIR)


_STATE_FIELDS={kind:tuple(f.name for f in fields(kind))
               for kind in (Filter,Gate,Dynamics,FIR,DynamicEQ,Channel)}
_SCALAR_TYPES=frozenset((str,int,float,bool,type(None)))


def state_snapshot(value):
    """Independent asdict-equivalent snapshot of the known model records.

    These records contain scalar settings and lists. Cache their field names
    instead of rediscovering them for every filter on every fader movement.
    Unknown objects keep deepcopy/asdict behavior; validation remains separate.
    """
    kind=type(value)
    if kind in _SCALAR_TYPES:return value
    names=_STATE_FIELDS.get(kind)
    if names is not None:return {name:state_snapshot(getattr(value,name)) for name in names}
    if kind is list:return [state_snapshot(item) for item in value]
    if hasattr(kind,'__dataclass_fields__'):return asdict(value)
    return deepcopy(value)

# UI increments are editing precision, NOT verified device quantization.
LIMITS = {'gain':(-60,12), 'delay_ms':(0,680), 'hpf_hz':(FREQUENCY_MIN,FREQUENCY_MAX), 'lpf_hz':(FREQUENCY_MIN,FREQUENCY_MAX),
 'filters.frequency':(FREQUENCY_MIN,FREQUENCY_MAX),'filters.gain':(-12,12),'filters.q':(.4,128),
 'gate.threshold':(-90,0),'gate.hold_ms':(10,999),'gate.attack_ms':(1,999),'gate.release_ms':(10,3000),
 'compressor.threshold':(-90,20),'compressor.ratio':(1,20),'compressor.knee':(0,12),'compressor.attack_ms':(1,999),'compressor.release_ms':(10,3000),
 'limiter.threshold':(-90,20),'limiter.ratio':(1,20),'limiter.knee':(0,12),'limiter.attack_ms':(1,999),'limiter.release_ms':(10,3000),
 # Readback/storage may include inactive or legacy FIR co-fields. New design
 # controls and source_codec.fir_frequency_raw enforce HP88..299/LP89..300.
 'fir.hpf_hz':(FREQUENCY_MIN,FREQUENCY_MAX),'fir.lpf_hz':(FREQUENCY_MIN,FREQUENCY_MAX)}

def number(value, low, high, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: expected finite number in [{low}, {high}]')

def boolean(value,label):
    if type(value) is not bool: raise ValueError(f'{label}: expected boolean')

class DeviceModel:
    def __init__(self):
        self.inputs = [Channel(f'IN {i+1}') for i in range(4)]
        for c in self.inputs: c.filters=c.filters[:8]
        self.outputs = [Channel(f'OUT {i+1}') for i in range(8)]
        self.routing = [[i == (j % 4) for i in range(4)] for j in range(8)]
        self.routing_gains = [[0.0]*4 for _ in range(8)]
        self.fir_path = ''  # legacy preset compatibility
        self.vendor_prs_hex = ''  # optional complete original file; opaque data retained through clones/JSON
        self.links = [False]*12
        self.settings = {'device_id':1,'ip':'192.168.1.101','input_select':'ANALOG','output_select':'ANALOG','test_tone':'ANALOG INPUT','sine_hz':1000.0,'delay_unit':'ms'}

    @property
    def channels(self): return self.inputs + self.outputs

    def validate(self):
        if len(self.inputs)!=4 or len(self.outputs)!=8: raise ValueError('Invalid channel count')
        if getattr(self,'device_link_masks',None) is not None:
            from dsp408.channel_link import topology
            topology(self.device_link_masks)
        for idx,c in enumerate(self.channels):
            if not isinstance(c.name,str) or not c.name.strip() or len(c.name)>80: raise ValueError('Invalid channel name (demo max 80 characters)')
            for key,(lo,hi) in LIMITS.items():
                if key.startswith('filters.'): continue
                obj=c
                parts=key.split('.')
                for part in parts[:-1]: obj=getattr(obj,part)
                number(getattr(obj,parts[-1]),lo,hi,key)
            for key in ('mute','polarity_inverted','hpf_bypass','lpf_bypass','eq_bypass'): boolean(getattr(c,key),key)
            if c.hpf_type not in CROSS_TYPES or c.lpf_type not in CROSS_TYPES: raise ValueError('Invalid crossover type')
            if c.crossover_mode not in ('IIR','FIR'): raise ValueError('Invalid crossover mode')
            if len(c.filters)!=(8 if idx<4 else 9): raise ValueError('Expected 8 input / 9 output PEQ bands (editor V1.12)')
            if len(c.deq)!=3: raise ValueError('Expected 3 DEQ sections')
            for f in c.deq:
                boolean(f.bypass,'DEQ bypass')
                if f.kind not in DEQ_TYPES or f.mode not in DEQ_MODES: raise ValueError('Invalid DEQ option')
                for key,(lo,hi) in DEQ_LIMITS.items(): number(getattr(f,key),lo,hi,'DEQ '+key)
            for dynamics in (c.compressor,c.limiter):
                boolean(dynamics.ratio_limit,'ratio Limit')
                number(dynamics.detector_frequency,FREQUENCY_MIN,FREQUENCY_MAX,'detector frequency')
                if dynamics.detector_type not in DETECTOR_TYPES: raise ValueError('Invalid detector type')
            for f in c.filters:
                boolean(f.enabled,'filter enabled')
                if f.kind not in FILTER_TYPES+LEGACY_FILTER_TYPES: raise ValueError('Invalid PEQ type')
                for k in ('frequency','gain','q'): number(getattr(f,k),*LIMITS['filters.'+k],k)
            boolean(c.fir.bypass,'FIR bypass')
            if c.fir.mode not in FIR_TYPES or c.fir.window not in FIR_WINDOWS: raise ValueError('Invalid FIR option')
            if type(c.fir.taps) is not int or c.fir.taps not in range(256,1025,32): raise ValueError('Invalid output design tap option')
            if not isinstance(c.fir.path,str): raise ValueError('Invalid FIR path')
            if not isinstance(c.fir.name,str) or len(c.fir.name)>60: raise ValueError('Invalid local FIR name')
            maximum=2048 if idx<4 else 1024
            if len(c.fir.coefficients)>maximum: raise ValueError(f'FIR coefficient count exceeds {maximum}')
            for x in c.fir.coefficients: number(x,-1e100,1e100,'FIR coefficient')
        for name in ('routing','routing_gains'):
            matrix=getattr(self,name)
            if len(matrix)!=8 or any(len(row)!=4 for row in matrix): raise ValueError('Invalid routing dimensions')
            for row in matrix:
                for x in row:
                    boolean(x,'route') if name=='routing' else number(x,-60,0,'mix gain')
        # Stored inactive banks are part of a portable PRS too. The editor's
        #4096 budget concerns active FIR, not the sum of archived coefficients.
        active=sum(len(c.fir.coefficients) for c in self.inputs if not c.fir.bypass)
        active+=sum((len(c.fir.coefficients) if c.fir.mode=='External FIR' else c.fir.taps)
                    for c in self.outputs if c.crossover_mode=='FIR' and not c.fir.bypass and c.fir.mode!='BYPASS')
        if active>4096:raise ValueError('Active FIR resource budget exceeded: 4096 coefficients')
        if len(self.links)!=12: raise ValueError('Invalid links')
        for x in self.links: boolean(x,'link')
        number(self.settings['device_id'],1,254,'device ID')
        if type(self.settings['device_id']) is not int: raise ValueError('Device ID must be integer')
        import ipaddress
        ipaddress.IPv4Address(self.settings['ip'])
        for k in ('input_select','output_select'):
            if self.settings[k] not in ('ANALOG','AES / EBU'): raise ValueError('Invalid I/O selection')
        if self.settings['test_tone'] not in ('ANALOG INPUT','PINK NOISE','WHITE NOISE','SINE'): raise ValueError('Invalid test tone')
        number(self.settings['sine_hz'],20,20000,'sine frequency')
        if self.settings['delay_unit'] not in ('ms','m','ft'): raise ValueError('Invalid delay unit')
        if not isinstance(self.fir_path,str): raise ValueError('Invalid legacy FIR path')
        if not isinstance(self.vendor_prs_hex,str):raise ValueError('Invalid PRS template')
        if self.vendor_prs_hex:
            if len(self.vendor_prs_hex)!=67108*2:raise ValueError('Invalid PRS template size')
            raw=bytes.fromhex(self.vendor_prs_hex)
            if raw[:16]!=b'***FIR408V011***' or raw[-2:]!=b'\r\n':raise ValueError('Invalid PRS template header/trailer')

    def to_dict(self):
        result={'schema_version':2,'inputs':[state_snapshot(x) for x in self.inputs],'outputs':[state_snapshot(x) for x in self.outputs], 'routing':[r[:] for r in self.routing],'routing_gains':[r[:] for r in self.routing_gains],'fir_path':self.fir_path,'links':self.links[:],'settings':dict(self.settings)}
        if self.vendor_prs_hex:result['vendor_prs_hex']=self.vendor_prs_hex
        if getattr(self,'device_link_masks',None) is not None:result['device_link_masks']=list(self.device_link_masks)
        return result

    def save(self,path):
        if Path(path).suffix.lower()=='.prs':
            from dsp408.prs import save
            return save(self,path)
        self.validate()
        from dsp408.atomic_file import write_bytes
        write_bytes(path,json.dumps(self.to_dict(),indent=2,ensure_ascii=False,allow_nan=False).encode('utf-8'))

    @classmethod
    def load(cls,path):
        if Path(path).suffix.lower()=='.prs':
            from dsp408.prs import load
            return load(path)
        data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls,data):
        try:
            version=data.get('schema_version',1)
            if version not in (1,2): raise ValueError('Unsupported preset schema')
            obj=cls()
            for group in ('inputs','outputs'):
                channels=[]
                for source in data[group]:
                    c=dict(source)
                    filters=[Filter(**f) for f in c.pop('filters')]
                    if version==1 and group=='outputs' and len(filters)==8: filters.append(Filter(enabled=False))
                    if 'deq' in c: c['deq']=[DynamicEQ(**v) for v in c['deq']]
                    c['filters']=filters
                    for key,kind in [('gate',Gate),('compressor',Dynamics),('limiter',Dynamics),('fir',FIR)]:
                        if key in c:
                            values=dict(c[key])
                            if kind is FIR and 'coefficients' in values:values['coefficients']=deepcopy(values['coefficients'])
                            c[key]=kind(**values)
                    channels.append(Channel(**c))
                setattr(obj,group,channels)
            for key in ('routing','routing_gains','fir_path','links'):
                if key in data: setattr(obj,key,deepcopy(data[key]))
            obj.vendor_prs_hex=data.get('vendor_prs_hex','')
            if 'device_link_masks' in data:obj.device_link_masks=tuple(data['device_link_masks'])
            obj.settings.update(data.get('settings',{}))
            obj.validate(); return obj
        except (KeyError,TypeError,AttributeError,OverflowError) as e: raise ValueError(f'Invalid preset: {e}') from e

    def _channel_edit_copy(self,targets):
        """Copy only touched channels; validate() reads the entire model.

        The edit transaction must not mutate routing/settings or untouched
        channels. Their containers remain shared only for this read-only check.
        On failure nothing is committed; on success commit channel arrays only.
        """
        clone=copy(self);clone.inputs=self.inputs[:];clone.outputs=self.outputs[:]
        for index in targets:
            group=clone.inputs if index<4 else clone.outputs
            local=index if index<4 else index-4
            group[local]=deepcopy(group[local])
        return clone

    def link_masks(self):
        from dsp408.channel_link import self_mask,topology
        values=getattr(self,'device_link_masks',None)
        if values is None:
            values=[self_mask(i) for i in range(12)]
            for scope in (range(4),range(4,12)):
                group=[i for i in scope if self.links[i]]
                if len(group)>1:
                    for i in group:values[i]=sum(self_mask(t) for t in group) if i==group[0] else 0
        topology(values)
        return tuple(values)

    def with_link_group(self,selected,members):
        """Offline equivalent of native group membership/copy semantics; no wire I/O."""
        from dsp408.channel_link import topology,members_for,self_mask
        if type(selected) is not int or not 0<=selected<12:raise ValueError('Invalid channel')
        if not isinstance(members,(list,tuple)) or not members or any(type(i) is not int or not 0<=i<12 or (i<4)!=(selected<4) for i in members):raise ValueError('Choose channels from one input/output group')
        wanted=tuple(sorted(set(members)))
        if len(wanted)!=len(members) or selected not in wanted:raise ValueError('Include the selected channel once')
        old=self.link_masks()
        if members_for(old,selected)==wanted:raise ValueError('Link group has not changed')
        groups=[tuple(i for i in g if i not in wanted) for g in topology(old)]
        groups=[g for g in groups if g]+[wanted]
        clone=DeviceModel.from_dict(self.to_dict());values=[0]*12;copies=[]
        for group in groups:
            for i in group:values[i]=sum(self_mask(t) for t in group) if i==group[0] else 0
            source=group[0]
            for target in group[1:]:
                if target in members_for(old,source):continue
                name=clone.channels[target].name
                dest=deepcopy(clone.channels[source]);dest.name=name
                (clone.inputs if target<4 else clone.outputs)[target if target<4 else target-4]=dest
                copies.append((source,target))
        clone.device_link_masks=tuple(values);clone.links=[False]*12
        clone.validate()
        return clone,tuple(copies)

    def set_channel(self,index,key,value,band=-1):
        """Validate on a copy, then apply atomically, including same-group DEMO links."""
        if type(index) is not int or not 0<=index<12: raise ValueError('Invalid channel')
        if key=='filters' or any(p.startswith('_') for p in key.split('.')): raise ValueError('Invalid parameter')
        targets=[index]
        if getattr(self,'device_link_masks',None) is not None and key not in ('name','fir.name'):
            from dsp408.channel_link import members_for
            targets=list(members_for(self.device_link_masks,index))
        elif self.links[index] and not key.startswith('fir.') and key!='name':
            targets=[i for i in (range(4) if index<4 else range(4,12)) if self.links[i]]
        clone=self._channel_edit_copy(targets)
        for i in targets:
            obj=clone.channels[i]; parts=key.split('.')
            if parts[0] in ('filters','deq'):
                entries=getattr(obj,parts[0])
                if type(band) is not int or not 0<=band<len(entries): raise ValueError('Invalid filter band')
                obj=entries[band];parts=parts[1:]
            for p in parts[:-1]: obj=getattr(obj,p)
            if parts[-1] not in obj.__dataclass_fields__: raise ValueError('Unknown parameter')
            setattr(obj,parts[-1],deepcopy(value))
        clone.validate()
        self.inputs,self.outputs=clone.inputs,clone.outputs

    def copy_channel(self,source,target):
        if not (0<=source<12 and 0<=target<12) or (source<4)!=(target<4): raise ValueError('Copy within input/output group only')
        clone=self._channel_edit_copy([]);name=self.channels[target].name
        dest=deepcopy(self.channels[source]); dest.name=name
        (clone.inputs if target<4 else clone.outputs)[target if target<4 else target-4]=dest
        clone.validate();self.inputs,self.outputs=clone.inputs,clone.outputs

    def set_peq_point(self,index,band,frequency,gain):
        """One atomic graph edit for both coordinates and linked channels."""
        if type(index) is not int or not 0<=index<12:raise ValueError('Invalid channel')
        if type(band) is not int or not 0<=band<len(self.channels[index].filters):raise ValueError('Invalid filter band')
        number(frequency,*LIMITS['filters.frequency'],'PEQ frequency');number(gain,*LIMITS['filters.gain'],'PEQ gain')
        targets=[index]
        if getattr(self,'device_link_masks',None) is not None:
            from dsp408.channel_link import members_for
            targets=list(members_for(self.device_link_masks,index))
        elif self.links[index]:targets=[i for i in (range(4) if index<4 else range(4,12)) if self.links[i]]
        clone=self._channel_edit_copy(targets)
        for target in targets:
            f=clone.channels[target].filters[band];f.frequency=frequency;f.gain=gain
        clone.validate();self.inputs,self.outputs=clone.inputs,clone.outputs
