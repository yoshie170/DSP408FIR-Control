"""Opaque full storage bank description. Never infer active DSP coefficients."""
import hashlib,math,struct


def describe_bank(raw):
    raw=bytes(raw)
    if len(raw)!=65536:raise ValueError('FIR bank needs exactly65536 received bytes')
    channels=[];offset=0
    for ch in range(12):
        capacity=2048 if ch<4 else 1024
        area=raw[offset:offset+capacity*4];words=struct.unpack('<'+str(capacity)+'I',area)
        floats=struct.unpack('<'+str(capacity)+'f',area)
        sentinels=sum(w==0xffffffff for w in words)
        invalid=sum(not math.isfinite(v) and w!=0xffffffff for v,w in zip(floats,words))
        channels.append({'channel_index':ch,'offset':offset,'capacity':capacity,
            'sentinel_words':sentinels,'other_nonfinite_words':invalid,
            'finite_words':capacity-sentinels-invalid,
            'sha256':hashlib.sha256(area).hexdigest(),
            'first_words_hex':[f'{w:08X}' for w in words[:16]],
            'first_float_values':[v if math.isfinite(v) else None for v in floats[:16]]})
        offset+=len(area)
    return {'scope':'Received FIR storage bank, not a reconstructed active audio filter',
            'selector':0,'bytes':len(raw),'blocks':1261,'complete':True,
            'sha256':hashlib.sha256(raw).hexdigest(),'channels':channels,
            'sentinel_words':sum(c['sentinel_words'] for c in channels)}
