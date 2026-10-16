"""Raw source Link resolver diagnostics, not model checkbox or MCU emulation.

MCU9662 and EXE47B4E8 return a mask (not a channel number). Preserve their
fallback when malformed topology has no earlier owner; never normalize masks.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class LinkResolution:
    channel:int
    mask:int
    mask_source_channel:int
    members:tuple[int,...]
    used_fallback:bool
    unknown_bits:int


def resolve_link_mask(masks,channel):
    masks=tuple(masks)
    if len(masks)!=12 or any(type(v) is not int or not 0<=v<=65535 for v in masks):
        raise ValueError('Twelve explicit raw u16 Link masks required')
    if type(channel) is not int or not 0<=channel<12:raise ValueError('Channel must be0..11')
    first,count=(0,4) if channel<4 else (4,8)
    local=channel-first;bit=1<<local;owner=channel;value=masks[channel];fallback=False
    if not value&bit:
        fallback=True
        for candidate in range(first,channel):
            owner=candidate;value=masks[candidate]
            if value&bit:fallback=False;break
    return LinkResolution(channel,value,owner,tuple(first+i for i in range(count) if value&(1<<i)),
                          fallback,value&~((1<<count)-1))


def channel_copy_scope(source,target):
    """Confirmed document effects of725C, with further side effects explicit.

    No mutation, no presumed EEPROM success, and no active DSP/filter emulation.
    Three extra masks live outside the1556-byte firmware read prefix.
    """
    if any(type(v) is not int or not 0<=v<12 for v in (source,target)):
        raise ValueError('Channel must be0..11')
    if (source<4)!=(target<4):raise ValueError('MCU FIR copy rejects mixed input/output groups')
    is_input=source<4
    def base(ch):return 16+138*ch if ch<4 else 568+108*(ch-4)
    start,end=(8,136) if is_input else (18,106)
    return {'source_channel':source,'target_channel':target,
            'record_source_slice':[base(source)+start,base(source)+end],
            'record_target_slice':[base(target)+start,base(target)+end],
            'preserved_target_record_fields':['channel name','Link mask']+([] if is_input else ['routing','mix gains']),
            'peq_mask_source_offset':1436+2*source,
            'peq_mask_target_offset':1436+2*target,
            'mute_mask_offset':1432 if is_input else 1434,
            'extra_mask_bit_copy_offsets':[1566,1570] if is_input else [1568],
            'fir_name_source_slice':[1460+8*source,1468+8*source],
            'fir_name_target_slice':[1460+8*target,1468+8*target],
            'fir_storage_source_address':source<<13 if is_input else 0x4000+(source<<12),
            'fir_storage_target_address':target<<13 if is_input else 0x4000+(target<<12),
            'coefficient_count_source_offset':base(source)+(126 if is_input else 34),
            'unmodeled_effects':['conditional storage erase/copy','guarded parameter persistence','DSP apply725C→AA42/AA5A and369E'],
            'hardware_verified':False}
