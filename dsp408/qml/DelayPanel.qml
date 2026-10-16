import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
ColumnLayout {
    id: root
    property real factor: backend.delayFactor(backend.settings.delay_unit)
    readonly property bool compact: Window.window && Window.window.height<768
    spacing: compact?2:4
    RowLayout {
        Layout.fillWidth: true
        Label { text: 'DELAY / ALL CHANNELS'; font.pixelSize: 17; font.bold: true; Layout.fillWidth: true }
        Repeater { model: ['ms','m','ft']; ConsoleButton { required property string modelData; objectName: 'delay_unit_'+modelData; text: modelData; checked: backend.settings.delay_unit===modelData; onClicked: backend.setting('delay_unit',modelData) } }
    }
    Repeater {
        model: 12
        Rectangle {
            id: row
            required property int index
            property var ch: { backend.revision;return backend.channel(index) }
            Component.onCompleted: ch=backend.channel(index)
            onVisibleChanged: if(visible)ch=backend.channel(index)
            Connections { target: backend; function onChanged() {if(row.visible)row.ch=backend.channel(row.index)} }
            Layout.fillWidth: true; Layout.preferredHeight: root.compact?29:33
            color: backend.selected===index ? Theme.color('#14384d', backend.lightTheme) : index%2 ? Theme.color('#12232d', backend.lightTheme) : Theme.color('#0e1b24', backend.lightTheme); radius: 5
            RowLayout {
                anchors.fill: parent; anchors.margins: root.compact?2:4; spacing: 8
                ConsoleButton { text: row.ch.name; implicitHeight: 25; Layout.preferredWidth: 125; onClicked: backend.select(row.index) }
                Slider {
                    id: time
                    objectName: 'delay_'+row.index
                    Layout.fillWidth: true; implicitHeight: 24; from: 0; to: 680; stepSize: .1; wheelEnabled: true
                    Binding { target: time; property: 'value'; value: row.ch.delay_ms; when: !time.pressed; restoreMode: Binding.RestoreNone }
                    onMoved: backend.edit(row.index,'delay_ms',value,-1)
                    onPressedChanged: if(!pressed)backend.flushControlView()
                    background: Rectangle { x: time.leftPadding; y: (time.height-height)/2; width: time.availableWidth; height: 5; radius: 2; color: Theme.color('#071117', backend.lightTheme); border.color: Theme.color('#345061', backend.lightTheme); Rectangle { width: parent.width*time.position; height: parent.height; color: Theme.color('#1380a4', backend.lightTheme); radius: 2 } }
                    handle: Rectangle { x: time.leftPadding+time.visualPosition*(time.availableWidth-width); y: (time.height-height)/2; width: 12; height: 19; radius: 3; color: Theme.color('#97b7c7', backend.lightTheme); border.color: Theme.color('#22bbe0', backend.lightTheme) }
                }
                NumberField { controlId: 'delay_exact_'+row.index; Layout.preferredWidth: 92; fieldHeight: 24; number: backend.delayDisplay(row.ch.delay_ms,backend.settings.delay_unit); minimum: 0; maximum: 680*root.factor; step: .1*root.factor; decimals: backend.settings.delay_unit==='ms'?1:3; onCommitted: value => backend.editDelay(row.index,value,backend.settings.delay_unit) }
                Label { text: backend.settings.delay_unit; Layout.preferredWidth: 18; color: Theme.color('#799caf', backend.lightTheme) }
                Label { objectName: 'delay_equivalent_'+row.index; text: backend.settings.delay_unit==='ms'?backend.delayDisplay(row.ch.delay_ms,'m').toFixed(3)+' m':row.ch.delay_ms.toFixed(1)+' ms'; Layout.preferredWidth: 78; horizontalAlignment: Text.AlignRight; color: Theme.color('#a4bfce', backend.lightTheme); font.pixelSize: 11 }
            }
        }
    }
    Label { text: 'Editor conversion: 343.5 m/s · state is stored in milliseconds'; font.pixelSize: 10; color: Theme.color('#7290a2', backend.lightTheme) }
    Item { Layout.fillHeight: true }
}
