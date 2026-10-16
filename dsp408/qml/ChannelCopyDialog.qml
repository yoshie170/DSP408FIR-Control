import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme
ConsoleDialog {
    id: root; objectName: 'channel_copy_dialog'; title: 'Copy channel settings'
    anchors.centerIn: parent; width: Math.min(570,parent.width-40)
    property int sourceIndex: 0
    property var targets: []
    property var destinations: []
    property var sections: []
    property var selectedSections: []
    property string initialSection: 'all'
    property string errorText: ''
    function openFor(section) { initialSection=section;open() }
    function toggle(values,key,checked) {
        var next=values.filter(v=>v!==key)
        if(checked)next.push(key)
        return next
    }
    onOpened: {
        sourceIndex=backend.selected;errorText=''
        var choices=[],start=sourceIndex<4?0:4,end=sourceIndex<4?4:12
        for(var i=start;i<end;i++)if(i!==sourceIndex)choices.push({index:i,label:(i<4?'IN '+String.fromCharCode(65+i):'OUT '+(i-3))+' · '+backend.channel(i).name})
        targets=choices;destinations=choices.length?[choices[0].index]:[]
        sections=[{key:'gain',label:'Gain'},{key:'mute',label:'Mute'},{key:'polarity',label:'Polarity'},{key:'delay',label:'Delay'},{key:'peq',label:'PEQ'}].concat(sourceIndex<4?[{key:'gate',label:'Gate'},{key:'compressor',label:'Compressor'}]:[{key:'crossover',label:'IIR crossover'},{key:'limiter',label:'Limiter'}])
        selectedSections=initialSection==='peq'?['peq']:sections.map(s=>s.key)
        Qt.callLater(()=>cancelCopy.forceActiveFocus())
    }
    contentItem: ColumnLayout {
        spacing: 8
        Label { text: 'From '+(root.sourceIndex<4?'IN '+String.fromCharCode(65+root.sourceIndex):'OUT '+(root.sourceIndex-3))+' · '+backend.channel(root.sourceIndex).name; font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.fillWidth: true
            Label { text: 'DESTINATIONS'; color: Theme.color('#95b3c4',backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true }
            ConsoleButton { objectName: 'copy_targets_all'; text: 'All'; implicitHeight: 25; onClicked: root.destinations=root.targets.map(t=>t.index) }
            ConsoleButton { text: 'None'; implicitHeight: 25; onClicked: root.destinations=[] }
        }
        GridLayout {
            Layout.fillWidth: true; columns: 2; columnSpacing: 12; rowSpacing: 2
            Repeater {
                model: root.targets
                ConsoleCheck {
                    required property var modelData
                    objectName: 'copy_target_'+modelData.index; text: modelData.label
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    checked: root.destinations.indexOf(modelData.index)>=0
                    onClicked: root.destinations=root.toggle(root.destinations,modelData.index,checked)
                    contentItem: Text { text: parent.text; leftPadding: 37; elide: Text.ElideRight; color: Theme.color('#adc2cf',backend.lightTheme); font: parent.font; verticalAlignment: Text.AlignVCenter }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.color('#304652',backend.lightTheme) }
        RowLayout {
            Layout.fillWidth: true
            Label { text: 'PARAMETERS'; color: Theme.color('#95b3c4',backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true }
            ConsoleButton { objectName: 'copy_sections_all'; text: 'All'; implicitHeight: 25; onClicked: root.selectedSections=root.sections.map(s=>s.key) }
            ConsoleButton { text: 'None'; implicitHeight: 25; onClicked: root.selectedSections=[] }
        }
        GridLayout {
            Layout.fillWidth: true; columns: 3; columnSpacing: 8; rowSpacing: 2
            Repeater {
                model: root.sections
                ConsoleCheck {
                    required property var modelData
                    objectName: 'copy_section_'+modelData.key; text: modelData.label; Layout.fillWidth: true
                    checked: root.selectedSections.indexOf(modelData.key)>=0
                    onClicked: root.selectedSections=root.toggle(root.selectedSections,modelData.key,checked)
                }
            }
        }
        Label { objectName: 'copy_summary'; text: root.selectedSections.length+' sections → '+root.destinations.length+' channel'+(root.destinations.length===1?'':'s'); font.bold: true; color: Theme.color('#39c9e4',backend.lightTheme); Layout.fillWidth: true }
        Label { text: 'FIR, names, Link and routing keep their own settings.'+(backend.usbReadActive?' Copy applies the selected parameters to the DSP. A linked destination applies them to its entire group.':''); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#95b3c4',backend.lightTheme) }
        Label { visible: root.errorText.length>0; text: root.errorText; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#efad67',backend.lightTheme) }
    }
    footer: DialogActions {
        Item { Layout.fillWidth: true }
        ConsoleButton { id: cancelCopy; objectName: 'copy_cancel'; text: 'Cancel'; onClicked: root.close(); Keys.onReturnPressed: root.close(); Keys.onEnterPressed: root.close() }
        ConsoleButton {
            objectName: 'copy_accept'; text: 'Copy'; emphasized: true
            enabled: backend.parameterEditingAllowed && root.destinations.length>0 && root.selectedSections.length>0
            onClicked: {if(backend.copyChannelSections(root.sourceIndex,root.destinations,root.selectedSections))root.close();else root.errorText=backend.displayMessage}
        }
    }
}
