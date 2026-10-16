import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property var draft: ({mode:'BYPASS',window:'HANNING',taps:512,hpf_hz:1000,lpf_hz:4000})
    property string signature: ''
    property bool modified: false
    function refresh() {
        if(!visible)return
        var actual=backend.current.fir
        var next=backend.selected+JSON.stringify(actual)
        if(next===signature)return
        signature=next
        draft={mode:actual.mode,window:actual.window,taps:actual.taps,
            hpf_hz:Math.max(backend.options.firHpMin,Math.min(backend.options.firHpMax,actual.hpf_hz)),
            lpf_hz:Math.max(backend.options.firLpMin,Math.min(backend.options.firLpMax,actual.lpf_hz))}
        modified=false
    }
    function change(key,value) {var copy=Object.assign({},draft);copy[key]=value;draft=copy;modified=true}
    Component.onCompleted: refresh()
    onVisibleChanged: if(visible)refresh()
    Connections { target: backend; function onChanged() {root.refresh()} function onOutputFirReviewReady() {if(root.visible)confirm.open()} }
    spacing: 6
    RowLayout {
        Layout.fillWidth: true
        Label { text: 'FIR CROSSOVER'; font.bold: true; font.pixelSize: 14 }
        Label { text: 'Name'; color: Theme.color('#98b3c5',backend.lightTheme) }
        FirNameField { objectName: 'output_fir_name'; Layout.fillWidth: true }
    }
    RowLayout {
        Layout.fillWidth: true; enabled: backend.usbControlReady
        ComboBox { objectName: 'output_fir_type'; Layout.fillWidth: true; implicitHeight: 30; model: backend.options.fir.slice(0,4); currentIndex: model.indexOf(root.draft.mode); displayText: currentIndex<0?'External FIR (stored)':currentText; onActivated: root.change('mode',model[currentIndex]) }
        ComboBox { objectName: 'output_fir_window'; Layout.fillWidth: true; implicitHeight: 30; enabled: root.draft.mode!=='BYPASS'; model: backend.options.windows; currentIndex: model.indexOf(root.draft.window); onActivated: root.change('window',model[currentIndex]) }
        ComboBox { objectName: 'output_fir_taps'; Layout.preferredWidth: 105; implicitHeight: 30; enabled: root.draft.mode!=='BYPASS'; model: Array.from({length:25},(_,i)=>256+i*32); currentIndex: model.indexOf(root.draft.taps); displayText: currentText+' taps'; onActivated: root.change('taps',model[currentIndex]) }
    }
    RowLayout {
        Layout.fillWidth: true; enabled: backend.usbControlReady
        ParameterFader { label: 'High pass'; controlId: 'output_fir_hp'; Layout.fillWidth: true; enabled: root.draft.mode==='HIGH PASS' || root.draft.mode==='BAND PASS'; number: root.draft.hpf_hz; minimum: backend.options.firHpMin; maximum: backend.options.firHpMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; onCommitted: value=>root.change('hpf_hz',value) }
        ParameterFader { label: 'Low pass'; controlId: 'output_fir_lp'; Layout.fillWidth: true; enabled: root.draft.mode==='LOW PASS' || root.draft.mode==='BAND PASS'; number: root.draft.lpf_hz; minimum: backend.options.firLpMin; maximum: backend.options.firLpMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; onCommitted: value=>root.change('lpf_hz',value) }
    }
    RowLayout {
        Layout.fillWidth: true
        Label { objectName: 'output_fir_draft_status'; text: root.draft.mode==='BYPASS'?'BYPASS · choose a filter type to enable HPF / LPF':root.modified?'Unapplied changes · DSP calculates the filter after Apply.':'Current DSP settings · DSP calculates the filter after Apply.'; color: Theme.color('#91b5c6',backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        ConsoleButton { objectName: 'output_fir_revert'; text: 'Revert'; enabled: root.modified; onClicked: {root.signature='';root.refresh()} }
        ConsoleButton { objectName: 'output_fir_apply'; text: 'Apply crossover…'; emphasized: true; enabled: backend.usbControlReady && root.draft.mode!=='External FIR'; onClicked: {if(backend.reviewOutputFir(root.draft))confirm.open()} }
    }
    ConsoleDialog {
        id: confirm; objectName: 'output_fir_confirmation'; title: (backend.outputFirReview.channel || 'Output')+' · FIR CROSSOVER'
        anchors.centerIn: parent
        width: Math.min(540,parent.width-40)
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: backend.outputFirReview.mode+' · '+backend.outputFirReview.taps+' taps · '+backend.outputFirReview.window; font.bold: true; color: Theme.color('#29c6e8',backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'FIR usage: '+backend.outputFirReview.used+'/4096 taps'; color: Theme.color('#bdd2df',backend.lightTheme); Layout.fillWidth: true }
            Label { text: backend.outputFirReview.replaces_storage?'Apply crossover to '+backend.outputFirReview.channel+'? Previous external FIR coefficients on these channels will be replaced. Storage outside this group is preserved.':'Bypass FIR crossover on '+backend.outputFirReview.channel+'? Stored coefficients remain unchanged.'; color: Theme.color('#bdd2df',backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'Channels are muted temporarily while settings are applied and checked. Keep the DSP connected until completion.'; color: Theme.color('#e2bd72',backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            ConsoleButton { objectName: 'output_fir_cancel'; text: 'Cancel'; focus: true; onClicked: confirm.close() }
            ConsoleButton { objectName: 'output_fir_accept'; text: 'Apply crossover'; enabled: backend.usbControlReady; onClicked: {if(backend.applyOutputFir())confirm.close()} }
        }
    }
}
