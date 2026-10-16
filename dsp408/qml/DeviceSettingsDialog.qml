import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: dialog; objectName: 'processor_settings_dialog'; title: 'Processor IP / Device ID'
    width: Math.min(550,parent.width-40)
    property string pendingKind: ''
    property var pendingValue: null
    property string before: ''
    property string observedIp: backend.deviceSettings.ip || ''
    onObservedIpChanged: processorIp.text=observedIp
    onOpened: {processorIp.text=observedIp;if(backend.utilitiesAvailable)backend.readDeviceSettings()}
    contentItem: ColumnLayout {
        spacing: 12
        Label { text: backend.deviceSettings.known?'Processor: '+backend.deviceSettings.ip+' · Connection ID '+backend.deviceSettings.connection_device_id:'Connect in Control mode to read processor settings.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#29c6e8',backend.lightTheme) }
        RowLayout {
            Layout.fillWidth: true
            Label { text: 'Connection ID'; Layout.preferredWidth: 100 }
            Label { objectName: 'processor_device_id'; text: backend.deviceSettings.known?backend.deviceSettings.connection_device_id:'—'; Layout.fillWidth: true }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: 'Processor IPv4'; Layout.preferredWidth: 100 }
            TextField { id: processorIp; objectName: 'processor_ip'; Layout.fillWidth: true; maximumLength: 15; selectByMouse: true; enabled: backend.deviceSettings.writable && backend.activeTransport==='usb' && backend.utilitiesAvailable && !backend.editingLocked }
            ConsoleButton { objectName: 'processor_ip_apply'; text: 'Apply IP…'; enabled: backend.activeTransport==='usb' && backend.deviceSettings.writable && processorIp.text.trim()!==backend.deviceSettings.ip && backend.utilitiesAvailable && !backend.editingLocked; onClicked: {dialog.pendingKind='device_ip';dialog.pendingValue=processorIp.text;dialog.before=backend.deviceSettingsRaw;confirm.open()} }
        }
        Label { text: 'Change the processor IP over USB with one DSP connected. Disconnect any Ethernet editor first. The PC network settings remain separate.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#95b3c4',backend.lightTheme) }
        Label { text: 'To change the device ID, use the DSP front panel (1–250), then select the same target ID in Connection. Changing the target alone does not renumber the DSP.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#95b3c4',backend.lightTheme) }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            ConsoleButton { objectName: 'processor_settings_read'; text: 'Read'; enabled: backend.utilitiesAvailable; onClicked: backend.readDeviceSettings() }
            ConsoleButton { text: 'Close'; onClicked: dialog.close() }
        }
    }
    ConsoleDialog {
        id: confirm; objectName: 'processor_settings_confirmation'; title: 'Change processor setting?'
        width: Math.min(500,parent.width-40); anchors.centerIn: parent
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: 'Set processor IP to '+dialog.pendingValue+'?'; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'This saves a new Ethernet address in the processor. Keep USB connected until verification finishes. The next Ethernet connection will use the new IP; the device ID stays unchanged.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#c3a46e',backend.lightTheme) }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                ConsoleButton { text: 'Cancel'; onClicked: confirm.close() }
                ConsoleButton { objectName: 'processor_settings_accept'; text: 'Apply'; enabled: backend.utilitiesAvailable && !backend.editingLocked; onClicked: {if(backend.applyDeviceSetting(dialog.pendingKind,dialog.pendingValue,dialog.before))confirm.close()} }
            }
        }
    }
}
