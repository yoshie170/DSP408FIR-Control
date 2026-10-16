"""Conventional RBJ biquad preview, not a measurement or manufacturer emulation."""
import cmath,math
from functools import lru_cache
from types import SimpleNamespace
from dsp408.editor_profile import FREQUENCY_POINTS

# Immutable preview grid. Keep the original expression/order exactly; this
# changes neither the source domain nor the fixed96kHz preview assumption.
_GRID_Z=tuple(cmath.exp(-2j*math.pi*hz/96000) for hz in FREQUENCY_POINTS)

def biquad(f):
    w=2*math.pi*f.frequency/96000; c=math.cos(w);s=math.sin(w);alpha=s/(2*f.q);A=10**(f.gain/40)
    k=f.kind
    if k=='Bell': b=[1+alpha*A,-2*c,1-alpha*A];a=[1+alpha/A,-2*c,1-alpha/A]
    elif k in ('High pass 6','Low pass 6'):
        t=math.tan(w/2);den=1+t
        b=[1/den,-1/den,0] if k=='High pass 6' else [t/den,t/den,0];a=[1,(t-1)/den,0]
    elif k in ('Low cut','High pass 12'): b=[(1+c)/2,-(1+c),(1+c)/2];a=[1+alpha,-2*c,1-alpha]
    elif k in ('High cut','Low pass 12'): b=[(1-c)/2,1-c,(1-c)/2];a=[1+alpha,-2*c,1-alpha]
    elif k=='Band pass': b=[alpha,0,-alpha];a=[1+alpha,-2*c,1-alpha]
    elif k=='All pass 1':
        t=math.tan(w/2);v=(t-1)/(t+1);b=[v,1,0];a=[1,v,0]
    elif k=='All pass 2': b=[1-alpha,-2*c,1+alpha];a=[1+alpha,-2*c,1-alpha]
    else:
        z=2*math.sqrt(A)*alpha
        if k=='Low shelf':
            b=[A*((A+1)-(A-1)*c+z),2*A*((A-1)-(A+1)*c),A*((A+1)-(A-1)*c-z)]
            a=[(A+1)+(A-1)*c+z,-2*((A-1)+(A+1)*c),(A+1)+(A-1)*c-z]
        else:
            b=[A*((A+1)+(A-1)*c+z),-2*A*((A-1)+(A+1)*c),A*((A+1)+(A-1)*c-z)]
            a=[(A+1)-(A-1)*c+z,2*((A-1)-(A+1)*c),(A+1)-(A-1)*c-z]
    return b,a

@lru_cache(maxsize=128)
def _band_transfer(kind,frequency,gain,q):
    """Immutable complex response; reusable for magnitude AND wrapped phase.

    Bound memory during long gestures. Retain coefficient formula, expression
    evaluation and band multiplication order rather than adding dB/phase curves.
    This cache never contains source bytes, commands or synthesized DSP data.
    """
    b,a=biquad(SimpleNamespace(kind=kind,frequency=frequency,gain=gain,q=q))
    return tuple((b[0]+b[1]*z+b[2]*z*z)/(a[0]+a[1]*z+a[2]*z*z) for z in _GRID_Z)


def response(channel,phase=False):
    transfers=[] if channel.eq_bypass else [_band_transfer(f.kind,f.frequency,f.gain,f.q)
        for f in channel.filters if f.enabled]
    points=[]
    for index in range(len(FREQUENCY_POINTS)):
        h=1+0j
        for values in transfers:h*=values[index]
        value=math.degrees(cmath.phase(h)) if phase else 20*math.log10(max(abs(h),1e-12))
        points.append(value)
    return points

def fir_response(coefficients, phase=False):
    """Stored-coefficient DTFT preview at96kHz; wrapped phase in degrees."""
    values=[]
    for z in _GRID_Z:
        h=0j
        for coefficient in reversed(coefficients):h=h*z+coefficient
        values.append(math.degrees(cmath.phase(h)) if phase else 20*math.log10(max(abs(h),1e-12)))
    return values
