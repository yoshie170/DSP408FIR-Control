# Third-party notices

DSP408FIR Control application code is licensed under the [MIT License](LICENSE).
Copyright © 2026 Łukasz Białas · [gremium.tech](https://gremium.tech).
Third-party components retain their own copyrights and licenses; MIT does not
replace their license terms.

The application includes an offline viewer: **Help → Open Source Licenses**.
Full license texts and notices are bundled in `dsp408/assets/licenses/`.

| Component | Notice / license |
| --- | --- |
| Python | PSF license and historical notices: `Python-LICENSE.txt` |
| PySide6 / shiboken6 | LGPLv3 option; upstream also offers GPL/commercial terms. See `LGPL-3.0.txt`, `GPL-3.0.txt` and component notices. |
| Qt 6 / QML / Qt Quick | License depends on the module. Applicable core/UI libraries use LGPLv3. Optional Qt Virtual Keyboard uses GPLv3. Full upstream third-party attributions: `Qt/THIRD_PARTY_NOTICES.txt`. |
| cython-hidapi / HIDAPI | Upstream alternative BSD/original/GPL terms and notices: `hidapi/`. |
| OpenSSL | Apache-2.0: `OpenSSL/LICENSE.txt`. |
| PyInstaller bootloader | GPLv2-or-later with upstream bootloader exception: `PyInstaller/COPYING.txt`. PyInstaller is a build tool. |

Qt/PySide libraries are distributed as unmodified shared libraries. Replacement
with interface-compatible versions and debugging those modifications are not
restricted by the application. Upstream source/version links and component
versions are included in `THIRD_PARTY_NOTICES.txt`. Commercial-license documents
from upstream wheels are informational; their presence grants no commercial license.

Qt attribution text is a versioned snapshot of the official module notices,
including conditional/platform-specific entries that may be inactive in this
Windows build. Its source URLs and content hash are in `Qt/sources.json`.
The content hash uses canonical UTF-8 text with LF newlines, independent of
the checkout's Windows line endings.
`tools/collect_qt_notices.py` is an explicit maintainer refresh for Qt6.12.0 and
OpenSSL3.5.9; it is not run during application startup or normal offline builds.

Official references: [Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html),
[Qt third-party code](https://doc.qt.io/qt-6/licenses-used-in-qt.html),
[LGPLv3](https://doc.qt.io/qt-6/lgpl.html),
[PyInstaller exception](https://pyinstaller.org/en/stable/license.html),
[OpenSSL licensing](https://openssl-library.org/source/license/index.html).

This is independent software for the t.racks FIR DSP 408. It is not officially
affiliated with, endorsed by or supported by the device manufacturer.
Manufacturer names identify compatibility; no manufacturer binaries or firmware
are included in the application installer or covered by the application's MIT grant.
