import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: root
    objectName: 'prs_review_dialog'
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(680,parent.width-40)
    height: Math.min(580,parent.height-40)
    modal: true
    title: report.hardware_review?'IMPORT SETTINGS':'COMPARE SETTINGS'
    standardButtons: Dialog.Close
    property var report: backend.prsImportReview

    contentItem: ColumnLayout {
        spacing: 12
        Label { text: root.report.file || ''; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true; Layout.fillWidth: true; elide: Text.ElideMiddle }
        Label { text: root.report.scope || ''; color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { objectName: 'prs_review_summary'; text: root.report.complete?'All parameter differences represented in the local plan.':'Some differences require additional handling.'; color: root.report.complete?Theme.color('#67d4ba', backend.lightTheme):Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { text: (root.report.name_changed?'Configuration name changes.\n':'')+(root.report.fir_different_bytes?'FIR filters will be replaced.':'FIR filters are unchanged.'); color: Theme.color('#bfd5e3', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        ListView {
            objectName: 'prs_review_channels'
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight>height+1
            model: root.report.channels || []
            spacing: 6
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width-14
                height: row.implicitHeight+18
                radius: 4; color: Theme.color('#152a37', backend.lightTheme); border.color: Theme.color('#2d4655', backend.lightTheme)
                ColumnLayout {
                    id: row; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 9
                    Label { text: modelData.channel+' · '+modelData.name; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true }
                    Label { text: modelData.functions; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#bfd5e3', backend.lightTheme) }
                    Label { visible: !!modelData.details; text: modelData.details || ''; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#9ab5c6', backend.lightTheme) }
                }
            }
            Label { visible: parent.count===0; text: 'No channel parameter changes.'; color: Theme.color('#9ab5c6', backend.lightTheme); anchors.centerIn: parent }
        }
        Label { visible: (root.report.blockers || []).length>0; text: (root.report.blockers || []).slice(0,4).join('\n'); color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { visible: (root.report.blockers || []).length>4; text: 'Additional issues: '+Math.max(0,(root.report.blockers || []).length-4); color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true }
        Label { text: backend.usbPrsImportAuthorized && root.report.hardware_review?'Import applies channel settings and FIR, briefly muting all channels. Stored preset slots are unchanged.':'Compare settings without applying them to the processor.'; color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        ConsoleButton { objectName: 'prs_import_confirm_button'; visible: root.report.hardware_review===true; text: 'Import configuration…'; enabled: backend.usbPrsImportAuthorized && backend.usbPresetRecallAvailable && !!root.report.complete; onClicked: prsConfirm.open() }
    }
    ConsoleDialog {
        id: prsConfirm; objectName: 'prs_import_confirmation'; parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(540,parent.width-40); height: 340; modal: true; title: 'Import configuration and FIR?'

        contentItem: Label { text: 'Apply “'+(root.report.file || '')+'” to all 12 DSP channels, including FIR filters?\n\nAll channels will be muted temporarily. The complete configuration and FIR bank are checked before target Mute is applied. If loading fails, reconnect to check the processor before unmuting. No stored preset will be saved or recalled.'; wrapMode: Text.WordWrap; color: Theme.color('#bfd5e3', backend.lightTheme) }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            ConsoleButton { text: 'Cancel'; focus: true; onClicked: prsConfirm.close() }
            ConsoleButton { objectName: 'prs_import_accept'; text: 'Import'; enabled: backend.usbPrsImportAuthorized && backend.usbPresetRecallAvailable; onClicked: {if(backend.requestUsbPrsImport()){prsConfirm.close();root.close()}} }
        }
    }
}
