# macOS installation and build guide

## Install the DMG

Download **DSP408FIR-Control-0.9.1-macOS-arm64.dmg** from
[Releases](https://github.com/yoshie170/DSP408FIR-Control/releases/latest).
Open the disk image, drag **DSP408FIR Control** to **Applications** and launch it
from there. The package includes its runtime; Python, Homebrew and Terminal
commands are not required to use it.

The available package targets Apple Silicon and macOS 14.4+. USB is currently
unavailable on macOS; the connection option is Ethernet. Intel packaging remains
a separate target for future distribution. The sections below are for running
or building from source.

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

The launcher has passed shell syntax/offline host-guard checks on Windows and
has been successfully started on an M5 Mac. Source launch and frozen-package
validation are separate checks.

`macos-preview.yml.template` is an optional manual GitHub Actions build template.
It is inactive until a repository maintainer installs it under `.github/workflows/`
with the required workflow permission. This template is separate from the DMG
published in Releases.

## Building from source (developers)

The build configuration supports **arm64** (Apple Silicon, including M5) and,
separately, **x86_64** (Intel). Only the arm64 DMG is currently distributed.
The verification results for a particular build and real DSP connection must
be assessed separately from the availability of that package.

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
`arm64` on M5. The preview offers DEMO and Ethernet; USB remains disabled until
its HID behavior has been tested on macOS.

## Build and verify

```sh
python tools/build_macos.py --arch arm64
```

The script generates Retina icons from the existing SVG, builds a self-contained
`.app`, verifies its architecture/signature/assets and runs an isolated offline
startup/preferences check. Only after those checks pass does it create:

- `dist/macos/arm64/DSP408FIR Control.app`
- `dist/macos/arm64/DSP408FIR-Control-0.9.1-macOS-arm64.zip`
- the matching `.zip.sha256`
- `work/macos-arm64-verification/verification.json`

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
   set the computer's IPv4 address in macOS network settings, then choose
   **Connection → Read only** with the DSP IP and ID. Allow local-network access
   if macOS asks. Compare the read values before testing existing control actions.

Neither building nor package verification connects to a DSP. Native startup,
Finder launch, real Ethernet and HID validation remain separate acceptance checks.
See [port status](../../docs/MACOS_PORT.md).
