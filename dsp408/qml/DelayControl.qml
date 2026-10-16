import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property int channelIndex: backend.selected
    property string controlId: 'channel_delay'
    property var channelData: { backend.revision; return backend.channel(channelIndex) }
    property string unit: backend.settings.delay_unit
    property real factor: backend.delayFactor(unit)
    spacing: 5
    RowLayout {
        Layout.fillWidth: true
        Label { text: 'Delay'; font.bold: true; color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true }
        Repeater {
            model: ['ms','m','ft']
            ConsoleButton { required property string modelData; objectName: root.controlId+'_unit_'+modelData; text: modelData; checked: root.unit===modelData; implicitHeight: 25; onClicked: backend.setting('delay_unit',modelData) }
        }
    }
    ParameterFader {
        Layout.fillWidth: true; label: 'Delay / '+root.unit; controlId: root.controlId
        number: backend.delayDisplay(root.channelData.delay_ms,root.unit)
        minimum: 0; maximum: 680*root.factor; step: .1*root.factor
        decimals: root.unit==='ms'?1:3; unit: root.unit
        onCommitted: value => backend.editDelay(root.channelIndex,value,root.unit)
    }
    RowLayout {
        Layout.fillWidth: true
        NumberField {
            controlId: root.controlId+'_exact'; Layout.preferredWidth: 105; fieldHeight: 26
            number: backend.delayDisplay(root.channelData.delay_ms,root.unit)
            minimum: 0; maximum: 680*root.factor; step: .1*root.factor; decimals: root.unit==='ms'?1:3
            onCommitted: value => backend.editDelay(root.channelIndex,value,root.unit)
        }
        Label { text: root.unit; color: Theme.color('#9ab5c6', backend.lightTheme) }
        Item { Layout.fillWidth: true }
        Label { objectName: root.controlId+'_equivalent'; text: root.channelData.delay_ms.toFixed(1)+' ms = '+backend.delayDisplay(root.channelData.delay_ms,'m').toFixed(3)+' m'; color: Theme.color('#9ab5c6', backend.lightTheme) }
    }
    Label { text: 'Editor conversion: 343.5 m/s · stored in ms'; color: Theme.color('#7290a2', backend.lightTheme); font.pixelSize: 10 }
}
