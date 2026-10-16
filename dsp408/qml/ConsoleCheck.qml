import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
CheckBox {
    id: control
    property color accent: Theme.color('#26c66b', backend.lightTheme)
    property bool compact: false
    implicitHeight: 24
    implicitWidth: compact ? contentItem.implicitWidth+leftPadding+rightPadding : contentItem.implicitWidth + 38
    spacing: compact?4:7; hoverEnabled: true; font.pixelSize: compact?10:11
    indicator: Rectangle {
        width: control.compact?20:30; height: control.compact?12:16; x: control.leftPadding; y: (control.height-height)/2
        radius: 8; color: control.checked ? control.accent : Theme.color('#14232d', backend.lightTheme); border.color: control.visualFocus ? Theme.color('#d8f7ff', backend.lightTheme) : control.checked ? Qt.lighter(control.accent,1.2) : Theme.color('#405562', backend.lightTheme)
        Rectangle { width: control.compact?8:12; height: width; radius: width/2; x: control.checked?parent.width-width-2:2; y: 2; color: '#eef8fc' }
    }
    contentItem: Text { text: control.text; leftPadding: control.indicator.width+control.spacing; color: control.enabled ? Theme.color('#adc2cf', backend.lightTheme) : Theme.color('#536d7d', backend.lightTheme); font: control.font; verticalAlignment: Text.AlignVCenter }
}
