import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
ColumnLayout {
    id: root
    property var currentData: backend.current
    function refreshView() {
        currentData=backend.current
        
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: {if(visible)refreshView();else kneeHeld=false}
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} }
    required property string section
    property var values: root.currentData[section]
    property bool available: section==='limiter' ? backend.selected>=4 : backend.selected<4
    property bool kneeHeld: false
    property var sample: { backend.meters; backend.revision; backend.dynamicsDisplayEnabled; return backend.dynamicsSample(section) }
    property var fields: section==='gate' ? [ ['Threshold','threshold',-90,0,'dB',.5,false],['Hold','hold_ms',10,999,'ms',1,true],['Attack','attack_ms',1,999,'ms',1,true],['Release','release_ms',10,3000,'ms',1,true] ] : [ ['Threshold','threshold',-90,20,'dB',.5,false],['Ratio','ratio',1,20,':1',.1,false],['Soft knee','knee',0,12,'dB',1,false],['Attack','attack_ms',1,999,'ms',1,true],['Release','release_ms',10,3000,'ms',1,true] ]
    readonly property bool compact: Window.window && Window.window.height<768
    spacing: compact?4:6
    RowLayout {
        Layout.fillWidth: true
        Label { text: root.section==='gate' ? 'NOISE GATE' : root.section==='compressor' ? 'RMS COMPRESSOR' : 'PEAK LIMITER'; font.pixelSize: 16; font.bold: true }
        Item { Layout.fillWidth: true }
        ConsoleButton { visible: root.section==='limiter' && !root.values.ratio_limit; text: 'Set Limit ∞'; onClicked: backend.setRatioIndex(backend.selected,'limiter',15) }
        Label { text: root.currentData.name; color: Theme.color('#25badd', backend.lightTheme); font.pixelSize: 11 }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 10
        DynamicsPlot {
            id: dynamicsGraph
            objectName: 'dynamics_graph_'+root.section
            section: root.section
            kneeHeld: root.kneeHeld
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 280; Layout.preferredWidth: 460; Layout.preferredHeight: root.compact?180:210; Layout.minimumHeight: root.compact?136:170; Layout.maximumHeight: 210
        }
        ColumnLayout {
            visible: root.section==='gate' && root.sample.available; Layout.preferredWidth: 138; Layout.maximumWidth: 138; spacing: 5
            Label { text: 'SIGNAL'; font.pixelSize: 10; color: Theme.color('#27c7e8', backend.lightTheme); font.bold: true }
            RowLayout {
                Layout.fillWidth: true; spacing: 5
                ColumnLayout {
                    Label { text: 'IN'; font.pixelSize: 10; color: Theme.color('#93adbd', backend.lightTheme) }
                    LevelMeter { Layout.preferredHeight: root.compact?120:140; Layout.preferredWidth: 55; level: backend.meterPosition(root.sample.input); db: root.sample.input; showScale: true; caption: 'Pre '+root.section }
                }
                ColumnLayout {
                    Label { text: 'OUT / PEAK'; font.pixelSize: 10; color: Theme.color('#93adbd', backend.lightTheme) }
                    LevelMeter { Layout.preferredHeight: root.compact?120:140; Layout.preferredWidth: 55; level: backend.meterPosition(root.sample.output); peak: backend.meterPosition(root.sample.peak); db: root.sample.output; showScale: true; caption: 'Post '+root.section }
                }
            }
            Label { text: 'GR '+root.sample.reduction.toFixed(1)+' dB'; color: Theme.color('#ff7483', backend.lightTheme); font.bold: true }
        }
        ColumnLayout {
            visible: root.section==='compressor'; enabled: root.available
            Layout.minimumWidth: 170; Layout.preferredWidth: 225; Layout.maximumWidth: 225; spacing: 6
            Label { text: 'DETECTOR EQ'; color: Theme.color('#90afc1', backend.lightTheme); font.bold: true; font.pixelSize: 11 }
            ComboBox {
                objectName: root.section+'_detector_type'
                Layout.fillWidth: true; implicitHeight: 30
                model: backend.options.detectorTypes; currentIndex: backend.options.detectorTypes.indexOf(root.values.detector_type)
                onActivated: backend.edit(backend.selected,'compressor.detector_type',model[currentIndex],-1)
                background: Rectangle { radius: 5; color: Theme.color('#142733', backend.lightTheme); border.color: Theme.color('#365263', backend.lightTheme) }
            }
            ParameterFader { label: 'Frequency'; controlId: root.section+'_detector_frequency'; number: root.values.detector_frequency || 1000; minimum: backend.options.frequencyMin; maximum: backend.options.frequencyMax; unit: 'Hz'; step: 1; logarithmic: true; Layout.fillWidth: true; onCommitted: value => backend.edit(backend.selected,'compressor.detector_frequency',value,-1) }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: root.section==='gate' && root.sample.available
        Label { text: 'IN '+root.sample.input.toFixed(1)+' dB   →   OUT '+root.sample.output.toFixed(1)+' dB   ·   Peak '+root.sample.peak.toFixed(1)+' dB'; color: Theme.color('#9bb8c7', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true }
        Label { visible: root.section!=='gate'; text: !root.values.ratio_limit && root.values.ratio===1 ? '1:1 · no gain reduction' : 'Gain reduction '+root.sample.reduction.toFixed(1)+' dB'; color: Theme.color('#f1c661', backend.lightTheme); font.pixelSize: 11 }
    }
    DynamicsReadouts {
        visible: root.section!=='gate' && backend.dynamicsDisplayEnabled
        Layout.fillWidth: true
        section: root.section; sample: dynamicsGraph.signalData; active: dynamicsGraph.displayActive
        compact: root.compact
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 8; enabled: root.available
        Repeater {
            model: root.fields
            ParameterFader {
                required property var modelData
                property bool ratioControl: modelData[1]==='ratio'
                Layout.fillWidth: true; Layout.minimumWidth: 85
                vertical: true; sliderHeight: root.compact?104:136
                label: modelData[0]; unit: modelData[4]; controlId: root.section+'_'+modelData[1]
                number: ratioControl && root.values.ratio_limit ? 1000000 : root.values[modelData[1]]
                minimum: modelData[2]; maximum: modelData[3]; step: modelData[5]; logarithmic: modelData[6]; decimals: modelData[4]==='ms'?0:1
                choices: ratioControl ? backend.options.ratios.concat([1000000]) : []
                choiceLabels: ratioControl ? backend.options.ratios.map(v=>v.toFixed(1)+':1').concat(['Limit ∞:1']) : []
                accent: root.section==='gate' ? Theme.color('#53d89d', backend.lightTheme) : Theme.color('#29bce5', backend.lightTheme)
                onPressedChanged: if(modelData[1]==='knee')root.kneeHeld=pressed
                onCommitted: value => { if(ratioControl)backend.setRatioIndex(backend.selected,root.section,value===1000000?15:backend.options.ratios.indexOf(value));else backend.edit(backend.selected,root.section+'.'+modelData[1],value,-1) }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; visible: root.section==='compressor'
        Label { text: 'CHANNEL'; font.pixelSize: 10; color: Theme.color('#95b3c4', backend.lightTheme) }
        LevelMeter { objectName: 'dynamics_channel_meter_'+root.section; horizontal: true; showScale: true; Layout.fillWidth: true; level: backend.meters[backend.selected]; peak: backend.meterPeaks[backend.selected]; db: backend.meterDb[backend.selected]; readingText: backend.meterLabels[backend.selected]; caption: 'DSP channel level'; indicatorKind: root.section==='compressor'?'COMP':'LIM'; reductionActive: backend.reductionState[backend.selected].active }
    }
    Label { objectName: 'dynamics_source_'+root.section; visible: root.section==='gate'; text: 'Static characteristic'; color: Theme.color('#708d9f', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Item { Layout.fillHeight: true }
}
