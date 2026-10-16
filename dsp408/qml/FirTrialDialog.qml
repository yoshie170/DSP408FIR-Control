import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: root
    objectName: 'fir_trial_confirmation'
    title: 'USB FIR TRIAL · IN A / 256 TAPS'
    width: 560; height: 360; modal: true

    contentItem: ColumnLayout {
        spacing: 12
        Label {
            text: 'Load a fixed identity filter on IN A: coefficient 1.0 followed by 255 zeros. This is the first numeric FIR write trial, not an arbitrary file upload.'
            color: Theme.color('#c2d4df', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap
        }
        Label {
            text: 'Fresh parameters and the complete current FIR bank are read first. An all-FF bank and explicit independent channels are required. All 12 channels are temporarily muted. Only IN A sectors 0/1 are erased, then its coefficients are sent. Full parameters and all 65536 bank bytes are checked before restoring the original Mute states.'
            color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap
        }
        Label {
            text: 'The filter remains in the current configuration. No Store/Recall or automatic repair follows. A failure stops the operation; channels may remain muted. Keep DSP connected until completion.'
            color: Theme.color('#c3a46e', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap
        }
        Label { text: backend.usbFirTrialAuthorized?'This write trial is separately authorized. Run it now?':'Write remains locked pending separate authorization.'; color: Theme.color('#21bce4', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Item { Layout.fillHeight: true }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            ConsoleButton { objectName: 'fir_trial_cancel'; text: 'Cancel'; focus: true; onClicked: root.close() }
            ConsoleButton { objectName: 'fir_trial_accept'; text: 'Run IN A FIR trial'; enabled: backend.usbFirTrialAuthorized && backend.usbPresetRecallAvailable; onClicked: {if(backend.requestUsbFirTrial())root.close()} }
        }
    }
}
