import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ApplicationWindow {
    id: win
    property var currentData: backend.current
    visible: true; width: 1366; height: 768; minimumWidth: 1180; minimumHeight: 700
    title: 'DSP408FIR Control - '+backend.connectionLabel
    color: Theme.color('#0b1319', backend.lightTheme)
    palette.window: Theme.color('#0b141c', backend.lightTheme); palette.windowText: Theme.color('#e3eef6', backend.lightTheme); palette.base: Theme.color('#13232f', backend.lightTheme); palette.text: Theme.color('#e3eef6', backend.lightTheme); palette.button: Theme.color('#213441', backend.lightTheme); palette.buttonText: Theme.color('#e3eef6', backend.lightTheme); palette.highlight: Theme.color('#087dab', backend.lightTheme); palette.highlightedText: '#ffffff'
    font.family: 'Segoe UI'; font.pixelSize: 12
    property int band: 0
    property int tab: 11
    property int slot: 0
    property int inputTab: 1
    property int outputTab: 1
    property int lastGroup: 0
    Component.onCompleted: lastGroup=backend.selected<4?0:1
    property bool rtaRequested: false
    property int comparisonRequested: -1
    property bool showConnection: false
    property bool closeApproved: false
    DeviceSettingsDialog { id: processorSettings; anchors.centerIn: parent }
    onClosing: close => {
        if(backend.usbReadConnected && !closeApproved){
            close.accepted=false
            if(!connectedCloseDialog.visible)connectedCloseDialog.open()
        } else closeApproved=false
    }
    onShowConnectionChanged: { if(showConnection)connectionDialog.open() }
    property string pendingConfiguration: ''
    property int pendingSlot: -1
    property string pendingFile: ''
    property string pendingName: ''
    property var pendingHardwarePreset: ({})
    ChannelCopyDialog { id: channelCopy }
    ChannelLinkDialog { id: channelLink; parent: Overlay.overlay; anchors.centerIn: parent }
    ConsoleDialog {
        objectName: 'channel_link_confirmation'; parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(560,win.width-40); modal: true; title: 'Confirm channel Link'
        visible: Object.keys(backend.channelLinkReview).length>0
        onRejected: backend.cancelChannelLink()
        contentItem: ColumnLayout {
            spacing: 14
            Label { text: backend.channelLinkReview.members || ''; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Label { text: backend.channelLinkReview.unlink?'Unlink selected channel.':'Source: '+(backend.channelLinkReview.source || ''); wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Label { text: (backend.channelLinkReview.copies || []).join('\n'); visible: text.length>0; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Label { text: 'Joining copies channel settings and FIR. Names and output routing stay independent. '+(backend.usbReadActive?'Channels are briefly muted. ':'Changes apply to the offline configuration only. ')+'Previous settings are not restored by unlinking.'; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                Layout.topMargin: 8; Layout.bottomMargin: 8; Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                ConsoleButton { text: 'Cancel'; onClicked: backend.cancelChannelLink() }
                ConsoleButton { objectName: 'channel_link_apply'; text: 'Apply Link'; enabled: !backend.usbReadActive || (backend.usbControlReady && !backend.usbControlPending); onClicked: backend.applyChannelLink() }
            }
        }
    }
    PrsReviewDialog { id: configPrsReview; parent: Overlay.overlay; anchors.centerIn: parent }
    function requestHardwarePreset(entry) {
        if(!backend.presetRecallAvailable || entry.marker_raw!==255)return
        pendingHardwarePreset=entry;hardwareRecallConfirm.open()
    }
    function requestHardwareStore(entry) {
        if(!backend.usbPresetStoreAvailable || !entry.slot)return
        pendingHardwarePreset=entry;hardwareStoreName.text=backend.usbCurrentPresetName
        hardwareStoreConfirm.open()
    }
    function tabAvailable(index) { return index!==10 && (backend.selected<4 ? index!==2 && index!==6 : index!==4 && index!==5 && index!==7) }
    onTabChanged: {
        if(!tabAvailable(tab)){tab=tab===7 && backend.selected>=4?2:1;return}
        if(tab!==11){if(backend.selected<4)inputTab=tab;else outputTab=tab}
    }
    function applyConfiguration() {
        if(!backend.modelEditingAllowed){configurationDialog.close();return}
        if(pendingConfiguration==='file')backend.loadPath(pendingFile)
        else if(pendingConfiguration==='previous')backend.undoConfigurationSwitch()
        else backend.recallSlot(pendingSlot)
        configurationDialog.close();pendingConfiguration=''
    }
    function requestConfiguration(kind,target) {
        if(!backend.modelEditingAllowed)return
        if(kind==='slot' && !backend.configurations[target].stored){backend.recallSlot(target);return}
        if(kind==='previous' && !backend.canUndoSwitch)return
        if(kind==='file'){
            var path=backend.choosePresetPath();if(!path.length)return
            pendingFile=path;pendingName=path.split(/[\\/]/).pop()
        }else pendingName=kind==='previous'?backend.previousConfigurationName:backend.configurations[target].name
        pendingConfiguration=kind;pendingSlot=target
        configurationDialog.open()
    }
    Connections {
        target: backend
        function onPrsReviewReady() { configPrsReview.open() }
        function onChanged() {
            if(backend.usbConnectionBusy)connectionDialog.close()
            if(win.band>=win.currentData.filters.length)win.band=0
            var group=backend.selected<4?0:1
            if(group!==win.lastGroup){win.lastGroup=group;if(win.tab!==11)win.tab=group===0?win.inputTab:win.outputTab}
        }
    }
    property bool phase: false
    property var flt: win.currentData.filters[Math.min(band,win.currentData.filters.length-1)]
    component Choice: ColumnLayout {
        id: choice
        property string caption: ''
        property var choices: []
        property var selectedValue
        signal picked(var value)
        spacing: 4
        Label { text: choice.caption; color: Theme.color('#8fa7b9', backend.lightTheme); font.pixelSize: 11 }
        ComboBox { Layout.fillWidth: true; implicitHeight: 32; model: choice.choices; currentIndex: choice.choices.indexOf(choice.selectedValue); onActivated: choice.picked(choice.choices[currentIndex]); background: Rectangle { color: Theme.color('#152631', backend.lightTheme); radius: 5; border.color: Theme.color('#365160', backend.lightTheme) } }
    }
    component Card: Rectangle { color: Theme.color('#101e28', backend.lightTheme); radius: 7; border.color: Theme.color('#293d4b', backend.lightTheme) }
    header: Rectangle {
        height: 72; color: Theme.color('#101d27', backend.lightTheme); border.color: Theme.color('#2a3d4a', backend.lightTheme)
        RowLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 10
            RowLayout {
                objectName: 'app_brand'; spacing: 9; Layout.preferredWidth: 246
                Image { objectName: 'app_mark'; source: '../assets/icons/dsp408.svg'; sourceSize.width: 76; sourceSize.height: 76; Layout.preferredWidth: 38; Layout.preferredHeight: 38 }
                Column {
                    spacing: 1
                    Row {
                        spacing: 7
                        Label { id: brandName; text: 'DSP408FIR'; font.pixelSize: 21; font.bold: true }
                        Label { text: 'CONTROL'; anchors.baseline: brandName.baseline; font.pixelSize: 10; font.letterSpacing: 1.3; color: Theme.color('#39c9e4',backend.lightTheme) }
                    }
                    Label { text: 't.racks FIR DSP 408'; color: Theme.color('#8ba5b7', backend.lightTheme); font.pixelSize: 10 }
                }
            }
            Rectangle { width: 1; Layout.fillHeight: true; color: Theme.color('#304652', backend.lightTheme) }
            Column {
                spacing: 5
                Label { objectName: 'connection_state'; text: '●  '+backend.connectionLabel; color: backend.usbReadConnected?Theme.color('#45dc80', backend.lightTheme):backend.usbReadActive?Theme.color('#efbd58', backend.lightTheme):Theme.color('#8fa8b9', backend.lightTheme); font.bold: true; font.pixelSize: 11 }
                Row {
                    spacing: 7
                    Rectangle {
                        objectName: 'input_source_dot'; width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter
                        color: !backend.inputSelectionState.known?Theme.color('#718b9b',backend.lightTheme):backend.inputSelectionState.source==='ANALOG'?Theme.color('#45dc80',backend.lightTheme):Theme.color('#39c9e4',backend.lightTheme)
                    }
                    Label { objectName: 'input_source_header'; text: 'INPUT A–B · '+(backend.inputSelectionState.known?backend.inputSelectionState.source:'—'); color: Theme.color('#dceaf3',backend.lightTheme); font.pixelSize: 15; font.bold: true }
                }
            }
            Item { Layout.fillWidth: true }
            Label { text: 'Config: '+backend.preset+(backend.dirty?' *':''); color: backend.dirty?Theme.color('#f2c868', backend.lightTheme):Theme.color('#dceaf3', backend.lightTheme); elide: Text.ElideRight; Layout.maximumWidth: 200 }
            ConsoleButton { objectName: 'configuration_load_json'; text: 'Load config…'; enabled: backend.modelEditingAllowed || backend.usbPresetRecallAvailable; onClicked: {if(backend.usbReadActive){if(backend.choosePrsImportReview())configPrsReview.open()}else win.requestConfiguration('file',-1)} ToolTip.visible: hovered; ToolTip.text: backend.usbReadActive?'Review and confirm configuration and FIR from a PRS file.':'Open a .prs or .json configuration. Loading requires confirmation.' }
            ConsoleButton { objectName: 'configuration_save_json'; text: 'Save config…'; onClicked: backend.savePreset(); ToolTip.visible: hovered; ToolTip.text: backend.usbReadActive?'Save the configuration and FIR as PRS, or choose a JSON snapshot.':'Save JSON, or save PRS using the original PRS template loaded with this configuration.' }
            ConsoleButton { objectName: 'connection_options'; text: 'Connection…'; outlined: true; onClicked: connectionDialog.open(); ToolTip.visible: hovered; ToolTip.text: 'Connect or disconnect the processor.' }
            ConsoleButton { visible: backend.developerTools; text: 'Send'; enabled: false; opacity: .4; ToolTip.visible: hovered; ToolTip.text: 'Unavailable for this connection.' }
        }
    }
    footer: Rectangle {
        height: 32; color: Theme.color('#101d27', backend.lightTheme); border.color: Theme.color('#293c49', backend.lightTheme)
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14
            Label { text: backend.displayMessage; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.color('#94b2c5', backend.lightTheme); font.pixelSize: 11 }
            Label {
                objectName: 'dsp_usage'; text: 'DSP usage: '+(backend.dspUsage.available?backend.dspUsage.percent.toFixed(1):'—')+'%'
                color: !backend.dspUsage.available?Theme.color('#94b2c5', backend.lightTheme):backend.dspUsage.percent>=100?Theme.color('#ff6774',backend.lightTheme):backend.dspUsage.percent>=90?Theme.color('#ed934b',backend.lightTheme):Theme.color('#25b7d8',backend.lightTheme); font.pixelSize: 11
                MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; ToolTip.visible: containsMouse; ToolTip.text: backend.usbReadActive?'DSP resource usage':'Available when connected to the DSP' }
            }
            Label {
                objectName: 'app_copyright'; text: '<style>a { color: '+Theme.color('#25b7d8',backend.lightTheme)+'; }</style>v'+backend.applicationVersion+' · Copyright © 2026 Łukasz Białas · <a href="https://gremium.tech">gremium.tech</a>'
                textFormat: Text.RichText; color: Theme.color('#94b2c5', backend.lightTheme); linkColor: Theme.color('#25b7d8',backend.lightTheme); font.pixelSize: 10
                onLinkActivated: link => Qt.openUrlExternally(link)
            }
        }
    }
    RowLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 10
        Card {
            id: inputCard
            LinkRail { objectName: 'input_link_overlay'; sourceView: inputScroll; strips: inputStrips; firstChannel: 0; channelCount: 4 }
            Layout.preferredWidth: 232; Layout.fillHeight: true
            AdaptiveScrollView {
                id: inputScroll
                objectName: 'input_scroll'
                anchors.fill: parent; anchors.margins: 9; clip: true; contentWidth: availableWidth
                Column {
                    width: parent.width; spacing: 6
                    Item { width: 212; height: 19; Label { text: 'INPUTS (4)'; font.bold: true } }
                    Repeater { id: inputStrips; model: 4; ChannelStrip { required property int index; channelIndex: index; width: 212 } }
                    Label { text: 'MATRIX / ROUTING'; font.bold: true; height: 20; verticalAlignment: Text.AlignVCenter }
                    GridLayout {
                        columns: 9; columnSpacing: 2; rowSpacing: 2
                        Label { text: 'IN'; color: Theme.color('#8fa7b9', backend.lightTheme) }
                        Repeater { model: 8; Label { required property int index; text: String(index+1); horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 19; color: Theme.color('#8fa7b9', backend.lightTheme) } }
                        Repeater {
                            model: 36
                            delegate: Item {
                                required property int index
                                property int inp: Math.floor(index/9)
                                property int out: index%9-1
                                Layout.preferredWidth: out<0 ? 20 : 19; Layout.preferredHeight: 18
                                Label { visible: parent.out<0; text: String.fromCharCode(65+parent.inp); anchors.centerIn: parent; color: Theme.color('#90aabc', backend.lightTheme) }
                                Rectangle {
                                    visible: parent.out>=0; anchors.fill: parent; radius: 2
                                    color: parent.out>=0 && backend.routing[parent.out][parent.inp] ? Theme.color('#008ac0', backend.lightTheme) : Theme.color('#142430', backend.lightTheme); border.color: Theme.color('#345263', backend.lightTheme)
                                    MouseArea { anchors.fill: parent; enabled: backend.parameterEditingAllowed; onClicked: backend.route(parent.parent.out,parent.parent.inp,!backend.routing[parent.parent.out][parent.parent.inp],backend.routingGains[parent.parent.out][parent.parent.inp]) }
                                }
                            }
                        }
                    }
                    Label { text: backend.usbReadActive?'PRESETS · DSP':'CONFIGURATIONS · ALL 12'; font.bold: true; font.pixelSize: 11; height: 16 }
                    PresetBrowser { id: presetBrowser; width: 212; height: win.height>=900?174:backend.usbControlMode?(win.height<740?42:86):backend.usbReadActive?118:86; selectedSlot: win.slot; onSlotSelected: slot => win.slot=slot; onDetailsRequested: entry => {presetDetails.entry=entry;presetDetails.open()}; onRecallRequested: entry => win.requestHardwarePreset(entry) }
                    Label { visible: backend.usbReadActive; width: 212; text: backend.usbControlMode?'Select preset → Load · green = active':'Preview only · green = active preset'; color: Theme.color('#7db398', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap }
                    Row {
                        visible: backend.usbControlMode; width: 198; spacing: 6
                        ConsoleButton { objectName: 'hardware_preset_load'; width: 96; implicitHeight: 26; text: 'Load preset…'; enabled: backend.presetRecallAvailable && presetBrowser.selectedEntry.marker_raw===255; onClicked: win.requestHardwarePreset(presetBrowser.selectedEntry) }
                        ConsoleButton { objectName: 'hardware_preset_store'; width: 96; implicitHeight: 26; text: 'Store preset…'; enabled: backend.usbPresetStoreAvailable && !!presetBrowser.selectedEntry.slot; onClicked: win.requestHardwareStore(presetBrowser.selectedEntry); ToolTip.visible: hovered; ToolTip.text: backend.usbPresetStoreAuthorized?'Save the current DSP settings to the selected slot':'Store and naming prepared · awaiting separate authorization' }
                    }
                    TextField { id: configurationName; objectName: 'configuration_name'; visible: !backend.usbReadActive; width: 198; implicitHeight: 24; text: backend.configurations[win.slot].name; placeholderText: 'Name · max 14'; selectByMouse: true; maximumLength: 14; leftPadding: 8; background: Rectangle { radius: 4; color: Theme.color('#10202a', backend.lightTheme); border.color: configurationName.activeFocus?Theme.color('#28bde1', backend.lightTheme):Theme.color('#354e5c', backend.lightTheme) } ToolTip.visible: hovered; ToolTip.text: 'Original editor: 14 characters; DSP name field: 14 bytes. Hardware preset naming is not enabled.' }
                    Row { visible: !backend.usbReadActive; spacing: 6; ConsoleButton { objectName: 'configuration_apply'; text: 'Apply'; width: 96; implicitHeight: 28; enabled: backend.configurations[win.slot].stored; onClicked: win.requestConfiguration('slot',win.slot) } ConsoleButton { objectName: 'configuration_store'; text: 'Store session'; width: 96; implicitHeight: 28; onClicked: backend.storeNamedSlot(win.slot,configurationName.text) } }
                    ConsoleButton { objectName: 'configuration_undo'; text: 'Previous configuration / A–B'; visible: !backend.usbReadActive && backend.canUndoSwitch; width: 198; implicitHeight: 26; onClicked: win.requestConfiguration('previous',-1); ToolTip.visible: hovered; ToolTip.text: 'Switch between two snapshots; edits remain preserved locally.' }
                    Label { visible: !backend.usbReadActive && win.height>=900; text: 'Store: session only · Save config: portable file'; color: Theme.color('#718d9f', backend.lightTheme); font.pixelSize: 9 }
                }
            }
        }
        Card {
            Layout.fillWidth: true; Layout.fillHeight: true
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 10; spacing: 10
                RowLayout {
                    Layout.fillWidth: true; spacing: 3
                    Repeater {
                        model: ['MAIN','CHANNEL','PEQ','XOVER','DELAY','GATE','COMP','LIMIT','FIR','ROUTING','SETUP','DEQ']
                        ConsoleButton {
                            required property int index
                            required property string modelData
                            property int pageIndex: index===0?11:index-1
                            objectName: 'tab_'+pageIndex
                            visible: win.tabAvailable(pageIndex)
                            text: modelData; Layout.fillWidth: true; Layout.minimumWidth: 42; padding: 4; font.pixelSize: 11; implicitHeight: 32
                            Layout.rightMargin: index===0?22:0
                            Layout.leftMargin: pageIndex===9?22:0
                            Rectangle {
                                objectName: 'tab_separator_'+parent.pageIndex
                                visible: index===0 || parent.pageIndex===9
                                x: index===0?parent.width+12:-12; y: (parent.height-height)/2
                                width: 1; height: 20; color: Theme.color('#355361', backend.lightTheme)
                            }
                            onClicked: win.tab=pageIndex
                            checked: win.tab===pageIndex
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: win.tab===9?'DEVICE':win.tab===11?'ALL CHANNELS':win.currentData.name; font.pixelSize: 17; font.bold: true; color: Theme.color('#e3f3ff', backend.lightTheme) }
                    Label { text: win.tab===9?'INPUT / GENERATOR / LOCK':win.tab===11?'LEVELS / FUNCTIONS':backend.selected<4 ? 'INPUT '+String.fromCharCode(65+backend.selected) : 'OUTPUT '+(backend.selected-3); color: Theme.color('#7da4bd', backend.lightTheme); font.pixelSize: 11 }
                    Item { Layout.fillWidth: true }
                    ConsoleButton { objectName: 'processor_settings_open'; visible: win.tab===9; text: 'Processor IP / ID…'; implicitHeight: 22; enabled: !backend.usbPresetRecallBusy; onClicked: processorSettings.open() }
                    ConsoleButton { objectName: 'channel_copy'; visible: win.tab!==1 && win.tab!==9 && win.tab!==11; text: 'Copy…'; enabled: backend.parameterEditingAllowed; onClicked: channelCopy.openFor('all') }
                    Label { objectName: 'workspace_edit_status'; visible: backend.editingLocked || (backend.usbReadActive && !backend.usbControlMode); text: backend.editingLocked?'LOCKED':'READ ONLY'; color: backend.editingLocked?Theme.color('#e8b961', backend.lightTheme):Theme.color('#35b3d0', backend.lightTheme); font.pixelSize: 10 }
                }
                Label { visible: backend.developerTools && backend.usbReadActive; text: backend.usbWarnings; color: Theme.color('#e5bd70', backend.lightTheme); font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                AdaptiveScrollView {
                    id: workspaceScroll
                    objectName: 'workspace_scroll'
                    implicitHeight: 0; Layout.minimumHeight: 0; Layout.minimumWidth: 0
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                    contentHeight: pages.height
                    StackLayout {
                        enabled: win.tab===11 || win.tab===9 || backend.modelEditingAllowed || (backend.usbControlReady && win.tab!==7) || (win.tab===7 && backend.usbControlReady && backend.selected<4) || (win.tab===0 && backend.usbGainMode)
                        id: pages
                        width: workspaceScroll.availableWidth; currentIndex: win.tab
                        height: Math.max(workspaceScroll.availableHeight,children[win.tab] ? children[win.tab].Layout.minimumHeight : 0)
                        // Channel
                        ChannelPanel { onCopyRequested: channelCopy.openFor('all'); onLinkRequested: channelLink.openFor() }
                        // PEQ
                        PeqPanel { band: win.band; rta: win.rtaRequested; onBandSelected: value => win.band=value; onCopyRequested: channelCopy.openFor('peq'); implicitHeight: 500; tableHeight: win.height<900 ? 125 : 280 }
                        // Xover
                        CrossoverPanel { }
                        // Delay
                        DelayPanel { }
                        DynamicsPanel { section: 'gate' }
                        DynamicsPanel { section: 'compressor' }
                        DynamicsPanel { section: 'limiter' }
                        // FIR
                        FirPanel { }
                        // Routing
                        RoutingPanel { }
                        // Device-wide utilities
                        DeviceSetupPanel { }
                        DeqPanel { }
                        MainOverview { onOpenChannel: (channelIndex,page) => {backend.select(channelIndex);win.tab=page} }
                    }
                }
            }
        }
        Card {
            id: outputCard
            LinkRail { objectName: 'output_link_overlay'; sourceView: outputScroll; strips: outputStrips; firstChannel: 4; channelCount: 8 }
            Layout.preferredWidth: 246; Layout.fillHeight: true
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 6
                Label { text: 'OUTPUTS (8)'; font.bold: true; Layout.preferredHeight: 24 }
                AdaptiveScrollView {
                    id: outputScroll
                    objectName: 'output_scroll'
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                    Column { width: parent.width; spacing: 5; Repeater { id: outputStrips; model: 8; ChannelStrip { required property int index; channelIndex: index+4; compact: true; width: 226 } } }
                }
                ConsoleButton {
                    objectName: 'outputs_mute_all'; Layout.fillWidth: true
                    text: backend.outputsAllMuted?'Unmute ALL':'Mute ALL'
                    enabled: backend.parameterEditingAllowed
                    outlined: true; accent: Theme.color('#e55767',backend.lightTheme)
                    checked: backend.outputsAllMuted
                    onClicked: backend.setOutputsMuted(!backend.outputsAllMuted)
                    ToolTip.visible: hovered; ToolTip.text: backend.outputsAllMuted?'Unmute all eight outputs':'Mute all eight outputs'
                }
            }
        }
    }
    ConnectionDialog { id: connectionDialog; anchors.centerIn: parent; onPresetPreviewRequested: {connectionDialog.close();storedPreview.open()} onDiagnosticsRequested: diagnosticsDialog.open(); onPrsReviewRequested: configPrsReview.open() }
    DiagnosticsDialog { id: diagnosticsDialog; anchors.centerIn: parent; onPresetPreviewRequested: {diagnosticsDialog.close();storedPreview.open()} onPrsReviewRequested: configPrsReview.open() }
    PresetReadPreviewDialog { id: storedPreview; anchors.centerIn: parent }
    ConsoleDialog {
        id: presetDetails; objectName: 'preset_catalog_details'; property var entry: ({})
        anchors.centerIn: parent; width: 530; title: 'PRESET DETAILS'
        modal: true; standardButtons: Dialog.Close

        contentItem: ColumnLayout {
            spacing: 10
            Label { objectName: 'preset_details_name'; text: 'P'+String(presetDetails.entry.slot || 0).padStart(2,'0')+' · '+(presetDetails.entry.name || ''); font.bold: true; color: Theme.color('#29c6e8', backend.lightTheme) }
            Label { text: presetDetails.entry.active?'Currently active preset':'Stored slot selected for catalog inspection'; color: Theme.color('#a9c6d5', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { visible: backend.developerTools; text: 'Name index: '+presetDetails.entry.name_index+' · marker: '+presetDetails.entry.marker_raw; color: Theme.color('#a9c6d5', backend.lightTheme) }
            Label { visible: backend.developerTools; text: 'Raw name (14 bytes): '+presetDetails.entry.name_raw_hex; color: Theme.color('#a9c6d5', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; font.pixelSize: 11 }
            Label { text: 'Viewing preset details does not load it. Load and Save ask for confirmation.'; color: Theme.color('#e2bd72', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
    ConsoleDialog {
        id: hardwareRecallConfirm; objectName: 'hardware_recall_confirm'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(520,win.width-40)
        title: 'Load DSP preset?'; modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        onAboutToShow: Qt.callLater(()=>hardwareRecallCancel.forceActiveFocus())

        contentItem: ColumnLayout {
            spacing: 12
            Label { text: 'P'+String(win.pendingHardwarePreset.slot || 0).padStart(2,'0')+' · '+(win.pendingHardwarePreset.name || ''); font.bold: true; color: Theme.color('#29c6e8', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'This recalls the preset stored in the DSP and replaces the current settings for all 12 channels, including its native FIR configuration. Unsaved device adjustments will be lost. No preset is overwritten. Continue?'; color: Theme.color('#bfd5e3', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            spacing: 8
            ConsoleButton { objectName: 'hardware_recall_accept'; text: 'Load preset'; enabled: backend.presetRecallAvailable; onClicked: {var slot=win.pendingHardwarePreset.slot;hardwareRecallConfirm.close();backend.requestUsbPresetRecall(slot)} }
            ConsoleButton { id: hardwareRecallCancel; objectName: 'hardware_recall_cancel'; text: 'Cancel'; onClicked: hardwareRecallConfirm.close(); Keys.onPressed: event => {if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){hardwareRecallConfirm.close();event.accepted=true}} }
        }
    }
    ConsoleDialog {
        id: hardwareStoreConfirm; objectName: 'hardware_store_confirm'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(530,win.width-40)
        title: win.pendingHardwarePreset.stored?'Overwrite DSP preset?':'Save DSP preset?'
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        onAboutToShow: Qt.callLater(()=>hardwareStoreCancel.forceActiveFocus())

        contentItem: ColumnLayout {
            spacing: 12
            Label { text: 'P'+String(win.pendingHardwarePreset.slot || 0).padStart(2,'0')+' · '+(win.pendingHardwarePreset.stored?win.pendingHardwarePreset.name:'Empty slot'); color: Theme.color('#29c6e8', backend.lightTheme); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: win.pendingHardwarePreset.stored?'The saved parameters and native FIR in this slot will be replaced with the current DSP configuration.':'The current DSP parameters and native FIR will be saved to this slot.'; color: Theme.color('#bfd5e3', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            TextField { id: hardwareStoreName; objectName: 'hardware_store_name'; Layout.fillWidth: true; maximumLength: 14; placeholderText: 'Preset name · 1–14 ASCII characters'; selectByMouse: true; validator: RegularExpressionValidator { regularExpression: /[ -~]{1,14}/ } }
            Label { text: 'The name also becomes the current DSP configuration name. The saved slot becomes active. A stopped operation does not automatically restore earlier settings. Continue?'; color: Theme.color('#9ab5c6', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            spacing: 8
            ConsoleButton { objectName: 'hardware_store_accept'; text: win.pendingHardwarePreset.stored?'Overwrite preset':'Save preset'; enabled: backend.usbPresetStoreAvailable && hardwareStoreName.acceptableInput && hardwareStoreName.text.trim().length>0; onClicked: {var entry=win.pendingHardwarePreset;hardwareStoreConfirm.close();backend.requestUsbPresetStore(entry.slot,hardwareStoreName.text,entry.marker_raw,entry.name_raw_hex)} }
            ConsoleButton { id: hardwareStoreCancel; objectName: 'hardware_store_cancel'; text: 'Cancel'; onClicked: hardwareStoreConfirm.close(); Keys.onPressed: event => {if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){hardwareStoreConfirm.close();event.accepted=true}} }
        }
    }
    ConsoleDialog {
        id: connectionProgress; objectName: 'usb_connection_progress'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(500,win.width-40)
        modal: true; focus: true; closePolicy: Popup.NoAutoClose; visible: backend.usbConnectionBusy
        title: 'Connecting to DSP'
        Overlay.modal: Rectangle { objectName: 'usb_connection_dim'; color: Theme.color('#b300070b', backend.lightTheme) }

        contentItem: ColumnLayout {
            spacing: 12
            Label { objectName: 'usb_connection_stage'; text: backend.usbConnectionDisplayStage; color: Theme.color('#bfd5e3', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            ProgressBar {
                objectName: 'usb_connection_bar'; Layout.fillWidth: true; indeterminate: true
                implicitHeight: 8; padding: 0
                background: Rectangle { color: Theme.color('#142f3c', backend.lightTheme); radius: 4; border.color: Theme.color('#2d5364', backend.lightTheme) }
                contentItem: Item {
                    id: connectionTrack; clip: true; implicitHeight: 8
                    Rectangle {
                        id: connectionSweep; objectName: 'usb_connection_sweep'
                        width: Math.max(40,connectionTrack.width*0.24); height: connectionTrack.height
                        radius: 4; color: Theme.color('#29c6e8', backend.lightTheme)
                        NumberAnimation on x {
                            from: -connectionSweep.width; to: connectionTrack.width
                            duration: 1200; loops: Animation.Infinite; easing.type: Easing.Linear
                            running: backend.usbConnectionBusy && connectionProgress.visible
                        }
                    }
                }
            }
            Label { text: 'Reading DSP configuration…'; color: Theme.color('#29c6e8', backend.lightTheme); Layout.fillWidth: true }
            Label { text: 'Keep the DSP connected. Controls unlock after synchronization.'; color: Theme.color('#8faabb', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            ConsoleButton { objectName: 'usb_connection_cancel'; text: 'Cancel connection'; Layout.alignment: Qt.AlignRight; onClicked: backend.disconnectUsbRead() }
        }
    }
    ConsoleDialog {
        id: hardwareRecallProgress; objectName: 'hardware_recall_progress'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(500,win.width-40)
        modal: true; closePolicy: Popup.NoAutoClose; visible: backend.usbPresetRecallBusy
        title: backend.usbPresetRecallProgress.operation==='bank_restore'?'Restoring saved preset bank':backend.usbPresetRecallProgress.operation==='bank_backup'?'Backing up preset bank':backend.usbPresetRecallProgress.operation==='channel_link'?'Applying channel Link':backend.usbPresetRecallProgress.operation==='output_fir'?'Applying FIR crossover':backend.usbPresetRecallProgress.operation==='fir_read'?'Reading FIR storage':backend.usbPresetRecallProgress.operation==='fir_import'?'Applying input FIR':backend.usbPresetRecallProgress.operation==='fir_trial'?'Loading IN A identity FIR256':backend.usbPresetRecallProgress.operation==='prs_import'?'Importing configuration and FIR':(backend.usbPresetRecallProgress.operation==='store'?'Saving P':'Loading P')+String(backend.usbPresetRecallProgress.slot || 0).padStart(2,'0')

        contentItem: ColumnLayout {
            spacing: 12
            Label { objectName: 'fir_operation_phase'; visible: backend.usbPresetRecallProgress.operation==='fir_import'; text: backend.usbOperationPhase; color: Theme.color('#21bce4', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: backend.usbOperationStage; color: Theme.color('#bfd5e3', backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            ProgressBar {
                objectName: 'hardware_recall_bar'; Layout.fillWidth: true
                from: 0; to: backend.usbPresetRecallProgress.total || 70
                value: backend.usbPresetRecallProgress.done || 0
                indeterminate: backend.usbPresetRecallBusy
                implicitHeight: 8; padding: 0
                background: Rectangle { color: Theme.color('#142f3c', backend.lightTheme); radius: 4; border.color: Theme.color('#2d5364', backend.lightTheme) }
                contentItem: Item {
                    id: recallTrack; clip: true; implicitHeight: 8
                    Rectangle {
                        id: recallSweep; objectName: 'hardware_recall_sweep'
                        width: Math.max(40,recallTrack.width*0.24); height: recallTrack.height
                        radius: 4; color: Theme.color('#29c6e8', backend.lightTheme)
                        NumberAnimation on x {
                            from: -recallSweep.width; to: recallTrack.width
                            duration: 1200; loops: Animation.Infinite; easing.type: Easing.Linear
                            running: backend.usbPresetRecallBusy && hardwareRecallProgress.visible
                        }
                    }
                }
            }
            Label { text: backend.usbPresetRecallProgress.waiting?'Waiting for the DSP…':String(backend.usbPresetRecallProgress.done || 0)+' / '+String(backend.usbPresetRecallProgress.total || 70)+' steps'; color: Theme.color('#29c6e8', backend.lightTheme); Layout.fillWidth: true }
            Label { text: 'Keep the DSP connected until loading finishes.'; color: Theme.color('#8faabb', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
    }
    ConsoleDialog {
        id: connectedCloseDialog
        objectName: 'connected_close_guard'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(460,win.width-40)
        modal: true; focus: true; title: 'DSP connected'
        closePolicy: Popup.CloseOnEscape
        onAboutToShow: Qt.callLater(()=>connectedCloseCancel.forceActiveFocus())
        onOpened: connectedCloseCancel.forceActiveFocus()
        contentItem: Label {
            text: 'The application is connected to the DSP.\nClose the application and disconnect?'+(backend.usbPresetRecallBusy?'\n\nA preset operation is in progress. Disconnecting stops verification and does not restore the previous settings.':backend.usbControlPending?'\n\nChanges are still awaiting confirmation.':'')
            wrapMode: Text.WordWrap; color: Theme.color('#bfd5e3', backend.lightTheme); padding: 12
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            spacing: 8
            ConsoleButton { objectName: 'connected_close_confirm'; text: 'Close and disconnect'; onClicked: {win.closeApproved=true;connectedCloseDialog.close();win.close()} }
            ConsoleButton { id: connectedCloseCancel; objectName: 'connected_close_cancel'; text: 'Keep open'; onClicked: connectedCloseDialog.close(); Keys.onPressed: event => {if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){connectedCloseDialog.close();event.accepted=true}} }
        }
    }
    ConsoleDialog {
        id: configurationDialog
        objectName: 'configuration_guard'
        parent: Overlay.overlay; anchors.centerIn: parent; width: Math.min(510,win.width-40)
        modal: true; focus: true; title: 'Confirm configuration load'
        onAboutToShow: Qt.callLater(()=>configurationCancel.forceActiveFocus())
        onOpened: configurationCancel.forceActiveFocus()
        onClosed: {win.pendingConfiguration='';win.pendingSlot=-1;win.pendingFile='';win.pendingName=''}
        contentItem: Label { objectName: 'configuration_question'; text: 'Load “'+win.pendingName+'” into all 12 channels?\n\n'+(backend.dirty?'The current configuration has unsaved changes. Save first or load with a local undo snapshot.':'A local undo snapshot will be kept.')+'\n\nThis changes the offline configuration only.'; wrapMode: Text.WordWrap; color: Theme.color('#bfd5e3', backend.lightTheme); padding: 12 }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            spacing: 8
            ConsoleButton { visible: backend.dirty; text: 'Save and load'; onClicked: {if(backend.savePreset())win.applyConfiguration()} }
            ConsoleButton { objectName: 'configuration_discard'; text: 'Load · keep undo'; onClicked: win.applyConfiguration() }
            ConsoleButton { id: configurationCancel; objectName: 'configuration_cancel'; text: 'Cancel'; onClicked: configurationDialog.close(); Keys.onPressed: event => {if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter){configurationDialog.close();event.accepted=true}} }
        }
    }
}

