# macOS preview build

## Start without installing Python manually

1. Download the current repository ZIP using **Code → Download ZIP** on GitHub,
   or update your existing checkout.
2. Extract the entire folder on your Mac.
3. Double-click **START_MAC.command** inside that folder.

The launcher downloads a pinned, checksum-verified uv binary and uses it to
prepare Python 3.14.8 and the project dependencies automatically. The first
start needs internet and may take several minutes; subsequent starts reuse the
environment. Keep the Terminal window open while using the app.

No Homebrew, manual activation, administrator password or system Python change
is required. Bootstrap files stay under `work/macos-bootstrap/`; the isolated
environment is `.venv-macos-auto`. The launcher does not modify shell profiles.
It starts the application normally in DEMO; it never connects to a DSP itself.

Source launch and direct Ethernet/USB connections have been confirmed on an
Apple Silicon M5. The native build is verified separately with an offline
startup, preferences, signature and source-asset comparison.

`macos-preview.yml.template` is an optional manual GitHub Actions build template.
It is inactive until a repository maintainer installs it under `.github/workflows/`
with the required workflow permission. Local packaging does not publish a release.

## Building from source (developers)

Native builds are prepared for **arm64** (Apple Silicon, including M5) and,
separately, **x86_64** (Intel). The Apple Silicon build has run on an M5;
Intel remains a separate, unverified target.

Use macOS **14.4 or newer**, matching the Qt 6.12 minimum. Install a native
Python 3.14 interpreter for the target architecture and Apple's command-line
developer tools. Obtain the repository using your GitHub access:

```sh
git clone https://github.com/yoshie170/DSP408FIR-Control.git
cd DSP408FIR-Control
```

Then, from the repository root:

```sh
python3.14 -m venv .venv-macos
source .venv-macos/bin/activate
python -m pip install -r packaging/macos/requirements.txt
python main.py
```

The dependency pins are a candidate toolchain pending native validation.
Do not install the Windows lock file on macOS. Confirm the interpreter before
building: `python -c 'import platform; print(platform.machine())'` should print
`arm64` on M5. The preview offers DEMO, Ethernet and USB. USB checks the attached
HID descriptor before sending commands. Device acceptance testing remains
separate from source launch; see the [port status](../../docs/MACOS_PORT.md).

## Build and verify

```sh
python tools/build_macos.py --arch arm64
python -m pip install -r packaging/macos/requirements-dmg.txt
python tools/build_macos_dmg.py --arch arm64
```

The script generates Retina icons from the existing SVG, builds a self-contained
`.app`, verifies its architecture/signature/assets and runs an isolated offline
startup/preferences check. Only after those checks pass does it create:

- `dist/macos/arm64/DSP408FIR Control.app`
- `dist/macos/arm64/DSP408FIR-Control-0.9.2-macOS-arm64.zip`
- the matching `.zip.sha256`
- `dist/macos/arm64/DSP408FIR-Control-0.9.2-build170-macOS-arm64.dmg`
- the matching `.dmg.sha256`
- `work/macos-arm64-verification/verification.json`
- `work/macos-arm64-verification/dmg-verification.json`

The DMG opens in icon view with the application's icon on the left, an arrow
and an Applications shortcut on the right. A Retina background uses the app's
colors and bilingual drag-to-install instructions. The disk volume and the DMG
file use the application's existing ICNS icon.

The `Licenses` folder contains installation instructions, the project's
unchanged PolyForm Shield 1.0.0 license and complete third-party license texts.
Drag the app to Applications, eject the DMG and launch it from Applications.
Python, Qt and HIDAPI are bundled; no source folder or Terminal setup is needed.
The DMG script verifies the app first, creates a compressed read-only image,
mounts it read-only, checks its signature, file hashes, licenses, custom icon
and saved Finder icon positions, then ejects it. `dmgbuild` and its dependencies
are build-only tools and are not bundled into the application. Xcode command-line
tools provide Swift/AppKit for the DMG file's Finder icon.

For Intel use an x86_64 Python and dependencies on a compatible Mac, then
`python tools/build_macos.py --arch x86_64`. The script rejects architecture
mismatches. These are separate builds, not a universal2 bundle. macOS versions
older than 14.4 require a different, separately validated Qt toolchain.

The preview uses PyInstaller's ad-hoc signature. It is **not Developer ID signed
or notarized**. Gatekeeper may require explicit approval to open a downloaded
preview. Public distribution requires a separate signing/notarization step;
certificates and signing credentials do not belong in this repository.

## First M5 check

1. Start from source in DEMO. Check both themes, plots, dialogs and file import/
   export with copies of your configurations. Offline meters should stay empty.
2. Build with the command above and confirm the verification report passes.
3. Copy the `.app` to Applications, launch it through Finder and check that
   settings persist after restarting. Writable data belongs in
   `~/Library/Application Support/gremium.tech/DSP408FIR Control`, outside `.app`.
4. Test Ethernet manually: close other editors, use the known direct connection,
   set the computer's IPv4 address in macOS network settings, select that
   adapter under **Connection → Computer adapter**, then choose **Read only**
   with the DSP IP and ID. This matters when Wi-Fi shares the same subnet.
   Allow local-network access
   if macOS asks. Compare the read values before testing existing control actions.
5. Test USB separately through **Connection → USB → Read only**, with other
   editors closed. Compare startup, telemetry and readback before control tests.
   A failed descriptor check never falls back to another report format.

Neither building nor package verification connects to a DSP. Source-mode
Ethernet/USB were confirmed by the user; hardware checks of the packaged app
remain separate from offline packaging verification.
See [port status](../../docs/MACOS_PORT.md).
