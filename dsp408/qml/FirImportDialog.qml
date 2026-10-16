import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: root
    objectName: 'fir_import_confirmation'
    title: (backend.firImportReview.channel || 'Input')+(backend.firImportReview.clear?' · CLEAR FIR':' · FIR')
    width: Math.min(540,parent ? parent.width-40 : 540); height: 370; modal: true

    contentItem: ColumnLayout {
        spacing: 10
        Label { text: backend.firImportReview.file || ''; color: Theme.color('#c2d4df', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { text: backend.firImportReview.clear?'Remove stored coefficients · BYPASS':(backend.firImportReview.count || 0)+' coefficients · '+(backend.firImportReview.bypass?'BYPASS':'ACTIVE'); color: Theme.color('#21bce4', backend.lightTheme); font.pixelSize: 17 }
        Label { text: 'Up to 512 coefficients per input. Available: '+(backend.firImportReview.available || 0)+'. FIR usage: '+(backend.firImportReview.used || 0)+'/4096.'; color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { text: backend.firImportReview.clear?'Erase FIR on '+backend.firImportReview.channel+'? Bypass remains on. A new file is required to reactivate FIR. Storage outside this group is preserved.':backend.firImportReview.upload?'Replace FIR on '+backend.firImportReview.channel+' and activate it? Storage outside this group is preserved.':'Apply this bypass state to '+backend.firImportReview.channel+'?'; color: Theme.color('#c2d4df', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { text: 'All channels are muted temporarily. Keep the DSP connected until loading finishes. If loading fails, reconnect to check the device before unmuting.'; color: Theme.color('#c3a46e', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { visible: !backend.usbInputFirAuthorized; text: 'Prepared and tested offline. Hardware write awaits authorization.'; color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Item { Layout.fillHeight: true }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            ConsoleButton { objectName: 'fir_import_cancel'; text: 'Cancel'; focus: true; onClicked: root.close() }
            ConsoleButton { objectName: 'fir_import_accept'; text: backend.firImportReview.clear?'Clear FIR':'Apply FIR'; enabled: backend.usbInputFirAuthorized && backend.usbInputFirAvailable; onClicked: {if(backend.requestUsbInputFir())root.close()} }
        }
    }
}
