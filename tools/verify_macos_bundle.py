"""Explicit offline verification of the own macOS preview; no DSP connection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import runpy
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CONFIG=runpy.run_path(str(ROOT/'packaging/macos/bundle_config.py'))


def verify(bundle,arch,output):
    if sys.platform!='darwin':raise RuntimeError('Native macOS verification requires a Mac.')
    bundle=Path(bundle).resolve();output=Path(output).resolve()
    if not bundle.is_relative_to(ROOT/'dist') or bundle.suffix!='.app':
        raise ValueError('Verify the own .app under this project’s dist directory.')
    if arch not in CONFIG['ARCHITECTURES']:raise ValueError('Unsupported target architecture')
    output.mkdir(parents=True,exist_ok=True)
    with (bundle/'Contents/Info.plist').open('rb') as stream:info=plistlib.load(stream)
    version=runpy.run_path(str(ROOT/'dsp408/version.py'))
    assert info['CFBundleIdentifier']==CONFIG['BUNDLE_IDENTIFIER']
    for key,value in CONFIG['bundle_info'](version['VERSION'],version['BUILD']).items():
        assert info[key]==value,key
    executable=bundle/'Contents/MacOS'/CONFIG['APP_NAME']
    assert executable.resolve().is_relative_to(bundle)
    actual=subprocess.check_output(['/usr/bin/lipo','-archs',str(executable)],text=True).split()
    assert actual==[arch],actual
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(bundle)],check=True)
    env=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'):
        env.pop(key,None)
    env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
    with tempfile.TemporaryDirectory(prefix='macos-offline-',dir=output) as temporary:
        user=Path(temporary);env['DSP408_DATA_DIR']=str(user)
        report=user/'probe.json'
        run=subprocess.run([str(executable),'--verify-package',str(report)],cwd=user,
                           env=env,capture_output=True,timeout=45)
        assert run.returncode==0,(run.returncode,run.stderr.decode(errors='replace'))
        probe=json.loads(report.read_text(encoding='utf-8'))
        assert probe['frozen'] and not probe['connected'] and not probe['device_io']
        assert probe['preferences_write_read']
    assets=0
    for folder in ('qml','assets'):
        for source in (ROOT/'dsp408'/folder).rglob('*'):
            if not source.is_file():continue
            relative=source.relative_to(ROOT/'dsp408')
            candidates=[bundle/'Contents'/place/'dsp408'/relative for place in ('Resources','Frameworks')]
            target=next((p for p in candidates if p.is_file()),None)
            assert target and target.resolve().is_relative_to(bundle),str(relative)
            assert source.read_bytes()==target.read_bytes(),str(relative)
            assets+=1
    result={'passed':True,'architecture':arch,'version':version['VERSION'],'build':version['BUILD'],
            'bundle_identifier':info['CFBundleIdentifier'],'assets_equal':True,'source_asset_files':assets,
            'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
            'codesign_verified':True,'notarization_verified':False,'hardware_verified':False,
            'device_io':False,'stderr':run.stderr.decode(errors='replace')}
    (output/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path);parser.add_argument('--arch',required=True,choices=CONFIG['ARCHITECTURES'])
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(verify(args.bundle,args.arch,args.output),indent=2))
