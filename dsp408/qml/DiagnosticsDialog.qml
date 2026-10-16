import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: rootConnection
    parent: Overlay.overlay
    FirTrialDialog { id: firTrial }
    signal presetPreviewRequested()
    signal prsReviewRequested()
    objectName: 'diagnostics_dialog'; title: 'DIAGNOSTICS'
    width: 720; height: Math.min(680,parent.height-36); modal: true; standardButtons: Dialog.Close

    contentItem: AdaptiveScrollView {
        objectName: 'connection_scroll'
      id: scroll; clip: true; contentWidth: availableWidth
      ColumnLayout {
        width: scroll.availableWidth; spacing: 12
        Label { text: backend.connectionLabel; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true }
        Label { text: 'USB · FIR408 V0115P'; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true }
        Label { text: 'Close the original editor. USB Control enables channel parameters and confirmed loading of stored P01–P19 presets. Each preset operation asks for confirmation and checks its full parameter readback. '+(backend.usbPresetStoreAuthorized?'Store and naming enabled; ':'Store and naming await authorization; ')+'FIR uploads, firmware and Link stay locked.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#c2d4df', backend.lightTheme) }
        RowLayout {
            ConsoleButton { objectName: 'connect_usb'; text: backend.usbReadActive?'Disconnect USB':'Connect USB · read'; onClicked: backend.usbReadActive?backend.disconnectUsbRead():backend.connectUsbRead() }
            ConsoleButton { objectName: 'connect_usb_control'; text: 'Connect USB · Control'; enabled: !backend.usbReadActive; emphasized: true; onClicked: backend.connectUsbControl() }
            ConsoleButton { objectName: 'export_usb_read'; text: 'Export USB readback…'; enabled: backend.usbReadbackAvailable; onClicked: backend.exportUsbRead() }
        }
        RowLayout {
            ConsoleButton { objectName: 'connect_usb_fir_read'; text: 'Connect USB · full FIR read'; enabled: !backend.usbReadActive; onClicked: backend.connectUsbFirRead() }
            ConsoleButton { objectName: 'export_usb_prs'; text: 'Export DSP snapshot .prs…'; enabled: backend.usbPrsSnapshotAvailable; onClicked: backend.exportUsbPrs() }
        }
        Label { visible: backend.usbFirMode || backend.usbFirReport.complete===true; text: backend.usbFirSummary; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#92c9df', backend.lightTheme) }
        Label { visible: backend.usbFirJournal.length>0; text: 'FIR read journal: '+backend.usbFirJournal; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 11 }
        Label { text: 'Full FIR read is a separate read-only test: current bank0,1261 blocks,65536 raw bytes. Export USB readback includes the bank after completion. No FIR upload, preset Store or Recall.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 11 }
        RowLayout {
            ConsoleButton { objectName: 'connect_usb_preset_preview'; text: 'Preset staging · blocked'; enabled: backend.usbPresetPreviewAvailable && !backend.usbReadActive; onClicked: backend.connectUsbPresetPreview() }
            ConsoleButton { objectName: 'export_usb_preset_preview'; text: 'Export P02 preview…'; enabled: backend.usbPresetPreview.complete===true; onClicked: backend.exportUsbPresetPreview() }
            ConsoleButton { objectName: 'show_usb_preset_preview'; text: 'View P02…'; enabled: backend.usbPresetPreview.complete===true; onClicked: rootConnection.presetPreviewRequested() }
        }
        Label { visible: !backend.usbPresetPreviewAvailable; text: backend.usbPresetPreviewBlockReason; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#e2bd72', backend.lightTheme); font.pixelSize: 11 }
        ConsoleButton { objectName: 'connect_usb_eeprom_read'; text: 'Connect USB · read P02 EEPROM'; enabled: backend.usbEepromReadAvailable && !backend.usbReadActive; onClicked: backend.connectUsbEepromRead() }
        Label { visible: !backend.usbEepromReadAvailable; text: backend.usbEepromReadBlockReason; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#e2bd72', backend.lightTheme); font.pixelSize: 11 }
        Label { visible: backend.usbPresetPreviewMode || backend.usbPresetPreview.complete===true; text: backend.usbPresetPreview.complete===true?'Stored P02 snapshot ready · active preset and current raw state unchanged':'Reading stored P02 parameters directly from EEPROM · no staging'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#92c9df', backend.lightTheme) }
        Label { visible: backend.usbPresetPreviewJournal.length>0; text: 'P02 journal: '+backend.usbPresetPreviewJournal; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 11 }
        ConsoleButton { objectName: 'connect_usb_preset_trial'; text: 'P19 · Store / Recall trial…'; enabled: backend.usbPresetTrialAvailable && !backend.usbReadActive; onClicked: presetTrialConfirm.open() }
        Label { visible: !backend.usbPresetTrialAvailable; text: backend.usbPresetTrialBlockReason; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#e2bd72', backend.lightTheme); font.pixelSize: 11 }
        Label { visible: backend.usbPresetTrialResult.complete===true; text: 'Last P19 trial verified · ended on P02 · parameters and raw FIR banks checked'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#43d782', backend.lightTheme) }
        Label { visible: backend.usbPresetTrialJournal.length>0; text: 'Preset trial journal: '+backend.usbPresetTrialJournal; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 10 }
        Label { visible: backend.usbControlMode; text: backend.usbControlPending?'Requested values · background verification pending':backend.usbControlReady?'Controls enabled · EXE/MCU verification mode':'Synchronizing / controls locked'; color: backend.usbControlPending?Theme.color('#e8b961', backend.lightTheme):Theme.color('#43d782', backend.lightTheme); wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Label { visible: backend.usbControlMode; text: 'User-run journals confirm sampled readbacks for all ordinary command families; audio and EEPROM persistence remain unverified. Fader movements are coalesced; readback runs in the background. Disconnect keeps DSP settings. A mismatch stops the connection without retry or restore.'; color: Theme.color('#c3a46e', backend.lightTheme); wrapMode: Text.WordWrap; Layout.fillWidth: true }
        Label { visible: backend.usbControlJournal.length>0; text: 'Control journal: '+backend.usbControlJournal; color: Theme.color('#9ab5c6', backend.lightTheme); wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
        Label { visible: backend.usbGainMode; text: backend.usbGainBusy?'Reading back…':backend.usbGainReady?'IN A gain enabled':backend.usbReadConnected?'Gain locked · baseline differs':'Synchronizing…'; color: backend.usbGainReady?Theme.color('#43d782', backend.lightTheme):Theme.color('#e8b961', backend.lightTheme); font.pixelSize: 11 }
        RowLayout {
            visible: backend.usbGainMode
            ConsoleButton { objectName: 'usb_gain_minus1'; text: 'IN A -1 dB'; enabled: backend.usbGainReady; onClicked: backend.requestUsbGain(-1) }
            ConsoleButton { objectName: 'usb_gain_zero'; text: 'IN A 0 dB'; enabled: backend.usbGainReady; onClicked: backend.requestUsbGain(0) }
            Label { text: 'Confirmed: '+backend.channel(0).gain.toFixed(1)+' dB'; color: Theme.color('#c2d4df', backend.lightTheme) }
        }
        Label { visible: backend.usbGainJournal.length>0; text: 'Write journal: '+backend.usbGainJournal; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 10 }
        Label { visible: backend.usbGainMode; text: 'Only the verified configuration and self-only Link masks permit writes. Full readback confirms every change. A disconnect keeps the last confirmed gain in the DSP; it does not restore 0 dB automatically.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#c3a46e', backend.lightTheme); font.pixelSize: 11 }
        Label { objectName: 'usb_read_status'; text: backend.usbStatus; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#c2d4df', backend.lightTheme) }
        Label { text: 'USB read requires optional requirements-usb.txt. FIR408 V0115P startup and level reads were checked against your journals. Default read and Control permit captured FIR blocks; full FIR read separately permits all bank0 blocks. Other firmware remains unsupported.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme); font.pixelSize: 11 }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.color('#365361', backend.lightTheme) }
        RowLayout {
            Layout.fillWidth: true
            Label { text: 'Ethernet target (local setting)'; color: Theme.color('#9ab5c6', backend.lightTheme) }
            TextField { objectName: 'connection_ip'; text: backend.settings.ip; Layout.fillWidth: true; selectByMouse: true; onEditingFinished: backend.setting('ip',text) }
        }
        Label { text: 'Ethernet remains disabled: no exact-device Ethernet capture yet. Editor TCP default: 9761.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#9ab5c6', backend.lightTheme) }
        RowLayout {
            ConsoleButton { objectName: 'inspect_wire_log'; text: 'Inspect local wire log…'; onClicked: backend.inspectWireLog() }
            ConsoleButton { objectName: 'connect_ethernet'; text: 'Connect Ethernet'; enabled: false }
        }
        Label { text: 'Import a reassembled raw .bin stream or whitespace-separated .hex. No PCAP import, USB report assumptions or device commands.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11; color: Theme.color('#7290a2', backend.lightTheme) }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.color('#365361', backend.lightTheme) }
        Label { text: 'LOCAL SOURCE TEST'; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true }
        RowLayout {
            ConsoleButton { objectName: 'review_prs_import'; text: backend.usbReadActive?'Review PRS import…':'Compare PRS…'; enabled: backend.prsActive || backend.usbPresetRecallAvailable; onClicked: {if(backend.choosePrsImportReview())rootConnection.prsReviewRequested()} }
            Label { text: backend.usbReadActive?'Compare parameters with USB readback. Full FIR preflight runs only after approved import confirmation.':'Compare with the loaded offline PRS.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#9ab5c6', backend.lightTheme) }
        }
        RowLayout {
            ConsoleButton { objectName: 'review_fir_trial'; text: 'Review IN A FIR trial…'; enabled: backend.usbPresetRecallAvailable; onClicked: {if(backend.reviewUsbFirTrial())firTrial.open()} }
            Label { text: backend.usbFirTrialAuthorized?'Separate manual IN A identity256 trial. Full FIR preflight and confirmation required.':'Numeric FIR trial prepared; awaits separate authorization.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#9ab5c6', backend.lightTheme) }
        }
        Label { text: 'Edit the existing controls to build source-profile packets in memory. A local document receives their byte fields; meters remain empty. This does not connect to or emulate DSP audio processing.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Theme.color('#c2d4df', backend.lightTheme) }
        RowLayout {
            ConsoleButton { objectName: 'start_local_protocol'; text: backend.localProtocolActive?'Stop local test':'Start local test'; enabled: !backend.usbReadActive; onClicked: backend.setLocalProtocol(!backend.localProtocolActive) }
            ConsoleButton { objectName: 'read_local_source'; text: 'Read local state'; enabled: backend.localProtocolActive; onClicked: backend.readLocalSource() }
            ConsoleButton { objectName: 'export_source_journal'; text: 'Export packet journal…'; onClicked: backend.exportSourceJournal() }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: localStatus.implicitHeight+20; color: Theme.color('#08151d', backend.lightTheme); radius: 5; border.color: Theme.color('#2c414e', backend.lightTheme)
            Label { id: localStatus; objectName: 'source_status'; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; text: backend.sourceStatus; wrapMode: Text.WordWrap; color: Theme.color('#c2d4df', backend.lightTheme) }
        }
        RowLayout {
            Label { text: 'Explicit state layout'; color: Theme.color('#9ab5c6', backend.lightTheme) }
            ComboBox { id: sourceLayout; objectName: 'source_layout'; model: ['common-prefix1556','editor1572']; Layout.fillWidth: true }
            ConsoleButton { objectName: 'import_source_state'; text: 'Import state…'; enabled: !backend.usbReadActive; onClicked: backend.importSourceState(sourceLayout.currentText) }
        }
        Label { text: 'Import assembled raw .bin configuration. Known values enter the UI; unsupported fields remain raw and are listed in the journal. Unknown co-fields are preserved when planning compound commands.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11; color: Theme.color('#7290a2', backend.lightTheme) }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: summary.implicitHeight+24; color: Theme.color('#08151d', backend.lightTheme); radius: 5; border.color: Theme.color('#2c414e', backend.lightTheme)
            Label { id: summary; objectName: 'wire_summary'; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; text: backend.wireSummary; wrapMode: Text.WordWrap; color: Theme.color('#c2d4df', backend.lightTheme) }
        }
        Label { text: 'USB Control: channel parameters and confirmed preset Recall'+(backend.usbPresetStoreAuthorized?' / Store.':'. Store awaits authorization.')+' Full FIR read remains separate. Ethernet, FIR uploads and firmware updates stay locked.'; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11; color: Theme.color('#c3a46e', backend.lightTheme) }
        ConsoleButton { objectName: 'connect_usb_gain'; text: 'Legacy diagnostic · IN A -1 / 0 dB'; enabled: !backend.usbReadActive; onClicked: backend.connectUsbGain() }
      }
    }
    ConsoleDialog {
        id: presetTrialConfirm
        objectName: 'preset_trial_confirm'
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(560,parent.width-48); height: Math.min(430,parent.height-48); modal: true
        title: 'CONFIRM P19 PRESET TRIAL'
        standardButtons: Dialog.Ok | Dialog.Cancel

        contentItem: Label {
            objectName: 'preset_trial_scope'; wrapMode: Text.WordWrap; color: Theme.color('#d0e3ed', backend.lightTheme)
            text: 'Close the original editor. This writes the current DSP configuration and FIR into empty P19, briefly changes IN A to -1 dB, recalls P19 to verify restoration, then returns to P02. P19 remains stored. Fresh parameters, catalog and full FIR banks are checked. A nonempty P19 or different baseline refuses before writing. Failure stops without retry or automatic repair. Allow about 1–2 minutes. Run this approved trial?'
        }
        onAccepted: backend.connectUsbPresetTrial()
    }
}
