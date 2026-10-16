"""Display conversion audited against editor V1.12; storage remains milliseconds."""
import math

# isDelayInAChange: 0x439A62..0x439AB3, confirmed again in cvdDelayInAExit.
SPEED_METRES_PER_SECOND = 343.5
FEET_PER_METRE = 3.2808
FACTORS = {'ms': 1.0, 'm': SPEED_METRES_PER_SECOND / 1000,
           'ft': SPEED_METRES_PER_SECOND / 1000 * FEET_PER_METRE}


def display_delay(milliseconds, unit):
    return _finite(milliseconds) * FACTORS[unit]


def delay_milliseconds(value, unit):
    return _finite(value) / FACTORS[unit]


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Delay must be finite')
    return value
