import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Button {
    id: control
    property color accent: Theme.color('#1bb6e1', backend.lightTheme)
    property bool emphasized: false
    property bool highlightHover: false
    property bool outlined: false
    HoverHandler { enabled: control.enabled && control.highlightHover; cursorShape: Qt.PointingHandCursor }
    implicitHeight: 30; implicitWidth: Math.max(52,contentItem.implicitWidth+20)
    leftPadding: 10; rightPadding: 10; topPadding: 4; bottomPadding: 4
    hoverEnabled: true; font.pixelSize: 11; font.bold: checked || emphasized
    contentItem: Text { text: control.text; color: !control.enabled ? Theme.color('#587080', backend.lightTheme) : control.checked || control.emphasized ? Theme.onAccent(backend.lightTheme) : Theme.color('#b8cbd7', backend.lightTheme); font: control.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
    background: Rectangle {
        radius: 5
        gradient: Gradient { GradientStop { position: 0; color: control.down ? Theme.color('#0d4259', backend.lightTheme) : control.checked || control.emphasized ? Theme.color('#087faf', backend.lightTheme) : control.hovered ? Theme.color('#2b414e', backend.lightTheme) : Theme.color('#20313d', backend.lightTheme) } GradientStop { position: 1; color: control.checked || control.emphasized ? Theme.color('#06526f', backend.lightTheme) : Theme.color('#14212b', backend.lightTheme) } }
        border.width: control.highlightHover && (control.hovered || control.visualFocus)?2:1
        border.color: control.visualFocus || (control.highlightHover && control.hovered) ? Theme.color('#72def7', backend.lightTheme) : control.checked || control.emphasized ? control.accent : control.outlined ? Theme.color('#248eaa', backend.lightTheme) : Theme.color('#324650', backend.lightTheme)
    }
}
