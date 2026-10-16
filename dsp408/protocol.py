"""Offline parser ONLY for the 9-byte RS232 help table embedded in editor V1.12.
This is not an Ethernet/USB codec. No encoder or device IO is provided.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DocumentedSerialFrame:
    address: int
    command: int
    data: bytes

def parse_documented_serial_frame(frame:bytes)->DocumentedSerialFrame:
    if len(frame)!=9: raise ValueError('RS232 help frame requires 9 bytes')
    if frame[:2]!=b'\x7b\x7d' or frame[-2:]!=b'\x7d\x7b': raise ValueError('Invalid documented delimiters')
    if not 1<=frame[2]<=254: raise ValueError('Invalid documented address')
    if not 0x41<=frame[3]<=0x4a: raise ValueError('Command outside embedded help table')
    return DocumentedSerialFrame(frame[2],frame[3],frame[4:7])
