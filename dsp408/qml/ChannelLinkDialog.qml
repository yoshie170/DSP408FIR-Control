import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme
ConsoleDialog {
    id: dialog
    objectName: 'channel_link_dialog'
    width: Math.min(540,parent.width-32); modal: true; title: 'Link channels'
    property var members: []
    property int selected: 0
    function openFor() { selected=backend.selected; members=backend.channelLinkMembers.slice(); if(members.indexOf(selected)<0)members.push(selected); open() }
    contentItem: ColumnLayout {
        spacing: 14
        Label { text: 'Choose channels to control together.'; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Flow {
            Layout.fillWidth: true; spacing: 6
            Repeater {
                model: dialog.selected<4?4:8
                ConsoleCheck {
                    required property int index
                    property int channel: dialog.selected<4?index:index+4
                    objectName: 'link_member_'+channel
                    text: channel<4?'IN '+String.fromCharCode(65+channel):'OUT '+(channel-3)
                    enabled: channel!==dialog.selected
                    checked: dialog.members.indexOf(channel)>=0
                    onClicked: { var next=dialog.members.slice(); var at=next.indexOf(channel); if(checked && at<0)next.push(channel); else if(!checked && at>=0)next.splice(at,1); dialog.members=next }
                }
            }
        }
        Label { text: 'The lowest numbered channel becomes the source. Joining channels copies its settings, including FIR. Channel names and output routing stay independent. Keep only the selected channel to unlink it. FIR import, Clear and crossover design apply to every member of the selected group.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 12 }
        RowLayout {
            Layout.topMargin: 8; Layout.bottomMargin: 8; Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            ConsoleButton { text: 'Cancel'; onClicked: dialog.close() }
            ConsoleButton { objectName: 'channel_link_review'; text: 'Review…'; enabled: backend.usbControlReady && !backend.usbControlPending; onClicked: { dialog.close(); backend.reviewChannelLink(dialog.members) } }
        }
    }
}
