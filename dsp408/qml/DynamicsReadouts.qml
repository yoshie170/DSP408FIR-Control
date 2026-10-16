import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
RowLayout {
    id: root
    required property string section
    required property var sample
    required property bool active
    property bool compact: false
    spacing: 8
    Repeater {
        model: [ ['IN','input',Theme.color('#39c6e3', backend.lightTheme)],['OUT','output',Theme.color('#39c6e3', backend.lightTheme)],['GAIN REDUCTION','reduction',Theme.color('#e7b458', backend.lightTheme)] ]
        Rectangle {
            required property var modelData
            readonly property bool reduction: modelData[1]==='reduction'
            readonly property real reading: root.active ? root.sample[modelData[1]] : 0
            objectName: 'dynamics_readout_'+root.section+'_'+modelData[1]
            Layout.fillWidth: true; Layout.minimumWidth: 85; implicitHeight: root.compact?38:44
            color: Theme.color('#10212b', backend.lightTheme); radius: 5; border.color: Theme.color('#29424f', backend.lightTheme)
            ColumnLayout {
                anchors.fill: parent; anchors.margins: root.compact?5:7; spacing: 3
                RowLayout {
                    Layout.fillWidth: true
                    Label { objectName: 'dynamics_label_'+root.section+'_'+modelData[1]; text: modelData[0]; font.pixelSize: 9; color: Theme.color('#8fabba', backend.lightTheme); Layout.fillWidth: true }
                    Label {
                        objectName: 'dynamics_value_'+root.section+'_'+modelData[1]
                        text: root.active ? reading.toFixed(1)+' dB' : '—'
                        color: root.active ? modelData[2] : Theme.color('#6d8794', backend.lightTheme); font.pixelSize: 12; font.bold: true
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 6; color: Theme.color('#243a47', backend.lightTheme); radius: 2
                    Rectangle {
                        height: parent.height; radius: parent.radius; color: modelData[2]
                        width: parent.width*(root.active ? Math.max(0,Math.min(1,reduction ? reading/120 : (reading+100)/120)) : 0)
                        Behavior on width { enabled: root.active; NumberAnimation { duration: 90; easing.type: Easing.Linear } }
                    }
                }
            }
        }
    }
}
