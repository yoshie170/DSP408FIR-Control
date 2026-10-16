"""Conventional static display model. No audio processing or device emulation."""


def transfer_db(level, state, section):
    threshold = state.threshold
    if section == 'gate':
        return level if level >= threshold else -100.0
    inverse_ratio = 0.0 if state.ratio_limit else 1.0 / state.ratio
    knee = state.knee
    if knee > 0 and threshold-knee/2 < level < threshold+knee/2:
        return level+(inverse_ratio-1)*(level-threshold+knee/2)**2/(2*knee)
    if level >= threshold+knee/2:
        return threshold+(level-threshold)*inverse_ratio
    return level


METER_BREAKPOINTS = [-60,-50,-20,-10,-5,0,5,12,20]


def knee_detail(state,section):
    """Same static characteristic in a labelled16dB window, never exaggerated."""
    from copy import copy
    hard=copy(state);hard.knee=0
    low=max(-100.,min(state.threshold-8.,4.));high=low+16.
    xs=[low+(high-low)*i/120 for i in range(121)]
    return {'low':low,'high':high,'threshold':state.threshold,'knee':state.knee,
            'actual':[transfer_db(x,state,section) for x in xs],
            'hard':[transfer_db(x,hard,section) for x in xs]}


def meter_position(db):
    """Piecewise display spacing: original marked levels, DEMO end headroom.

    -60/+20 bounds are local display choices, not hardware/clip calibration.
    """
    if db<=METER_BREAKPOINTS[0]:return 0.0
    for i,high in enumerate(METER_BREAKPOINTS[1:]):
        low=METER_BREAKPOINTS[i]
        if db<=high:return (i+(db-low)/(high-low))/8
    return 1.0


