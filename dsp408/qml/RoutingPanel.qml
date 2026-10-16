import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property int output: backend.selected>=4 ? backend.selected-4 : 0
    spacing: 9
    RowLayout {
        Label { text: 'ROUTING / MIX'; font.pixelSize: 17; font.bold: true }
        Item { Layout.fillWidth: true }
        Label { text: '4 inputs × 8 outputs'; color: Theme.color('#82a3b7', backend.lightTheme); font.pixelSize: 11 }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 4
        Repeater { model: 8; ConsoleButton { required property int index; text: 'OUT '+(index+1); Layout.fillWidth: true; checked: root.output===index; onClicked: backend.select(index+4) } }
    }
    Rectangle {
        Layout.fillWidth: true; Layout.preferredHeight: 278; color: Theme.color('#0b1821', backend.lightTheme); radius: 6; border.color: Theme.color('#2d4655', backend.lightTheme)
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 10; spacing: 3
            RowLayout {
                Layout.fillWidth: true
                Label { text: 'OUTPUT'; Layout.preferredWidth: 135; color: Theme.color('#7999ad', backend.lightTheme) }
                Repeater { model: 4; Label { required property int index; text: {backend.revision;return backend.channel(index).name} Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: Theme.color('#9bb7c9', backend.lightTheme) } }
            }
            Repeater {
                model: 8
                Rectangle {
                    id: row
                    required property int index
                    Layout.fillWidth: true; Layout.preferredHeight: 26
                    color: root.output===index ? Theme.color('#143449', backend.lightTheme) : index%2 ? Theme.color('#10202b', backend.lightTheme) : 'transparent'; radius: 4
                    RowLayout {
                        anchors.fill: parent
                        ConsoleButton { text: {backend.revision;return backend.channel(row.index+4).name} Layout.preferredWidth: 135; implicitHeight: 24; checked: root.output===row.index; onClicked: backend.select(row.index+4) }
                        Repeater {
                            model: 4
                            Item {
                                required property int index
                                Layout.fillWidth: true; Layout.fillHeight: true
                                ConsoleCheck { anchors.centerIn: parent; checked: backend.routing[row.index][parent.index]; onClicked: backend.route(row.index,parent.index,checked,backend.routingGains[row.index][parent.index]) }
                            }
                        }
                    }
                }
            }
        }
    }
    Label { text: 'MIX LEVELS / '+backend.channel(root.output+4).name; font.bold: true; color: Theme.color('#94b4c7', backend.lightTheme); font.pixelSize: 11 }
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        Repeater {
            model: 4
            ColumnLayout {
                required property int index
                Layout.fillWidth: true
                ConsoleCheck { text: {backend.revision;return backend.channel(parent.index).name} checked: backend.routing[root.output][parent.index]; onClicked: backend.route(root.output,parent.index,checked,backend.routingGains[root.output][parent.index]) }
                ParameterFader { Layout.fillWidth: true; label: 'Mix level'; controlId: 'mix_gain_'+parent.index; minimum: -60; maximum: 0; step: .1; unit: 'dB'; number: backend.routingGains[root.output][parent.index]; onCommitted: value => backend.route(root.output,parent.index,backend.routing[root.output][parent.index],value) }
            }
        }
    }
    Label { text: 'Enabled paths are mixed into the selected output · all edits are local'; color: Theme.color('#708e9f', backend.lightTheme); font.pixelSize: 10 }
    Item { Layout.fillHeight: true }
}

