"""Offline install/uninstall acceptance in an isolated workspace directory.

Runs only our own build, with no DSP enumeration or connection. Creates no
shortcuts. Refuses to replace an existing registered installation or directory.
"""
import hashlib
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg

ROOT=Path(__file__).resolve().parents[1]
import runpy
VERSION=runpy.run_path(str(ROOT/'dsp408/version.py'))['VERSION']
WORK=ROOT/'work/release-verification/windows'
KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{5A2478C4-CECE-4280-A896-5AECE3478B04}_is1'


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,KEY,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY):return True
    except FileNotFoundError:return False


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(args,*,env=None,cwd=WORK,timeout=60):
    result=subprocess.run([str(x) for x in args],cwd=cwd,env=env,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode:raise RuntimeError(f'{Path(args[0]).name} exit{result.returncode}: {result.stderr[-2000:]!r}')
    return result


def probe(executable,label):
    environment=os.environ.copy()
    for key in ('PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'):
        environment.pop(key,None)
    windows=Path(environment.get('SystemRoot',r'C:\Windows'))
    environment['PATH']=str(windows/'System32')+';'+str(windows)
    environment['QT_QPA_PLATFORM']='offscreen'
    environment['QT_QUICK_BACKEND']='software'
    environment['QT_QPA_FONTDIR']=str(windows/'Fonts')
    environment['DSP408_DATA_DIR']=str(WORK/'test-user-data')
    cwd=WORK/'empty-working-directory';cwd.mkdir(exist_ok=True)
    report=WORK/f'{label}-probe.json';image=WORK/f'{label}.png'
    start=time.perf_counter()
    run([executable,'--verify-package',report,'--screenshot',image,'--theme','dark'],env=environment,cwd=cwd,timeout=45)
    data=json.loads(report.read_text(encoding='utf-8'))
    assert data.get('frozen') and data.get('preferences_write_read') and not data['connected']
    assert not data['device_io'] and len(data['icon_sizes'])>=7 and image.stat().st_size>10000
    return {'seconds_including_1_2s_render_delay':time.perf_counter()-start,'report':report.name,'image':image.name}


def verify():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('The Program Files installer test requires an elevated shell; no UAC prompt is started automatically')
    setup=ROOT/f'dist/installer/DSP408FIR-Control-{VERSION}-Setup.exe'
    bundle=ROOT/'dist/DSP408FIR Control'
    destination=(WORK/'install-test').resolve()
    assert destination.is_relative_to(WORK.resolve()) and destination.parent==WORK.resolve()
    if registered():raise RuntimeError('Existing installation: do not replace it during verification')
    if destination.exists():raise RuntimeError('Test destination already exists; choose a fresh test run')
    data=WORK/'test-user-data';data.mkdir(exist_ok=True)
    preferences=data/'ui-preferences.json'
    expected_preferences='{"schema":1,"theme":"light"}'
    if preferences.exists():
        if preferences.read_text(encoding='utf-8')!=expected_preferences:
            raise RuntimeError('Unexpected existing test preferences; leaving them intact')
    else:preferences.write_text(expected_preferences,encoding='utf-8')
    preference_hash=digest(preferences)
    result={'scope':'Own build only, no DSP I/O; temporary all-users installation, no shortcuts',
            'setup_sha256':digest(setup),'bundle_probe':probe(bundle/'DSP408FIR Control.exe','bundle')}
    # Paths are individual arguments, never concatenated shell commands.
    run([setup,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=',
         f'/DIR={destination}',f'/LOG={WORK / "install.log"}'])
    try:
        assert registered()
        files=[p for p in bundle.rglob('*') if p.is_file()]
        for source in files:
            target=destination/source.relative_to(bundle)
            assert target.is_file() and digest(source)==digest(target), str(source)
        result['installed_files_verified']=len(files)
        result['installed_probe']=probe(destination/'DSP408FIR Control.exe','installed')
    finally:
        # Only uninstall the verified workspace installation, never another copy.
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,KEY,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            location=winreg.QueryValueEx(key,'InstallLocation')[0]
        assert Path(location).resolve()==destination
        run([destination/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={WORK / "uninstall.log"}'])
    for _ in range(30):
        if not registered() and not (destination/'DSP408FIR Control.exe').exists():break
        time.sleep(.1)
    assert not registered() and not (destination/'DSP408FIR Control.exe').exists()
    assert digest(preferences)==preference_hash
    result.update(uninstall_verified=True,user_preferences_preserved=True,physical_io=False)
    (WORK/'install-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':verify()
