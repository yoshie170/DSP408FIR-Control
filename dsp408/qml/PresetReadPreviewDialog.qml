import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    objectName: 'stored_preset_preview_dialog'; title: 'STORED P02 · READ PREVIEW'
    width: 650; modal: true; standardButtons: Dialog.Close

    contentItem: ColumnLayout {
        spacing: 8
        Label { text: 'Stored P02 parameters · separate preview · active configuration unchanged'; color: Theme.color('#2ac6e8', backend.lightTheme); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { objectName: 'stored_preset_preview_scope'; text: backend.usbPresetPreview.complete===true?(backend.usbPresetPreview.fir_bank_read===false?'1556 parameter bytes · FIR not read in this session':'1556 parameter bytes + 65536 FIR bank bytes')+' · active slot '+backend.usbPresetPreview.active_slot_before+' preserved':'Preview unavailable'; color: Theme.color('#a9c6d5', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Label { visible: backend.usbPresetPreviewChannels.length===0; text: 'Unrepresented values retained in raw export; numeric preview unavailable'; color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        GridLayout {
            columns: 6; columnSpacing: 14; rowSpacing: 7
            Repeater { model: ['CHANNEL','NAME','GAIN dB','MUTE','DELAY ms','PEQ ON']; Label { required property string modelData; text: modelData; color: Theme.color('#7fb7ce', backend.lightTheme); font.pixelSize: 10 } }
            Repeater {
                model: backend.usbPresetPreviewChannels.length*6
                Label {
                    required property int index
                    property var row: backend.usbPresetPreviewChannels[Math.floor(index/6)]
                    text: !row?'': [row.channel,row.name,row.gain.toFixed(1),row.mute?'ON':'OFF',row.delay_ms.toFixed(2),String(row.enabled_peq)][index%6]
                    color: Theme.color('#deedf7', backend.lightTheme); font.pixelSize: 11
                }
            }
        }
        Label { text: backend.usbPresetPreview.fir_bank_read===false?'Parameter preview only. This window does not Recall or Store P02.':'FIR raw bank preserved; no coefficient upload. This window does not Recall or Store P02.'; color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
    }
}
