; Build with Inno Setup 6.7+. No drivers, firmware or network configuration.
#ifndef AppVersion
  #include "version.iss"
#endif
#ifndef AppSource
  #define AppSource SourcePath + "..\..\dist\DSP408FIR Control"
#endif
#ifndef SetupOutput
  #define SetupOutput SourcePath + "..\..\dist\installer"
#endif
#define AppExe "DSP408FIR Control.exe"
#define AppIcon SourcePath + "..\..\dsp408\assets\icons\dsp408.ico"

[Setup]
AppId={code:DSPAppId}
AppName=DSP408FIR Control
AppVersion={#AppVersion}
AppPublisher=Łukasz Białas · gremium.tech
AppPublisherURL=https://gremium.tech
AppSupportURL=https://github.com/yoshie170/DSP408FIR-Control/issues
AppUpdatesURL=https://github.com/yoshie170/DSP408FIR-Control/releases
AppCopyright=Copyright © 2026 Łukasz Białas
VersionInfoCopyright=Copyright © 2026 Łukasz Białas · gremium.tech
LicenseFile={#SourcePath}..\..\dsp408\assets\info\LICENSE.txt
InfoBeforeFile={#SourcePath}..\..\dsp408\assets\info\ABOUT.txt
DefaultDirName={autopf}\DSP408FIR Control
UsePreviousAppDir=yes
DefaultGroupName={code:DSPDisplayName}
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousPrivileges=no
UsePreviousLanguage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
WizardStyle=modern
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#SetupOutput}
OutputBaseFilename=DSP408FIR-Control-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
; Manual closure only: preserve the application's connected-DSP confirmation.
; application_use.iss blocks updates/uninstall while target files are in use.
CloseApplications=no
RestartApplications=no
UninstallDisplayName={code:DSPDisplayName}

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[INI]
Filename: "{app}\dsp408-instance.ini"; Section: "Instance"; Key: "Id"; String: "{code:DSPCopyId}"; Check: DSPHasInstance; Flags: uninsdeleteentry uninsdeletesectionifempty

[Icons]
Name: "{autoprograms}\{code:DSPDisplayName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Check: not WizardNoIcons
Name: "{autodesktop}\{code:DSPDisplayName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon; Check: not WizardNoIcons

; Rename only shortcuts/old executable owned by the previous application.
[InstallDelete]
Type: files; Name: "{app}\DSP408 Control.exe"; Check: DSPIsPrimary
Type: files; Name: "{autoprograms}\DSP408 Control.lnk"; Check: DSPIsPrimary
Type: files; Name: "{autodesktop}\DSP408 Control.lnk"; Check: DSPIsPrimary

[UninstallDelete]
Type: files; Name: "{app}\dsp408-instance.ini"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,DSP408FIR Control}"; Flags: nowait postinstall skipifsilent unchecked

[CustomMessages]
polish.UpdateAction=Aktualizuj
english.UpdateAction=Update
polish.UpdateTitle=Aktualizacja DSP408FIR Control
english.UpdateTitle=Update DSP408FIR Control
polish.UpdateDescription=Zainstalowana wersja %1 → {#AppVersion}
english.UpdateDescription=Installed version %1 → {#AppVersion}
polish.UpdateDetails=Program zostanie zaktualizowany w dotychczasowym folderze. Ustawienia użytkownika i zapisane konfiguracje zostaną zachowane.%n%nZamknij DSP408FIR Control przed kontynuowaniem. Podczas instalacji możesz wybrać skrót na pulpicie.
english.UpdateDetails=The application will be updated in its existing folder. User preferences and saved configurations will be retained.%n%nClose DSP408FIR Control before continuing. You can choose a desktop shortcut during installation.
polish.NewerInstalled=Zainstalowano nowszą wersję (%1). Ten instalator zawiera {#AppVersion}. Aktualizacja do starszej wersji została zatrzymana.
english.NewerInstalled=A newer version (%1) is installed. This installer contains {#AppVersion}. Downgrading has been stopped.

polish.MaintenanceDetails=Wybierz działanie. Aktualizacja zachowuje obecną instalację i ustawienia. Druga kopia będzie mieć osobny folder, skróty oraz własne ustawienia i dzienniki.
english.MaintenanceDetails=Choose an action. Update retains the existing installation and preferences. A second copy has a separate folder, shortcuts, preferences and journals.
polish.UpdateExisting=Aktualizuj obecną instalację
english.UpdateExisting=Update the existing installation
polish.InstallSeparate=Zainstaluj drugą niezależną kopię w innym folderze
english.InstallSeparate=Install a second independent copy in another folder
polish.UninstallExisting=Odinstaluj obecną instalację
english.UninstallExisting=Uninstall the existing installation
polish.UninstallAction=Odinstaluj
english.UninstallAction=Uninstall
polish.ConfirmUninstall=Odinstalować program z folderu %1?%n%nZapisane konfiguracje i ustawienia użytkownika pozostaną. Instalator nie zainstaluje programu ponownie po tej operacji.
english.ConfirmUninstall=Uninstall the application from %1?%n%nSaved configurations and user preferences will remain. Setup will not reinstall the application after this action.
polish.UninstallUnavailable=Nie znaleziono prawidłowego deinstalatora tej instalacji. Użyj ustawień Aplikacje w Windows.
english.UninstallUnavailable=This installation has no valid uninstaller. Use Windows Apps settings.
polish.SeparateDirectory=Wybierz oddzielny folder. Druga kopia nie może znajdować się wewnątrz obecnej instalacji ani jej nadpisywać.
english.SeparateDirectory=Choose a separate folder. A second copy cannot overlap or overwrite the existing installation.
polish.UnsafeDirectory=Wybierz pusty folder albo folder zarejestrowanej niezależnej kopii DSP408FIR Control.
english.UnsafeDirectory=Choose an empty folder or the folder of a registered independent DSP408FIR Control copy.
polish.UseCopyAction=Aby wybrać inny folder, wróć i wybierz instalację drugiej niezależnej kopii.
english.UseCopyAction=To choose another folder, go back and select the independent copy action.
polish.ApplicationInUse=DSP408FIR Control jest uruchomiony lub pliki tej instalacji są zajęte albo niedostępne.%n%nZapisz potrzebne konfiguracje, rozłącz DSP i zamknij tę kopię programu. Następnie wybierz Ponów próbę.%n%nFolder: %1%n%nInstalator nie zamknie aplikacji automatycznie. Jeśli program jest już zamknięty, sprawdź uprawnienia do tego folderu.
english.ApplicationInUse=DSP408FIR Control is running, or this installation's files are in use or inaccessible.%n%nSave any configurations you need, disconnect the DSP and close this copy of the application. Then choose Retry.%n%nFolder: %1%n%nSetup will not close the application automatically. If it is already closed, check access permissions for this folder.

[Code]
#include "update.iss"
