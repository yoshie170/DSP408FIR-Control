# Windows installer

Project: https://github.com/yoshie170/DSP408FIR-Control

The package is `dist/installer/DSP408FIR-Control-0.9.1-Setup.exe` for
Windows10 build19041 or later / Windows11, x64-compatible. Python and Qt are
included. Default installation: `C:\Program Files\DSP408FIR Control`.

The wizard supports Polish/English, optional desktop shortcut and all-users
or current-user installation. Updates retain the existing folder and user
data; choose the same installation mode as before. A registered installation
offers Update / independent second copy / Uninstall. A detected newer public
version blocks downgrading.

Setup checks the selected folder's current and legacy application EXE before
updating and again before modifying files. A running application or inaccessible
file stops the operation with Retry/Cancel. Close the application manually;
Setup must not bypass the connected-DSP close confirmation. Other independent
copies are unaffected. The same check protects uninstall. Automatic closing
and restarting are disabled deliberately.

The wizard shows the author/independence notice and requires MIT acceptance.
Component license texts are included offline and keep their separate terms.
Installation does not open a DSP connection or change drivers, firmware or
network settings. The EXE currently has no code-signing certificate.

## Build

Use the Windows x64 Python/toolchain versions in `requirements-lock.txt` and
Inno Setup6.7.3. The script locates ISCC in standard installation folders or
PATH; an explicit compiler path takes precedence:

```powershell
.\tools\build_windows.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

The script prepares bundled notices, builds the PyInstaller onedir package in
`dist/DSP408FIR Control`, uses `build/windows` for temporary compiler output,
compiles Inno and writes the installer SHA256 file. It restricts PATH to Python
and Windows. The spec rejects binary dependencies outside project/Python/Windows
roots, preventing unrelated SDK DLLs from entering the package.

Only application Python modules, QML, icons and explicit information/license
assets enter the bundle. Local working documents, manufacturer material,
captures, environments and repository metadata are not packaging inputs.
The QtQml hook retains the required Quick/Controls/Layouts/Window modules.

The release version and Windows build revision come from `dsp408/version.py`.
`tools/release_version.py` generates Inno and PE metadata. A changed Python/QML
payload requires rebuilding the bundle; an installer-only change may be compiled
against an existing matching bundle. `DSP408_BUILD_CONSOLE=1` is for diagnostic
builds only. Keys/certificates are never generated automatically.

## User data and independent copies

Primary user data remains `%LOCALAPPDATA%\gremium.tech\DSP408 Control` for
compatibility. Source mode uses `work/`; an absolute `DSP408_DATA_DIR` override
supports isolated verification. Uninstall preserves user data and externally
saved configurations.

Independent copies use a separate `DSP408FIR-copy-<32hex>` AppId, Copy<ID8>
shortcuts/title and installer-owned `dsp408-instance.ini`. Their preferences
and journals are under `instances/<ID>`. Existing registered copies retain
their identity. Invalid markers, overlapping/nested folders and unregistered
nonempty destinations are rejected. Primary legacy shortcuts are not removed
when installing a second copy.

Registrations are read in the selected installation mode: HKLM64/HKLM32 for
all users, HKCU64/HKCU32 for current user. Uninstall invokes only a validated
uninsNNN.exe from the registered folder, then exits without reinstalling.

## Verification tools

- `verify_installer_running.py`: native guard checks for both EXE names and
  independent copies in PL/EN. Optional `--frozen` probes the project's own
  offline package and lets it exit normally. No installation/registry writes.
- `verify_installer_update.py`: native version ordering and maintenance wizard,
  aborting before installation and without registry writes.
- `verify_help_license.py`: native full-text/author/MIT-acceptance checks in
  both languages, aborting before installation.
- `verify_installer_copies.py`: actual isolated current-user fixture installs
  under a separate random test AppId; removes only its own test registrations.
- `verify_windows_release.py`: actual isolated installation/uninstallation of
  the built package under `work/release-verification/windows`. Requires an
  elevated test shell and refuses an existing real installation.

The last two tools perform installation/registry actions and must be run
deliberately in an appropriate test environment. None connects to the DSP.
Compilation success alone is not package validation: verify imports, QML,
icons, preferences, metadata and source-asset consistency in the frozen app.
