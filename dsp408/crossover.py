"""Conventional magnitude previews; manufacturer realization is unverified.

96 kHz bilinear prewarp. BW: -3.0103 dB; LR: cascaded half-order BW,
-6.0206 dB; BL: reverse Bessel polynomial, magnitude-normalized to -3.0103.
FIR design uses the audited MCU source formula as a local approximation.
No phase/coherent/acoustic sum, numeric MCU identity or hardware synthesis.
"""
import math
from functools import lru_cache
from dsp408.response import response,fir_response
from dsp408.editor_profile import FREQUENCY_POINTS
from dsp408.fir_source_research import design_from_raw,WINDOW_NAMES
from dsp408.source_codec import fir_frequency_raw

FREQUENCIES = list(FREQUENCY_POINTS)


@lru_cache(maxsize=8)
def bessel_profile(order):
    coefficients = [math.factorial(2*order-k)/(2**(order-k)*math.factorial(order-k)*math.factorial(k)) for k in range(order+1)]
    def magnitude(w):
        polynomial = 0j
        for coefficient in reversed(coefficients): polynomial = polynomial*complex(0,w)+coefficient
        return coefficients[0]/abs(polynomial)
    low, high = 0.0, float(order*4)
    for _ in range(60):
        mid = (low+high)/2
        if magnitude(mid) > 1/math.sqrt(2): low = mid
        else: high = mid
    return coefficients, (low+high)/2


def filter_db(frequency, cutoff, kind, highpass=False):
    family, slope = kind.split(' -'); order = int(slope)//6
    relative = math.tan(math.pi*frequency/96000)/math.tan(math.pi*cutoff/96000)
    if highpass: relative = 1/relative
    if family == 'BW': return -10*math.log10(1+relative**(2*order))
    if family == 'LR': return -20*math.log10(1+relative**order)
    if family != 'BL': raise ValueError('Unsupported preview family')
    coefficients, scale = bessel_profile(order); polynomial = 0j
    for coefficient in reversed(coefficients): polynomial = polynomial*complex(0,relative*scale)+coefficient
    return 20*math.log10(coefficients[0]/abs(polynomial))


@lru_cache(maxsize=64)
def _iir_curve(cutoff,kind,highpass):
    """Bounded immutable preview; preserve filter_db evaluation exactly."""
    return tuple(filter_db(hz,cutoff,kind,highpass) for hz in FREQUENCIES)


def curves(channel, include_eq=True):
    hp = [0.0]*len(FREQUENCIES) if channel.hpf_bypass else list(_iir_curve(channel.hpf_hz,channel.hpf_type,True))
    lp = [0.0]*len(FREQUENCIES) if channel.lpf_bypass else list(_iir_curve(channel.lpf_hz,channel.lpf_type,False))
    eq = response(channel) if include_eq else [0.0]*len(FREQUENCIES)
    total = [a+b+c+channel.gain for a,b,c in zip(hp,lp,eq)]
    return hp,lp,eq,total


def intersections(first, second):
    """Finite separated crossings; identical curves do not invent a crossover."""
    found = []
    for i in range(1,len(first)):
        previous = first[i-1]-second[i-1]; current = first[i]-second[i]
        if abs(previous-current)<1e-9 or previous*current>0: continue
        fraction = previous/(previous-current)
        db = first[i-1]+fraction*(first[i]-first[i-1])
        hz = FREQUENCIES[i-1]*(FREQUENCIES[i]/FREQUENCIES[i-1])**fraction
        if db < -60 or (found and abs(math.log(hz/found[-1]['hz'])) < .02): continue
        found.append({'hz':hz,'db':db})
    return found


@lru_cache(maxsize=12)
def imported_fir_curve(coefficients):
    return tuple(fir_response(coefficients))


@lru_cache(maxsize=32)
def design_fir_curve(type_raw,window_raw,hp_raw,lp_raw,tap_raw):
    # Derived coefficients never enter the model, imported FIR data or TX plans.
    result=design_from_raw(type_raw=type_raw,window_raw=window_raw,
        hp_position_raw=hp_raw,lp_position_raw=lp_raw,tap_parameter_raw=tap_raw)
    return tuple(fir_response(result.coefficients))


def fir_curves(channel,include_eq):
    fir=channel.fir
    if fir.mode=='External FIR':
        if not fir.coefficients:return None
        raw=imported_fir_curve(tuple(fir.coefficients))
    elif fir.mode=='BYPASS':raw=(0.,)*len(FREQUENCIES)
    else:
        try:
            if type(fir.taps) is not int or fir.taps not in range(256,1025,32):return None
            from dsp408.source_codec import frequency_raw
            raw=design_fir_curve(('BYPASS','LOW PASS','HIGH PASS','BAND PASS').index(fir.mode),
                WINDOW_NAMES.index(fir.window),fir_frequency_raw(fir.hpf_hz,'hp') if fir.mode!='LOW PASS' else frequency_raw(fir.hpf_hz),
                fir_frequency_raw(fir.lpf_hz,'lp') if fir.mode!='HIGH PASS' else frequency_raw(fir.lpf_hz),(fir.taps-256)//32)
        except ValueError:return None  # Preserve unsupported imported settings, never clamp.
    eq=response(channel) if include_eq else [0.0]*len(FREQUENCIES)
    total=[(0.0 if channel.fir.bypass else a)+b+channel.gain for a,b in zip(raw,eq)]
    return raw,eq,total


def plot_data(channel, comparison=None, include_eq=True):
    if channel.crossover_mode != 'IIR':
        result=fir_curves(channel,include_eq)
        if result is None:return {'traces':[], 'crossings':[], 'notice':'FIR preview unavailable: import External FIR coefficients or use design settings within the original editor profile.'}
        raw,eq,total=result
        imported=channel.fir.mode=='External FIR'
        traces=[{'label':'FIR imported' if imported else 'FIR design preview','color':'#53dba0','values':list(raw)}]
        if include_eq:traces.append({'label':'PEQ','color':'#94a9bb','values':eq})
        traces.append({'label':channel.name+' · combined','color':'#36c7ef','values':total,
                       'preview':'imported' if imported else 'source_formula'})
        notice=('Imported FIR magnitude · 96 kHz · combined honors FIR bypass; raw FIR trace ignores bypass' if imported else
                'Approximate FIR design · 96 kHz · not measured DSP coefficients · sum honors FIR bypass')
        crossings=[]
        if comparison is not None:
            other=curves(comparison,include_eq)[3] if comparison.crossover_mode=='IIR' else (fir_curves(comparison,include_eq) or (None,None,None))[2]
            if other is not None:
                traces.append({'label':comparison.name+' · combined','color':'#e187ea','values':other});crossings=intersections(total,other)
                if comparison.crossover_mode=='FIR' and comparison.fir.mode!='External FIR':notice+=' · comparison: approximate FIR design'
            else:notice+=' · comparison FIR coefficients unavailable'
        return {'traces':traces,'crossings':crossings,'notice':notice,
                'fir_preview':{'kind':'imported' if imported else 'source_formula',
                               'sample_rate':96000,'bit_identical_to_mcu':False,'hardware_verified':False}}
    hp,lp,eq,total = curves(channel,include_eq)
    traces = [{'label':'HPF','color':'#53dba0','values':hp}, {'label':'LPF','color':'#f7c95a','values':lp}]
    if include_eq: traces.append({'label':'PEQ','color':'#94a9bb','values':eq})
    traces.append({'label':channel.name+' · combined','color':'#36c7ef','values':total})
    crossings = intersections(hp,lp) if not channel.hpf_bypass and not channel.lpf_bypass else []
    notice = 'Conventional IIR magnitude preview · BL normalized to -3 dB · no acoustic sum'
    if comparison is not None:
        if comparison.crossover_mode == 'IIR':
            other = curves(comparison,include_eq)[3]
            traces.append({'label':comparison.name+' · combined','color':'#e187ea','values':other})
            crossings = intersections(total,other)
        else:
            result=fir_curves(comparison,include_eq)
            if result is None:notice='Comparison output uses FIR; comparison curve unavailable.'
            else:
                other=result[2]
                traces.append({'label':comparison.name+' · combined','color':'#e187ea','values':other})
                crossings=intersections(total,other)
                if comparison.fir.mode!='External FIR':notice+=' · comparison: approximate FIR design'
    return {'traces':traces,'crossings':crossings,'notice':notice}
