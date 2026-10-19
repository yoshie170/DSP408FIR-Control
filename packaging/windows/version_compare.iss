function DSPVersionRelation(Installed, Incoming: String): Integer;
var
  Previous, Current: Int64;
begin
  { Unknown versions are treated as reinstall, never as a confirmed downgrade. }
  Result := 0;
  if (Installed <> '') and StrToVersion(Installed, Previous) and StrToVersion(Incoming, Current) then
    Result := ComparePackedVersion(Previous, Current);
end;
