import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Rectangle {
    id: root
    property int selectedSlot: 0
    property int hardwareIndex: -1
    property int seenCatalogRevision: -1
    signal slotSelected(int slot)
    signal detailsRequested(var entry)
    signal recallRequested(var entry)
    property var selectedEntry: list.currentIndex>=0 && list.currentIndex<entries.length?entries[list.currentIndex]:({})
    color: Theme.color('#0c1922', backend.lightTheme); radius: 5; border.color: list.activeFocus?Theme.color('#51ccea', backend.lightTheme):Theme.color('#2d4655', backend.lightTheme)
    implicitHeight: 174
    property var entries: backend.usbReadActive?backend.hardwarePresets:backend.configurations
    function activeIndex() { for(var i=0;i<entries.length;i++)if(entries[i].active)return i;return -1 }
    Connections { target: backend; function onChanged() { if(!backend.usbReadActive || root.seenCatalogRevision!==backend.usbCatalogRevision){root.hardwareIndex=-1;root.seenCatalogRevision=backend.usbCatalogRevision} } }
    ListView {
        id: list; objectName: 'preset_browser'
        anchors.fill: parent; anchors.margins: 3; clip: true; spacing: 2
        model: root.entries
        currentIndex: backend.usbReadActive?(root.hardwareIndex>=0?root.hardwareIndex:root.activeIndex()):root.selectedSlot
        keyNavigationEnabled: false
        function pick(index) {
            if(!count)return
            index=Math.max(0,Math.min(count-1,index))
            if(backend.usbReadActive)root.hardwareIndex=index;else root.slotSelected(root.entries[index].slot)
            positionViewAtIndex(index,ListView.Contain)
        }
        Keys.onPressed: event => {
            if(event.key===Qt.Key_Down){pick(currentIndex+1);event.accepted=true}
            else if(event.key===Qt.Key_Up){pick(currentIndex-1);event.accepted=true}
            else if(event.key===Qt.Key_Home){pick(0);event.accepted=true}
            else if(event.key===Qt.Key_End){pick(count-1);event.accepted=true}
            else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){pick(currentIndex);event.accepted=true}
        }
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: Rectangle {
            id: row
            required property int index
            required property var modelData
            objectName: 'preset_row_'+index
            width: list.width; height: 25; radius: 3
            color: list.currentIndex===index?Theme.color('#123e57', backend.lightTheme):index%2?Theme.color('#101f2a', backend.lightTheme):Theme.color('#0c1922', backend.lightTheme)
            border.color: list.currentIndex===index?Theme.color('#24bde4', backend.lightTheme):'transparent'
            Label { x: 5; width: 26; anchors.verticalCenter: parent.verticalCenter; text: String(backend.usbReadActive?row.modelData.slot:row.modelData.slot+1).padStart(2,'0'); color: row.modelData.active?Theme.color('#45dc80', backend.lightTheme):Theme.color('#83a4ba', backend.lightTheme); font.pixelSize: 10 }
            Label { x: 34; width: parent.width-54; anchors.verticalCenter: parent.verticalCenter; text: row.modelData.name; elide: Text.ElideRight; color: row.modelData.stored===false?Theme.color('#8196a5', backend.lightTheme):Theme.color('#deedf7', backend.lightTheme); font.pixelSize: 11 }
            Rectangle { x: parent.width-14; y: 9; width: 7; height: 7; radius: 4; color: row.modelData.active?Theme.color('#39d674', backend.lightTheme):row.modelData.stored?Theme.color('#28b7d6', backend.lightTheme):Theme.color('#354b59', backend.lightTheme) }
            MouseArea {
                anchors.fill: parent; hoverEnabled: true
                onClicked: {list.forceActiveFocus();list.pick(row.index)}
                onDoubleClicked: if(backend.usbReadActive){if(backend.presetRecallAvailable && row.modelData.marker_raw===255)root.recallRequested(row.modelData);else root.detailsRequested(row.modelData)}
                ToolTip.visible: containsMouse
                ToolTip.text: row.modelData.name+'\n'+(backend.usbReadActive?(backend.usbControlMode && row.modelData.marker_raw===255?'Double-click: confirm preset loading':'Double-click: catalog details'):row.modelData.stored?'Local session configuration · use Apply':'Empty local session slot')
            }
        }
        Accessible.name: backend.usbReadActive?'Hardware preset catalog preview':'Local configuration list'
    }
    Label { anchors.centerIn: parent; visible: root.entries.length===0; text: 'Reading preset catalog…'; color: Theme.color('#8faabb', backend.lightTheme); font.pixelSize: 11 }
}
