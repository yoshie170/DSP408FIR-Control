import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    objectName: 'main_overview'
    property var summaries: backend.channelSummaries
    Component.onCompleted: summaries=backend.channelSummaries
    onVisibleChanged: if(visible)summaries=backend.channelSummaries
    Connections { target: backend; function onChanged() {if(root.visible)root.summaries=backend.channelSummaries} }
    property var activity: backend.overviewActivity
    signal openChannel(int channelIndex,int page)
    spacing: 6
    RowLayout {
        Layout.fillWidth: true
        Label {
            objectName: 'overview_activity_counts'
            text: 'Mute: '+root.summaries.filter(c=>c.mute).length+(backend.meterReadingsAvailable?'  ·  COMP working: '+root.activity.slice(0,4).filter(c=>c.reducing).length+'  ·  LIM working: '+root.activity.slice(4).filter(c=>c.reducing).length:'  ·  No live signal readings')
            color: Theme.color('#c5dce8', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true
        }
        Label { text: '4 IN / 8 OUT'; color: Theme.color('#25bddb', backend.lightTheme); font.pixelSize: 11 }
    }
    AdaptiveScrollView {
        objectName: 'overview_scroll'
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
        contentWidth: Math.max(760,availableWidth)
        Column {
            width: Math.max(760,parent.width); spacing: 3
            RowLayout {
                width: parent.width; height: 20; spacing: 6
                Label { text: 'CHANNEL / ROUTING'; Layout.preferredWidth: root.width>=1150?178:118; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'LEVEL · PEAK HOLD'; Layout.preferredWidth: root.width>=1150?200:115; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'dB'; Layout.preferredWidth: 40; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'GAIN'; Layout.preferredWidth: 40; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'DYNAMICS / GR'; Layout.preferredWidth: 83; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'MUTE'; Layout.preferredWidth: 36; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
                Label { text: 'FUNCTIONS · LEFT: BYPASS · RIGHT: EDIT'; Layout.fillWidth: true; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 9 }
            }
            Repeater {
                model: 12
                Column {
                    id: channelRow
                    required property int index
                    property var info: root.summaries[index]
                    property var live: root.activity[index]
                    width: parent.width; spacing: 3
                    Label { visible: channelRow.index===0 || channelRow.index===4; text: channelRow.index===0?'INPUTS':'OUTPUTS'; height: visible?16:0; color: Theme.color('#8faabc', backend.lightTheme); font.bold: true; font.pixelSize: 10 }
                    Rectangle {
                        width: parent.width; height: root.height>=750?46:32; radius: 4
                        color: backend.selected===channelRow.index?Theme.color('#173647', backend.lightTheme):channelRow.index%2?Theme.color('#12212b', backend.lightTheme):Theme.color('#0c1922', backend.lightTheme)
                        border.color: backend.selected===channelRow.index?Theme.color('#148eb4', backend.lightTheme):Theme.color('#253c49', backend.lightTheme)
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 4; spacing: 6
                            ConsoleButton {
                                objectName: 'overview_channel_'+channelRow.index
                                highlightHover: true
                                Layout.preferredWidth: root.width>=1150?170:110; implicitHeight: 24; text: channelRow.info.label+' · '+channelRow.info.name; font.pixelSize: root.width>=1150?12:10
                                onClicked: root.openChannel(channelRow.index,0)
                                ToolTip.visible: hovered; ToolTip.text: channelRow.info.name+'\nRouting: '+channelRow.info.routing+'\n'+channelRow.info.crossover+' · open channel controls'
                                contentItem: Text { text: parent.text; color: Theme.color('#d4e9f4', backend.lightTheme); font: parent.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                            }
                            Item {
                                objectName: 'overview_meter_'+channelRow.index
                                property real level: backend.meters[channelRow.index]
                                Layout.preferredWidth: root.width>=1150?200:115; Layout.fillHeight: true
                                LevelMeter { horizontal: true; showScale: true; anchors.left: parent.left; anchors.right: parent.right; y: 0; height: 26; level: backend.meters[channelRow.index]; peak: backend.meterPeaks[channelRow.index]; db: channelRow.live.db; readingText: backend.meterLabels[channelRow.index]; caption: channelRow.info.name }
                            }
                            Label { objectName: 'overview_db_'+channelRow.index; text: backend.meterLabels[channelRow.index]; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignRight; color: Theme.color('#b4d9e9', backend.lightTheme); font.pixelSize: 11 }
                            Rectangle { Layout.preferredWidth: 40; height: 23; radius: 3; color: Theme.color('#102630', backend.lightTheme); Label { anchors.centerIn: parent; text: channelRow.info.gain.toFixed(1); color: Theme.color('#8aaec0', backend.lightTheme); font.pixelSize: 10 } }
                            Rectangle {
                                objectName: 'overview_dynamics_'+channelRow.index
                                property bool reducing: channelRow.live.reducing
                                property bool gateClosed: channelRow.live.gateClosed
                                Layout.preferredWidth: 83; height: 23; radius: 3
                                color: reducing||gateClosed?Theme.color('#ffa346', backend.lightTheme):Theme.color('#182b37', backend.lightTheme)
                                Label { anchors.centerIn: parent; text: (channelRow.index<4?'COMP ':'LIM ')+(backend.meterReadingsAvailable && channelRow.live.reducing?'ACTIVE':'—'); color: parent.reducing||parent.gateClosed?Theme.color('#241506', backend.lightTheme):Theme.color('#6f94a7', backend.lightTheme); font.pixelSize: 9; font.bold: parent.reducing||parent.gateClosed }
                            }
                            ConsoleButton { objectName: 'overview_mute_'+channelRow.index; enabled: backend.parameterEditingAllowed; highlightHover: true; text: 'M'; checked: channelRow.info.mute; accent: Theme.color('#df4255', backend.lightTheme); Layout.preferredWidth: 36; implicitHeight: 24; onClicked: backend.edit(channelRow.index,'mute',!channelRow.info.mute,-1) }
                            RowLayout {
                                Layout.fillWidth: true; spacing: 3
                                Repeater {
                                    model: channelRow.info.blocks.length
                                    ConsoleButton {
                                        required property int index
                                        property var modelData: channelRow.info.blocks[index]
                                        readonly property bool bypassDisplay: modelData.display_bypassed
                                        readonly property bool pendingDisplay: modelData.pending && !bypassDisplay
                                        readonly property bool configuredDisplay: modelData.enabled && !bypassDisplay
                                        readonly property color stateFill: bypassDisplay?Theme.color('#4b2e14',backend.lightTheme):pendingDisplay?Theme.color('#4b3421',backend.lightTheme):configuredDisplay?Theme.color('#134155',backend.lightTheme):Theme.color('#172b36',backend.lightTheme)
                                        readonly property color stateBorder: bypassDisplay||pendingDisplay?Theme.color('#ffa346',backend.lightTheme):configuredDisplay?Theme.color('#248eaa',backend.lightTheme):Theme.color('#304958',backend.lightTheme)
                                        objectName: 'overview_function_'+channelRow.index+'_'+modelData.label.split(' ')[0]
                                        highlightHover: true
                                        text: modelData.label+(bypassDisplay?' BP':''); checked: configuredDisplay; accent: bypassDisplay||pendingDisplay?Theme.color('#ffa346', backend.lightTheme):Theme.color('#1db8d5', backend.lightTheme); implicitHeight: 24; implicitWidth: 32; padding: 3; font.pixelSize: 9; font.bold: configuredDisplay||bypassDisplay; Layout.fillWidth: true
                                        contentItem: Text { text: parent.text; font: parent.font; color: parent.bypassDisplay?Theme.color('#ffb566',backend.lightTheme):parent.checked?Theme.onAccent(backend.lightTheme):Theme.color('#b8cbd7',backend.lightTheme); horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
                                        onClicked: backend.toggleOverviewFunction(channelRow.index,modelData.action)
                                        MouseArea {
                                            anchors.fill: parent; acceptedButtons: Qt.RightButton
                                            onClicked: root.openChannel(channelRow.index,parent.modelData.tab)
                                        }
                                        Keys.onPressed: event => {
                                            if(event.key===Qt.Key_Menu || (event.key===Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))){root.openChannel(channelRow.index,modelData.tab);event.accepted=true}
                                        }
                                        opacity: hovered||visualFocus||configuredDisplay||pendingDisplay||bypassDisplay?1:.5
                                        ToolTip.visible: hovered; ToolTip.text: modelData.detail+'\n'+((modelData.toggle_key || modelData.software_supported)?(backend.parameterEditingAllowed?(modelData.action==='Ø'?'Left: toggle polarity':modelData.software_bypassed?'Left: restore saved settings':modelData.software_supported?'Left: software bypass':modelData.bypassed?'Left: enable':'Left: bypass'):'Read only · bypass unavailable'):'No quick bypass for this block')+'\nRight: edit'
                                        background: Rectangle { radius: 3; color: parent.stateFill; border.width: parent.hovered||parent.visualFocus?2:1; border.color: parent.hovered||parent.visualFocus?Theme.color('#72def7',backend.lightTheme):parent.stateBorder }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    Label { text: backend.meterReadingsAvailable?'Live DSP levels · amber: compressor / limiter active':'Offline configuration · connect the DSP for live readings'; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
}
