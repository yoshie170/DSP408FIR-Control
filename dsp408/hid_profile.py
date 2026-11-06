"""Verify the attached HID report layout before any DSP command on macOS."""


def validate_descriptor(descriptor):
    """Require 64-byte input/output reports without Report IDs.

    HID short-item Report Size/Count and Push/Pop follow USB HID 1.11 §6.2.2.
    Unknown long items and Report IDs fail closed; no alternate framing.
    """
    data=bytes(descriptor)
    if not data or len(data)>4096:raise ValueError('Missing or oversized DSP HID descriptor')
    offset=0;size=0;count=0;stack=[];totals={8:0,9:0}
    while offset<len(data):
        prefix=data[offset];offset+=1
        if prefix==0xFE:raise ValueError('Unsupported HID long item')
        length=(0,1,2,4)[prefix & 3]
        if offset+length>len(data):raise ValueError('Truncated HID descriptor')
        value=int.from_bytes(data[offset:offset+length],'little');offset+=length
        kind=(prefix>>2)&3;tag=prefix>>4
        if kind==1:
            if tag==7:size=value
            elif tag==8:raise ValueError('Numbered HID reports do not match the DSP profile')
            elif tag==9:count=value
            elif tag==10:stack.append((size,count))
            elif tag==11:
                if not stack:raise ValueError('Invalid HID global Pop')
                size,count=stack.pop()
        elif kind==0 and tag in totals:
            if not size or not count:raise ValueError('Missing HID Report Size/Count')
            totals[tag]+=size*count
    if stack or totals!={8:512,9:512}:
        raise ValueError('DSP HID requires unnumbered 64-byte input and output reports')
