"""Offline editor V1.12 profile from static handlers/tables; not a hardware codec.
Evidence and image hash: docs/EDITOR_PARAMETER_AUDIT.md.
"""
FREQUENCY_BASE = 1.023373891996775
FREQUENCY_MIN = 1000 * FREQUENCY_BASE ** -170
FREQUENCY_MAX = 1000 * FREQUENCY_BASE ** 130
# Output FIR design sliders from the hash-pinned V1.12 DFM. Storage/readback
# uses the full0..300 frequency domain, including inactive and legacy values.
FIR_HP_MIN = 1000 * FREQUENCY_BASE ** (88-170)
FIR_HP_MAX = 1000 * FREQUENCY_BASE ** (299-170)
FIR_LP_MIN = 1000 * FREQUENCY_BASE ** (89-170)
FIR_LP_MAX = FREQUENCY_MAX
FREQUENCY_POINTS = tuple(FREQUENCY_MIN * (FREQUENCY_MAX/FREQUENCY_MIN)**(i/240) for i in range(241))
DETECTOR_TYPES = ['Bypass', 'LC-6', 'LC-12', 'HC-6', 'HC-12', '1.0', '2.0', '3.0', '5.0', '10.0']
RATIO_VALUES = [1.0,1.1,1.3,1.5,1.7,2.0,2.5,3.0,3.5,4.0,5.0,6.0,8.0,10.0,20.0]
SINE_FREQUENCIES = [20,25,31.5,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,20000]
Q_VALUES = [0.4, 0.42, 0.45, 0.47, 0.5, 0.53, 0.56, 0.59, 0.63, 0.67, 0.71, 0.75, 0.79, 0.84, 0.89, 0.94, 1.0, 1.06, 1.12, 1.19, 1.26, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.4, 2.5, 2.7, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0, 4.2, 4.5, 4.8, 5.0, 5.3, 5.7, 6.0, 6.3, 6.7, 7.1, 7.6, 8.0, 8.5, 9.0, 9.5, 10.1, 10.7, 11.3, 12.0, 12.7, 13.5, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 23.0, 24.0, 25.0, 27.0, 29.0, 30.0, 32.0, 34.0, 36.0, 38.0, 40.0, 43.0, 45.0, 48.0, 51.0, 54.0, 57.0, 60.0, 64.0, 68.0, 72.0, 76.0, 81.0, 85.0, 91.0, 96.0, 102.0, 108.0, 114.0, 121.0, 128.0]
DEQ_LIMITS = {'threshold':(-40,20),'gain':(6,18),'frequency':(FREQUENCY_MIN,FREQUENCY_MAX),'q':(.4,128),'ratio':(1,5),'attack_ms':(1,999),'release_ms':(10,3000)}
