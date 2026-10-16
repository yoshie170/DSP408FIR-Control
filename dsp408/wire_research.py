"""Offline-only decoder of editor V1.12's static frame-builder output.

Not a verified device response codec. No opcode interpretations, encoder, I/O,
HID report assumptions or hardware session logic. Source: tools/audit_connection.py.
"""
from dataclasses import dataclass
from functools import reduce
from operator import xor


@dataclass(frozen=True)
class EditorFrame:
    address_bytes: bytes
    command: int
    data: bytes
    raw: bytes


def decode_editor_frame(raw):
    raw=bytes(raw)
    if len(raw)<9 or raw[:2]!=b'\x10\x02':
        raise ValueError('Missing editor frame header or frame too short')
    length=raw[4]
    if length<1 or len(raw)!=length+8:
        raise ValueError('Editor frame length mismatch')
    if raw[-3:-1]!=b'\x10\x03':
        raise ValueError('Missing editor frame trailer')
    if reduce(xor,raw[:-1],0)!=raw[-1]:
        raise ValueError('Editor frame XOR mismatch')
    return EditorFrame(raw[2:4],raw[5],raw[6:-3],raw)


class EditorFrameStream:
    """Incremental analysis of already ordered, reassembled offline byte streams."""
    def __init__(self):
        self.pending=bytearray();self.discarded=0;self.invalid=0

    def feed(self,chunk):
        self.pending.extend(chunk);result=[]
        while self.pending:
            start=self.pending.find(b'\x10\x02')
            if start<0:
                count=len(self.pending)-(1 if self.pending[-1]==0x10 else 0)
                self.discarded+=count;del self.pending[:count];break
            if start:
                self.discarded+=start;del self.pending[:start]
            if len(self.pending)<5:break
            length=self.pending[4]+8
            if length==8:
                self.invalid+=1;self.discarded+=1;del self.pending[:1];continue
            if len(self.pending)<length:break
            try:frame=decode_editor_frame(self.pending[:length])
            except ValueError:
                self.invalid+=1;self.discarded+=1;del self.pending[:1];continue
            result.append(frame);del self.pending[:length]
        return result


def inspect_wire_file(path):
    from pathlib import Path
    import hashlib
    file=Path(path)
    if file.stat().st_size>1024*1024:
        raise ValueError('Offline wire log limit: 1 MiB; export a short device stream')
    with file.open('rb') as stream:source=stream.read(1024*1024+1)
    if len(source)>1024*1024:raise ValueError('Offline wire log exceeds 1 MiB')
    if file.suffix.lower() in ('.hex','.txt'):
        source=bytes.fromhex(source.decode('utf-8-sig'))
    elif file.suffix.lower()!='.bin':
        raise ValueError('Use .bin raw stream or .hex/.txt hexadecimal bytes; PCAP containers are not raw streams')
    decoder=EditorFrameStream();counts={};total=0;examples=[]
    for offset in range(0,len(source),4096):
        for frame in decoder.feed(source[offset:offset+4096]):
            total+=1;command=f'0x{frame.command:02X}'
            counts[command]=counts.get(command,0)+1
            if len(examples)<12:
                examples.append({'address':frame.address_bytes.hex(' '),'command':command,
                                 'data':frame.data.hex(' '),'raw':frame.raw.hex(' ')})
    return {'file':file.name,'sha256_decoded_bytes':hashlib.sha256(source).hexdigest(),
            'bytes':len(source),'frames':total,'commands':counts,'examples':examples,
            'discarded':decoder.discarded,'invalid':decoder.invalid,'pending':len(decoder.pending),
            'status':'Offline editor framing analysis only; device/model/direction not established'}
