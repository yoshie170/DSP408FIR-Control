# DSP408FIR Control

English · [Polski](README.md) · [GitHub](https://github.com/yoshie170/DSP408FIR-Control)

**Version 0.9.1** · [Download](https://github.com/yoshie170/DSP408FIR-Control/releases/latest) · [Changelog](CHANGELOG.md)

**DSP408FIR Control** is an independent editor for the **t.racks FIR DSP 408**,
available for Windows and macOS. Control input and output channels, configure
PEQ, crossover, delay, dynamics and FIR, and manage presets and backups.
Configurations can also be prepared and saved offline without a connected DSP.

| Platform | Download version 0.9.1 |
| --- | --- |
| Windows 10/11, 64-bit | [Windows installer (.exe)](https://github.com/yoshie170/DSP408FIR-Control/releases/download/0.9.1/DSP408FIR-Control-0.9.1-Setup-win.exe) |
| macOS 14.4+, Apple Silicon | [macOS package (.dmg)](https://github.com/yoshie170/DSP408FIR-Control/releases/download/0.9.1/DSP408FIR-Control-0.9.1-macOS-arm64.dmg) |

Both packages include the runtime; Python and libraries do not need to be
installed separately. **USB HID and Ethernet are supported on both Windows
and macOS.** An Intel Mac version is planned.

The application is intended for the **FIR DSP 408 running firmware 1.15/1.15P**.

Copyright ©2026 Łukasz Białas · [gremium.tech](https://gremium.tech)

This is independent software, not officially affiliated with, endorsed by or
supported by the device manufacturer.

## Getting started

### Windows installer

Download and run the Windows `.exe` installer linked above.
The default location is `C:\Program Files\DSP408FIR Control`.
The installer offers an optional desktop shortcut and Polish/English languages.

When an existing installation is detected, choose **Update**, **Install a second
independent copy**, or **Uninstall**. Updating preserves the installation folder
and user preferences. Select the same per-user/all-users mode as before.
A second copy has its own folder, shortcuts, preferences and journals.
Uninstalling preserves user data and externally saved configuration files.

If the selected copy is running, Setup stops and asks you to close it. Save
your configuration, disconnect the DSP, close that copy and choose **Retry**.
Setup never terminates the application automatically. A copy running from a
different folder does not block this installation.

Build output is under `dist/installer/` and is not stored in Git.
The application has no automatic updater; install a newer package manually.

### macOS package

1. Download the Apple Silicon `.dmg`.
2. Open it and drag **DSP408FIR Control** to **Applications**.
3. Launch the app from **Applications**.

Terminal commands are not needed to use the macOS package. Source launch and
build instructions are in the [macOS guide](packaging/macos/README.md).

### Running from source

With the local virtual environment already installed, use
`START_DSP408FIR_CONTROL.cmd`, an existing shortcut, or PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py
```

The application starts in **DEMO / OFFLINE**. It does not connect automatically
or upload an offline configuration at startup. Offline meters remain empty.

## Connecting a DSP

Close any other editor using the same processor. Use one transport at a time.

### USB

1. Connect the processor by USB.
2. Open **Connection…**, select **USB** and the target **DSP ID**.
3. Click **Connect** and wait for the initial read to finish.

USB supports configuration control as well as reading; it is not limited to
firmware updating. This application does not perform firmware updates.

### Direct Ethernet

1. Connect the PC and DSP by Ethernet.
2. Configure the computer's network adapter in system settings, in the same subnet
   as the DSP. For example: computer `192.168.1.12`, mask `255.255.255.0`,
   DSP `192.168.1.101`. The computer and DSP must have different addresses.
3. In **Connection…**, select **Ethernet**, enter the **DSP IP address** and
   **DSP ID**, then click **Connect**. The commonly tested ID is 1.

The address entered in the application belongs to the **DSP**. The OS selects
the local adapter; the application does not reconfigure it. **Save target**
stores a local connection profile without changing the DSP's IP or ID.
Router/Wi-Fi operation remains outside the currently verified connection scope.

**Control** reads the current device state and enables editing. **Read only**
permits viewing without writing settings. **Disconnect** replaces Connect
during an active session. Connecting loads the DSP state, rather than uploading
the currently open offline file. Closing while connected requires confirmation.

## Workspace

Four inputs are on the left and eight outputs on the right. Select a channel
to edit it; applicable tabs depend on whether it is an input or output.

| View | Purpose |
| --- | --- |
| MAIN | Channel overview, levels, Mute, active processing and bypass state. |
| CHANNEL | Name, gain, polarity, Mute, delay, Link and section-based Copy. |
| PEQ | Interactive bands, Magnitude/Phase, Q wheel/Fine and channel comparisons. |
| XOVER | Output IIR/FIR crossover, response comparisons and PEQ interaction. |
| DELAY | All channels in ms/meters/feet, temperature and optional air conditions. |
| GATE / COMP | Input gate and compressor. |
| LIMIT | Output limiter. |
| FIR | Input coefficient import, filter names, response, bypass and Clear. |
| ROUTING | Input-to-output assignments and mix levels. |
| SETUP | Analog/AES, generator, lock/password, appearance, backup and device settings. |

In MAIN, left-click toggles supported bypass and right-click opens editing.
Blue means active, orange **BP** means bypassed, and dimmed means inactive.
Output FIR is edited in XOVER. Gate, compressor, limiter and delay have
restorable software bypass; manual changes cancel the corresponding bypass.

Gain faders support wheel steps of 0.1 dB and double-click reset to 0 dB.
PEQ nodes support dragging and Q adjustment with the wheel; Fine uses smaller
steps. Multiple channels can be compared at the same time.

## Link and Copy

Link creates separate input or output groups. The lowest-numbered member is
the native source when adding members. Gain, PEQ, delay, dynamics and relevant
crossover/FIR operations follow native group behavior. Channel names, routing
and mix levels remain independent. Group colors and rails show membership.

**Copy** selects supported processing sections and destination channels.
It accounts for destination groups. It does not copy names, FIR coefficients,
Link membership, routing or global device settings.

## Files, device presets and backups

These are different workflows:

- **Load config / Save config:** portable local JSON or manufacturer-compatible
  PRS files. Full PRS includes numeric FIR coefficients. Device import has a
  separate review and confirmation; opening a file alone does not upload it.
- **DSP presets P01–P19:** the processor's stored slots. Load/Store requires
  confirmation and shows progress. Names use up to 14 ASCII bytes.
- **Local configuration slots:** session-local editing and switching; these
  are separate from the DSP's stored presets.
- **SETUP preset-bank backup:** `.dspbank` includes CURRENT and saved/empty
  slots with FIR and checksums. Restore reviews destinations and preserves
  CURRENT; Extract works offline. This is an application format, not an OEM
  multi-preset file.

A partial FIR startup preview is not a complete bank. Exports, backups and FIR
operations request full data when needed. JSON previews may lack unread FIR;
use full PRS when the complete coefficient data is required.

Imports/restores can mute channels temporarily and validate readback before
restoring target Mute states. A failed operation stops without automatic
retries or repair. Multi-slot restore is not atomic. Keep the device connected
and do not change presets on its front panel during these operations.

## FIR

Input import accepts CSV/TXT with **1–512 numeric coefficients per input**.
Imported files replace the selected input/group filter. Bypass is a separate
fast operation and does not erase coefficients; **Clear FIR** erases the
selected input/group storage through a reviewed operation.

Output FIR crossover is generated by the DSP in XOVER, with supported types,
windows and 256–1024 taps in steps of 32. Normal output editing does not expose
an input-style coefficient upload. Full PRS can carry supported external
output coefficient data. The active FIR resource budget is 4096.

## Settings and readings

- **Input Analog / AES/EBU:** switches A–B; C–D remain analog.
- **Generator:** Analog input, Pink, White or Sine, with explicit Apply.
- **Device lock:** four characters, A–Z/0–9. Permanent retains password
  protection; One Time removes saved protection after successful unlock.
  Offline editing uses a separate local lock.
- **Delay distance:** defaults to 20°C. Temperature affects distance conversion,
  while stored ms remain unchanged. Advanced can include humidity and absolute
  pressure. The Cramer correction is limited to 0–30°C/760–1020 hPa; outside its
  temperature range the UI identifies the temperature-only estimate.
- **Meter polling:**100/300 ms requests. These intervals are not a guarantee
  of real-time device response. Levels below −99 dB display as −∞.
- **Dynamics IN/OUT/GR:** optional static calculations based on real channel
  levels. They are not independent pre/post measurements and do not model the
  complete attack/release envelope. Their explanation is in SETUP.

Plots are mathematical previews, not acoustic measurements. There is no local
RTA because channel-level telemetry does not contain PCM audio samples.

## Help, licensing and privacy

**Help** includes About, Open Source Licenses, Changelog, Copy Diagnostics,
Report an Issue (GitHub) and [gremium.tech](https://gremium.tech).
About shows the application version/build, author, technologies and links.
License texts and changelog are available offline.

Original application code is licensed under [MIT](LICENSE). Dependencies,
including PySide6/Qt, retain their own terms; see
[third-party notices](THIRD_PARTY_NOTICES.md).

**Copy Diagnostics** copies only curated version, OS and connection-state
information to the clipboard. It excludes IP/MAC addresses, passwords, serial
numbers, configuration names and paths, and sends nothing automatically.
Issue reporting opens the project GitHub page; submitting an issue requires a
GitHub account. The English startup warning has a local **Don't show again** option,
which can be changed through **About → Safety notice**.

## Troubleshooting

See the [troubleshooting guide](docs/TROUBLESHOOTING.md#english) for connection
errors, locked controls, PRS files, backups and installation issues.

## About the project

Author: **Łukasz Białas** · [gremium.tech](https://gremium.tech).
Copyright © 2026 Łukasz Białas. Original code is licensed under [MIT](LICENSE).
Dependencies retain their own licenses; see
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) and the Help menu.

Installed Windows preferences are under
`%LOCALAPPDATA%\gremium.tech\DSP408 Control`; macOS uses
`~/Library/Application Support/gremium.tech/DSP408FIR Control`.
PRS/JSON configurations and DSPBANK backups are saved in your chosen folder.

[Download](https://github.com/yoshie170/DSP408FIR-Control/releases/latest)
· [Report an issue](https://github.com/yoshie170/DSP408FIR-Control/issues)
