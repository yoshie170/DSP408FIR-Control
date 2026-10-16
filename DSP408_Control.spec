# Windows onedir build; offline release verification never opens a DSP.
# python -m PyInstaller DSP408_Control.spec
from pathlib import Path
import os
import sys

root=Path(SPECPATH)
icons=root/'dsp408'/'assets'/'icons'
a=Analysis(
    [str(root/'main.py')],pathex=[str(root)],binaries=[],
    datas=[(str(root/'dsp408'/'qml'),'dsp408/qml'),
           (str(root/'dsp408'/'assets'),'dsp408/assets')],
    hiddenimports=['hid','PySide6.QtSvg'],hookspath=[str(root/'packaging'/'windows'/'hooks')],runtime_hooks=[],
    excludes=['pytest','capstone','pefile','pypdf','PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick'],
)
# Reject accidental libraries from unrelated SDKs/tools on the build machine.
allowed_roots=(root.resolve(),Path(sys.base_prefix).resolve(),Path(os.environ['SystemRoot']).resolve())
for entry in a.binaries:
    if not any(Path(entry[1]).resolve().is_relative_to(folder) for folder in allowed_roots):
        raise ValueError('Unexpected external build dependency: '+entry[1])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='DSP408 Control',
        debug=False,strip=False,upx=False,console=os.environ.get('DSP408_BUILD_CONSOLE')=='1',icon=str(icons/'dsp408.ico'),
        version=str(root/'packaging'/'windows'/'version_info.txt'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='DSP408 Control')
