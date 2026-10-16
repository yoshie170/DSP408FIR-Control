import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    FirImportDialog { id: firImport; parent: Overlay.overlay; anchors.centerIn: parent }
    property var coefficients: backend.usbReadActive ? backend.usbInputFirCoefficients : root.currentData.fir.coefficients
    property bool phaseView: false
    property var magnitudeScale: scaleFor(backend.firResponseRange)
    function scaleFor(range) {
        if(range.minimum===undefined || range.maximum===undefined)return {minimum:-1,maximum:1,step:0.5,decimals:1}
        var low=Math.min(0,range.minimum),high=Math.max(0,range.maximum)
        var margin=Math.max(0.01,(high-low)*0.1)
        low-=margin;high+=margin
        if(high-low<0.2){var center=(high+low)/2;low=center-0.1;high=center+0.1}
        var ideal=(high-low)/5,power=Math.pow(10,Math.floor(Math.log(ideal)/Math.LN10))
        var unit=ideal/power,step=(unit<=1?1:unit<=2?2:unit<=5?5:10)*power
        return {minimum:Math.floor(low/step)*step,maximum:Math.ceil(high/step)*step,
                step:step,decimals:Math.max(0,-Math.floor(Math.log(step)/Math.LN10))}
    }
    property var currentData: backend.current
    function refreshView() {
        currentData=backend.current
        
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: if(visible)refreshView()
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} function onFirImportReady() {if(root.visible)firImport.open()} }
    property bool embedded: false
    property bool input: backend.selected<4
    property bool outputMode: root.currentData.crossover_mode==='FIR'
    property bool external: root.currentData.fir.mode==='External FIR'
    property bool rawPrsFir: backend.prsActive && root.currentData.fir.coefficients.length===0
    property bool canImport: input || (outputMode && external)
    spacing: root.embedded?6:10
    Label { objectName: 'fir_bank_read_status'; visible: backend.developerTools && backend.usbReadActive && backend.usbFirReport.complete===true; text: backend.usbFirSummary; color: Theme.color('#9bcfe0', backend.lightTheme); font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Label { text: root.input?'INPUT FIR · EXTERNAL COEFFICIENTS':'FIR CROSSOVER · DESIGN / EXTERNAL'; font.pixelSize: root.embedded?14:17; font.bold: true }
    Label { visible: backend.developerTools; text: root.rawPrsFir?'Original PRS FIR banks retained verbatim · coefficients not decoded':root.input || root.external ? (backend.usbReadActive?(root.input && backend.usbControlMode?'USB input FIR · quick bypass · confirmed import / Clear':'USB FIR storage preview · writes locked'):'Local DEMO only · no device upload') : (backend.usbReadActive?'DSP settings · approximate design preview · active coefficients not read':'Approximate FIR design preview · local DEMO · no device upload'); color: Theme.color('#88aabb', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    RowLayout {
        Layout.fillWidth: true
        ConsoleCheck { objectName: 'fir_output_mode'; visible: !root.input && !root.embedded; text: 'Use FIR crossover mode'; checked: root.outputMode; onClicked: backend.edit(backend.selected,'crossover_mode',checked?'FIR':'IIR',-1) }
        ConsoleCheck { objectName: root.embedded?'xover_fir_bypass':'fir_bypass'; text: 'FIR bypass'; checked: root.currentData.fir.bypass; enabled: !backend.usbReadActive || (root.input && backend.usbFirBypassAvailable); onClicked: {if(backend.usbReadActive){backend.requestUsbFirBypass(checked);checked=Qt.binding(()=>root.currentData.fir.bypass)}else backend.edit(backend.selected,'fir.bypass',checked,-1)} ToolTip.visible: hovered; ToolTip.text: 'Bypass processing; keep FIR coefficients unchanged.' }
    }
    RowLayout {
        visible: !root.input; enabled: root.outputMode; Layout.fillWidth: true
        ColumnLayout {
            Layout.fillWidth: true
            Label { text: root.currentData.fir.mode==='BYPASS'?'TYPE · select a filter to enable frequency controls':'TYPE'; color: Theme.color('#98b3c5', backend.lightTheme); font.pixelSize: 10 }
            ComboBox { objectName: root.embedded?'xover_fir_type':'fir_type'; Layout.fillWidth: true; model: backend.options.fir; currentIndex: model.indexOf(root.currentData.fir.mode); onActivated: backend.edit(backend.selected,'fir.mode',model[currentIndex],-1) }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: !root.external
            Label { text: 'WINDOW · DESIGN SETTING'; color: Theme.color('#98b3c5', backend.lightTheme); font.pixelSize: 10 }
            ComboBox { Layout.fillWidth: true; model: backend.options.windows; currentIndex: model.indexOf(root.currentData.fir.window); onActivated: backend.edit(backend.selected,'fir.window',model[currentIndex],-1) }
        }
        ColumnLayout {
            Layout.preferredWidth: 110; visible: !root.external
            Label { text: 'DESIGN TAPS'; color: Theme.color('#98b3c5', backend.lightTheme); font.pixelSize: 10 }
            ComboBox { Layout.fillWidth: true; model: Array.from({length:25},(_,i)=>256+i*32); currentIndex: model.indexOf(root.currentData.fir.taps); onActivated: backend.edit(backend.selected,'fir.taps',model[currentIndex],-1) }
        }
    }
    RowLayout {
        visible: !root.input && !root.external; enabled: root.outputMode && root.currentData.fir.mode!=='BYPASS'; Layout.fillWidth: true
        ParameterFader { label: 'High pass'; controlId: 'fir_highpass'; number: root.currentData.fir.hpf_hz; minimum: backend.options.firHpMin; maximum: backend.options.firHpMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; hint: 'FIR high-pass design: '+minimum.toFixed(1)+'–'+maximum.toFixed(1)+' Hz; imported settings preserved'; Layout.fillWidth: true; onCommitted: value => backend.edit(backend.selected,'fir.hpf_hz',value,-1) }
        ParameterFader { label: 'Low pass'; controlId: 'fir_lowpass'; number: root.currentData.fir.lpf_hz; minimum: backend.options.firLpMin; maximum: backend.options.firLpMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; hint: 'FIR low-pass design: '+minimum.toFixed(1)+'–'+maximum.toFixed(1)+' Hz; imported settings preserved'; Layout.fillWidth: true; onCommitted: value => backend.edit(backend.selected,'fir.lpf_hz',value,-1) }
    }
    Label { visible: !root.input && !root.canImport; text: root.outputMode?'To import output coefficients, choose TYPE: External FIR.':'Output FIR controls become available in FIR crossover mode.'; color: Theme.color('#e2bd72', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    RowLayout {
        Layout.fillWidth: true
        ConsoleButton { objectName: root.embedded?'xover_fir_import':'fir_import'; text: backend.usbReadActive?'Load input FIR…':root.input?'Import input CSV / TXT':'Import External FIR · OUT'; visible: root.canImport; enabled: !backend.usbReadActive || backend.usbInputFirAvailable; onClicked: {if(backend.usbReadActive){if(backend.chooseUsbInputFir())firImport.open()}else backend.importFIR()} }
        ConsoleButton { objectName: 'fir_clear'; text: backend.usbReadActive?'Clear FIR…':'Clear local FIR'; visible: root.input || !backend.usbReadActive; enabled: backend.usbReadActive?backend.usbInputFirAvailable && (root.coefficients.length>0 || backend.activeTransport==='ethernet'):root.currentData.fir.coefficients.length>0; onClicked: {if(backend.usbReadActive){if(backend.reviewUsbClearFir())firImport.open()}else backend.clearFIR()} }
    }
    Label { objectName: 'fir_coefficient_status'; visible: root.input || root.external; text: backend.usbReadActive?(root.coefficients.length?root.coefficients.length+' coefficients · '+(root.currentData.fir.bypass?'BYPASS':'ACTIVE'):backend.ethernetFirPreview.mode?'No finite input FIR coefficients available in this channel':'No finite input FIR in current storage; reconnect USB Control if the bank is unavailable'):root.rawPrsFir?'PRS FIR bank preserved; local coefficient preview unavailable':root.currentData.fir.path || (root.currentData.fir.coefficients.length?'Coefficients stored in configuration':'No external coefficients'); color: Theme.color('#a9c2d0', backend.lightTheme); Layout.fillWidth: true; elide: Text.ElideMiddle }
    RowLayout {
        Layout.fillWidth: true
        Label { text: 'Filter name'; color: Theme.color('#98b3c5', backend.lightTheme) }
        FirNameField { objectName: root.embedded?'xover_fir_name':'fir_name'; Layout.fillWidth: true }
    }
    Label { visible: (root.input || root.external) && !backend.usbReadActive && !root.rawPrsFir; text: root.currentData.fir.coefficients.length+' coefficients · '+(root.input?'max 512 taps per input':'OUT max 1024'); color: Theme.color('#2bc7e7', backend.lightTheme); font.pixelSize: 11 }
    RowLayout {
        visible: !root.embedded && root.coefficients.length>0 && !root.rawPrsFir
        Layout.fillWidth: true
        ConsoleButton { objectName: 'fir_magnitude'; text: 'Magnitude'; checkable: true; checked: !root.phaseView; onClicked: root.phaseView=false }
        ConsoleButton { objectName: 'fir_phase'; text: 'Phase'; checkable: true; checked: root.phaseView; onClicked: root.phaseView=true }
        Label { text: 'Stored coefficients · 96 kHz preview · bypass ignored'+(root.phaseView?' · phase wrapped ±180°':''); color: Theme.color('#7c9bad', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
    Label { objectName: 'fir_magnitude_range'; visible: !root.embedded && root.coefficients.length>0 && !root.rawPrsFir; text: 'Magnitude range: '+Number(backend.firResponseRange.minimum || 0).toFixed(3)+' … '+Number(backend.firResponseRange.maximum || 0).toFixed(3)+' dB. A flat magnitude may still change phase or delay.'; color: Theme.color('#9cb7c7', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    ResponsePlot {
        objectName: 'fir_response_plot'; visible: !root.embedded && root.coefficients.length>0 && !root.rawPrsFir; Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredHeight: 170; Layout.minimumHeight: 150; Layout.maximumHeight: 170; curveData: root.phaseView?backend.firPhaseCurve:backend.firCurve; phase: root.phaseView; showBands: false; magnitudeMinimum: root.magnitudeScale.minimum; magnitudeMaximum: root.magnitudeScale.maximum; magnitudeStep: root.magnitudeScale.step; magnitudeDecimals: root.magnitudeScale.decimals
        Rectangle {
            objectName: 'fir_bypass_overlay'; anchors.fill: parent; z: 10; radius: 6
            visible: root.currentData.fir.bypass; color: Theme.color('#c409151c', backend.lightTheme)
            Label {
                objectName: 'fir_bypass_label'; anchors.centerIn: parent; text: 'BYPASS'
                font.pixelSize: Math.min(56,parent.width/7,parent.height*.3)
                font.bold: true; font.letterSpacing: 5; color: Theme.color('#f0c26e', backend.lightTheme)
                Accessible.name: 'FIR bypassed'
            }
        }
    }
    AdaptiveScrollView {
        objectName: 'fir_coefficients_scroll'
        visible: !root.embedded && root.coefficients.length>0 && !root.rawPrsFir
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredHeight: 100; Layout.minimumHeight: 60; Layout.maximumHeight: 100; clip: true
        TextArea { readOnly: true; selectByMouse: true; text: root.coefficients.slice(0,64).map((v,i)=>i+': '+v.toPrecision(8)).join('\n'); placeholderText: 'First 64 coefficients'; color: Theme.color('#a9c2d0', backend.lightTheme); background: Rectangle { color: Theme.color('#0b1921', backend.lightTheme) } }
    }
    Label { visible: root.input || root.external; text: root.input?'CSV / TXT · max 512 taps per input':'CSV / TXT · coefficient list'; color: Theme.color('#7495a9', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Item { visible: !root.embedded; Layout.fillHeight: true }
}
