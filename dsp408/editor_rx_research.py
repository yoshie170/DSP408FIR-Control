"""Offline interpretations of the hash-audited V1.12 editor's RX payloads.

These are source-derived layouts, NOT verified firmware/device codecs. The caller
must explicitly supply an RX payload: neither direction nor device identity can
be inferred from an opcode. No transport, encoder, controller/model integration
or automatic telemetry activation. See docs/PROTOCOL_TELEMETRY_V9.md.
"""
from dataclasses import dataclass
import math
import struct


EDITOR_SHA256 = '50598b8cf1c0cecefa59af65f88c0b4eef627e3a5e9187bbb5814d3baa3124fb'
INPUT_MARKS = (-50., -30., -10., -5., 0., 5., 10., 14.)
OUTPUT_MARKS = (-50., -30., -10., -5., 0., 5., 12., 18.)
METER_OFFSET = 17.
DSP_REFERENCE = 4809.


@dataclass(frozen=True)
class EditorLevel:
    channel_index: int  # IN A-D = 0..3, OUT 1-8 = 4..11
    raw_word: int
    amplitude: float
    log_level_db: float | None  # log of source amplitude; not calibrated dBu/dBFS
    editor_segments: int | None  # original progress bars 0..8
    status: str


@dataclass(frozen=True)
class EditorTelemetry:
    levels: tuple[EditorLevel, ...]
    dynamics_word: int
    input_compressor_bits: tuple[bool, ...]  # raw bits, before editor UI guards
    output_limiter_bits: tuple[bool, ...]
    unknown_dynamics_bits: int
    dsp_counter: int
    editor_dsp_percent: float  # original formula, deliberately not clamped
    trailing_bytes: bytes  # source consumes 42 bytes; exact device size unknown


def decode_telemetry_payload(payload):
    """Decode the 42-byte prefix consumed by RX40 -> editor function 0x408E64.

    Three wire bytes a,b,c reconstruct IEEE754 bits 0xBBAACC00, not a
    24-bit integer. The source zeroes words >=0xFF000000 and substitutes
    1e-7 only for zero before log10. Other negative/nonfinite values are kept
    raw and flagged here; we do not emulate the vendor runtime's FPU errors.
    """
    payload = bytes(payload)
    if len(payload) < 42:
        raise ValueError('Editor RX40 needs at least 42 payload bytes')
    levels = []
    for index in range(12):
        a, b, c = payload[3*index:3*index+3]
        word = (b << 24) | (a << 16) | (c << 8)
        amplitude = struct.unpack('<f', struct.pack('<I', word))[0]
        status = 'source_float'
        if word >= 0xFF000000:
            amplitude = 0.
            status = 'source_word_guard_zero'
        if not math.isfinite(amplitude) or amplitude < 0:
            log_db = segments = None
            status = 'unsupported_log_domain'
        else:
            log_db = 20 * math.log10(amplitude if amplitude else 1e-7)
            marks = INPUT_MARKS if index < 4 else OUTPUT_MARKS
            # Source stops at first threshold >= log_level: equality is unlit.
            segments = next((i for i, mark in enumerate(marks)
                             if mark - METER_OFFSET >= log_db), len(marks))
            if amplitude == 0 and status == 'source_float':
                status = 'source_zero_log_floor'
        levels.append(EditorLevel(index, word, amplitude, log_db, segments, status))
    dynamics = int.from_bytes(payload[36:38], 'little')
    counter = int.from_bytes(payload[38:42], 'little', signed=True)
    percent = struct.unpack('<f', struct.pack('<f',
                            (DSP_REFERENCE-counter)*100/DSP_REFERENCE))[0]
    return EditorTelemetry(tuple(levels), dynamics,
                           tuple(bool(dynamics & (1 << i)) for i in range(4)),
                           tuple(bool(dynamics & (1 << (8+i))) for i in range(8)),
                           dynamics & 0x00F0, counter, percent, payload[42:])


@dataclass(frozen=True)
class EditorFirReadChunk:
    selector_byte: int  # memory area/bank, not a channel; source mapping in V13
    block_index: int
    coefficient_words: tuple[int, ...]
    source_floats: tuple[float | None, ...]  # FFFFFFFF sentinel is not a NaN coef
    sentinel_indices: tuple[int, ...]


def decode_fir_read_payload(payload):
    """Parse raw RX56 header/words without emulating stateful FIR reconstruction.

    0x4078F4/0x407EC8 read a big-endian block index at bytes1..2 and
    little-endian float words from byte3. FFFFFFFF invokes channel-dependent
    impulse/zero filling and may advance across blocks in the original editor.
    Do not concatenate sentinel chunks into an uploadable FIR.
    """
    payload = bytes(payload)
    if len(payload) < 3 or (len(payload)-3) % 4:
        raise ValueError('Editor RX56 requires a 3-byte header and complete 4-byte words')
    words = tuple(struct.unpack_from('<I', payload, i)[0]
                  for i in range(3, len(payload), 4))
    floats = tuple(None if word == 0xFFFFFFFF else
                   struct.unpack('<f', struct.pack('<I', word))[0] for word in words)
    return EditorFirReadChunk(payload[0], int.from_bytes(payload[1:3], 'big'),
                              words, floats,
                              tuple(i for i, word in enumerate(words) if word == 0xFFFFFFFF))


class FirAreaAssembler:
    """One explicit MCU RX56 area:1260×52+16 bytes, not an active-channel FIR.

    Preserve sentinel/nonfinite words exactly. Preserve the raw bank selector. No
    guessed channel allocation, impulse filling, upload or read requests.
    """
    def __init__(self,*,selector):
        if type(selector) is not int or not 0<=selector<=255:raise ValueError('Explicit selector byte required')
        self.selector=selector;self._blocks={}

    def add(self,payload):
        payload=bytes(payload);chunk=decode_fir_read_payload(payload)
        if chunk.selector_byte!=self.selector:raise ValueError('FIR area selector changed; reset session explicitly')
        index=chunk.block_index;body=payload[3:]
        if index>1260 or len(body)!=(16 if index==1260 else 52):
            raise ValueError('FIR area requires52-byte blocks and16-byte final block1260')
        if index in self._blocks and self._blocks[index]!=body:raise ValueError('Changed duplicate FIR area block')
        self._blocks[index]=body

    @property
    def missing_blocks(self):return tuple(i for i in range(1261) if i not in self._blocks)

    @property
    def received_blocks(self):return tuple(sorted(self._blocks))

    def received_bytes(self,offset,size):
        """Exact covered bytes only. Never fill holes in a sparse read."""
        if type(offset) is not int or type(size) is not int or offset<0 or size<0 or offset+size>65536:
            raise ValueError('FIR byte range is outside the raw bank')
        if not size:return b''
        first=offset//52;last=(offset+size-1)//52
        if any(i not in self._blocks for i in range(first,last+1)):
            raise ValueError('Requested FIR bytes were not received')
        raw=b''.join(self._blocks[i] for i in range(first,last+1))
        return raw[offset-first*52:offset-first*52+size]

    def data(self):
        if self.missing_blocks:raise ValueError('FIR area read incomplete')
        return b''.join(self._blocks[i] for i in range(1261))


@dataclass(frozen=True)
class EditorSystemStatus:
    flag0_raw:int
    word1_be_raw:int
    word3_be_raw:int
    flag5_raw:int
    flag6_raw:int
    trailing_bytes:bytes


def decode_system_payload(payload):
    """RX2C seven-byte prefix: MCU B086 and EXE40705C/48E3A4.

    Raw names deliberately avoid guessing flag/counter meanings. The editor
    tests flag0 with word3>=word1, then flag5, and separately reads flag6.
    This parser initiates none of its subsequent commands or UI states.
    """
    payload=bytes(payload)
    if len(payload)<7:raise ValueError('Editor RX2C needs at least7 payload bytes')
    return EditorSystemStatus(payload[0],int.from_bytes(payload[1:3],'big'),
                              int.from_bytes(payload[3:5],'big'),payload[5],payload[6],payload[7:])


@dataclass(frozen=True)
class EditorPresetCatalog:
    marker_bytes:tuple[int,...]
    source_slot_numbers:tuple[int,...]
    stored_prefix_selected:tuple[bool,...]
    trailing_bytes:bytes


@dataclass(frozen=True)
class EditorCurrentNameReply:
    active_slot_raw:int
    name_bytes_hex:str


def decode_current_name_reply(payload):
    """MCU B2F6/B31E emits RX01 with slot+14 name bytes after TX26.

    Shared AF1E's empty01 is a different reply shape. Neither contains a TX
    command echo/transaction ID. Do not infer ACK correlation from opcode01.
    """
    payload=bytes(payload)
    if len(payload)!=15:raise ValueError('Source RX01 current-name shape needs exactly15 bytes')
    return EditorCurrentNameReply(payload[0],payload[1:].hex())


def decode_preset_catalog_payload(payload):
    """MCU RX22:19 record markers, not names or our20-slot local session bank.

    MCU6E7C selects stored data when a slot's marker is nonzero. Preserve other
    values, do not claim record integrity or complete/persisted FIR from a byte.
    """
    payload=bytes(payload)
    if len(payload)<19:raise ValueError('Source RX22 needs19 slot marker bytes')
    markers=tuple(payload[:19])
    return EditorPresetCatalog(markers,tuple(range(1,20)),tuple(bool(v) for v in markers),payload[19:])
