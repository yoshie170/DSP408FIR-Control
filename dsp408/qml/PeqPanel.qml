import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property var currentData: backend.current
    function refreshView() {
        if(lastChannel!==backend.selected){lastChannel=backend.selected;freezeRta=false}
        currentData=backend.current
        
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: if(visible)refreshView()
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} }
    property var deviceData: backend.usbConfirmedCurrent
    property int band: 0
    property int tableHeight: 155
    property bool phase: false
    property bool individualBands: true
    property bool includeCrossover: true
    readonly property bool channelView: backend.selected>=4 && root.includeCrossover && !root.phase
    property bool fineQ: false
    property bool rta: false
    property bool freezeRta: false
    property var frozenSpectrum: []
    property int lastChannel: 0
    property var flt: root.currentData.filters[Math.min(band,root.currentData.filters.length-1)]
    signal bandSelected(int value)
    signal copyRequested()
    spacing: 5
    RowLayout {
        Layout.fillWidth: true; spacing: 5
        Label { text: root.currentData.filters.length+'-band PEQ · 96 kHz preview'; color: Theme.color('#819dad', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true }
        ConsoleButton { objectName: 'peq_magnitude'; text: 'Magnitude'; checkable: true; checked: !root.phase; onClicked: {root.phase=false;backend.showPhase(false)} }
        ConsoleButton { objectName: 'peq_phase'; text: 'Phase'; checkable: true; checked: root.phase; onClicked: {root.phase=true;backend.showPhase(true)} }
        ConsoleButton { objectName: 'peq_reset'; text: 'Reset'; onClicked: backend.resetEQ() }
        ConsoleButton { objectName: 'peq_copy'; text: 'Copy…'; enabled: backend.parameterEditingAllowed; onClicked: root.copyRequested() }
        ConsoleCheck { objectName: 'peq_bypass'; text: 'Bypass'; checked: root.currentData.eq_bypass; onClicked: backend.edit(backend.selected,'eq_bypass',checked,-1) }
    }
    Flow {
        objectName: 'peq_compare_flow'
        Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; spacing: 3
        Label { text: 'COMPARE'; height: 24; verticalAlignment: Text.AlignVCenter; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 10 }
        Repeater {
            model: 12
            ConsoleCheck {
                required property int index
                objectName: 'peq_compare_'+index
                compact: true; leftPadding: 1; rightPadding: 1
                property color traceColor: [Theme.color('#38aeff', backend.lightTheme),Theme.color('#48e77c', backend.lightTheme),Theme.color('#ff6774', backend.lightTheme),Theme.color('#c66cf5', backend.lightTheme),Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme),Theme.color('#ff89c5', backend.lightTheme),Theme.color('#b8d6ee', backend.lightTheme),Theme.color('#d7b68c', backend.lightTheme)][index]
                accent: traceColor
                text: index<4?'IN '+String.fromCharCode(65+index):'OUT '+(index-3)
                checked: backend.peqCompared.indexOf(index)>=0; enabled: index!==backend.selected
                onClicked: backend.comparePeq(index,checked)
                contentItem: Text { text: parent.text; leftPadding: 24; color: parent.enabled?parent.traceColor:Theme.color('#718b9b', backend.lightTheme); font: parent.font; verticalAlignment: Text.AlignVCenter }
                ToolTip.visible: hovered; ToolTip.text: {backend.revision;return backend.channel(index).name+(index===backend.selected?' · current channel (solid white curve)':' · dashed comparison curve')}
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 6
        ConsoleCheck { objectName: 'peq_band_curves_toggle'; compact: true; text: 'Band curves'; enabled: !root.phase; checked: root.individualBands; onClicked: root.individualBands=checked; ToolTip.visible: hovered; ToolTip.text: 'Colored per-band responses and fills in Magnitude view. White sum and numbered editing handles remain visible.' }
        ConsoleCheck { objectName: 'peq_channel_response_toggle'; compact: true; visible: backend.selected>=4 && !root.phase; text: 'Include XOVER'; checked: root.includeCrossover; onClicked: root.includeCrossover=checked; ToolTip.visible: hovered; ToolTip.text: 'Show XOVER + PEQ + gain. Curves and editing points share the same dB axis. Display only; filters stay active.' }
        Rectangle { Layout.preferredWidth: 24; Layout.preferredHeight: 3; color: Theme.color('#f0faff', backend.lightTheme); radius: 1 }
        Label { objectName: 'peq_sum_legend'; text: root.channelView?'Σ XOVER + PEQ + gain':(root.phase?'Σ PEQ phase':'Σ PEQ sum')+(root.currentData.eq_bypass?(root.phase?' · BYPASS · 0°':' · BYPASS · 0 dB'):' · all enabled bands'); color: Theme.color('#f0faff', backend.lightTheme); font.bold: true; font.pixelSize: 11 }
        Label { text: root.channelView?'PEQ: same dB axis · dashed: compare':(root.individualBands && !root.phase?'· colored: individual bands ':'')+'· dashed: compared channels'; color: Theme.color('#819dad', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
    }
    ResponsePlot {
        objectName: 'peq_plot'; Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 160; Layout.preferredHeight: 280; band: root.band; phase: root.phase; fineQ: root.fineQ; showBandCurves: root.individualBands; comparisons: backend.peqComparisons; spectrum: []; channelView: root.channelView; channelResponse: root.channelView?backend.peqChannelResponse:({values:[],available:false}); onBandSelected: index => root.bandSelected(index)
        Rectangle {
            objectName: 'peq_bypass_overlay'; anchors.fill: parent; z: 10; radius: 6
            visible: root.currentData.eq_bypass && !root.channelView; color: Theme.color('#c409151c', backend.lightTheme)
            Label {
                objectName: 'peq_bypass_label'; anchors.centerIn: parent; text: 'BYPASS'
                font.pixelSize: Math.min(56,parent.width/7,parent.height*.3)
                font.bold: true; font.letterSpacing: 5; color: Theme.color('#f0c26e', backend.lightTheme)
                Accessible.name: 'PEQ bypassed'
            }
        }
        Label { objectName: 'peq_context_bypass'; visible: root.channelView && root.currentData.eq_bypass; anchors.left: parent.left; anchors.top: parent.top; anchors.leftMargin: 52; anchors.topMargin: 4; text: 'PEQ BYPASS · XOVER active'; font.bold: true; font.pixelSize: 10; color: Theme.color('#e2bd72',backend.lightTheme) }
    }
    Label { objectName: 'peq_device_values'; visible: backend.developerTools; text: (backend.usbControlMode && root.deviceData.filters ? 'DSP readback: '+root.deviceData.filters[root.band].frequency.toFixed(1)+' Hz / '+root.deviceData.filters[root.band].gain.toFixed(1)+' dB / Q '+root.deviceData.filters[root.band].q.toFixed(2)+(backend.usbControlPending?' · previous reading':'') : 'White: current sum · dashed: comparisons')+(root.fineQ?' · wheel: Q ±0.10':' · wheel: Q ×5 · Shift: one table step'); color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; elide: Text.ElideRight }
    RowLayout {
        Layout.fillWidth: true; spacing: 4
        Label { text: 'PEQ BANDS'; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 10 }
        Repeater {
            model: root.currentData.filters.length
            ConsoleButton {
                required property int index
                objectName: 'peq_band_'+index
                property color bandColor: [Theme.color('#38aeff', backend.lightTheme),Theme.color('#48e77c', backend.lightTheme),Theme.color('#ff6774', backend.lightTheme),Theme.color('#c66cf5', backend.lightTheme),Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme)][index]
                text: String(index+1); Layout.fillWidth: true; implicitHeight: 29; implicitWidth: 26; leftPadding: 3; rightPadding: 3; font.pixelSize: root.band===index ? 14 : 11; font.bold: root.band===index
                checked: root.band===index; accent: bandColor; onClicked: root.bandSelected(index)
                background: Rectangle { radius: 4; color: root.band===parent.index ? Qt.darker(parent.bandColor,2.8) : Theme.color('#18252f', backend.lightTheme); border.color: parent.bandColor; opacity: root.band===parent.index ? 1 : .5 }
            }
        }
        ConsoleCheck { text: 'Enabled'; accent: [Theme.color('#38aeff', backend.lightTheme),Theme.color('#48e77c', backend.lightTheme),Theme.color('#ff6774', backend.lightTheme),Theme.color('#c66cf5', backend.lightTheme),Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme)][root.band]; checked: root.flt.enabled; onClicked: backend.edit(backend.selected,'filters.enabled',checked,root.band) }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 7
        ColumnLayout {
            Layout.preferredWidth: 135
            Label { text: 'TYPE'; color: Theme.color('#8ea8b9', backend.lightTheme); font.pixelSize: 10 }
            ComboBox { Layout.fillWidth: true; implicitHeight: 32; model: backend.options.filters; currentIndex: model.indexOf(root.flt.kind); onActivated: backend.edit(backend.selected,'filters.kind',model[currentIndex],root.band); background: Rectangle { radius: 5; color: Theme.color('#172a37', backend.lightTheme); border.color: Theme.color('#395667', backend.lightTheme) } }
        }
        ParameterFader { Layout.fillWidth: true; label: 'Frequency'; controlId: 'peq_frequency'; number: root.flt.frequency; minimum: backend.options.frequencyMin; maximum: backend.options.frequencyMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; onCommitted: value => backend.edit(backend.selected,'filters.frequency',value,root.band) }
        ParameterFader { Layout.fillWidth: true; label: 'Gain'; controlId: 'peq_gain'; number: root.flt.gain; minimum: -12; maximum: 12; step: .1; decimals: 1; unit: 'dB'; onCommitted: value => backend.edit(backend.selected,'filters.gain',value,root.band) }
        ParameterFader {
            Layout.fillWidth: true; label: 'Q / bandwidth'; controlId: 'peq_q'; number: root.flt.q; minimum: .4; maximum: 128
            choices: backend.options.qValues; wheelStep: root.fineQ?.10:0; wheelChoiceStride: root.fineQ?1:5; decimals: 2
            onCommitted: value => backend.edit(backend.selected,'filters.q',value,root.band)
            ConsoleCheck { objectName: 'peq_q_fine'; anchors.left: parent.left; anchors.leftMargin: 10; y: 24; compact: true; text: 'Fine'; checked: root.fineQ; onClicked: root.fineQ=checked; ToolTip.visible: hovered; ToolTip.text: 'Mouse wheel: Q in 0.10 steps.' }
        }
    }
    Rectangle {
        Layout.fillWidth: true; Layout.preferredHeight: root.tableHeight; Layout.minimumHeight: 125
        color: Theme.color('#0c1821', backend.lightTheme); radius: 6; border.color: Theme.color('#2c4250', backend.lightTheme)
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 5; spacing: 2
            RowLayout {
                Layout.fillWidth: true; Layout.preferredHeight: 20
                Label { text: '#'; Layout.preferredWidth: 26; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
                Label { text: 'TYPE'; Layout.fillWidth: true; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
                Label { text: 'FREQUENCY / Hz'; Layout.preferredWidth: 105; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
                Label { text: 'GAIN / dB'; Layout.preferredWidth: 75; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
                Label { text: 'Q'; Layout.preferredWidth: 65; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
                Label { text: 'ON'; Layout.preferredWidth: 36; color: Theme.color('#7d9aad', backend.lightTheme); font.pixelSize: 10 }
            }
            AdaptiveScrollView {
                objectName: 'peq_table_scroll'
                Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth; clip: true
                Column {
                    width: parent.width; spacing: 2
                    Repeater {
                        model: root.currentData.filters.length
                        Rectangle {
                            id: eqrow
                            required property int index
                            property var f: root.currentData.filters[index] || root.currentData.filters[0]
                            width: parent.width; height: 25; radius: 3; color: root.band===index ? Theme.color('#183649', backend.lightTheme) : index%2 ? Theme.color('#101d27', backend.lightTheme) : Theme.color('#0c1821', backend.lightTheme)
                            RowLayout {
                                anchors.fill: parent; spacing: 5
                                ConsoleButton { text: String(eqrow.index+1); Layout.preferredWidth: 26; implicitHeight: 24; onClicked: root.bandSelected(eqrow.index) }
                                Label { text: eqrow.f.kind; Layout.fillWidth: true; font.pixelSize: 11; elide: Text.ElideRight; MouseArea { anchors.fill: parent; onClicked: root.bandSelected(eqrow.index) } }
                                NumberField { number: eqrow.f.frequency; minimum: backend.options.frequencyMin; maximum: backend.options.frequencyMax; decimals: 1; step: 1; fieldHeight: 23; Layout.preferredWidth: 105; onCommitted: value => backend.edit(backend.selected,'filters.frequency',value,eqrow.index) }
                                NumberField { number: eqrow.f.gain; minimum: -12; maximum: 12; decimals: 1; fieldHeight: 23; Layout.preferredWidth: 75; onCommitted: value => backend.edit(backend.selected,'filters.gain',value,eqrow.index) }
                                NumberField { number: eqrow.f.q; minimum: .4; maximum: 128; decimals: 2; fieldHeight: 23; Layout.preferredWidth: 65; onCommitted: value => backend.edit(backend.selected,'filters.q',value,eqrow.index) }
                                ConsoleCheck { accent: [Theme.color('#38aeff', backend.lightTheme),Theme.color('#48e77c', backend.lightTheme),Theme.color('#ff6774', backend.lightTheme),Theme.color('#c66cf5', backend.lightTheme),Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme)][eqrow.index]; checked: eqrow.f.enabled; Layout.preferredWidth: 36; onClicked: backend.edit(backend.selected,'filters.enabled',checked,eqrow.index) }
                            }
                        }
                    }
                }
            }
        }
    }
}
