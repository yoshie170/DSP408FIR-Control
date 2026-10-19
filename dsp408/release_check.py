"""Explicit offline bundle verification, no enumeration/connect/device I/O."""
import importlib
import json
from pathlib import Path
import sys
from uuid import uuid4
from dsp408.app_paths import DATA_DIRECTORY,JOURNAL_DIRECTORY,PREFERENCES_PATH
from dsp408.branding import application_icon
from dsp408.preferences import Preferences


def verify(controller,window,path):
    modules=('hid','dsp408.usb_parameter_control',
             'dsp408.ethernet_control','dsp408.prs','dsp408.preset_bank_restore',
             'dsp408.fir_usb_import','dsp408.output_fir','dsp408.channel_link')
    for name in modules:importlib.import_module(name)
    assert not controller.usbReadActive and controller._usb_worker is None
    icon=application_icon()
    assert not icon.isNull() and window.width()>0 and window.height()>0
    DATA_DIRECTORY.mkdir(parents=True,exist_ok=True)
    temporary=DATA_DIRECTORY/f'preferences-probe-{uuid4().hex}.json'
    air_probe={}
    try:
        preferences=Preferences(temporary)
        preferences.save_theme('light')
        assert preferences.theme()=='light'
        preferences.save_delay_air_conditions({'enabled':True,'humidity':60,'pressure_hpa':1000})
        from dsp408.controller import Controller
        from dsp408.delay import cramer_speed,sound_speed
        probe=Controller(preferences_path=temporary);probe.timer.stop()
        try:
            before=probe.model.to_dict()
            assert probe.delayAirCorrectionActive and probe.soundSpeed==cramer_speed(20,60,1000)
            air_probe={'humidity':probe.delayHumidity,'pressure_hpa':probe.delayPressureHpa,
                       'speed_20c':probe.soundSpeed}
            assert probe.setAmbientTemperature(40) and not probe.delayAirCorrectionActive
            assert probe.soundSpeed==sound_speed(40) and probe.model.to_dict()==before
            air_probe['fallback_40c']=probe.soundSpeed
        finally:probe.shutdown()
    finally:temporary.unlink(missing_ok=True)
    result={'frozen':bool(getattr(sys,'frozen',False)), 'python':sys.version.split()[0],
            'application_name':controller.applicationName,'application_version':controller.applicationVersion,
            'window_title':window.title(),'ambient_temperature':controller.ambientTemperature,
            'optional_air_conversion':air_probe,
            'modules':list(modules),'icon_sizes':[(s.width(),s.height()) for s in icon.availableSizes()],
            'data_directory':str(DATA_DIRECTORY),'preferences_path':str(PREFERENCES_PATH),
            'journal_directory':str(JOURNAL_DIRECTORY), 'preferences_write_read':True,
            'connected':False,'device_io':False}
    Path(path).write_text(json.dumps(result,indent=2),encoding='utf-8')
