import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Dialog {
    id: dialog
    parent: Overlay.overlay
    modal: true
    focus: true
    padding: 18
    spacing: 12
    closePolicy: Popup.CloseOnEscape
    palette.window: Theme.color('#101f29', backend.lightTheme)
    palette.windowText: Theme.color('#e3eef6', backend.lightTheme)
    palette.text: Theme.color('#e3eef6', backend.lightTheme)
    Overlay.modal: Rectangle { color: Theme.color('#b300070b', backend.lightTheme) }
    background: Rectangle {
        color: Theme.color('#101f29', backend.lightTheme)
        border.color: Theme.color('#365361', backend.lightTheme); radius: 8
    }
    header: Item {
        implicitHeight: 52
        Label {
            anchors.left: parent.left; anchors.leftMargin: 18
            anchors.right: closeButton.left; anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: dialog.title; font.pixelSize: 16; font.bold: true
            color: Theme.color('#e3eef6', backend.lightTheme); elide: Text.ElideRight
        }
        ConsoleButton {
            id: closeButton; objectName: dialog.objectName+'_close'
            anchors.right: parent.right; anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 30; implicitWidth: 30; text: '×'; font.pixelSize: 18
            visible: (dialog.closePolicy & Popup.CloseOnEscape)!==0
            Accessible.name: 'Close dialog'; onClicked: dialog.reject()
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.color('#294451', backend.lightTheme) }
    }
    footer: DialogButtonBox {
        id: dialogButtons
        visible: count>0; standardButtons: dialog.standardButtons
        spacing: 8; padding: 12; alignment: Qt.AlignRight
        delegate: ConsoleButton {
            implicitWidth: Math.max(90,contentItem.implicitWidth+24)
            Keys.onPressed: event => {
                if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){clicked();event.accepted=true}
            }
        }
        background: Item {}
        onAccepted: dialog.accept()
        onRejected: dialog.reject()
    }
    Connections {
        target: dialog
        function onOpened() {
            if(dialog.standardButtons & Dialog.Cancel)Qt.callLater(()=> {
                var cancel=dialogButtons.standardButton(Dialog.Cancel)
                if(cancel && dialog.visible)cancel.forceActiveFocus()
            })
        }
    }
}
