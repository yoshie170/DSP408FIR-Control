import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: root
    required property int channelIndex
    property bool compact: false
    property var channelData: { backend.revision; return backend.channel(channelIndex) }
    property var linkData: backend.channelLinks[channelIndex]
    property bool selected: backend.selected===channelIndex
    property var dynamicsStatus: backend.reductionState[channelIndex]
    property bool gainAllowed: { backend.revision; backend.usbGainReady; return backend.gainEditingAllowed(channelIndex) }
    property bool limitedGain: backend.usbGainMode && channelIndex===0
    height: compact ? 66 : 68
    color: 'transparent'
    Rectangle { x: 12; width: parent.width-12; height: parent.height; radius: 6
        color: root.selected ? Theme.color('#143649', backend.lightTheme) : Theme.color('#101e28', backend.lightTheme)
        border.color: root.selected ? Theme.color('#079acb', backend.lightTheme) : root.linkData.linked ? (backend.lightTheme?'#91bdb9':'#355b62') : Theme.color('#2c414e', backend.lightTheme)
    }
    LinkRail { objectName: 'link_rail_'+root.channelIndex; channelIndex: root.channelIndex; rowGap: root.compact?5:6; width: 10; height: parent.height }
    RowLayout {
        anchors.fill: parent; anchors.margins: 4; spacing: 5
        anchors.leftMargin: 17
        ColumnLayout {
            Layout.fillWidth: true; spacing: 1
            RowLayout {
              Layout.fillWidth: true; spacing: 3
              ConsoleButton {
                objectName: 'select_'+root.channelIndex
                Layout.fillWidth: true; implicitHeight: 16; topPadding: 0; bottomPadding: 0
                text: (root.channelIndex<4 ? String.fromCharCode(65+root.channelIndex) : String(root.channelIndex-3))+'   '+root.channelData.name
                checked: root.selected; onClicked: backend.select(root.channelIndex)
                ToolTip.visible: hovered; ToolTip.text: root.channelData.name
              }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 3
                NumberField { enabled: root.gainAllowed; fieldHeight: 18; number: root.channelData.gain; minimum: root.limitedGain?-1:-60; maximum: root.limitedGain?0:12; decimals: 1; step: root.limitedGain?1:.1; Layout.fillWidth: true; onCommitted: value => backend.edit(root.channelIndex,'gain',value,-1) }
                Label { text: 'dB'; font.pixelSize: 9; color: Theme.color('#809eaf', backend.lightTheme) }
                ConsoleButton {
                    objectName: 'mute_'+root.channelIndex
                    enabled: backend.parameterEditingAllowed
                    text: 'M'; Layout.preferredWidth: 26; implicitHeight: 18; leftPadding: 2; rightPadding: 2; topPadding: 0; bottomPadding: 0
                    onClicked: backend.edit(root.channelIndex,'mute',!root.channelData.mute,-1)
                    background: Rectangle { radius: 4; color: root.channelData.mute ? Theme.color('#a32940', backend.lightTheme) : Theme.color('#1b2d39', backend.lightTheme); border.color: root.channelData.mute ? Theme.color('#e55767', backend.lightTheme) : Theme.color('#3a5261', backend.lightTheme) }
                    ToolTip.visible: hovered; ToolTip.text: root.channelData.mute ? 'Unmute '+root.channelData.name : 'Mute '+root.channelData.name
                }
                ConsoleButton {
                    objectName: 'polarity_'+root.channelIndex
                    enabled: backend.parameterEditingAllowed
                    text: 'Ø'; Layout.preferredWidth: 24; implicitHeight: 18; leftPadding: 2; rightPadding: 2; topPadding: 0; bottomPadding: 0
                    checked: root.channelData.polarity_inverted
                    onClicked: backend.edit(root.channelIndex,'polarity_inverted',!root.channelData.polarity_inverted,-1)
                    ToolTip.visible: hovered; ToolTip.text: 'Invert polarity / 180°'
                }
            }
            LevelMeter {
                objectName: 'meter_'+root.channelIndex
                horizontal: true; showScale: true; Layout.fillWidth: true; Layout.preferredHeight: 22
                level: backend.meters[root.channelIndex]; peak: backend.meterPeaks[root.channelIndex]; db: backend.meterDb[root.channelIndex]; readingText: backend.meterLabels[root.channelIndex]
                caption: root.channelData.name
                indicatorKind: root.dynamicsStatus.kind; reductionActive: root.dynamicsStatus.active; reductionDb: root.dynamicsStatus.db
            }
        }
        Slider {
            id: fader
            objectName: 'fader_'+root.channelIndex
            enabled: root.gainAllowed
            orientation: Qt.Vertical; from: root.limitedGain?-1:-60; to: root.limitedGain?0:12; stepSize: root.limitedGain?1:.1
            Binding { target: fader; property: 'value'; value: root.channelData.gain; when: !fader.pressed; restoreMode: Binding.RestoreNone }
            snapMode: Slider.SnapAlways
            Layout.preferredWidth: 26; Layout.fillHeight: true; wheelEnabled: false
            FaderGestures {
                number: root.channelData.gain; minimum: fader.from; maximum: fader.to
                wheelStep: root.limitedGain?1:.1; resetToZero: true
                onCommitted: value => backend.edit(root.channelIndex,'gain',value,-1)
            }
            onMoved: backend.edit(root.channelIndex,'gain',value,-1)
            onPressedChanged: if(!pressed)backend.flushControlView()
            background: Rectangle { x: (fader.width-width)/2; y: fader.topPadding; width: 5; height: fader.availableHeight; radius: 2; color: Theme.color('#061117', backend.lightTheme); border.color: Theme.color('#3e5867', backend.lightTheme) }
            handle: Rectangle { x: (fader.width-width)/2; y: fader.topPadding+fader.visualPosition*(fader.availableHeight-height); width: 24; height: 10; radius: 2; gradient: Gradient { GradientStop { position: 0; color: Theme.color('#cce0ea', backend.lightTheme) } GradientStop { position: 1; color: Theme.color('#6a899b', backend.lightTheme) } } border.color: Theme.color('#31bce0', backend.lightTheme); Rectangle { anchors.centerIn: parent; width: 18; height: 1; color: Theme.color('#182b38', backend.lightTheme) } }
            Accessible.name: root.channelData.name+' gain fader'
            ToolTip.visible: hovered && root.limitedGain; ToolTip.text: 'Verified USB gain: IN A -1 or 0 dB. Display updates after readback.'
        }
    }
}
