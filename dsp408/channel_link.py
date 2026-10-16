"""Canonical native Link groups and source-derived observable copy effects."""
from dataclasses import dataclass
from dsp408.source_codec import frame,integer
from dsp408.link_research import channel_copy_scope

GROUPED_COMMANDS=frozenset((0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x38,0x3E,0x3F,0x4C,0x4F))


def offsets(index):return 16+138*index if index<4 else 568+108*(index-4)
def mask_offset(index):return offsets(index)+(136 if index<4 else 106)
def masks(state):return tuple(int.from_bytes(state[mask_offset(i):mask_offset(i)+2],'little') for i in range(12))
def self_mask(index):return 1<<(index if index<4 else index-4)


def topology(values):
    """Accept disjoint groups owned by their lowest member; no MCU fallback."""
    if len(values)!=12 or any(type(v) is not int for v in values):raise ValueError('Twelve Link masks required')
    groups=[]
    for first,count in ((0,4),(4,8)):
        covered=set()
        for index in range(first,first+count):
            value=values[index]
            if value<0 or value>>count:raise ValueError('Unknown Link mask bits')
            if index in covered:
                if value:raise ValueError('Overlapping Link owners')
                continue
            members=tuple(first+bit for bit in range(count) if value&(1<<bit))
            if not members or members[0]!=index or covered.intersection(members):raise ValueError('Ambiguous Link topology')
            groups.append(members);covered.update(members)
    return tuple(groups)


def members_for(values,index):
    integer(index,0,11)
    return next(g for g in topology(values) if index in g)


def require_independent(state):
    if masks(state)!=tuple(self_mask(i) for i in range(12)):
        raise ValueError('Unlink channels before importing/designing FIR or PRS')


def validate_input_activation(state,bank,index):
    """Read-only preflight for native4F group activation; no coefficient writes."""
    import math,struct
    integer(index,0,3)
    if bank is None or len(bank)!=65536:raise ValueError('Read complete FIR storage before activation')
    for target in members_for(masks(state),index):
        at=offsets(target)+126;count=int.from_bytes(state[at:at+2],'little')
        if not 1<=count<=512:raise ValueError('Input FIR activation requires1–512 coefficients per linked input')
        values=struct.unpack('<'+'f'*count,bank[target*8192:target*8192+count*4])
        if any(not math.isfinite(v) or v>50 for v in values):raise ValueError('Linked input FIR is empty or invalid; import a filter for this group first')
    from dsp408.source_session import SourceDocument
    from dsp408.fir_usb_import import resource_usage
    doc=SourceDocument(state);apply_parameter(doc,frame(0x4F,bytes((index,0))));resource_usage(bytes(doc.data))


def validate_group_state(state):
    values=masks(state);groups=topology(values)
    for group in groups:
        source=group[0]
        for target in group[1:]:
            scope=channel_copy_scope(source,target)
            a,b=scope['record_source_slice'];c,d=scope['record_target_slice']
            if state[a:b]!=state[c:d]:raise ValueError('Linked channel parameters differ; use read only')
            a=scope['peq_mask_source_offset'];b=scope['peq_mask_target_offset']
            if state[a:a+2]!=state[b:b+2]:raise ValueError('Linked PEQ bypass masks differ')
            offset=scope['mute_mask_offset'];mask=int.from_bytes(state[offset:offset+2],'little')
            if bool(mask&self_mask(source))!=bool(mask&self_mask(target)):raise ValueError('Linked Mute values differ')
    return values


def validate_wanted_groups(wanted,values):
    channels=wanted['inputs']+wanted['outputs']
    common=('gain','mute','polarity_inverted','delay_ms','filters','eq_bypass')
    for group in topology(values):
        source=channels[group[0]]
        fields=common+(('gate','compressor') if group[0]<4 else ('limiter','hpf_hz','lpf_hz','hpf_type','lpf_type','hpf_bypass','lpf_bypass','crossover_mode'))
        for i in group[1:]:
            if any(channels[i][key]!=source[key] for key in fields) or (i<4 and channels[i]['fir']['bypass']!=source['fir']['bypass']):
                raise ValueError('Linked channel values must match; edit the group together')


def apply_parameter(document,raw):
    """Opt-in control reducer. Research SourceDocument default remains strict."""
    values=masks(document.data);group=members_for(values,raw[6])
    if len(group)==1 or raw[5] not in GROUPED_COMMANDS:
        if len(group)==1 and values==tuple(self_mask(i) for i in range(12)):
            document.apply(raw);return
        targets=(raw[6],)
    else:targets=group
    from dsp408.source_session import SourceDocument
    temp=bytearray(document.data)
    for i in range(12):temp[mask_offset(i):mask_offset(i)+2]=self_mask(i).to_bytes(2,'little')
    doc=SourceDocument(temp)
    for target in targets:doc.apply(frame(raw[5],bytes((target,))+raw[7:-3]))
    for i in range(12):doc.data[mask_offset(i):mask_offset(i)+2]=values[i].to_bytes(2,'little')
    document.data[:]=doc.data


def set_mute(state,index,flag):
    state=bytearray(state);at=1432 if index<4 else 1434;mask=int.from_bytes(state[at:at+2],'little')
    bit=self_mask(index);mask=mask|bit if flag else mask&~bit
    state[at:at+2]=mask.to_bytes(2,'little');return bytes(state)


def copy_record(state,source,target):
    state=bytearray(state);scope=channel_copy_scope(source,target)
    a,b=scope['record_source_slice'];c,d=scope['record_target_slice'];state[c:d]=state[a:b]
    a=scope['peq_mask_source_offset'];b=scope['peq_mask_target_offset'];state[b:b+2]=state[a:a+2]
    a,b=scope['fir_name_source_slice'];c,d=scope['fir_name_target_slice'];state[c:d]=state[a:b]
    at=scope['mute_mask_offset'];mute=bool(int.from_bytes(state[at:at+2],'little')&self_mask(source))
    return set_mute(state,target,mute)


@dataclass(frozen=True)
class LinkPermit:
    state:bytes
    bank:bytes|None
    selected:int
    members:tuple
    frames:tuple
    expected_state:bytes
    expected_bank:bytes|None
    bank_known:bytes|None
    copies:tuple
    requests:tuple


def prepare_link(state,bank,selected,members):
    from dsp408.source_session import SourceDocument
    from dsp408.fir_usb_import import resource_usage
    state=bytes(state);bank=None if bank is None else bytes(bank);integer(selected,0,11)
    if len(state)!=1556 or (bank is not None and len(bank)!=65536):raise ValueError('Read complete parameters and FIR before Link')
    old=validate_group_state(state);old_groups=topology(old)
    if not isinstance(members,(tuple,list)) or not members or any(type(i) is not int or not 0<=i<12 or (i<4)!=(selected<4) for i in members):raise ValueError('Choose channels from one input/output group')
    wanted=tuple(sorted(set(members)))
    if len(wanted)!=len(members) or selected not in wanted:raise ValueError('Include the selected channel once')
    if members_for(old,selected)==wanted:raise ValueError('Link group has not changed')
    new_groups=[tuple(i for i in g if i not in wanted) for g in old_groups]
    new_groups=[g for g in new_groups if g]+[wanted]
    final=list(old)
    for group in new_groups:
        for i in group:final[i]=sum(self_mask(t) for t in group) if i==group[0] else 0
    affected={i for group in old_groups if any(final[t]!=old[t] for t in group) for i in group}
    affected.update(i for group in new_groups if any(final[t]!=old[t] for t in group) for i in group)
    result=bytearray(state);storage=None if bank is None else bytearray(bank);known=None if bank is None else bytearray(b'\1'*65536);frames=[];copies=[]
    def mask(index,value):
        at=mask_offset(index)
        if int.from_bytes(result[at:at+2],'little')==value:return
        # Exact EXE47DC40: channel:u8, mask:u8 (RAM/readback mask remains u16).
        frames.append(frame(0x3B,bytes((index,value))));result[at:at+2]=value.to_bytes(2,'little')
    # Remove memberships first. Keep surviving members under the same owner:
    # a mask shrink has no newly-added bits and must not recopy their FIR.
    for group in old_groups:
        if not set(group).intersection(affected):continue
        owner=group[0]
        keep=old[owner]&(final[owner] if final[owner]&self_mask(owner) else self_mask(owner))
        mask(owner,keep)
        for target in group[1:]:
            if not keep&self_mask(target):mask(target,self_mask(target))
    for group in sorted(new_groups):
        if not set(group).intersection(affected):continue
        source=group[0]
        current=int.from_bytes(result[mask_offset(source):mask_offset(source)+2],'little')
        added=(current^final[source])&final[source]
        for target in group[1:]:
            if not added&self_mask(target):continue
            scope=channel_copy_scope(source,target);count_at=scope['coefficient_count_source_offset']
            count=int.from_bytes(result[count_at:count_at+2],'little')
            capacity=8192 if source<4 else 4096
            if count>capacity//4:raise ValueError('FIR copy count outside source channel storage')
            if storage is not None:
                a=scope['fir_storage_source_address'];b=scope['fir_storage_target_address']
                erased=8192 if count>1024 else 4096
                prefix=bytes(storage[a:a+count*4]);marker=int.from_bytes(storage[a:a+4],'little')
                storage[b:b+erased]=b'\xff'*erased;known[b:b+erased]=b'\1'*erased
                if marker!=0x0FFFFFFF:
                    storage[b:b+count*4]=prefix
                    # C9CE reads count words; CA9A writes whole256-byte pages.
                    # Unused last-page scratch bytes are NOT guessed as zero.
                    end=((count+63)//64)*256
                    known[b+count*4:b+end]=b'\0'*(end-count*4)
            copies.append((source,target,count))
            result[:]=copy_record(result,source,target)
        mask(source,final[source])
        for target in group[1:]:mask(target,0)
    if masks(result)!=tuple(final):raise ValueError('Link transition does not reach requested topology')
    validate_group_state(result);resource_usage(result);SourceDocument(result)
    states=tuple(frame(0x27,bytes((i,))) for i in range(32))
    banks=() if bank is None else tuple(frame(0x56,b'\0'+i.to_bytes(2,'little')) for i in range(1261))
    catalog=(frame(0x22,b''),frame(0x14,b''))
    mute=tuple(frame(0x35,bytes((i,1))) for i in range(12))
    restore=tuple(frame(0x35,bytes((i,bool(int.from_bytes(result[(1432 if i<4 else 1434):(1434 if i<4 else 1436)],'little')&self_mask(i))))) for i in range(12))
    requests=catalog+states+banks+mute+states+tuple(frames)+states+banks+restore+states+catalog
    return LinkPermit(state,bank,selected,wanted,tuple(frames),bytes(result),None if storage is None else bytes(storage),None if known is None else bytes(known),tuple(copies),requests)


from dsp408.prs_apply_transaction import PrsApplyRehearsal


def muted(state):
    for i in range(12):state=set_mute(state,i,True)
    return state


class LinkOperation(PrsApplyRehearsal):
    def check_port(self,port):pass  # Access requires the exact canonical typed permit below.
    def exchange(self,raw,*args,**kwargs):
        self.port.arm_prs_request(raw,self.permit)
        return super().exchange(raw,*args,**kwargs)
    def report(self,stage,waiting=False):
        self.progress({'busy':True,'operation':'channel_link','stage':stage,'waiting':waiting,'done':self.done,'total':self.TOTAL})
    def run_import(self,permit):
        import hashlib
        if type(permit) is not LinkPermit or permit!=prepare_link(permit.state,permit.bank,permit.selected,permit.members):
            raise ValueError('Link permit differs from canonical plan')
        self.permit=permit;self.TOTAL=len(permit.requests);self.port.begin_prs_import(permit)
        try:
            catalog=self.exchange(frame(0x22,b''),0x22,'Checking catalog')
            active=self.exchange(frame(0x14,b''),0x14,'Checking active preset')
            if len(catalog)!=19 or len(active)!=1 or not 1<=active[0]<=19:raise ValueError('Invalid Link baseline metadata')
            if self.state('Checking parameters')!=permit.state or (permit.bank is not None and self.bank('Checking complete FIR')!=permit.bank):
                raise ValueError('Configuration changed after Link review; no mutation')
            self.record({'kind':'link_baseline','state_hex':permit.state.hex(),'bank_hex':None if permit.bank is None else permit.bank.hex(),
                         'members':permit.members,'selected':permit.selected,'copies':permit.copies,
                         'catalog_hex':catalog.hex(),'active_slot':active[0]})
            for i in range(12):self.exchange(frame(0x35,bytes((i,1))),1,'Muting channels')
            if self.state('Checking Mute')!=muted(permit.state):raise ValueError('Mute readback differs')
            for raw in permit.frames:self.exchange(raw,1,'Applying channel Link',timeout=10.)
            if self.state('Checking linked parameters')!=muted(permit.expected_state):raise ValueError('Link parameters differ; no automatic unmute')
            actual=None if permit.bank is None else self.bank('Checking complete linked FIR')
            if actual is not None and any(known and a!=b for a,b,known in zip(actual,permit.expected_bank,permit.bank_known)):
                raise ValueError('Link FIR storage differs; no automatic unmute')
            for raw in permit.requests[-46:-34]:  # Final12 Mute requests before32 state + metadata.
                self.exchange(raw,1,'Restoring linked Mute')
            if self.state('Checking final parameters')!=permit.expected_state:raise ValueError('Final Link parameters differ')
            if self.exchange(frame(0x22,b''),0x22,'Checking catalog')!=catalog:raise ValueError('Link changed preset catalog')
            if self.exchange(frame(0x14,b''),0x14,'Checking active preset')!=active:raise ValueError('Link changed active preset')
            self.port.complete_prs_import(permit)
            result={'operation':'channel_link','parameters_verified':True,'fir_storage_verified':actual is not None,
                    'bank_hex':None if actual is None else actual.hex(),
                    'bank_sha256':None if actual is None else hashlib.sha256(actual).hexdigest(),'unpredicted_unused_padding_bytes':None if actual is None else permit.bank_known.count(0),
                    'audio_verified':False,'power_cycle_persistence_verified':False,'done':self.done,'total':self.TOTAL}
            self.record({'kind':'link_verified',**result});self.progress({'busy':False,**result})
            return permit.expected_state,result
        finally:self.port.end_prs_import()
