"""Run actual Inno version comparison without installing or registering an application.

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
    production=production.replace('#include "application_use.iss"',f'#include "{ROOT / "packaging/windows/application_use.iss"}"')
    for name in ('InitializeSetup','InitializeWizard','CurPageChanged','NextButtonClick','CancelButtonClick','ShouldSkipPage','PrepareToInstall'):
        production=production.replace(name,'DSPProduction'+name)
    source=output/'wizard-test.iss'
    existing=output/'existing';existing.mkdir()
    copy_folder=output/'secondary-empty';copy_folder.mkdir()
    uninstaller=existing/'unins000.exe';uninstaller.write_bytes(b'fixture-not-executed')
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
  Data, OriginalId: String;
  Choice, I: Integer;
begin
  DSPReadInstalled(HKCU64); DSPReadInstalled(HKLM64);
  DSPReadInstalled(HKCU32); DSPReadInstalled(HKLM32);
  DSPInstalledVersion := ExpandConstant('{{param:installed|}}');
  DSPInstalledDirectory := '{existing}';
  DSPInstalledUninstaller := '{uninstaller}';
  Log('registry roots read');
  DSPInstalledRoot := HKCU;
  Log('after root');
  DSPHasInstallation := DSPInstalledVersion <> '';
  Log('before production wizard');
  DSPProductionInitializeWizard;
  Log('after production wizard');
  OriginalId := DSPAppId('');
  Log('after ID');
  Data := 'maintenance='+IntToStr(Ord(DSPHasInstallation))+#13#10;
  if DSPHasInstallation then begin
    for I := 0 to 2 do Data := Data+'option'+IntToStr(I)+'='+DSPUpdatePage.CheckListBox.ItemCaption[I]+#13#10;
    Choice := StrToInt(ExpandConstant('{{param:action|0}}'));
    DSPUpdatePage.SelectedValueIndex := Choice;
    DSPActionChanged(nil);
    Data := Data+'page_button='+WizardForm.NextButton.Caption+#13#10;
    if Choice <> 2 then begin
      if not DSPProductionNextButtonClick(DSPUpdatePage.ID) then RaiseException('Action selection failed');
      if Choice = 1 then WizardForm.DirEdit.Text := '{copy_folder}';
      if DSPValidateDirectory <> '' then RaiseException('Valid directory refused');
      DSPProductionCurPageChanged(wpReady);
      Data := Data+'ready_button='+WizardForm.NextButton.Caption+#13#10;
      Data := Data+'directory='+WizardForm.DirEdit.Text+#13#10;
      Data := Data+'appid='+DSPAppId('')+#13#10+'original_id='+OriginalId+#13#10;
      Data := Data+'name='+DSPDisplayName('')+#13#10;
      if Choice = 1 then begin
        WizardForm.DirEdit.Text := '{existing}';
        if DSPValidateDirectory = '' then RaiseException('Overlapping copy allowed');
        WizardForm.DirEdit.Text := '{existing}\\child';
        if DSPValidateDirectory = '' then RaiseException('Nested copy allowed');
      end;
    end;
    Data := Data+'bad_uninstaller='+DSPCheckedUninstaller('{existing}', 'C:\\elsewhere\\unins000.exe')+#13#10;
  end else DSPProductionCurPageChanged(wpReady);
  SaveStringToFile(ExpandConstant('{{param:result}}'), Data, False);
  Abort;
end;
''',encoding='utf-8')
    compiled=subprocess.run([str(compiler),'/Q',str(source)],capture_output=True,timeout=30)
    (output/'wizard-compile.txt').write_bytes(compiled.stdout+compiled.stderr);compiled.check_returncode()
    cases=[('polish','0.9.0',0),('english','0.9.1',0),('polish','0.9.0',1),('english','0.9.0',1),
           ('polish','0.9.0',2),('english','0.9.0',2),('polish','',0)]
    for index,(language,installed,action) in enumerate(cases):
        result=output/f'wizard-{index}.txt';log=output/f'wizard-{index}.log'
        run=subprocess.run([str(output/'wizard-test.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
                            f'/LANG={language}',f'/installed={installed}',f'/action={action}',f'/result={result}',f'/LOG={log}'],capture_output=True,timeout=30)
        assert run.returncode==1,run.returncode
        text=result.read_text(encoding='mbcs');assert 'maintenance='+str(int(bool(installed))) in text
        if installed:
            if action==0:
                caption='Aktualizuj' if language=='polish' else 'Update'
                assert 'page_button='+caption in text and 'ready_button='+caption in text
                assert 'directory='+str(existing) in text
            elif action==1:
                lines=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
                assert lines['appid']!=lines['original_id'] and '-copy-' in lines['appid']
                assert '(Copy ' in lines['name'] and lines['directory']==str(copy_folder)
            else:assert 'page_button='+('Odinstaluj' if language=='polish' else 'Uninstall') in text
            assert all('option'+str(i)+'=' in text for i in range(3))
            assert 'bad_uninstaller=\n' in text
        assert 'Deinitializing Setup' in log.read_text(encoding='utf-8-sig')
    return len(cases)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compiler',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.compiler,args.output),indent=2))
