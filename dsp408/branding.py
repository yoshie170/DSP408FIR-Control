"""Application-owned assets, relative to the package in source and bundles."""
from pathlib import Path
import sys
from PySide6.QtGui import QIcon

ICON_DIRECTORY=Path(__file__).resolve().parent/'assets'/'icons'


def application_icon():
    name='dsp408-512.png' if sys.platform=='darwin' else 'dsp408.ico'
    return QIcon(str(ICON_DIRECTORY/name))
