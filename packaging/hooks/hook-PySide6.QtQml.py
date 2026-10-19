"""Qt QML modules used by this app; retain upstream plugin validation.

The app imports QtQuick, QtQuick.Controls, QtQuick.Layouts and QtQuick.Window.
Do not ship unrelated installed add-ons (WebEngine, Charts, 3D, keyboard etc.).
Pinned PyInstaller6.22.3 supplies the actual plugin/dependency collector.
"""
from pathlib import PurePath
from PyInstaller.utils.hooks.qt import add_qt6_dependencies,pyside6_library_info

hiddenimports,binaries,datas=add_qt6_dependencies(__file__)
qml_binaries,qml_datas=pyside6_library_info.collect_qtqml_files()


def used_qml(entry):
    parts=PurePath(entry[1]).parts
    if 'qml' not in parts:return False
    relative=parts[parts.index('qml')+1:]
    if not relative:return False
    if relative[0] in ('QtCore','QtQml'):return True
    if relative[0]!='QtQuick':return False
    # Keep complete controls/styles and their supported implementation imports.
    return len(relative)==1 or relative[1] in (
        'Controls','Dialogs','Effects','Layouts','NativeStyle','Shapes',
        'Templates','VectorImage','Window',
    )


binaries += [entry for entry in qml_binaries if used_qml(entry)]
datas += [entry for entry in qml_datas if used_qml(entry)]
