"""Run actual Inno version comparison without installing or touching registry.

The own harness exits from InitializeSetup; a second creates the wizard and
Aborts from InitializeWizard before installation. Both run without elevation.
It shares the production Pascal function, runs as user and writes only work/.
"""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CASES=[('', '0.9.1', 0), ('0.9.0','0.9.1',-1), ('0.9.0.160','0.9.1',-1),
       ('0.8.9','0.9.1',-1), ('0.9.1','0.9.1',0), ('0.9.1.0','0.9.1',0),
       ('0.9.2','0.9.1',1), ('0.10.0','0.9.1',1), ('0.9.10','0.9.1',1),
       ('1.0.0','0.9.1',1), ('invalid','0.9.1',0)]


def verify(compiler,output):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()):raise ValueError('Use a work/ test directory')
    output.mkdir(parents=True,exist_ok=True)
    result=output/'version-cases.txt'
    if result.exists():raise ValueError('Choose a fresh verification directory')
    source=output/'inno-version-test.iss'
    checks='\n'.join(f"  SaveStringToFile('{result}', '{old} -> {new} = '+IntToStr(DSPVersionRelation('{old}', '{new}'))+#13#10, True);" for old,new,_ in CASES)
    source.write_text(f'''[Setup]
AppName=DSP408 installer comparison test
AppVersion=1
AppId=DSP408OfflineVersionTest
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir={output}
OutputBaseFilename=version-test
[Code]
#include "{ROOT/'packaging/windows/version_compare.iss'}"
function InitializeSetup: Boolean;
begin
{checks}
  Result := False;
end;
''',encoding='utf-8')
    compiled=subprocess.run([str(compiler),'/Q',str(source)],capture_output=True,timeout=30)
    (output/'compile.txt').write_bytes(compiled.stdout+compiled.stderr)
    compiled.check_returncode()
    executed=subprocess.run([str(output/'version-test.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/LOG={output/"run.log"}'],capture_output=True,timeout=30)
    # Inno returns1 for InitializeSetup=False (intentional test termination).
    assert executed.returncode==1,executed.returncode
    lines=result.read_text(encoding='utf-8-sig').splitlines()
    assert len(lines)==len(CASES)
    for line,(_,_,expected) in zip(lines,CASES):
        value=int(line.rsplit('=',1)[1]);assert (value>0)-(value<0)==expected,line
    wizard_cases=verify_wizard(compiler,output)
    report=dict(cases=len(CASES),wizard_cases=wizard_cases,passed=True,installation_performed=False,registry_writes=False,device_io=False)
    (output/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def verify_wizard(compiler,output):
    """Create the real wizard, test its update page, Abort before installation."""
    installer=(ROOT/'packaging/windows/DSP408_Control.iss').read_text(encoding='utf-8')
    messages=installer.split('[CustomMessages]',1)[1].split('[Code]',1)[0]
    production=(ROOT/'packaging/windows/update.iss').read_text(encoding='utf-8')
    production=production.replace('#include "version_compare.iss"',f'#include "{ROOT / "packaging/windows/version_compare.iss"}"')
    for name in ('InitializeSetup','InitializeWizard','CurPageChanged'):
        production=production.replace(name,'DSPProduction'+name)
    source=output/'wizard-test.iss'
    source.write_text(f'''#include "{ROOT/'packaging/windows/version.iss'}"
[Setup]
AppName=DSP408 offline wizard test
AppVersion={{#AppVersion}}
AppId=DSP408OfflineWizardTest
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir={output}
OutputBaseFilename=wizard-test
[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[CustomMessages]
{messages}
[Code]
{production}
function InitializeSetup: Boolean;
begin
  Result := True;
end;
procedure InitializeWizard;
var
  Data: String;
begin
  DSPInstalledVersion := ExpandConstant('{{param:installed|}}');
  DSPInstalledDirectory := '{output}';
  DSPIsUpdate := DSPVersionRelation(DSPInstalledVersion, '{{#AppVersion}}') < 0;
  DSPProductionInitializeWizard;
  Data := 'update='+IntToStr(Ord(DSPIsUpdate))+#13#10;
  if DSPIsUpdate then begin
    DSPProductionCurPageChanged(DSPUpdatePage.ID);
    Data := Data+'page_button='+WizardForm.NextButton.Caption+#13#10;
    DSPProductionCurPageChanged(wpReady);
    Data := Data+'ready_button='+WizardForm.NextButton.Caption+#13#10;
    Data := Data+'directory='+WizardForm.DirEdit.Text+#13#10;
    Data := Data+'details='+CustomMessage('UpdateDetails')+#13#10;
  end else DSPProductionCurPageChanged(wpReady);
  SaveStringToFile(ExpandConstant('{{param:result}}'), Data, False);
  Abort;
end;
''',encoding='utf-8')
    compiled=subprocess.run([str(compiler),'/Q',str(source)],capture_output=True,timeout=30)
    (output/'wizard-compile.txt').write_bytes(compiled.stdout+compiled.stderr);compiled.check_returncode()
    cases=[('polish','0.9.0',True),('english','0.9.0.160',True),('polish','',False),('english','0.9.1',False)]
    for index,(language,installed,update) in enumerate(cases):
        result=output/f'wizard-{index}.txt';log=output/f'wizard-{index}.log'
        run=subprocess.run([str(output/'wizard-test.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
                            f'/LANG={language}',f'/installed={installed}',f'/result={result}',f'/LOG={log}'],capture_output=True,timeout=30)
        assert run.returncode==1,run.returncode
        text=result.read_text(encoding='mbcs');assert 'update='+str(int(update)) in text
        if update:
            action='Aktualizuj' if language=='polish' else 'Update'
            assert 'page_button='+action in text and 'ready_button='+action in text
            assert 'directory='+str(output) in text
        assert 'Deinitializing Setup' in log.read_text(encoding='utf-8-sig')
    return len(cases)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compiler',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.compiler,args.output),indent=2))
