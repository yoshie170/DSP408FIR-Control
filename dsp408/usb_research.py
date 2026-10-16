"""Pure Windows HID report inspection from editor source; no HID handles/I/O.

Source: EXE402F94/70925C/70A1B0, thread70847C and callback708428.
Caller supplies a Windows report length explicitly. USB bus captures and
hidapi-returned buffers are different containers and are not autodetected.
"""
from dataclasses import dataclass
from dsp408.wire_research import EditorFrame,decode_editor_frame


def _length(value):
    if type(value) is not int or not 10<=value<=65535:
        raise ValueError('Explicit Windows HID report length must be 10..65535')
    return value


@dataclass(frozen=True)
class WindowsSourceReport:
    report_id:int
    frame:EditorFrame
    trailing_bytes:bytes


def build_windows_source_report(packet,*,report_length):
    """Zero tail is our deterministic local policy, not observed vendor padding.

    Exactly one mode1 frame must fit; there is no invented fragmentation.
    This returns bytes only and cannot send them to a device.
    """
    length=_length(report_length);packet=bytes(packet);decode_editor_frame(packet)
    if len(packet)+1>length:raise ValueError('Frame exceeds one Windows HID report; fragmentation is unverified')
    return b'\0'+packet+bytes(length-1-len(packet))


def inspect_windows_source_report(report,*,report_length):
    length=_length(report_length);report=bytes(report)
    if len(report)!=length:raise ValueError('Windows report length differs from explicit profile')
    if report[0]!=0:raise ValueError('Only source Report ID zero is established')
    frame_length=report[5]+8
    if frame_length<9 or frame_length>length-1:raise ValueError('Contained frame extent exceeds Windows report')
    packet=decode_editor_frame(report[1:1+frame_length])
    return WindowsSourceReport(0,packet,report[1+frame_length:])
