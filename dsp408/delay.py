"""Local distance conversion; DSP storage always remains milliseconds.

The temperature law is c ∝ sqrt(T kelvin), anchored to the editor's343.5m/s
at20°C. It is an ambient-air estimate, without humidity compensation.
"""
import math

# isDelayInAChange: 0x439A62..0x439AB3, confirmed again in cvdDelayInAExit.
SPEED_METRES_PER_SECOND = 343.5
FEET_PER_METRE = 3.2808
FACTORS = {'ms': 1.0, 'm': SPEED_METRES_PER_SECOND / 1000,
           'ft': SPEED_METRES_PER_SECOND / 1000 * FEET_PER_METRE}
DEFAULT_TEMPERATURE = 20.0


def checked_temperature(value):
    if isinstance(value,bool):raise ValueError('Use a temperature between −40 and 60 °C.')
    value=float(value)
    if not math.isfinite(value) or not -40<=value<=60:
        raise ValueError('Use a temperature between −40 and 60 °C.')
    return value


def sound_speed(temperature=DEFAULT_TEMPERATURE):
    return SPEED_METRES_PER_SECOND * math.sqrt((273.15+checked_temperature(temperature))/293.15)


def conversion_factors(temperature=DEFAULT_TEMPERATURE):
    metres=sound_speed(temperature)/1000
    return {'ms':1.0,'m':metres,'ft':metres*FEET_PER_METRE}


def display_delay(milliseconds, unit, temperature=DEFAULT_TEMPERATURE):
    return _finite(milliseconds) * conversion_factors(temperature)[unit]


def delay_milliseconds(value, unit, temperature=DEFAULT_TEMPERATURE):
    return _finite(value) / conversion_factors(temperature)[unit]


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Delay must be finite')
    return value
