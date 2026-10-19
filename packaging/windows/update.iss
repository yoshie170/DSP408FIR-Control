const
  DSPBaseAppId = '{5A2478C4-CECE-4280-A896-5AECE3478B04}';
  DSPCopyAppPrefix = 'DSP408FIR-copy-';
  DSPUninstallBase = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\';
var
  DSPInstalledVersion, DSPInstalledDirectory, DSPInstalledUninstaller: String;
  DSPNewCopyId, DSPCopyInstance: String;
  DSPHasInstallation, DSPCopyMode, DSPExitAfterUninstall: Boolean;
  DSPInstalledRoot: Int64;
  DSPUpdatePage: TInputOptionWizardPage;

#include "version_compare.iss"

function DSPValidInstance(Value: String): Boolean;
var I: Integer;
begin
  Result := Length(Value) = 32;
  if not Result then Exit;
  for I := 1 to Length(Value) do
    if Pos(Value[I], '0123456789abcdef') = 0 then begin Result := False; Exit; end;
end;

function DSPActiveInstance: String;
begin
  if DSPCopyMode then Result := DSPCopyInstance
  else Result := ExpandConstant('{param:INSTANCE|}');
  if (Result <> '') and not DSPValidInstance(Result) then
    RaiseException('Invalid DSP408 installation instance.');
end;

function DSPAppId(Param: String): String;
begin
  Result := DSPBaseAppId;
  if DSPActiveInstance <> '' then Result := DSPCopyAppPrefix + DSPActiveInstance;
end;

function DSPDisplayName(Param: String): String;
begin
  Result := 'DSP408FIR Control';
  if DSPActiveInstance <> '' then Result := Result + ' (Copy ' + Copy(DSPActiveInstance, 1, 8) + ')';
end;

function DSPCopyId(Param: String): String;
begin
  Result := DSPActiveInstance;
end;

function DSPHasInstance: Boolean;
begin
  Result := DSPActiveInstance <> '';
end;

function DSPIsPrimary: Boolean;
begin
  Result := not DSPHasInstance;
end;

function DSPCanonicalPath(Value: String): String;
begin
  Result := Lowercase(RemoveBackslashUnlessRoot(ExpandFileName(Value)));
end;

function DSPPathsOverlap(First, Second: String): Boolean;
var A, B: String;
begin
  A := AddBackslash(DSPCanonicalPath(First)); B := AddBackslash(DSPCanonicalPath(Second));
  Result := (Pos(A, B) = 1) or (Pos(B, A) = 1);
end;

function DSPCheckedUninstaller(Directory, Command: String): String;
var FileName, Candidate: String; I: Integer;
begin
  Result := '';
  if (Directory = '') or (Command = '') then Exit;
  Candidate := RemoveQuotes(Trim(Command)); FileName := Lowercase(ExtractFileName(Candidate));
  if (Length(FileName) <> 12) or (Copy(FileName, 1, 5) <> 'unins') or
     (Copy(FileName, 9, 4) <> '.exe') then Exit;
  for I := 6 to 8 do if Pos(FileName[I], '0123456789') = 0 then Exit;
  if DSPCanonicalPath(ExtractFileDir(Candidate)) <> DSPCanonicalPath(Directory) then Exit;
  if FileExists(Candidate) then Result := Candidate;
end;

function DSPReadInstalled(Root: Int64): Boolean;
var Key, Command: String;
begin
  Key := DSPUninstallBase + DSPAppId('') + '_is1';
  Result := RegQueryStringValue(Root, Key, 'DisplayVersion', DSPInstalledVersion);
  if Result then begin
    DSPInstalledRoot := Root;
    RegQueryStringValue(Root, Key, 'InstallLocation', DSPInstalledDirectory);
    RegQueryStringValue(Root, Key, 'UninstallString', Command);
    DSPInstalledUninstaller := DSPCheckedUninstaller(DSPInstalledDirectory, Command);
  end;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if IsAdminInstallMode then begin
    DSPHasInstallation := DSPReadInstalled(HKLM64);
    if not DSPHasInstallation then DSPHasInstallation := DSPReadInstalled(HKLM32);
  end else begin
    DSPHasInstallation := DSPReadInstalled(HKCU64);
    if not DSPHasInstallation then DSPHasInstallation := DSPReadInstalled(HKCU32);
  end;
  if DSPVersionRelation(DSPInstalledVersion, '{#AppVersion}') > 0 then begin
    SuppressibleMsgBox(FmtMessage(CustomMessage('NewerInstalled'), [DSPInstalledVersion]), mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

procedure DSPActionChanged(Sender: TObject);
begin
  if DSPUpdatePage.SelectedValueIndex = 2 then WizardForm.NextButton.Caption := CustomMessage('UninstallAction')
  else if DSPUpdatePage.SelectedValueIndex = 1 then WizardForm.NextButton.Caption := SetupMessage(msgButtonNext)
  else WizardForm.NextButton.Caption := CustomMessage('UpdateAction');
end;

procedure InitializeWizard;
begin
  DSPNewCopyId := Lowercase(GetMD5OfUnicodeString(ExpandConstant('{tmp}') + GetDateTimeString('yyyymmddhhnnss', '-', ':')));
  if DSPHasInstallation then begin
    DSPUpdatePage := CreateInputOptionPage(wpWelcome, CustomMessage('UpdateTitle'),
      FmtMessage(CustomMessage('UpdateDescription'), [DSPInstalledVersion]), CustomMessage('MaintenanceDetails'), True, False);
    DSPUpdatePage.Add(CustomMessage('UpdateExisting'));
    DSPUpdatePage.Add(CustomMessage('InstallSeparate'));
    DSPUpdatePage.Add(CustomMessage('UninstallExisting'));
    DSPUpdatePage.SelectedValueIndex := 0;
    DSPUpdatePage.CheckListBox.OnClickCheck := @DSPActionChanged;
    DSPUpdatePage.CheckListBox.ItemEnabled[2] := DSPInstalledUninstaller <> '';
    if DirExists(DSPInstalledDirectory) then WizardForm.DirEdit.Text := DSPInstalledDirectory;
  end;
end;

function DSPDirectoryEmpty(Directory: String): Boolean;
var Entry: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(Directory) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then begin Result := False; Exit; end;
      until not FindNext(Entry);
    finally FindClose(Entry); end;
  end;
end;

function DSPValidateDirectory: String;
var Directory, Marker, Identity, Key, Registered, Version: String;
begin
  Result := ''; Directory := WizardDirValue;
  if DSPCopyMode then begin
    if (DSPInstalledDirectory <> '') and DSPPathsOverlap(Directory, DSPInstalledDirectory) then begin
      Result := CustomMessage('SeparateDirectory'); Exit;
    end;
    Marker := AddBackslash(Directory) + 'dsp408-instance.ini';
    DSPCopyInstance := DSPNewCopyId;
    if FileExists(Marker) then begin
      Identity := GetIniString('Instance', 'Id', '', Marker);
      if not DSPValidInstance(Identity) then begin Result := CustomMessage('UnsafeDirectory'); Exit; end;
      Key := DSPUninstallBase + DSPCopyAppPrefix + Identity + '_is1';
      if not RegQueryStringValue(DSPInstalledRoot, Key, 'InstallLocation', Registered) then begin
        Result := CustomMessage('UnsafeDirectory'); Exit;
      end;
      if DSPCanonicalPath(Registered) <> DSPCanonicalPath(Directory) then begin
        Result := CustomMessage('SeparateDirectory'); Exit;
      end;
      if RegQueryStringValue(DSPInstalledRoot, Key, 'DisplayVersion', Version) then
        if DSPVersionRelation(Version, '{#AppVersion}') > 0 then begin
          Result := FmtMessage(CustomMessage('NewerInstalled'), [Version]); Exit;
        end;
      DSPCopyInstance := Identity;
    end else if not DSPDirectoryEmpty(Directory) then Result := CustomMessage('UnsafeDirectory');
  end else if DSPHasInstallation then begin
    if DSPCanonicalPath(Directory) <> DSPCanonicalPath(DSPInstalledDirectory) then Result := CustomMessage('UseCopyAction');
  end else if FileExists(AddBackslash(Directory) + 'dsp408-instance.ini') or
              FileExists(AddBackslash(Directory) + 'DSP408FIR Control.exe') then Result := CustomMessage('UnsafeDirectory');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var Choice, ExitCode: Integer; ErrorText, Uninstaller: String;
begin
  Result := True;
  if DSPHasInstallation then begin
    if CurPageID = DSPUpdatePage.ID then begin
      Choice := DSPUpdatePage.SelectedValueIndex;
      if Choice = 2 then begin
        Result := False;
        Uninstaller := DSPCheckedUninstaller(DSPInstalledDirectory, DSPInstalledUninstaller);
        if Uninstaller = '' then begin MsgBox(CustomMessage('UninstallUnavailable'), mbError, MB_OK); Exit; end;
        if MsgBox(FmtMessage(CustomMessage('ConfirmUninstall'), [DSPInstalledDirectory]), mbConfirmation, MB_YESNO) <> IDYES then Exit;
        if Exec(Uninstaller, '/NORESTART', DSPInstalledDirectory, SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode) then begin
          if ExitCode = 0 then begin DSPExitAfterUninstall := True; WizardForm.Close; end;
        end else MsgBox(SysErrorMessage(ExitCode), mbError, MB_OK);
        Exit;
      end;
      DSPCopyMode := Choice = 1;
      if DSPCopyMode then begin
        DSPCopyInstance := DSPNewCopyId;
        WizardForm.DirEdit.Text := ExpandConstant('{autopf}\DSP408FIR Control Copy ') + Copy(DSPNewCopyId, 1, 8);
      end else WizardForm.DirEdit.Text := DSPInstalledDirectory;
    end;
  end;
  if CurPageID = wpSelectDir then begin
    ErrorText := DSPValidateDirectory;
    if ErrorText <> '' then begin MsgBox(ErrorText, mbError, MB_OK); Result := False; end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := DSPHasInstallation and not DSPCopyMode and (PageID = wpSelectDir);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := DSPValidateDirectory;
end;

procedure CurPageChanged(CurPageID: Integer);
var Choice: Integer;
begin
  if DSPHasInstallation then begin
    Choice := DSPUpdatePage.SelectedValueIndex;
    if CurPageID = DSPUpdatePage.ID then begin
      if Choice = 2 then WizardForm.NextButton.Caption := CustomMessage('UninstallAction')
      else if Choice = 1 then WizardForm.NextButton.Caption := SetupMessage(msgButtonNext)
      else WizardForm.NextButton.Caption := CustomMessage('UpdateAction');
    end else if (CurPageID = wpReady) and not DSPCopyMode then
      WizardForm.NextButton.Caption := CustomMessage('UpdateAction');
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if DSPExitAfterUninstall then begin Cancel := True; Confirm := False; end;
end;
