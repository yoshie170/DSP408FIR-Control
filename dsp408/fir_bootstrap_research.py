"""Source4078F4 FIR bootstrap carry/skip reconstruction, offline only.

Preserve original words. FFFFFFFF creates an impulse at channel start or zeros
to the source's next table boundary. This is an editor display buffer, never
proof of active audio coefficients or of all flash bytes having been read.
"""
import struct
from dsp408.editor_rx_research import decode_fir_read_payload

START_BLOCKS=(0,157,315,472,630,708,787,866,945,1024,1102,1181,1261)
START_OFFSETS=(0,28,4,32,8,48,36,24,12,0,40,28,0)


class FirReconstructionBoundary(ValueError):
    """Source path would exceed the known16384-word editor coefficient layout."""


class FirBootstrapReview:
    def __init__(self):
        self.expected_block=0;self.carry_offset=0;self.channel_index=0
        self.words=[];self.complete=False;self.sentinel_events=[];self.received_blocks=[]

    def add(self,payload):
        payload=bytes(payload);chunk=decode_fir_read_payload(payload);block=chunk.block_index
        if self.complete:raise ValueError('FIR bootstrap already complete; reset explicitly')
        if chunk.selector_byte!=0 or block!=self.expected_block:
            raise ValueError('FIR bootstrap requires pending selector0/block')
        if len(payload)!=(19 if block==1260 else 55):raise ValueError('FIR bootstrap requires52-byte body or16-byte final body')
        channel=self.channel_index;first=False
        for i in range(12):
            if block==START_BLOCKS[i]:channel=i;first=True;break
        pos=self.carry_offset+3;carry=self.carry_offset;appended=[];events=[];effective_block=block
        while pos<len(payload):
            if pos+4>len(payload):raise ValueError('Incomplete source FIR word at carry offset')
            word=struct.unpack_from('<I',payload,pos)[0]
            if word!=0xffffffff:
                appended.append(word);pos+=4;continue
            at_start=first and pos==START_OFFSETS[channel]+3
            if at_start:
                count=2048 if channel<4 else 1024
                appended.extend([0x3f800000]+[0]*(count-1));kind='source channel-start impulse'
            else:
                #407BDA..407C74: signed division toward zero, inclusive loop.
                count=(START_BLOCKS[channel+1]-1-block)*13+int((52-pos)/4)+START_OFFSETS[channel+1]//4+1
                if count<0:raise FirReconstructionBoundary('Source sentinel zero-fill has a negative extent')
                appended.extend([0]*count);kind='source sentinel zero-fill to next table boundary'
            events.append({'channel_index_raw':channel,'block':block,'payload_byte_offset':pos,'generated_words':count,'source_action':kind})
            effective_block=START_BLOCKS[channel+1]-1;carry=START_OFFSETS[channel+1];break
        if pos==len(payload):carry=0
        if len(self.words)+len(appended)>16384:
            raise FirReconstructionBoundary('Source sentinel path exceeds16384 words; final table boundary is65572, not65536')
        complete=effective_block>=1260
        if complete and len(self.words)+len(appended)!=16384:
            raise FirReconstructionBoundary('Source ends bootstrap before a complete16384-word buffer')
        self.words.extend(appended);self.sentinel_events.extend(events);self.received_blocks.append(block)
        self.carry_offset=carry;self.channel_index=channel;self.complete=complete
        self.expected_block=None if complete else effective_block+1
        return self.expected_block

    def data(self):
        if not self.complete:raise ValueError('Source FIR bootstrap buffer incomplete')
        return struct.pack('<16384I',*self.words)

    def report(self):
        import hashlib
        return {'scope':'source editor FIR buffer, including sentinel-generated data; not an active DSP FIR',
            'hardware_verified':False,'complete':self.complete,'word_count':len(self.words),
            'expected_block':self.expected_block,'carry_offset':self.carry_offset,
            'received_block_count':len(self.received_blocks),'sentinel_events':self.sentinel_events,
            'candidate_sha256':hashlib.sha256(self.data()).hexdigest() if self.complete else None}
