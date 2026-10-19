import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ConsoleButton {
    id: root
    objectName: 'help_button'
    text: 'Help ▾'
    property var info: backend.information
    function showSafety() { safety.open() }
    function showDocument(kind) {
        documents.title=kind==='changelog'?'Changelog':'Open Source Licenses'
        documents.licenses=kind!=='changelog'
        licenseChoice.currentIndex=0
        documentText.text=info.document(kind==='changelog'?'changelog':'license')
        documentScroll.contentItem.contentY=0
        documents.open()
    }
    onClicked: helpMenu.popup()
    Menu {
        id: helpMenu; objectName: 'help_menu'
        y: root.height+5; x: root.width-width; width: 210; padding: 5
        background: Rectangle { radius: 6; color: Theme.color('#101f29',backend.lightTheme); border.color: Theme.color('#365361',backend.lightTheme) }
        delegate: MenuItem {
            id: entry
            objectName: 'help_entry_'+text
            implicitHeight: 33
            contentItem: Text { text: entry.text; font.pixelSize: 12; color: Theme.color('#e3eef6',backend.lightTheme); verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
            background: Rectangle { radius: 4; color: entry.highlighted?Theme.color('#17445c',backend.lightTheme):'transparent' }
        }
        Action { objectName: 'help_about'; text: 'About'; onTriggered: about.open() }
        Action { objectName: 'help_licenses'; text: 'Open Source Licenses'; onTriggered: root.showDocument('licenses') }
        Action { objectName: 'help_changelog'; text: 'Changelog'; onTriggered: root.showDocument('changelog') }
        MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Theme.color('#294451',backend.lightTheme) } }
        Action { objectName: 'help_copy_diagnostics'; text: 'Copy Diagnostics'; onTriggered: { about.open();root.info.copyDiagnostics() } }
        Action { objectName: 'help_report_issue'; text: 'Report an Issue (GitHub)'; onTriggered: root.info.reportIssue() }
        Action { objectName: 'help_website'; text: 'gremium.tech'; onTriggered: root.info.openWebsite() }
    }
    ConsoleDialog {
        id: about; objectName: 'about_dialog'; anchors.centerIn: parent
        width: Math.min(580,parent.width-40); title: 'About '+root.info.metadata.name
        contentItem: ColumnLayout {
            spacing: 12
            RowLayout {
                spacing: 16; Layout.fillWidth: true
                Image { source: '../assets/icons/dsp408.svg'; sourceSize.width: 128; sourceSize.height: 128; Layout.preferredWidth: 64; Layout.preferredHeight: 64 }
                ColumnLayout {
                    spacing: 4; Layout.fillWidth: true
                    Label { text: root.info.metadata.name; font.pixelSize: 23; font.bold: true }
                    Label { objectName: 'about_version'; text: 'Version '+root.info.metadata.version+' · Build '+root.info.metadata.build; color: Theme.color('#39c9e4',backend.lightTheme) }
                    Label {
                        objectName: 'about_website'
                        text: '<style>a { color: '+Theme.color('#25b7d8',backend.lightTheme)+'; }</style>'+root.info.metadata.author+' · <a href="'+root.info.metadata.website+'">gremium.tech</a>'
                        textFormat: Text.RichText; linkColor: Theme.color('#25b7d8',backend.lightTheme)
                        color: Theme.color('#9ab5c6',backend.lightTheme)
                        onLinkActivated: root.info.openWebsite()
                    }
                }
            }
            Label { text: root.info.metadata.copyright; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: 'MIT License · application code'; Layout.fillWidth: true }
            Label { text: root.info.metadata.technologies; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#9ab5c6',backend.lightTheme) }
            Label { text: root.info.metadata.independence; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11 }
            Label { text: root.info.metadata.qtCopyright; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 10; color: Theme.color('#9ab5c6',backend.lightTheme) }
            Label {
                text: '<style>a { color: '+Theme.color('#25b7d8',backend.lightTheme)+'; }</style><a href="'+root.info.metadata.github+'">'+root.info.metadata.github+'</a>'
                textFormat: Text.RichText; linkColor: Theme.color('#25b7d8',backend.lightTheme); font.pixelSize: 11
                Layout.fillWidth: true; wrapMode: Text.WrapAnywhere
                onLinkActivated: root.info.openGithub()
            }
            Label { objectName: 'about_status'; text: root.info.status; visible: text.length>0; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.color('#9ab5c6',backend.lightTheme); font.pixelSize: 10 }
            ConsoleButton { objectName: 'about_safety'; text: 'Safety notice…'; implicitHeight: 26; onClicked: { about.close();root.showSafety() } }
        }
        footer: DialogActions {
            ConsoleButton { objectName: 'about_licenses'; text: 'Licenses'; onClicked: { about.close();root.showDocument('licenses') } }
            ConsoleButton { objectName: 'about_copy_diagnostics'; text: 'Copy Diagnostics'; onClicked: root.info.copyDiagnostics() }
            Item { Layout.fillWidth: true }
            ConsoleButton { text: 'GitHub'; onClicked: root.info.openGithub() }
            ConsoleButton { objectName: 'about_done'; text: 'Close'; onClicked: about.close() }
        }
    }
    ConsoleDialog {
        id: documents; objectName: 'help_documents'; anchors.centerIn: parent
        property bool licenses: true
        width: Math.min(820,parent.width-48); height: Math.min(590,parent.height-64)
        contentItem: ColumnLayout {
            spacing: 10
            ComboBox {
                id: licenseChoice; objectName: 'help_license_choice'; visible: documents.licenses
                Layout.fillWidth: true; implicitHeight: 32
                model: root.info.licenseDocuments; textRole: 'title'
                background: Rectangle { color: Theme.color('#152631',backend.lightTheme); radius: 4; border.color: Theme.color('#365160',backend.lightTheme) }
                onActivated: { documentText.text=root.info.document(root.info.licenseDocuments[currentIndex].key);documentScroll.contentItem.contentY=0 }
            }
            AdaptiveScrollView {
                id: documentScroll; objectName: 'help_document_scroll'
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
                TextArea {
                    id: documentText; objectName: 'help_document_text'
                    width: documentScroll.availableWidth; readOnly: true; selectByMouse: true
                    textFormat: TextEdit.PlainText; wrapMode: TextEdit.Wrap; padding: 10
                    font.pixelSize: 12; color: Theme.color('#e3eef6',backend.lightTheme)
                    background: Rectangle { color: Theme.color('#101e29',backend.lightTheme); radius: 4 }
                }
            }
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            ConsoleButton { objectName: 'help_document_done'; text: 'Close'; onClicked: documents.close() }
        }
    }
    ConsoleDialog {
        id: safety; objectName: 'startup_safety_notice'; anchors.centerIn: parent
        width: Math.min(580,parent.width-40); title: 'Before you enable audio'
        closePolicy: Popup.NoAutoClose
        onOpened: { dontShow.checked=root.info.safetyNoticeDismissed;Qt.callLater(()=>acknowledge.forceActiveFocus()) }
        contentItem: ColumnLayout {
            spacing: 16
            Label { text: 'Incorrect settings can damage equipment'; font.bold: true; font.pixelSize: 16; color: Theme.color('#e8b961',backend.lightTheme); Layout.fillWidth: true; wrapMode: Text.WordWrap }
            Label { text: root.info.safetyText; wrapMode: Text.WordWrap; Layout.fillWidth: true; lineHeight: 1.2 }
            ConsoleCheck { id: dontShow; objectName: 'safety_dont_show'; text: "Don't show again" }
            Label { text: root.info.status; visible: text.length>0; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 10 }
        }
        footer: DialogActions {
            Item { Layout.fillWidth: true }
            ConsoleButton { id: acknowledge; objectName: 'safety_acknowledge'; text: 'I understand'; onClicked: { root.info.acknowledgeSafety(dontShow.checked);safety.close() } }
        }
    }
}
