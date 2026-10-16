import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property var currentData: backend.current
    function refreshView() {
        currentData=backend.current
        
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: if(visible)refreshView()
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} }
    property int section: 0
    property var entry: root.currentData.deq[section]
    property bool available: backend.selected<4
    property var fields: [ ['Frequency','frequency','Hz',1,1,true],['Q / bandwidth','q','',.1,2,true],['Gain','gain','dB',1,0,false],['Threshold','threshold','dB',.5,1,false],['Ratio','ratio',':1',.1,1,false],['Attack','attack_ms','ms',1,0,true],['Release','release_ms','ms',1,0,true] ]
    spacing: 10
    RowLayout {
        Label { text: 'DYNAMIC EQ'; font.pixelSize: 17; font.bold: true }
        Item { Layout.fillWidth: true }
        Label { text: root.available ? root.currentData.name+' · 3 sections' : 'Select an input channel'; color: root.available ? Theme.color('#25badd', backend.lightTheme) : Theme.color('#dbb67c', backend.lightTheme) }
    }
    RowLayout {
        Layout.fillWidth: true
        Repeater { model: 4; ConsoleButton { required property int index; text: 'IN '+(index+1); Layout.fillWidth: true; checked: backend.selected===index; onClicked: backend.select(index) } }
    }
    RowLayout {
        Layout.fillWidth: true
        Repeater { model: 3; ConsoleButton { required property int index; text: 'DEQ '+(index+1); Layout.fillWidth: true; checked: root.section===index; onClicked: root.section=index } }
        ConsoleCheck { text: 'Bypass'; checked: root.entry.bypass; enabled: root.available; onClicked: backend.edit(backend.selected,'deq.bypass',checked,root.section) }
    }
    RowLayout {
        Layout.fillWidth: true; enabled: root.available
        ComboBox { Layout.fillWidth: true; model: backend.options.deqTypes; currentIndex: model.indexOf(root.entry.kind); onActivated: backend.edit(backend.selected,'deq.kind',model[currentIndex],root.section); background: Rectangle { color: Theme.color('#152733', backend.lightTheme); radius: 5; border.color: Theme.color('#365263', backend.lightTheme) } }
        ComboBox { Layout.fillWidth: true; model: backend.options.deqModes; currentIndex: model.indexOf(root.entry.mode); onActivated: backend.edit(backend.selected,'deq.mode',model[currentIndex],root.section); background: Rectangle { color: Theme.color('#152733', backend.lightTheme); radius: 5; border.color: Theme.color('#365263', backend.lightTheme) } }
    }
    GridLayout {
        Layout.fillWidth: true; columns: root.width>950 ? 4 : 3; columnSpacing: 8; rowSpacing: 8; enabled: root.available
        Repeater {
            model: root.fields
            ParameterFader {
                required property var modelData
                property var bounds: backend.options.deqLimits[modelData[1]]
                Layout.fillWidth: true; Layout.minimumWidth: 130
                label: modelData[0]; controlId: 'deq_'+modelData[1]; number: root.entry[modelData[1]]
                unit: modelData[2]; minimum: bounds[0]; maximum: bounds[1]; step: modelData[3]; decimals: modelData[4]; logarithmic: modelData[5]
                choices: modelData[1]==='q' ? backend.options.qValues : modelData[1]==='ratio' ? backend.options.ratios.slice(0,11) : []
                onCommitted: value => backend.edit(backend.selected,'deq.'+modelData[1],value,root.section)
            }
        }
    }
    Label { text: 'Editor V1.12 parameter profile · offline settings only · no dynamic audio processing'; color: Theme.color('#718e9f', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Item { Layout.fillHeight: true }
}
