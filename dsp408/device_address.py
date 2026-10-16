"""Strict physical target adapter; planners retain their canonical logical ID1.

Only envelope addresses/checksum change. No broadcast, discovery or retries.
"""
from functools import reduce
from operator import xor
from dsp408.wire_research import decode_editor_frame
from dsp408.ethernet_stream import EthernetFrames

def checked_id(value):
    if type(value) is not int or not 1<=value<=250:raise ValueError('DSP ID must be1–250')
    return value

def addressed(raw,target,outgoing):
    p=decode_editor_frame(raw);expected=b'\0\1' if outgoing else bytes((target,0))
    if p.address_bytes!=expected:raise ValueError('Frame does not belong to selected DSP ID')
    b=bytearray(raw);b[2:4]=bytes((0,target)) if outgoing else b'\1\0'
    b[-1]=reduce(xor,b[:-1],0);return bytes(b)

class AddressedHid:
    def __init__(self,device,target,record=lambda _:None):self.device=device;self.target=checked_id(target);self.record=record
    def write(self,report):
        report=bytes(report)
        if len(report)!=65 or report[0]:raise ValueError('Expected65-byte output report')
        raw=report[1:1+report[5]+8]
        mapped=raw if raw[5]==0xB8 and raw[2:4]==b'\0\xfd' else addressed(raw,self.target,True)
        n=self.device.write(b'\0'+mapped+report[1+len(raw):])
        # MCU15 writes EEPROM17, not the envelope address at EEPROM0.
        # Its ACK and subsequent frames retain the selected physical address.
        return n
    def read(self,size,timeout):
        report=bytes(self.device.read(size,timeout))
        if not report:return report
        if len(report)!=64:raise ValueError('Expected64-byte input report')
        n=report[4]+8;return addressed(report[:n],self.target,False)+report[n:]
    def close(self):self.device.close()

class AddressedStream:
    def __init__(self,stream,target,record=lambda _:None):self.stream=stream;self.target=checked_id(target);self.decoder=EthernetFrames();self.record=record
    @property
    def physical_pending(self):return bool(self.decoder.pending)
    def settimeout(self,value):self.stream.settimeout(value)
    def sendall(self,raw):
        raw=bytes(raw);self.stream.sendall(addressed(raw,self.target,True))
    def recv(self,size):
        if self.target==1 and not self.decoder.pending:return self.stream.recv(size)
        chunk=self.stream.recv(size)
        if not chunk:self.decoder.finish();return b''
        packets=self.decoder.feed(chunk)
        if packets and self.decoder.pending:raise ValueError('Unrequested partial physical frame after reply')
        if packets:return b''.join(addressed(p.raw,self.target,False) for p in packets)
        # Return control after every physical read so deadlines/cancel remain
        # bounded even when a frame arrives in many small fragments.
        raise TimeoutError('Waiting for the rest of a physical DSP frame')
    def close(self):
        if hasattr(self.stream,'close'):self.stream.close()
        else:self.stream.__exit__(None,None,None)
    def getsockname(self):return self.stream.getsockname() if hasattr(self.stream,'getsockname') else None
    def __enter__(self):
        if hasattr(self.stream,'__enter__'):self.stream.__enter__()
        return self
    def __exit__(self,*args):
        if hasattr(self.stream,'__exit__'):return self.stream.__exit__(*args)
        self.close()
