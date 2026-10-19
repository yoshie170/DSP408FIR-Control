"""Build a native macOS .app/ZIP preview, verify it offline, never connect DSP."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CONFIG=runpy.run_path(str(ROOT/'packaging/macos/bundle_config.py'))


def native_target(requested=None):
    if sys.platform!='darwin':raise RuntimeError('Build the macOS preview on a Mac, not Windows.')
    target=requested or platform.machine()
    if target not in CONFIG['ARCHITECTURES'] or target!=platform.machine():
        raise ValueError('Use an arm64/x86_64 Python matching the requested architecture.')
    current=tuple(int(p) for p in platform.mac_ver()[0].split('.')[:2])
    minimum=tuple(int(p) for p in CONFIG['MINIMUM_MACOS'].split('.'))
    if current<minimum:raise RuntimeError('The Qt6.12 candidate requires macOS '+CONFIG['MINIMUM_MACOS']+' or newer.')
    return target


def build(arch=None):
    arch=native_target(arch)
    for tool in ('iconutil','codesign','lipo','ditto'):
        if not Path('/usr/bin',tool).is_file():raise FileNotFoundError('Required macOS tool: '+tool)
    version=runpy.run_path(str(ROOT/'dsp408/version.py'))
    env=os.environ.copy();env['DSP408_MAC_ARCH']=arch
    for key in ('PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'):
        env.pop(key,None)
    def run(*args):subprocess.run(list(map(str,args)),cwd=ROOT,env=env,check=True)
    run(sys.executable,ROOT/'tools/prepare_release_assets.py')
    run(sys.executable,ROOT/'tools/build_macos_icon.py')
    dist=ROOT/'dist/macos'/arch
    run(sys.executable,'-m','PyInstaller','--noconfirm','--distpath',dist,
        '--workpath',ROOT/'build/macos'/arch,ROOT/'packaging/macos/DSP408FIR_Control.spec')
    app=dist/(CONFIG['APP_NAME']+'.app')
    run(sys.executable,ROOT/'tools/verify_macos_bundle.py',app,'--arch',arch,
        '--output',ROOT/'work'/('macos-'+arch+'-verification'))
    archive=dist/('DSP408FIR-Control-'+version['VERSION']+'-macOS-'+arch+'.zip')
    run('/usr/bin/ditto','-c','-k','--keepParent',app,archive)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    return archive


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch',choices=CONFIG['ARCHITECTURES']);args=parser.parse_args()
    try:print(build(args.arch))
    except (RuntimeError,ValueError,FileNotFoundError) as error:parser.exit(2,str(error)+'\n')
