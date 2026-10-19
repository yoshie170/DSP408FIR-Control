const
  DSPUninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{5A2478C4-CECE-4280-A896-5AECE3478B04}_is1';
var
  DSPInstalledVersion, DSPInstalledDirectory: String;
  DSPIsUpdate: Boolean;
  DSPUpdatePage: TOutputMsgWizardPage;

#include "version_compare.iss"

function DSPReadInstalled(Root: Integer): Boolean;
begin
  Result := RegQueryStringValue(Root, DSPUninstallKey, 'DisplayVersion', DSPInstalledVersion);
  if Result then
    RegQueryStringValue(Root, DSPUninstallKey, 'InstallLocation', DSPInstalledDirectory);
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  { Inno retains the previous install mode. Do not mix per-user and all-users copies. }
  if IsAdminInstallMode then begin
    if not DSPReadInstalled(HKLM64) then DSPReadInstalled(HKLM32);
  end else begin
    if not DSPReadInstalled(HKCU64) then DSPReadInstalled(HKCU32);
  end;
  if DSPVersionRelation(DSPInstalledVersion, '{#AppVersion}') > 0 then begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('NewerInstalled'), [DSPInstalledVersion]), mbError, MB_OK, IDOK);
    Result := False;
  end;
  DSPIsUpdate := DSPVersionRelation(DSPInstalledVersion, '{#AppVersion}') < 0;
end;

procedure InitializeWizard;
begin
  if DSPIsUpdate then begin
    DSPUpdatePage := CreateOutputMsgPage(wpWelcome, CustomMessage('UpdateTitle'),
      FmtMessage(CustomMessage('UpdateDescription'), [DSPInstalledVersion]), CustomMessage('UpdateDetails'));
    if DirExists(DSPInstalledDirectory) then WizardForm.DirEdit.Text := DSPInstalledDirectory;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if DSPIsUpdate then
    if (CurPageID = DSPUpdatePage.ID) or (CurPageID = wpReady) then
      WizardForm.NextButton.Caption := CustomMessage('UpdateAction');
end;
