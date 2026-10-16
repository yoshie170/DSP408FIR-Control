"""Collect installed component license notices; never loads DSP transports."""
import shutil
import sys
from pathlib import Path
from importlib.metadata import distribution


def prepare(root):
    target=Path(root)/'dsp408/assets/licenses'
    target.mkdir(parents=True,exist_ok=True)
    lines=['DSP408FIR Control - third-party components',
           'Copyright © 2026 Łukasz Białas · https://gremium.tech',
           '', 'Components retain their original copyrights and licenses.',
           'Qt/PySide6 are distributed as separate shared libraries.',
           'The application does not alter these libraries.', '']
    for name in ('PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','hidapi','PyInstaller'):
        package=distribution(name)
        lines.append(f'{name} {package.version}: {package.metadata.get("License", "See included license")}')
        folder=target/name
        folder.mkdir(exist_ok=True)
        for item in package.files or ():
            if '/licenses/' in item.as_posix():
                shutil.copyfile(package.locate_file(item),folder/Path(item).name)
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',target/'Python-LICENSE.txt')
    lines += ['',f'Python: {sys.version.split()[0]}',
              'Qt/PySide sources: https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v6.12.0)',
              'Qt sources: https://code.qt.io/cgit/qt/qtbase.git/ (tag v6.12.0)',
              'HIDAPI wrapper: https://github.com/trezor/cython-hidapi/tree/0.15.0',
              'PyInstaller: https://github.com/pyinstaller/pyinstaller/tree/v6.22.3',
              'Qt for Python licensing: https://doc.qt.io/qtforpython-6/licenses.html',
              'LGPL/GPL texts: https://www.gnu.org/licenses/',
              'PyInstaller bootloader distribution exception is in PyInstaller/COPYING.txt.']
    (target/'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':prepare(Path(__file__).resolve().parents[1])
