"""Native Inno running-file guards; Abort before install, no registry writes.

Use only own fixture files under work/. An optional own frozen app can be
probed during its explicit --verify-package run; no DSP transports are opened.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def verify(compiler, output):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT/'work').resolve()):
        raise ValueError('Use a work/ test directory')
    output.mkdir(parents=True, exist_ok=True)
    source = output/'running-test.iss'
    if source.exists():
        raise ValueError('Choose a fresh verification directory')
    target = output/'selected'; target.mkdir()
    other = output/'other-copy'; other.mkdir()
    current = target/'DSP408FIR Control.exe'
    legacy = target/'DSP408 Control.exe'
    unrelated = other/current.name
    files = (current, legacy, unrelated)
    for path in files:
        path.write_bytes(b'Own non-executable installer guard fixture.\n')
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    installer = (ROOT/'packaging/windows/DSP408_Control.iss').read_text(encoding='utf-8')
    messages = installer.split('[CustomMessages]', 1)[1].split('[Code]', 1)[0]
    production = (ROOT/'packaging/windows/update.iss').read_text(encoding='utf-8')
    for name in ('version_compare.iss', 'application_use.iss'):
        production = production.replace(f'#include "{name}"', f'#include "{ROOT/"packaging/windows"/name}"')
    for event in ('InitializeSetup', 'InitializeWizard', 'NextButtonClick', 'ShouldSkipPage',
                  'PrepareToInstall', 'CurPageChanged', 'CancelButtonClick'):
        production = production.replace(event, 'DSPProduction'+event)
    source.write_text(f'''#include "{ROOT/'packaging/windows/version.iss'}"
[Setup]
AppName=DSP408 offline running-file test
AppVersion={{#AppVersion}}
AppId=DSP408OfflineRunningFileTest
DefaultDirName={target}
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir={output}
OutputBaseFilename=running-test
[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[CustomMessages]
{messages}
[Code]
{production}
procedure Check(Value: Boolean; Name: String);
begin
  if not Value then RaiseException('Guard check failed: ' + Name);
  SaveStringToFile(ExpandConstant('{{param:result}}'), Name+#13#10, True);
end;
function InitializeSetup: Boolean;
begin Result := True; end;
procedure InitializeWizard;
var
  Held: TFileStream;
  Restart: Boolean;
  I: Integer;
  Name, ErrorText, ProbeDirectory: String;
begin
  ProbeDirectory := ExpandConstant('{{param:probe|}}');
  if ProbeDirectory <> '' then begin
    ErrorText := DSPApplicationUseError(ProbeDirectory);
    Check((ErrorText <> '') = (ExpandConstant('{{param:busy|0}}') = '1'), 'actual-executable');
    Abort;
  end;
  DSPHasInstallation := True;
  DSPInstalledVersion := '0.9.0';
  DSPInstalledDirectory := '{target}';
  DSPProductionInitializeWizard;
  WizardForm.DirEdit.Text := '{target}';
  Check(DSPApplicationUseError('{target}') = '', 'closed-copy');
  Check(DSPProductionNextButtonClick(DSPUpdatePage.ID), 'closed-update-action');
  Check(DSPProductionPrepareToInstall(Restart) = '', 'closed-pre-install');
  for I := 0 to 1 do begin
    if I = 0 then Name := '{current}' else Name := '{legacy}';
    Held := TFileStream.Create(Name, fmOpenRead or fmShareDenyWrite);
    try
      ErrorText := DSPApplicationUseError('{target}');
      Check((ErrorText <> '') and (Pos('{target}', ErrorText) > 0), 'blocked-file-'+IntToStr(I));
      Check(not DSPProductionNextButtonClick(DSPUpdatePage.ID), 'blocked-update-action-'+IntToStr(I));
      Check(DSPProductionPrepareToInstall(Restart) <> '', 'blocked-pre-install-'+IntToStr(I));
      Check(not DSPRequireClosed('{target}'), 'silent-cancel-'+IntToStr(I));
    finally Held.Free; end;
    Check(DSPApplicationUseError('{target}') = '', 'released-file-'+IntToStr(I));
    Check(DSPProductionPrepareToInstall(Restart) = '', 'released-pre-install-'+IntToStr(I));
  end;
  Held := TFileStream.Create('{unrelated}', fmOpenRead or fmShareDenyWrite);
  try
    Check(DSPApplicationUseError('{target}') = '', 'independent-copy-allowed');
    Check(DSPApplicationUseError('{other}') <> '', 'selected-other-copy-blocked');
    DSPUpdatePage.SelectedValueIndex := 1;
    Check(DSPProductionNextButtonClick(DSPUpdatePage.ID), 'separate-copy-action-allowed');
    WizardForm.DirEdit.Text := '{output/'new-empty'}';
    Check(DSPProductionPrepareToInstall(Restart) = '', 'new-copy-allowed');
  finally Held.Free; end;
  Check(DSPApplicationUseError('{output/'absent'}') = '', 'new-install-allowed');
  Abort;
end;
''', encoding='utf-8')
    compile_run = subprocess.run([str(compiler), '/Q', str(source)], capture_output=True, timeout=30)
    (output/'compile.txt').write_bytes(compile_run.stdout+compile_run.stderr)
    compile_run.check_returncode()
    counts = {}
    for language in ('polish', 'english'):
        result = output/f'{language}.txt'
        log = output/f'{language}.log'
        run = subprocess.run([str(output/'running-test.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
            '/NORESTART', f'/LANG={language}', f'/result={result}', f'/LOG={log}'],
            capture_output=True, timeout=30)
        assert run.returncode == 1, run.returncode  # expected Abort before install
        lines = result.read_text(encoding='mbcs').splitlines()
        assert len(lines) == 20, lines
        counts[language] = len(lines)
        assert 'Deinitializing Setup' in log.read_text(encoding='utf-8-sig')
    assert hashes == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    report = {'passed': True, 'checks': counts, 'fixture_bytes_unchanged': True,
              'installation_performed': False, 'registry_writes': False, 'device_io': False}
    (output/'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def verify_frozen(output):
    """Probe this project's own EXE, letting --verify-package exit normally."""
    output = Path(output).resolve()
    executable = ROOT/'dist/DSP408FIR Control/DSP408FIR Control.exe'
    guard = output/'running-test.exe'
    user = output/'frozen-user'; user.mkdir()
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
        env.pop(key, None)
    windows = Path(env.get('SystemRoot', 'C:/Windows'))
    env.update(PATH=str(windows/'System32')+';'+str(windows), DSP408_DATA_DIR=str(user),
               QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_QPA_FONTDIR=str(windows/'Fonts'))
    before = hashlib.sha256(executable.read_bytes()).hexdigest()
    package_result = output/'frozen-package.json'
    process = subprocess.Popen([str(executable), '--verify-package', str(package_result)],
                               cwd=output, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        result = output/'actual-running.txt'
        run = subprocess.run([str(guard), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
            f'/probe={executable.parent}', '/busy=1', f'/result={result}', f'/LOG={output/"actual-running.log"}'],
            capture_output=True, timeout=30)
        assert run.returncode == 1 and result.read_text(encoding='mbcs').strip() == 'actual-executable'
    finally:
        stdout, stderr = process.communicate(timeout=45)  # no forced termination
    assert process.returncode == 0, (process.returncode, stdout, stderr)
    package = json.loads(package_result.read_text(encoding='utf-8'))
    assert package['frozen'] and not package['device_io'] and not package['connected']
    result = output/'actual-closed.txt'
    run = subprocess.run([str(guard), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
        f'/probe={executable.parent}', '/busy=0', f'/result={result}', f'/LOG={output/"actual-closed.log"}'],
        capture_output=True, timeout=30)
    assert run.returncode == 1 and result.read_text(encoding='mbcs').strip() == 'actual-executable'
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == before
    report = {'passed': True, 'actual_executable_running_blocked': True, 'closed_allowed': True,
              'exe_unchanged': True, 'process_exited_normally': True, 'device_io': False,
              'installation_performed': False}
    (output/'actual-executable.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frozen', action='store_true', help='Also probe the own dist EXE in offline verification mode')
    args = parser.parse_args()
    print(json.dumps(verify(args.compiler, args.output), indent=2))
    if args.frozen:
        print(json.dumps(verify_frozen(args.output), indent=2))
