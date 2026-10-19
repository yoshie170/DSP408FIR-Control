"""Local distance conversion; DSP storage always remains milliseconds.

Default: c ∝ sqrt(T kelvin), anchored to the editor's343.5m/s at20°C.
Optional humid-air estimate: Cramer's interpolating equation (1993), with
Davis saturation pressure, 400 ppm CO2, 0..30°C and 760..1020 hPa.
Sources, units and independent comparison: docs/DELAY_AIR_V163.md.
"""
import math

# isDelayInAChange: 0x439A62..0x439AB3, confirmed again in cvdDelayInAExit.
SPEED_METRES_PER_SECOND = 343.5
FEET_PER_METRE = 3.2808
FACTORS = {'ms': 1.0, 'm': SPEED_METRES_PER_SECOND / 1000,
           'ft': SPEED_METRES_PER_SECOND / 1000 * FEET_PER_METRE}
DEFAULT_TEMPERATURE = 20.0
DEFAULT_HUMIDITY = 50.0
DEFAULT_PRESSURE_HPA = 1013.25


def checked_temperature(value):
    return _bounded(value, -40, 60, 'Use a temperature between −40 and 60 °C.')


def checked_humidity(value):
    return _bounded(value, 0, 100, 'Use relative humidity between 0 and 100 %.')


def checked_pressure(value):
    return _bounded(value, 760, 1020, 'Use absolute air pressure between 760 and 1020 hPa.')


def checked_air_conditions(value):
    if not isinstance(value, dict) or type(value.get('enabled')) is not bool:
        raise ValueError('Choose whether to include humidity and pressure.')
    return {'enabled': value['enabled'], 'humidity': checked_humidity(value['humidity']),
            'pressure_hpa': checked_pressure(value['pressure_hpa'])}


def cramer_speed(temperature, humidity, pressure_hpa=DEFAULT_PRESSURE_HPA):
    """Humid-air estimate in m/s. Reject extrapolation of Cramer's equation."""
    t = checked_temperature(temperature)
    if not 0 <= t <= 30:
        raise ValueError('Humidity correction is available from 0 to 30 °C.')
    rh, p = checked_humidity(humidity), checked_pressure(pressure_hpa) * 100
    kelvin = t + 273.15
    # Davis / CIPM: saturation pressure in Pa and enhancement factor.
    psv = math.exp(1.2378847e-5 * kelvin**2 - .019121316 * kelvin
                   + 33.93711047 - 6343.1645 / kelvin)
    enhancement = 1.00062 + 3.14e-8 * p + 5.6e-7 * t**2
    xw, xc = rh / 100 * enhancement * psv / p, .0004
    return (331.5024 + .603055 * t - .000528 * t**2
            + (51.471935 + .1495874 * t - .000782 * t**2) * xw
            + (-1.82e-7 + 3.73e-8 * t - 2.93e-10 * t**2) * p
            + (-85.20931 - .228525 * t + 5.91e-5 * t**2) * xc
            - 2.835149 * xw**2 - 2.15e-13 * p**2
            + 29.179762 * xc**2 + .000486 * xw * p * xc)


def sound_speed(temperature=DEFAULT_TEMPERATURE, *, humidity=None,
                pressure_hpa=DEFAULT_PRESSURE_HPA):
    t = checked_temperature(temperature)
    if humidity is not None:
        checked_humidity(humidity)
        checked_pressure(pressure_hpa)
        if 0 <= t <= 30:
            return cramer_speed(t, humidity, pressure_hpa)
    # Keep the existing estimate outside the humid-air model's valid range.
    return SPEED_METRES_PER_SECOND * math.sqrt((273.15+t)/293.15)


def conversion_factors(temperature=DEFAULT_TEMPERATURE, **air):
    metres=sound_speed(temperature, **air)/1000
    return {'ms':1.0,'m':metres,'ft':metres*FEET_PER_METRE}


def display_delay(milliseconds, unit, temperature=DEFAULT_TEMPERATURE, **air):
    return _finite(milliseconds) * conversion_factors(temperature, **air)[unit]


def delay_milliseconds(value, unit, temperature=DEFAULT_TEMPERATURE, **air):
    return _finite(value) / conversion_factors(temperature, **air)[unit]


def _bounded(value, minimum, maximum, message):
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(message) from error
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(message)
    return value


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Delay must be finite')
    return value
