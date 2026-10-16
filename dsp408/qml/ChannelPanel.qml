import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    signal copyRequested()
    signal linkRequested()
    property var currentData: backend.current
    function refreshView() {
        currentData=backend.current
        
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: if(visible)refreshView()
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} }
    property var deviceData: backend.usbConfirmedCurrent
    property var dynamicsStatus: backend.reductionState[backend.selected]
    spacing: 12
    Label { text: 'CHANNEL PARAMETERS'+(backend.usbControlMode && root.deviceData.gain!==undefined?' · DSP '+root.deviceData.gain.toFixed(1)+' dB':''); font.bold: true; font.pixelSize: 17 }
    RowLayout {
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 18
        ParameterFader {
            enabled: { backend.revision; backend.usbGainReady; return backend.gainEditingAllowed(backend.selected) }
            label: 'Channel gain'; controlId: 'channel_gain'; number: root.currentData.gain
            minimum: backend.usbGainMode && backend.selected===0?-1:-60; maximum: backend.usbGainMode && backend.selected===0?0:12; step: backend.usbGainMode && backend.selected===0?1:.1; decimals: 1; unit: 'dB'; vertical: true; sliderHeight: 270
            scaleDivisions: backend.usbGainMode && backend.selected===0?2:5
            Layout.preferredWidth: 230; Layout.minimumWidth: 210; Layout.maximumWidth: 230; Layout.alignment: Qt.AlignTop
            onCommitted: value => backend.edit(backend.selected,'gain',value,-1)
            LevelMeter {
                objectName: 'channel_large_meter'; x: parent.width-65; y: 54; width: 59; height: 270; showScale: true
                level: backend.meters[backend.selected]; peak: backend.meterPeaks[backend.selected]; db: backend.meterDb[backend.selected]; readingText: backend.meterLabels[backend.selected]
                caption: root.currentData.name
                indicatorKind: root.dynamicsStatus.kind; reductionActive: root.dynamicsStatus.active; reductionDb: root.dynamicsStatus.db
            }
        }
        ColumnLayout {
            enabled: backend.parameterEditingAllowed
            Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; spacing: 12
            Label { text: 'CHANNEL NAME'; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 10 }
            TextField {
                id: nameEditor
                enabled: backend.parameterEditingAllowed; objectName: 'channel_name'
                Layout.fillWidth: true; selectByMouse: true; maximumLength: 8
                placeholderText: 'Channel name · max 8'
                property int editIndex: -1
                property string draft: ''
                property bool edited: false
                Binding { target: nameEditor; property: 'text'; value: root.currentData.name; when: !nameEditor.activeFocus; restoreMode: Binding.RestoreNone }
                onTextEdited: { editIndex=backend.selected; draft=text; edited=true }
                onEditingFinished: {
                    if(edited) { edited=false; backend.renameChannel(editIndex,draft) }
                    focus=false
                }
                Keys.onEscapePressed: { edited=false; focus=false }
                background: Rectangle { color: Theme.color('#132631', backend.lightTheme); radius: 5; border.color: nameEditor.activeFocus?Theme.color('#28bde1', backend.lightTheme):Theme.color('#365361', backend.lightTheme) }
            }
            DelayControl { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true; spacing: 18
                ConsoleCheck { text: 'Mute'; checked: root.currentData.mute; onClicked: backend.edit(backend.selected,'mute',checked,-1) }
                ConsoleCheck { text: 'Invert polarity (180°)'; checked: root.currentData.polarity_inverted; onClicked: backend.edit(backend.selected,'polarity_inverted',checked,-1) }
            }
            Label { text: 'LINK · same channel group'; color: Theme.color('#9ab5c6', backend.lightTheme); font.bold: true }
            Flow {
                visible: !backend.usbReadActive
                Layout.fillWidth: true; spacing: 4
                Repeater { model: backend.selected<4?4:8; ConsoleCheck { required property int index; property int target: backend.selected<4?index:index+4; objectName: 'offline_link_member_'+target; text: backend.selected<4?'IN '+(index+1):'OUT '+(index+1); enabled: target!==backend.selected; checked: target===backend.selected || backend.links[target]; onClicked: backend.link(target,checked) } }
            }
            ConsoleButton { objectName: 'channel_link_edit'; visible: backend.usbReadActive; enabled: backend.usbControlReady && !backend.usbControlPending; text: 'Link channels…'; onClicked: root.linkRequested() }
            ConsoleButton { text: 'Copy channel settings…'; onClicked: root.copyRequested() }
            Label { objectName: 'channel_link_status'; text: backend.usbReadActive?backend.channelLinkMembers.map(function(i){return i<4?'IN '+String.fromCharCode(65+i):'OUT '+(i-3)}).join(' + '):'Linked DEMO edits · channel names and FIR remain independent'; color: Theme.color('#7697aa', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
    }
}
