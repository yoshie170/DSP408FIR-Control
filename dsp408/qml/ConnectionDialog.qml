import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleDialog {
    id: root
    signal presetPreviewRequested()
    signal diagnosticsRequested()
    signal prsReviewRequested()
    objectName: 'connection_dialog'; title: 'CONNECTION'
    width: Math.min(620,parent.width-40); height: Math.min(440,parent.height-32); modal: true
    property string targetMessage: ''
    readonly property bool ethernet: transport.currentIndex===1
    readonly property bool targetReady: !ethernet || backend.ethernetTargetValid(targetIp.text,targetId.value,'')
    function connect(readOnly) {
        if(ethernet) {
            if(readOnly)backend.connectEthernetRead(targetIp.text,targetId.value,'')
            else backend.connectEthernetControl(targetIp.text,targetId.value,'')
        } else {
            backend.setNetworkTarget(backend.networkTarget.ip,targetId.value)
            if(readOnly)backend.connectUsbRead()
            else backend.connectUsbControl()
        }
    }
    onOpened: {
        targetIp.text=backend.networkTarget.ip;targetId.value=backend.networkTarget.device_id
        if(backend.usbReadActive)transport.currentIndex=backend.activeTransport==='ethernet'?1:0
        targetMessage=''
    }
    standardButtons: Dialog.Close
    contentItem: ColumnLayout {
        spacing: 12
        Label { text: backend.connectionLabel; color: Theme.color('#21bce4', backend.lightTheme); font.bold: true; font.pixelSize: 16 }
        Label { text: 'Choose how to connect. Close any other DSP editor before connecting.'; color: Theme.color('#bdd2df', backend.lightTheme); wrapMode: Text.WordWrap; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Label { text: 'Transport'; color: Theme.color('#95b3c4',backend.lightTheme) }
            ComboBox { id: transport; objectName: 'connection_transport'; model: ['USB','Ethernet']; enabled: !backend.usbReadActive; Layout.fillWidth: true; implicitHeight: 34 }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                visible: root.ethernet
                Layout.fillWidth: true; spacing: 4
                Label { text: 'DSP IP address'; font.pixelSize: 11; color: Theme.color('#95b3c4',backend.lightTheme) }
                TextField { id: targetIp; objectName: 'ethernet_target_ip'; Layout.fillWidth: true; implicitHeight: 32; enabled: !backend.usbReadActive; maximumLength: 15; selectByMouse: true; validator: RegularExpressionValidator { regularExpression: /[0-9.]{0,15}/ } onTextEdited: root.targetMessage='' }
            }
            ColumnLayout {
                spacing: 4
                Label { text: 'DSP ID'; font.pixelSize: 11; color: Theme.color('#95b3c4',backend.lightTheme) }
                SpinBox { id: targetId; objectName: 'ethernet_target_id'; implicitHeight: 32; implicitWidth: 100; from: 1; to: 250; editable: true; enabled: !backend.usbReadActive; onValueModified: root.targetMessage='' }
            }
            ConsoleButton { objectName: 'save_network_target'; text: 'Save target'; Layout.alignment: Qt.AlignBottom; enabled: !backend.usbReadActive && backend.networkTargetValid(targetIp.text,targetId.value); onClicked: root.targetMessage=backend.setEthernetTarget(targetIp.text,targetId.value,'')?'Connection target saved':backend.displayMessage }
        }
        Label { objectName: 'network_target_message'; text: root.targetMessage || (root.ethernet?'Set the PC address in Windows network settings. The app uses Windows routing.':'Choose the ID of the connected processor.'); color: Theme.color('#95b3c4',backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.color('#294451',backend.lightTheme) }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Label { text: 'VU refresh · USB / Ethernet'; color: Theme.color('#bdd2df',backend.lightTheme); Layout.fillWidth: true }
            ComboBox {
                objectName: 'meter_refresh'; implicitHeight: 32; implicitWidth: 155
                model: ['Fast · 100 ms','Standard · 300 ms']; currentIndex: backend.meterPollMs===100?0:1
                onActivated: {backend.setMeterPollMs(currentIndex===0?100:300);currentIndex=Qt.binding(()=>backend.meterPollMs===100?0:1)}
                ToolTip.visible: hovered; ToolTip.text: 'Live level query interval for either transport. Long operations pause meters.'
            }
        }
        Label { objectName: 'usb_connection_summary'; text: backend.connectionError || (backend.usbReadActive?(backend.usbConnectionBusy?'Connecting…':backend.editingLocked?'Processor locked':backend.usbControlReady?'Ready for control':'Read only'):'Not connected'); color: backend.connectionError?Theme.color('#efad67',backend.lightTheme):Theme.color('#95b3c4',backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            ConsoleButton { objectName: 'connection_connect'; text: backend.usbReadActive?'Disconnect':'Connect'; emphasized: true; enabled: backend.usbReadActive || root.targetReady; onClicked: {if(backend.usbReadActive)backend.disconnectUsbRead();else root.connect(false)} }
            ConsoleButton { objectName: 'connection_read_only'; text: 'Read only'; visible: !backend.usbReadActive; enabled: root.targetReady; onClicked: root.connect(true) }
            Item { Layout.fillWidth: true }
        }
        RowLayout {
            visible: backend.developerTools
            ConsoleButton { text: 'Diagnostics…'; onClicked: {root.close();root.diagnosticsRequested()} }
            ConsoleButton { objectName: 'export_usb_read'; text: 'Export session…'; enabled: backend.usbReadbackAvailable; onClicked: backend.exportUsbRead() }
        }
        Item { Layout.fillHeight: true }
    }
}
