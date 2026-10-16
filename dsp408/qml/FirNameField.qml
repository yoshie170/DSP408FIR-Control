import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
TextField {
    id: field
    property string actualName: backend.current.fir.name
    property int editIndex: -1
    property string draft: ''
    property bool edited: false
    enabled: backend.parameterEditingAllowed
    maximumLength: 8; selectByMouse: true; placeholderText: 'FIR name · max 8'
    Binding { target: field; property: 'text'; value: field.actualName; when: !field.activeFocus; restoreMode: Binding.RestoreNone }
    onTextEdited: {if(!edited)editIndex=backend.selected;draft=text;edited=true}
    onEditingFinished: {if(edited){edited=false;backend.renameFir(editIndex,draft)}focus=false}
    Keys.onEscapePressed: {edited=false;focus=false}
    background: Rectangle {radius: 5;color: Theme.color('#132631',backend.lightTheme);border.color: field.activeFocus?Theme.color('#28bde1',backend.lightTheme):Theme.color('#365361',backend.lightTheme)}
}
