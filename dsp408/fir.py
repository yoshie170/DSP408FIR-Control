"""Strict offline FIR import. This is our format, not a verified device decoder."""
from pathlib import Path
import math,re

def parse_coefficients(path,maximum):
    p=Path(path)
    if p.stat().st_size>2_000_000: raise ValueError('FIR file exceeds demo import size limit')
    tokens=[]
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        line=line.split('#',1)[0].strip()
        if line: tokens.extend(re.split(r'[,;\s]+',line))
    if not tokens: raise ValueError('No FIR coefficients')
    if len(tokens)>maximum: raise ValueError(f'At most {maximum} coefficients for this channel')
    try: values=[float(x) for x in tokens]
    except ValueError as e: raise ValueError('Expected numeric coefficients only (no CSV headers/index columns)') from e
    if not all(math.isfinite(x) and abs(x)<=1e100 for x in values): raise ValueError('FIR coefficients must be finite')
    return values
