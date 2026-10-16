; Build with Inno Setup 6.7+. No drivers, firmware or network configuration.
#ifndef AppVersion
  #define AppVersion "0.9.0"
#endif
#ifndef AppSource
  #define AppSource SourcePath + "..\..\dist\DSP408 Control"
#endif
#ifndef SetupOutput
  #define SetupOutput SourcePath + "..\..\dist\installer"
#endif
#define AppExe "DSP408 Control.exe"
#define AppIcon SourcePath + "..\..\dsp408\assets\icons\dsp408.ico"

[Setup]
AppId={{5A2478C4-CECE-4280-A896-5AECE3478B04}
AppName=DSP408 Control
AppVersion={#AppVersion}
AppPublisher=Łukasz Białas · gremium.tech
AppPublisherURL=https://gremium.tech
AppSupportURL=https://gremium.tech
AppCopyright=Copyright © 2026 Łukasz Białas
VersionInfoCopyright=Copyright © 2026 Łukasz Białas · gremium.tech
DefaultDirName={autopf}\DSP408 Control
UsePreviousAppDir=no
DefaultGroupName=DSP408 Control
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
DisableProgramGroupPage=yes
AllowNoIcons=yes
WizardStyle=modern
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#SetupOutput}
OutputBaseFilename=DSP408-Control-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=no
RestartApplications=no
UninstallDisplayName=DSP408 Control

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DSP408 Control"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Check: not WizardNoIcons
Name: "{autodesktop}\DSP408 Control"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon; Check: not WizardNoIcons

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,DSP408 Control}"; Flags: nowait postinstall skipifsilent unchecked
