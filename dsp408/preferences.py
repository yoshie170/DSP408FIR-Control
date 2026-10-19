"""Local application preferences, separate from DSP settings and presets."""
import json
import os
from pathlib import Path
import tempfile

from dsp408.app_paths import PREFERENCES_PATH
DEFAULT_PATH=PREFERENCES_PATH


class Preferences:
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else DEFAULT_PATH

    def theme(self):
        value=self._read().get('theme')
        return value if value in ('dark','light') else 'dark'

    def _read(self):
        try:
            with self.path.open('r',encoding='utf-8') as source:
                data=json.loads(source.read(4096))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError,UnicodeError):return {}

    def network_target(self):
        from dsp408.connection_profile import DEFAULT_TARGET,target_profile
        data=self._read().get('network_target')
        try:return target_profile(data['ip'],data['device_id'])
        except (ValueError,KeyError,TypeError,AttributeError):return DEFAULT_TARGET.copy()

    def save_theme(self,value):
        if value not in ('dark','light'):raise ValueError('Choose dark or light theme.')
        self._save(self._updated(theme=value))

    def save_network_target(self,value):
        from dsp408.connection_profile import target_profile
        value=target_profile(value['ip'],value['device_id'])
        self._save(self._updated(network_target=value))

    def network_source_ip(self):
        from dsp408.connection_profile import source_address
        value=self._read().get('network_source_ip','')
        if value=='':return ''
        try:return source_address(value)
        except (ValueError,TypeError):return ''

    def save_network_connection(self,ip,device_id,source_ip):
        from dsp408.connection_profile import ethernet_profile
        target,source=ethernet_profile(ip,device_id,source_ip)
        self._save(self._updated(network_target=target,network_source_ip=source or ''))

    def meter_poll_ms(self):
        value=self._read().get('meter_poll_ms',100)
        return value if type(value) is int and value in (100,300) else 100

    def save_meter_poll_ms(self,value):
        if type(value) is not int or value not in (100,300):raise ValueError('Choose 100 or 300 ms.')
        self._save(self._updated(meter_poll_ms=value))

    def dynamics_display(self):
        value=self._read().get('dynamics_display',True)
        return value if type(value) is bool else True

    def save_dynamics_display(self,value):
        if type(value) is not bool:raise ValueError('Choose enabled or disabled.')
        self._save(self._updated(dynamics_display=value))

    def ambient_temperature(self):
        from dsp408.delay import checked_temperature,DEFAULT_TEMPERATURE
        try:return checked_temperature(self._read().get('ambient_temperature',DEFAULT_TEMPERATURE))
        except (ValueError,TypeError):return DEFAULT_TEMPERATURE

    def save_ambient_temperature(self,value):
        from dsp408.delay import checked_temperature
        self._save(self._updated(ambient_temperature=checked_temperature(value)))

    def delay_air_conditions(self):
        from dsp408.delay import checked_air_conditions,DEFAULT_HUMIDITY,DEFAULT_PRESSURE_HPA
        default={'enabled':False,'humidity':DEFAULT_HUMIDITY,'pressure_hpa':DEFAULT_PRESSURE_HPA}
        try:return checked_air_conditions(self._read().get('delay_air_conditions',default))
        except (ValueError,TypeError,KeyError):return default

    def save_delay_air_conditions(self,value):
        from dsp408.delay import checked_air_conditions
        self._save(self._updated(delay_air_conditions=checked_air_conditions(value)))

    def _updated(self,**changes):
        saved=self._read();data={'schema':1,'theme':self.theme()}
        # Preserve all known optional preferences across unrelated UI edits.
        # Omitted fields keep their defaults without changing old file shapes.
        for key,reader in (('network_target',self.network_target),('meter_poll_ms',self.meter_poll_ms),
                           ('network_source_ip',self.network_source_ip),
                           ('dynamics_display',self.dynamics_display),
                           ('ambient_temperature',self.ambient_temperature),
                           ('delay_air_conditions',self.delay_air_conditions)):
            if key in saved:data[key]=reader()
        data.update(changes)
        return data

    def _save(self,data):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,
                                             prefix='ui-preferences-',suffix='.tmp',delete=False) as target:
                temporary=Path(target.name)
                json.dump(data,target);target.flush();os.fsync(target.fileno())
            os.replace(temporary,self.path)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
