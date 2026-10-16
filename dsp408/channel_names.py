"""Portable subset of the original eight-byte ANSI channel name field."""


def encode_channel_name(value):
    if not isinstance(value,str) or not value.strip() or not 1<=len(value)<=8:
        raise ValueError('Channel name: enter 1–8 characters')
    if any(not 32<=ord(c)<=126 for c in value):
        raise ValueError('Channel name: use ASCII letters, numbers, spaces or punctuation')
    return value.encode('ascii').ljust(8,b'\0')


def encode_fir_name(value):
    if not isinstance(value,str) or len(value)>8 or any(not 32<=ord(c)<=126 for c in value):
        raise ValueError('FIR name: use up to 8 printable ASCII characters')
    return value.encode('ascii').ljust(8,b'\0')
