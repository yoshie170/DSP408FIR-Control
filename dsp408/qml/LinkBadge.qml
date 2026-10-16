import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme
Rectangle {
    id: root
    required property var info
    property color accent: Theme.color(info.color || '#40d9c4',backend.lightTheme)
    visible: info.linked===true
    implicitHeight: 16
    implicitWidth: text.implicitWidth+23
    radius: 4
    color: Theme.color('#132631',backend.lightTheme)
    border.color: accent
    Accessible.role: Accessible.StaticText
    Accessible.name: info.description || ''
    Item {
        x: 3; width: 13; height: 12; anchors.verticalCenter: parent.verticalCenter
        Rectangle { x: 1; y: 2; width: 8; height: 5; radius: 2; rotation: -40; color: 'transparent'; border.color: root.accent }
        Rectangle { x: 5; y: 5; width: 8; height: 5; radius: 2; rotation: -40; color: 'transparent'; border.color: root.accent }
    }
    Label { id: text; anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter; text: root.info.label || ''; color: root.accent; font.pixelSize: 9; font.bold: true }
    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered
    ToolTip.text: info.description || ''
}
