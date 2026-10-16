import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Column {
    id: root
    property int fieldHeight: 31
    property string label: ''
    property string controlId: ''
    property real number: 0
    property real minimum: -100000
    property real maximum: 100000
    property real step: 0.1
    property int decimals: 1
    property string suffix: ''
    signal committed(real value)
    spacing: 4
    Label { text: root.label; color: Theme.color('#8fa7b9', backend.lightTheme); font.pixelSize: 11; visible: text.length>0 }
    TextField {
        id: field
        objectName: root.controlId.length ? root.controlId : 'number_' + root.label
        width: root.width; height: root.fieldHeight
        color: Theme.color('#e7f1f7', backend.lightTheme); selectByMouse: true; topPadding: 1; bottomPadding: 1
        font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter
        validator: DoubleValidator { bottom: root.minimum; top: root.maximum; locale: 'en_US'; notation: DoubleValidator.StandardNotation }
        background: Rectangle { color: Theme.color('#101e29', backend.lightTheme); radius: 4; border.color: field.activeFocus ? Theme.color('#13b7df', backend.lightTheme) : Theme.color('#304452', backend.lightTheme) }
        Binding { target: field; property: 'text'; value: root.number.toFixed(root.decimals); when: !field.activeFocus; restoreMode: Binding.RestoreNone }
        onEditingFinished: {
            if (acceptableInput && isFinite(Number(text))) root.committed(Number(text))
            text = root.number.toFixed(root.decimals)
        }
        Keys.onUpPressed: root.committed(Math.min(root.maximum,root.number+root.step))
        Keys.onDownPressed: root.committed(Math.max(root.minimum,root.number-root.step))
    }
    Label { text: root.suffix; color: Theme.color('#6d879b', backend.lightTheme); font.pixelSize: 10; visible: text.length>0; anchors.horizontalCenter: parent.horizontalCenter }
}
