"""Writable application data, separate from installed executables and assets."""
import os
import sys
import configparser
import re
from pathlib import Path


def installed_instance_id():
    """Only an installed side copy has this small installer-owned marker."""
    if not getattr(sys,'frozen',False):return ''
    marker=Path(sys.executable).resolve().parent/'dsp408-instance.ini'
    if not marker.exists():return ''
    parser=configparser.ConfigParser(interpolation=None)
    try:
        with marker.open(encoding='utf-8-sig') as source:data=source.read(2049)
        if len(data)>2048:raise ValueError('Instance marker too large')
        parser.read_string(data);value=parser['Instance']['Id']
        if not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Invalid instance ID')
    except (OSError,ValueError,KeyError,configparser.Error) as error:
        raise ValueError('Invalid installed copy marker; reinstall this copy.') from error
    return value


def application_name():
    instance=installed_instance_id()
    return 'DSP408FIR Control'+(' (Copy '+instance[:8]+')' if instance else '')


def data_directory():
    override=os.environ.get('DSP408_DATA_DIR')
    if override:
        path=Path(override)
        if not path.is_absolute():raise ValueError('DSP408_DATA_DIR must be an absolute path')
        return path
    if getattr(sys,'frozen',False):
        if sys.platform=='darwin':
            data=Path.home()/'Library'/'Application Support'/'gremium.tech'/'DSP408FIR Control'
        else:
            base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
            data=base/'gremium.tech'/'DSP408 Control'
        instance=installed_instance_id()
        return data/'instances'/instance if instance else data
    return Path(__file__).resolve().parents[1]/'work'


DATA_DIRECTORY=data_directory()
PREFERENCES_PATH=DATA_DIRECTORY/'ui-preferences.json'
JOURNAL_DIRECTORY=DATA_DIRECTORY/'hardware-captures'
