import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    spacing: 6
    property var sources: ['ANALOG INPUT','PINK NOISE','WHITE NOISE','SINE']
    property string chosenSource: backend.generatorState.source || ''
    property real chosenFrequency: backend.generatorState.frequency || 1000
    property bool canApply: !backend.editingLocked && !backend.utilityBusy && (!backend.usbReadActive || backend.utilitiesAvailable)
    property bool canApplyInput: !backend.editingLocked && !backend.utilityBusy && (!backend.usbReadActive || backend.inputSelectionAvailable && backend.inputSelectionState.known)
    property string chosenInput: 'ANALOG'
    property string observedInput: backend.inputSelectionState.source || ''
    onObservedInputChanged: chosenInput=observedInput || 'ANALOG'
    Component.onCompleted: chosenInput=observedInput || 'ANALOG'
    Label { objectName: 'setup_read_status'; visible: backend.editingLocked; text: backend.usbReadActive?'Processor locked':'Editing locked'; color: Theme.color('#93b7c9', backend.lightTheme); Layout.fillWidth: true }

    Rectangle {
        Layout.fillWidth: true; implicitHeight: bankLayout.implicitHeight+20
        color: Theme.color('#10202a', backend.lightTheme); border.color: Theme.color('#294451', backend.lightTheme); radius: 6
        RowLayout {
            id: bankLayout; anchors.fill: parent; anchors.margins: 10; spacing: 6
            Label { text: 'PRESET BANK BACKUP'; font.pixelSize: 14; font.bold: true; Layout.fillWidth: true }
            ConsoleButton { objectName: 'bank_backup_choose'; text: 'Back up bank…'; implicitHeight: 30; enabled: backend.bankBackupAvailable; onClicked: {if(backend.chooseBankBackup())bankConfirm.open()} ToolTip.visible: hovered; ToolTip.text: 'P01–P19 and current configuration, including FIR. Read only.' }
            ConsoleButton { objectName: 'bank_restore_choose'; text: 'Restore bank…'; implicitHeight: 30; enabled: backend.bankBackupAvailable; onClicked: {if(backend.chooseBankRestore())restoreConfirm.open()} }
            ConsoleButton { objectName: 'bank_backup_extract'; text: 'Extract backup…'; implicitHeight: 30; enabled: !backend.usbPresetRecallBusy; onClicked: backend.extractBankBackup(); ToolTip.visible: hovered; ToolTip.text: 'Verify a backup and extract individual .prs files into a new folder.' }
        }
    }
    Connections { target: backend; function onBankBackupReady(){bankConfirm.open()} function onBankRestoreReady(){restoreConfirm.open()} }
    ConsoleDialog {
        id: restoreConfirm; objectName: 'bank_restore_confirmation'; title: 'Replace saved preset bank?'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(550,parent.width-40)
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: 'Replace P01–P19: '+(backend.bankRestoreReview.count || 0)+' stored presets, '+(backend.bankRestoreReview.empty || 0)+' empty slots, including FIR and preset names.'; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'A complete backup is saved before writing. The active configuration stays unchanged. Keep the DSP connected and do not recall presets on the processor during restoration. A failed operation can leave part of the saved bank updated.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#c3a46e',backend.lightTheme) }
            Label { text: backend.bankRestoreReview.path || ''; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                ConsoleButton { text: 'Cancel'; onClicked: restoreConfirm.close() }
                ConsoleButton { objectName: 'bank_restore_accept'; text: 'Replace bank'; enabled: backend.bankBackupAvailable; onClicked: {if(backend.applyBankRestore())restoreConfirm.close()} }
            }
        }
    }
    ConsoleDialog {
        id: bankConfirm; objectName: 'bank_backup_confirmation'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(530,parent.width-40)
        title: 'Back up preset bank?'; modal: true
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: (backend.bankBackupReview.count || 0)+' stored presets and the current configuration, with complete FIR banks.'; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'The active preset and signal settings stay unchanged. Large banks can take several minutes. Keep the processor connected until the backup finishes.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#95b3c4',backend.lightTheme) }
            Label { text: backend.bankBackupReview.path || ''; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.color('#29c6e8',backend.lightTheme) }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                ConsoleButton { text: 'Cancel'; onClicked: bankConfirm.close() }
                ConsoleButton { objectName: 'bank_backup_accept'; text: 'Back up'; enabled: backend.bankBackupAvailable; onClicked: {if(backend.applyBankBackup())bankConfirm.close()} }
            }
        }
    }
    Rectangle {
        Layout.fillWidth: true; implicitHeight: inputLayout.implicitHeight+20
        color: Theme.color('#10202a', backend.lightTheme); border.color: Theme.color('#294451', backend.lightTheme); radius: 6
        RowLayout {
            id: inputLayout; anchors.fill: parent; anchors.margins: 10; spacing: 6
            ColumnLayout {
                spacing: 2
                Label { text: 'INPUT SOURCE · A–D'; font.pixelSize: 15; font.bold: true; Layout.fillWidth: true }
                Label { objectName: 'input_source_readback'; text: backend.inputSelectionState.known?backend.inputSelectionState.source:'Not read'; color: Theme.color('#95b3c4', backend.lightTheme) }
            }
                ComboBox { objectName: 'input_source_choice'; Layout.fillWidth: true; enabled: root.canApplyInput; model: ['Analog','AES / EBU']; currentIndex: root.chosenInput==='ANALOG'?0:1; onActivated: root.chosenInput=currentIndex===0?'ANALOG':'AES / EBU' }
                ConsoleButton { objectName: 'apply_input_source'; text: 'Apply'; enabled: root.canApplyInput; onClicked: {if(backend.usbReadActive)inputConfirm.open();else backend.applyInputSelection(root.chosenInput)} }
        }
    }

    Rectangle {
        Layout.fillWidth: true; implicitHeight: appearanceLayout.implicitHeight+24
        color: Theme.color('#10202a', backend.lightTheme); border.color: Theme.color('#294451', backend.lightTheme); radius: 6
        ColumnLayout {
            id: appearanceLayout; anchors.fill: parent; anchors.margins: 12; spacing: 6
            RowLayout {
                Layout.fillWidth: true
                Label { text: 'APPEARANCE'; font.pixelSize: 15; font.bold: true; Layout.fillWidth: true }
                ComboBox {
                    objectName: 'appearance_theme'; Layout.preferredWidth: 200; implicitHeight: 32
                    model: ['Dark','Light']; currentIndex: backend.lightTheme?1:0
                    onActivated: {backend.setTheme(currentIndex===1?'light':'dark');currentIndex=Qt.binding(()=>backend.lightTheme?1:0)}
                }
            }
            ConsoleCheck {
                objectName: 'dynamics_display'; text: 'Dynamics IN / OUT / Gain Reduction'; Layout.fillWidth: true
                checked: backend.dynamicsDisplayEnabled
                onClicked: {
                    backend.setDynamicsDisplay(checked)
                    checked=Qt.binding(function(){return backend.dynamicsDisplayEnabled})
                }
            }
            Label {
                objectName: 'dynamics_display_info'; Layout.fillWidth: true; wrapMode: Text.WordWrap
                font.pixelSize: 10; color: Theme.color('#95b3c4', backend.lightTheme)
                text: 'IN/OUT, Gain Reduction and dot are calculated from the channel level and static curve. Internal tap, detector EQ and attack/release are unmeasured. CHANNEL is the DSP reading.'
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true; implicitHeight: generatorLayout.implicitHeight+24
        color: Theme.color('#10202a', backend.lightTheme); border.color: Theme.color('#294451', backend.lightTheme); radius: 6
        ColumnLayout {
            id: generatorLayout; anchors.fill: parent; anchors.margins: 12; spacing: 8
            Label { text: 'SIGNAL GENERATOR'; font.pixelSize: 15; font.bold: true }
            Label { text: backend.usbReadActive && !backend.generatorState.known ? 'Choose a source to apply.' : (backend.usbReadActive?'Last applied: ':'Source: ')+(backend.generatorState.source || '—'); color: Theme.color('#95b3c4', backend.lightTheme) }
            RowLayout {
                Layout.fillWidth: true
                ComboBox {
                    objectName: 'generator_source'; Layout.fillWidth: true
                    model: ['Analog input','Pink noise','White noise','Sine wave']
                    displayText: currentIndex<0?'Choose source…':currentText
                    currentIndex: root.sources.indexOf(root.chosenSource)
                    enabled: root.canApply
                    onActivated: root.chosenSource=root.sources[currentIndex]
                }
                ComboBox {
                    objectName: 'sine_frequency_choice'; Layout.preferredWidth: 150
                    visible: root.chosenSource==='SINE'; enabled: root.canApply
                    model: backend.sineFrequencies; currentIndex: model.indexOf(root.chosenFrequency)
                    displayText: root.chosenFrequency+' Hz'
                    onActivated: root.chosenFrequency=model[currentIndex]
                }
                ConsoleButton {
                    objectName: 'generator_apply'; text: 'Apply source'; emphasized: true
                    enabled: root.canApply && root.chosenSource.length>0
                    onClicked: {if(backend.usbReadActive)generatorConfirm.open();else backend.applyGenerator(root.chosenSource,root.chosenFrequency)}
                }
            }
        }
    }
    Rectangle {
        Layout.fillWidth: true; implicitHeight: securityLayout.implicitHeight+24
        color: Theme.color('#10202a', backend.lightTheme); border.color: Theme.color('#294451', backend.lightTheme); radius: 6
        ColumnLayout {
            id: securityLayout; anchors.fill: parent; anchors.margins: 12; spacing: 8
            Label { text: 'PASSWORD / LOCK'; font.pixelSize: 15; font.bold: true }
            RowLayout {
                Layout.fillWidth: true
                Label { text: backend.editingLocked?'LOCKED':'UNLOCKED'; color: backend.editingLocked?Theme.color('#e8b961', backend.lightTheme):Theme.color('#43d782', backend.lightTheme); font.bold: true; Layout.fillWidth: true }
                ConsoleButton {
                    objectName: 'device_lock_button'; text: backend.editingLocked?'Unlock…':backend.usbReadActive?'Lock processor…':'Lock editing…'
                    enabled: !backend.utilityBusy && (!backend.usbReadActive || backend.utilitiesAvailable)
                    onClicked: securityDialog.open()
                }
            }
            Label { text: backend.usbReadActive?(backend.processorPasswordProtected?'Password protection enabled · '+(backend.processorLocked?'access locked':'access unlocked'):'Password protection disabled'):'DEMO lock protects editing in this session.'+(backend.processorLocked?' Last observed DSP access was locked; reconnect to unlock the processor.':''); color: Theme.color('#95b3c4', backend.lightTheme); wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
    }
    RowLayout {
        visible: !backend.usbReadActive && !backend.prsActive && backend.developerTools
        NumberField { label: 'Device ID'; number: backend.settings.device_id; minimum: 1; maximum: 254; decimals: 0; step: 1; onCommitted: value => backend.setting('device_id',Math.round(value)) }
        TextField { text: backend.settings.ip; Layout.fillWidth: true; onEditingFinished: backend.setting('ip',text) }
    }
    Item { Layout.fillHeight: true }

    ConsoleDialog {
        id: inputConfirm; objectName: 'input_source_confirmation'; parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(480,parent.width-40); title: 'Switch input source?'; standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Label { text: 'Switch all four inputs to '+root.chosenInput+'? The processor saves this selection. The signal generator is a separate setting.'; wrapMode: Text.WordWrap; color: Theme.color('#c2d4df', backend.lightTheme) }
        onAccepted: backend.applyInputSelection(root.chosenInput)
    }

    ConsoleDialog {
        id: generatorConfirm; objectName: 'generator_confirmation'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(470,parent.width-40)
        title: 'Apply signal source?'; modal: true; standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Label { text: 'Replace the input signal with '+root.chosenSource+(root.chosenSource==='SINE'?' · '+root.chosenFrequency+' Hz':'')+'?'; wrapMode: Text.WordWrap; color: Theme.color('#c2d4df', backend.lightTheme) }
        onAccepted: backend.applyGenerator(root.chosenSource,root.chosenFrequency)
    }
    ConsoleDialog {
        id: securityDialog; objectName: 'device_password_dialog'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(460,parent.width-40)
        modal: true; title: backend.editingLocked?'Unlock':'Set password and lock'
        onOpened: passwordField.forceActiveFocus()
        onClosed: {passwordField.clear();passwordRepeat.clear()}
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: 'Four characters: A–Z and 0–9.'; color: Theme.color('#95b3c4', backend.lightTheme) }
            TextField { id: passwordField; objectName: 'device_password'; Layout.fillWidth: true; maximumLength: 4; echoMode: TextInput.Password; placeholderText: 'Password'; validator: RegularExpressionValidator { regularExpression: /[A-Za-z0-9]{4}/ } }
            TextField { id: passwordRepeat; objectName: 'device_password_repeat'; visible: !backend.editingLocked; Layout.fillWidth: true; maximumLength: 4; echoMode: TextInput.Password; placeholderText: 'Repeat password'; validator: RegularExpressionValidator { regularExpression: /[A-Za-z0-9]{4}/ } }
            Label { visible: backend.usbReadActive && !backend.editingLocked; text: 'Locking saves the password in the processor and disconnects control. Keep this password to reconnect and unlock.'; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#c2d4df', backend.lightTheme) }
            Label { visible: backend.message==='Incorrect password.'; text: 'Incorrect password.'; color: Theme.color('#efad67', backend.lightTheme) }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                ConsoleButton { text: 'Cancel'; onClicked: securityDialog.close() }
                ConsoleButton {
                    objectName: 'device_password_apply'; text: backend.editingLocked?'Unlock':'Lock'; emphasized: true
                    enabled: passwordField.acceptableInput && (backend.editingLocked || (passwordRepeat.acceptableInput && passwordField.text.toUpperCase()===passwordRepeat.text.toUpperCase()))
                    onClicked: {var ok=backend.editingLocked?backend.unlockEditing(passwordField.text):backend.lockEditing(passwordField.text);passwordField.clear();passwordRepeat.clear();if(ok)securityDialog.close()}
                }
            }
        }
    }
}
