"""Writable application data, separate from installed executables and assets."""
import os
import sys
from pathlib import Path


def data_directory():
    override=os.environ.get('DSP408_DATA_DIR')
    if override:
        path=Path(override)
        if not path.is_absolute():raise ValueError('DSP408_DATA_DIR must be an absolute path')
        return path
    if getattr(sys,'frozen',False):
        base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
        return base/'gremium.tech'/'DSP408 Control'
    return Path(__file__).resolve().parents[1]/'work'


DATA_DIRECTORY=data_directory()
PREFERENCES_PATH=DATA_DIRECTORY/'ui-preferences.json'
JOURNAL_DIRECTORY=DATA_DIRECTORY/'hardware-captures'
