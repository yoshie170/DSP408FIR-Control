"""Compile an own minimal Inno wizard to verify license controls, then Abort.

No files are installed, registry keys written, or DSP transports opened.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def verify(compiler,output):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()) or output.exists():
        raise ValueError('Choose a fresh work/ verification folder')
    output.mkdir(parents=True)
    installer=(ROOT/'packaging/windows/DSP408_Control.iss').read_text(encoding='utf-8')
    directives=[]
    for key in ('LicenseFile','InfoBeforeFile'):
        line=next(line for line in installer.splitlines() if line.startswith(key+'='))
        directives.append(line.replace('{#SourcePath}..\\..\\',str(ROOT)+'\\'))
    source=output/'license-test.iss'
    source.write_text('''[Setup]
AppName=DSP408 offline license test
AppVersion=1
AppId=DSP408OfflineLicenseTest
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir='''+str(output)+'''
OutputBaseFilename=license-test
'''+ '\n'.join(directives)+'''
[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Code]
procedure InitializeWizard;
begin
  if Pos('MIT License', WizardForm.LicenseMemo.Text) = 0 then RaiseException('Missing MIT text');
  if Pos('Copyright © 2026 Łukasz Białas', WizardForm.LicenseMemo.Text) = 0 then RaiseException('Missing Unicode author');
  if Pos('Permission is hereby granted', WizardForm.LicenseMemo.Text) = 0 then RaiseException('Incomplete MIT text');
  if Pos('WITHOUT WARRANTY', WizardForm.LicenseMemo.Text) = 0 then RaiseException('Missing disclaimer');
  if WizardForm.LicenseAcceptedRadio.Checked then RaiseException('License is already accepted');
  if not WizardForm.LicenseNotAcceptedRadio.Checked then RaiseException('Expected default rejection');
  WizardForm.LicenseAcceptedRadio.Checked := True;
  if not WizardForm.LicenseAcceptedRadio.Checked then RaiseException('Cannot accept license');
  if Pos('Author: Łukasz Białas', WizardForm.InfoBeforeMemo.Text) = 0 then RaiseException('Missing author information');
  if Pos('Independent software', WizardForm.InfoBeforeMemo.Text) = 0 then RaiseException('Missing independence notice');
  SaveStringToFile(ExpandConstant('{param:result}'), 'MIT/full-text/Unicode/acceptance/author/independence PASS', False);
  Abort;
end;
''',encoding='utf-8-sig')
    compiled=subprocess.run([str(compiler),'/Q',str(source)],capture_output=True,timeout=30)
    (output/'compile.txt').write_bytes(compiled.stdout+compiled.stderr);compiled.check_returncode()
    for language in ('polish','english'):
        result=output/(language+'.txt')
        executed=subprocess.run([str(output/'license-test.exe'),'/SUPPRESSMSGBOXES','/NORESTART',
            '/LANG='+language,'/result='+str(result),'/LOG='+str(output/(language+'.log'))],
            capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        assert executed.returncode==1,(executed.returncode,executed.stderr)
        assert result.read_text()=='MIT/full-text/Unicode/acceptance/author/independence PASS'
    data={'passed':True,'languages':['polish','english'],'normal_license_default_unaccepted':True,
          'full_mit_text':True,'unicode_author':True,'author_and_independence':True,
          'installation_performed':False,'registry_writes':False,'device_io':False}
    (output/'validation.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.compiler,args.output),indent=2))
