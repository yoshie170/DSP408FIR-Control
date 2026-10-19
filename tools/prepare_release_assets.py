"""Collect installed component license notices; never loads DSP transports."""
import shutil
import sys
import ssl
from pathlib import Path
from importlib.metadata import distribution


def prepare(root):
    root=Path(root)
    info=root/'dsp408/assets/info';info.mkdir(parents=True,exist_ok=True)
    (info/'LICENSE.txt').write_text((root/'LICENSE').read_text(encoding='utf-8'),encoding='utf-8-sig')
    shutil.copyfile(root/'CHANGELOG.md',info/'CHANGELOG.md')
    (info/'ABOUT.txt').write_text('DSP408FIR Control\n\n'
        'Author: Łukasz Białas · https://gremium.tech\n'
        'Copyright © 2026 Łukasz Białas\n'
        'Application license: MIT\n'
        'Technologies: Python, PySide6, Qt 6 / QML\n'
        'Project: https://github.com/yoshie170/DSP408FIR-Control\n\n'
        'Independent software for the t.racks FIR DSP 408. Not officially affiliated with, '
        'endorsed by or supported by the device manufacturer.\n\n'
        'Third-party libraries retain their original licenses, including LGPLv3 for '
        'the applicable Qt / Qt for Python libraries. Full license texts and notices '
        'are included in the application under Help > Open Source Licenses.\n',encoding='utf-8-sig')
    target=Path(root)/'dsp408/assets/licenses'
    target.mkdir(parents=True,exist_ok=True)
    lines=['DSP408FIR Control - third-party components',
           'Copyright © 2026 Łukasz Białas · https://gremium.tech',
           'Project: https://github.com/yoshie170/DSP408FIR-Control',
           '', 'Components retain their original copyrights and licenses.',
           'MIT applies to the application code, not to third-party components.',
           'Qt / Qt for Python: © The Qt Company Ltd. and other contributors.',
           'Applicable Qt / PySide6 / shiboken libraries use the LGPLv3 option.',
           'LGPL-3.0.txt and GPL-3.0.txt contain the corresponding license texts.',
           'Qt/PySide6 are distributed as separate shared libraries.',
           'The application does not alter these libraries.',
           'You may replace interface-compatible shared Qt/PySide libraries and debug those modifications.',
           'Commercial license texts included by upstream packages do not grant a commercial license.', '']
    for name in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','hidapi','PyInstaller'):
        package=distribution(name)
        lines.append(f'{name} {package.version}: {package.metadata.get("License-Expression") or package.metadata.get("License") or "See included license"}')
        folder=target/name
        folder.mkdir(exist_ok=True)
        for item in package.files or ():
            if '/licenses/' in item.as_posix():
                shutil.copyfile(package.locate_file(item),folder/Path(item).name)
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',target/'Python-LICENSE.txt')
    lines += ['',f'Python: {sys.version.split()[0]}',
              f'OpenSSL: {ssl.OPENSSL_VERSION}; Apache-2.0 (OpenSSL/LICENSE.txt).',
              'Qt third-party authors and full notices: Qt/THIRD_PARTY_NOTICES.txt; sources listed in Qt/sources.json.',
              'Module licenses are component-specific; optional Qt Virtual Keyboard uses GPLv3.',
              'Qt Virtual Keyboard sources: https://code.qt.io/cgit/qt/qtvirtualkeyboard.git/ (tag v6.12.0)',
              'Qt PDF sources: https://code.qt.io/cgit/qt/qtwebengine.git/ (tag v6.12.0)',
              'Qt/PySide sources: https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v6.12.0)',
              'Qt sources: https://code.qt.io/cgit/qt/qtbase.git/ (tag v6.12.0)',
              'Qt Declarative/QML/Quick sources: https://code.qt.io/cgit/qt/qtdeclarative.git/ (tag v6.12.0)',
              'Qt SVG sources: https://code.qt.io/cgit/qt/qtsvg.git/ (tag v6.12.0)',
              'Qt module and third-party attributions: https://doc.qt.io/qt-6/licenses-used-in-qt.html',
              'HIDAPI wrapper: https://github.com/trezor/cython-hidapi/tree/0.15.0',
              'PyInstaller: https://github.com/pyinstaller/pyinstaller/tree/v6.22.3',
              'Qt for Python licensing: https://doc.qt.io/qtforpython-6/licenses.html',
              'LGPL/GPL texts: https://www.gnu.org/licenses/',
              'PyInstaller bootloader distribution exception is in PyInstaller/COPYING.txt.']
    (target/'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':prepare(Path(__file__).resolve().parents[1])
