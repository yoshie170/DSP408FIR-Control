"""Application-owned assets, relative to the package in source and bundles."""
from pathlib import Path
from PySide6.QtGui import QIcon

ICON_DIRECTORY=Path(__file__).resolve().parent/'assets'/'icons'


def application_icon():
    return QIcon(str(ICON_DIRECTORY/'dsp408.ico'))
