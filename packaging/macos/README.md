# macOS preview build

Native builds are prepared for **arm64** (Apple Silicon, including M5) and,
separately, **x86_64** (Intel). This pipeline has not yet been run on a Mac.
It is not a published, hardware-validated macOS release.

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
