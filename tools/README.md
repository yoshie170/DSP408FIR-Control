# Release maintenance tools

The tools in this directory build application packages, prepare branding and
license assets, and verify the project's own installers. They do not form part
of the normal user workflow.

- `build_windows.ps1`: Windows application and Inno Setup installer.
- `build_macos.py`, `build_macos_icon.py`, `verify_macos_bundle.py`: native macOS
  packaging, Retina icons and offline package verification.
- `build_icons.py`: application icons from the canonical SVG.
- `release_version.py`: version resources for the Windows package.
- `prepare_release_assets.py`, `collect_qt_notices.py`: bundled information and
  dependency license notices. Notice collection is an explicit maintainer action.
- `verify_help_license.py`, `verify_installer_update.py`,
  `verify_installer_running.py`: installer/license checks.
- `verify_installer_copies.py`, `verify_windows_release.py`: isolated installer
  acceptance checks; run deliberately in a suitable test environment.

Packaging instructions: [Windows](../packaging/windows/README.md),
[macOS](../packaging/macos/README.md).
For everyday use, download the installer/DMG and follow the main README.
