"""Mathematical reconstruction of MCU8464, for offline research only.

NOT bit-identical to the MCU soft-float/libm, NOT an upload or production audio
filter. Source quirks are retained. Used only for research and approximate
crossover previews; no UI, model, packet planning or I/O imports.
"""
from dataclasses import dataclass
import math,struct

FREQUENCY_BASE=1.023373891996775
WINDOW_NAMES=('RECT','BARTLETT','HANNING','HAMMING','BLACKMAN','SINE','SINC','NUTTALL','KAISER','BLACK-NU','HARRIS')
COSINE_COEFFICIENTS={
    2:(.5,.5),3:(.54,.46),4:(.42,.5,.08),
    5:(.335768,.487396,.144232,.012604),
    7:(.335768,.487396,.144232,.012604),
    8:(.402,.498,.098,.001),
    9:(.3635819,.4891775,.1365995,.0106411),
    10:(.35875,.48829,.14128,.01168),
}


def _integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError(f'Expected raw integer {low}..{high}')
    return value


def _float32(value):return struct.unpack('<f',struct.pack('<f',value))[0]


def source_window(index,n,taps):
    """Centered n=-N/2..N/2; raw label need not describe a conventional window."""
    _integer(index,0,10);_integer(taps,256,1024);_integer(n,-taps//2,taps//2)
    if taps%32:raise ValueError('Editor FIR tap choices advance by32')
    theta=2*math.pi*n/taps
    if index==0:value=1.
    elif index==1:value=1-2*abs(n)/taps
    elif index==6:value=math.sin(theta)/theta if n else 1.
    else:value=sum(a*math.cos(k*theta) for k,a in enumerate(COSINE_COEFFICIENTS[index]))
    # Source stores window coefficients as binary32 before filtering.
    return _float32(value)


@dataclass(frozen=True)
class FirResearchResult:
    coefficients:tuple[float,...]
    computed_extra_endpoint:float
    taps:int
    sample_rate_constant:int=96000
    bit_identical_to_mcu:bool=False
    hardware_verified:bool=False
    scope:str='MCU source formula reconstruction; offline research, no normalization or upload'


def design_from_raw(*,type_raw,window_raw,hp_position_raw,lp_position_raw,tap_parameter_raw):
    """Source editor OUT design profile. External4 is deliberately unsupported.

    MCU calculates N+1 points (inclusive endpoint), DSP9A8 is called with N.
    Unordered HP/LP is not silently repaired; source branch has no such guard.
    Python math is a formula approximation, not vendor numeric emulation.
    """
    _integer(type_raw,0,3);_integer(window_raw,0,10)
    _integer(hp_position_raw,88 if type_raw in (2,3) else 0,299 if type_raw in (2,3) else 300)
    _integer(lp_position_raw,89 if type_raw in (1,3) else 0,300);_integer(tap_parameter_raw,0,24)
    taps=256+32*tap_parameter_raw
    hp=2*math.pi*1000*FREQUENCY_BASE**(hp_position_raw-170)/96000
    lp=2*math.pi*1000*FREQUENCY_BASE**(lp_position_raw-170)/96000
    values=[]
    for n in range(-taps//2,taps//2+1):
        if type_raw==0:value=1. if n==-taps//2 else 0.
        else:
            if n:
                low=math.sin(n*lp)/(n*math.pi)
                high=-math.sin(n*hp)/(n*math.pi)
            else:low=lp/math.pi;high=(math.pi-hp)/math.pi
            if type_raw==1:value=low
            elif type_raw==2:value=high
            else:value=low+high-(1. if n==0 else 0.)
            value=_float32(value*source_window(window_raw,n,taps))
        values.append(value)
    return FirResearchResult(tuple(values[:-1]),values[-1],taps)
