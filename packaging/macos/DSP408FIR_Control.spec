# Build only on macOS, with a Python/dependency environment for the target CPU.
from pathlib import Path
import os
import platform
import runpy
import sys

if sys.platform != 'darwin':
    raise SystemExit('Build the macOS application on macOS.')
root = Path(SPECPATH).resolve().parents[1]
config = runpy.run_path(str(root/'packaging/macos/bundle_config.py'))
version = runpy.run_path(str(root/'dsp408/version.py'))
target = os.environ.get('DSP408_MAC_ARCH', platform.machine())
if target not in config['ARCHITECTURES'] or target != platform.machine():
    raise SystemExit('Use a native arm64 or x86_64 Python matching DSP408_MAC_ARCH.')
icon = root/'build/macos/icons/dsp408.icns'
if not icon.is_file():
    raise SystemExit('Generate the macOS icon first with tools/build_macos.py.')

a = Analysis([str(root/'main.py')], pathex=[str(root)], binaries=[],
    datas=[(str(root/'dsp408/qml'), 'dsp408/qml'),
           (str(root/'dsp408/assets'), 'dsp408/assets')],
    hiddenimports=['hid', 'PySide6.QtSvg'], hookspath=[str(root/'packaging/hooks')],
    runtime_hooks=[], excludes=['pytest', 'capstone', 'pefile', 'pypdf',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=config['APP_NAME'],
    debug=False, strip=False, upx=False, console=False, argv_emulation=False,
    target_arch=target, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=config['APP_NAME'])
app = BUNDLE(coll, name=config['APP_NAME']+'.app', icon=str(icon),
    bundle_identifier=config['BUNDLE_IDENTIFIER'],
    info_plist=config['bundle_info'](version['VERSION'], version['BUILD']))
