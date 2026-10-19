"""Isolated native installer/copy/uninstaller regression. Own workspace fixture only.

Uses an unrelated AppId, small inert own payload, current-user registry and no
shortcuts. Production AppId, files, preferences and DSP are never modified.
"""
import argparse
import configparser
import json
import re
import subprocess
import time
from pathlib import Path
import uuid
import winreg

ROOT=Path(__file__).resolve().parents[1]
UNINSTALL='\\'.join(('Software','Microsoft','Windows','CurrentVersion','Uninstall',''))


def registration(identity):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,UNINSTALL+identity+'_is1',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            return {name:winreg.QueryValueEx(key,name)[0] for name in ('DisplayVersion','InstallLocation','UninstallString','DisplayName')}
    except FileNotFoundError:return None


def run(args,cwd,timeout=90):
    return subprocess.run([str(a) for a in args],cwd=cwd,capture_output=True,timeout=timeout)


def cleanup_fixture(output):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()):raise ValueError('Workspace fixtures only')
    text=(output/'update-fixture.iss').read_text(encoding='utf-8')
    identity=re.search(r"DSPBaseAppId = '(DSP408-Offline-Test-[0-9a-f]{32})'",text).group(1)
    candidates=set()
    for log in output.glob('*.log'):
        for key in re.findall(r'Creating new uninstall key: HKEY_CURRENT_USER.*\\([^\\\r\n]+)_is1',log.read_text(encoding='utf-8-sig')):
            if key.startswith(identity[:40]) or key.startswith('DSP408-Test-'):
                candidates.add(key)
    for key in candidates:
        record=registration(key)
        if record is None:continue
        directory=Path(record['InstallLocation']).resolve()
        assert directory in (output/'installed-primary',output/'installed-secondary')
        executable=Path(record['UninstallString'].strip('"')).resolve()
        assert executable.parent==directory and re.fullmatch(r'unins[0-9]{3}\.exe',executable.name)
        result=run([executable,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={output/"cleanup-owned.log"}'],output)
        result.check_returncode()
        assert registration(key) is None


def verify(compiler,output):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()) or output.exists():raise ValueError('Use a new work/ fixture directory')
    output.mkdir(parents=True)
    identity='DSP408-Offline-Test-'+uuid.uuid4().hex
    copy_prefix='DSP408-Test-'+uuid.uuid4().hex[:8]+'-'
    assert registration(identity) is None
    source=ROOT/'packaging/windows'
    inert=ROOT/'work/maintenance-temperature-v162/native-complete/version-test.exe'
    if not inert.is_file():raise ValueError('Run verify_installer_update first')
    bundle=output/'payload';bundle.mkdir()
    (bundle/'DSP408FIR Control.exe').write_bytes(inert.read_bytes())
    (bundle/'payload-marker.txt').write_text('verified-fixture-payload')
    primary=output/'installed-primary';secondary=output/'installed-secondary'
    script=(source/'DSP408_Control.iss').read_text(encoding='utf-8')
    script=script.replace('PrivilegesRequired=admin','PrivilegesRequired=lowest').replace('PrivilegesRequiredOverridesAllowed=dialog','PrivilegesRequiredOverridesAllowed=commandline')
    script=script.replace('#include "version.iss"',f'#include "{source / "version.iss"}"')
    script=script.replace('#include "update.iss"',f'#include "{output / "update-fixture.iss"}"')
    script=re.sub(r'#define AppIcon .*', '#define AppIcon "'+str(ROOT/'dsp408/assets/icons/dsp408.ico').replace('\\','/')+'"',script)
    # Never let a test execute the production legacy-shortcut cleanup.
    before,deletes=script.split('[InstallDelete]',1)
    deleted,after=deletes.split('[UninstallDelete]',1)
    assert deleted.count('Type: files;')==3
    script=before+'[UninstallDelete]'+after
    (output/'fixture.iss').write_text(script,encoding='utf-8')
    code=(source/'update.iss').read_text(encoding='utf-8')
    assert code.count("DSPBaseAppId = '{5A2478C4-CECE-4280-A896-5AECE3478B04}'")==1
    code=code.replace("DSPBaseAppId = '{5A2478C4-CECE-4280-A896-5AECE3478B04}'", "DSPBaseAppId = '"+identity+"'")
    code=code.replace("DSPCopyAppPrefix = 'DSP408FIR-copy-'", "DSPCopyAppPrefix = '"+copy_prefix+"'")
    code=code.replace('#include "version_compare.iss"',f'#include "{source / "version_compare.iss"}"')
    code=code.replace('#include "application_use.iss"',f'#include "{source / "application_use.iss"}"')
    code=code.replace('procedure InitializeWizard;','procedure DSPFixtureWizard;')
    code=code.replace('function NextButtonClick(','function DSPFixtureNextButtonClick(')
    # Only this fixture confirms its own uninstall and runs its child silently.
    code=code.replace("MsgBox(FmtMessage(CustomMessage('ConfirmUninstall'), [DSPInstalledDirectory]), mbConfirmation, MB_YESNO)", 'IDYES')
    code=code.replace("Exec(Uninstaller, '/NORESTART'", "Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'")
    code += '''
procedure InitializeWizard;
begin
  DSPFixtureWizard;
  if DSPHasInstallation then DSPUpdatePage.SelectedValueIndex := StrToInt(ExpandConstant('{param:ACTION|0}'));
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := DSPFixtureNextButtonClick(CurPageID);
  if DSPHasInstallation then
    if (CurPageID = DSPUpdatePage.ID) and DSPCopyMode then
      WizardForm.DirEdit.Text := ExpandConstant('{param:DIR}');
end;
'''
    (output/'update-fixture.iss').write_text(code,encoding='utf-8')
    compiled=run([compiler,'/Q',f'/DAppSource={bundle}',f'/DSetupOutput={output}',output/'fixture.iss'],output)
    (output/'compile.txt').write_bytes(compiled.stdout+compiled.stderr);compiled.check_returncode()
    setup=output/'DSP408FIR-Control-0.9.1-Setup.exe'
    checks=[];copy_identity=None
    def install(directory,action,label):
        result=run([setup,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=',
                    f'/DIR={directory}',f'/ACTION={action}',f'/LOG={output/(label+".log")}'],output)
        if result.returncode:raise RuntimeError(f'{label}: exit{result.returncode}; inspect fixture log')
    def uninstall(identity,label):
        record=registration(identity)
        if record is None:return
        directory=Path(record['InstallLocation']).resolve()
        assert directory in (primary,secondary) and directory.is_relative_to(output)
        executable=Path(record['UninstallString'].strip('"')).resolve()
        assert executable.parent==directory and re.fullmatch(r'unins[0-9]{3}\.exe',executable.name)
        result=run([executable,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={output/(label+".log")}'],output)
        result.check_returncode()
        for _ in range(30):
            if registration(identity) is None:return
            time.sleep(.1)
        raise RuntimeError('Fixture registration survived uninstall')
    try:
        install(primary,0,'primary-install')
        assert Path(registration(identity)['InstallLocation']).resolve()==primary
        assert not (primary/'dsp408-instance.ini').exists();checks.append('primary instance unchanged')
        (primary/'payload-marker.txt').write_text('modified-before-update')
        install(primary,0,'primary-update')
        assert (primary/'payload-marker.txt').read_text()=='verified-fixture-payload';checks.append('primary update')
        install(secondary,1,'secondary-install')
        marker=configparser.ConfigParser();marker.read(secondary/'dsp408-instance.ini')
        instance=marker['Instance']['Id'];assert re.fullmatch('[0-9a-f]{32}',instance)
        copy_identity=copy_prefix+instance
        assert Path(registration(copy_identity)['InstallLocation']).resolve()==secondary
        assert '(Copy ' in registration(copy_identity)['DisplayName']
        assert registration(identity) is not None;checks.append('two independent registrations and copy marker')
        install(secondary,1,'secondary-update')
        marker.read(secondary/'dsp408-instance.ini');assert marker['Instance']['Id']==instance
        assert registration(copy_identity) is not None;checks.append('secondary update retains identity')
        result=run([setup,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=',
                    '/ACTION=2',f'/LOG={output/"maintenance-uninstall.log"}'],output)
        # Closing the maintenance wizard after successful child uninstall is a cancel exit.
        assert result.returncode in (1,2),result.returncode
        assert registration(identity) is None and not (primary/'DSP408FIR Control.exe').exists()
        assert registration(copy_identity) is not None and (secondary/'DSP408FIR Control.exe').exists()
        checks.append('maintenance uninstall removes only primary; no reinstall')
        uninstall(copy_identity,'secondary-uninstall')
        assert not (secondary/'DSP408FIR Control.exe').exists() and not (secondary/'dsp408-instance.ini').exists()
        checks.append('secondary uninstaller removes only its own instance')
    finally:
        if copy_identity:uninstall(copy_identity,'cleanup-secondary')
        uninstall(identity,'cleanup-primary')
        cleanup_fixture(output)
    report={'passed':True,'checks':checks,'fixture_appid':identity,'fixture_registry_writes':True,
            'production_installation_modified':False,'device_io':False,'registrations_remaining':False}
    (output/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compiler',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cleanup-fixture',action='store_true')
    args=parser.parse_args()
    if args.cleanup_fixture:cleanup_fixture(args.output);print('Own fixture cleanup complete')
    else:
        if not args.compiler:parser.error('--compiler required for verification')
        print(json.dumps(verify(args.compiler.resolve(),args.output),indent=2))
