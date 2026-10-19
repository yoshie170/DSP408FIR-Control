// Check only the selected installation, including versions without a mutex.
// Opening an EXISTING file exclusively never creates, truncates or writes it.
// Keep CloseApplications=no: Setup must not shut down a DSP session itself.
function DSPApplicationUseError(Directory: String): String;
var
  I: Integer;
  FileName: String;
  Probe: TFileStream;
begin
  Result := '';
  for I := 0 to 1 do begin
    if I = 0 then FileName := 'DSP408FIR Control.exe'
    else FileName := 'DSP408 Control.exe';
    FileName := AddBackslash(Directory) + FileName;
    if FileExists(FileName) then begin
      try
        Probe := TFileStream.Create(FileName, fmOpenReadWrite or fmShareExclusive);
        Probe.Free;
      except
        Log('Selected installation is in use or inaccessible: ' + FileName);
        Result := FmtMessage(CustomMessage('ApplicationInUse'), [Directory]);
        Exit;
      end;
    end;
  end;
end;

function DSPRequireClosed(Directory: String): Boolean;
var ErrorText: String;
begin
  Result := False;
  repeat
    ErrorText := DSPApplicationUseError(Directory);
    if ErrorText = '' then begin Result := True; Exit; end;
  until SuppressibleMsgBox(ErrorText, mbError, MB_RETRYCANCEL, IDCANCEL) <> IDRETRY;
end;

function InitializeUninstall: Boolean;
begin
  Result := DSPRequireClosed(ExpandConstant('{app}'));
end;
