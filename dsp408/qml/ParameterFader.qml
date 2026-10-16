import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: root
    property string label: ''
    property string unit: ''
    property string controlId: ''
    property real number: 0
    property real minimum: 0
    property real maximum: 1
    property real step: 0.1
    property int decimals: 1
    property bool logarithmic: false
    property bool vertical: false
    property var choices: []
    property var choiceLabels: []
    property color accent: Theme.color('#21bce4', backend.lightTheme)
    property int sliderHeight: 142
    property int scaleDivisions: 5
    property string hint: ''
    property bool resetToZero: unit==='dB' && controlId.indexOf('gain')>=0
    property real wheelStep: choices.length ? 0 : step
    property int wheelChoiceStride: 1
    readonly property bool pressed: slider.pressed
    property real displayedNumber: slider.pressed ? decoded(slider.value) : number
    signal committed(real value)
    color: Theme.color('#111f29', backend.lightTheme); radius: 7; border.color: Theme.color('#2c414e', backend.lightTheme)
    implicitHeight: vertical ? sliderHeight+90 : 82
    implicitWidth: 120
    function position(v) {
        if(choices.length){var best=0;for(var i=1;i<choices.length;i++)if(Math.abs(choices[i]-v)<Math.abs(choices[best]-v))best=i;return best/(choices.length-1)}
        if(logarithmic)return Math.log(Math.max(minimum,v)/minimum)/Math.log(maximum/minimum)
        return (v-minimum)/(maximum-minimum)
    }
    function decoded(p) {
        if(choices.length)return choices[Math.round(p*(choices.length-1))]
        if(p<=0)return minimum
        if(p>=1)return maximum
        var v=logarithmic ? minimum*Math.pow(maximum/minimum,p) : minimum+p*(maximum-minimum)
        return Math.max(minimum,Math.min(maximum,Math.round(v/step)*step))
    }
    function valueText(v) {
        if(choiceLabels.length){var i=Math.round(position(v)*(choices.length-1));return choiceLabels[i]}
        return v.toFixed(decimals)+(unit.length?' '+unit:'')
    }
    Label { x: 10; y: 8; width: parent.width-20; text: root.label; font.pixelSize: 11; font.bold: true; color: Theme.color('#92adbe', backend.lightTheme); elide: Text.ElideRight }
    Label { x: 10; y: 27; width: parent.width-20; text: root.valueText(root.displayedNumber); color: root.accent; font.pixelSize: root.vertical ? 17 : 15; font.bold: true; horizontalAlignment: root.vertical ? Text.AlignHCenter : Text.AlignRight }
    Slider {
        id: slider
        objectName: root.controlId
        x: root.vertical ? Math.max(35,root.width*.45) : 10
        y: root.vertical ? 54 : 49
        width: root.vertical ? 36 : root.width-20
        height: root.vertical ? root.sliderHeight : 25
        orientation: root.vertical ? Qt.Vertical : Qt.Horizontal
        from: 0; to: 1; stepSize: root.choices.length ? 1/(root.choices.length-1) : root.logarithmic ? .005 : root.step/(root.maximum-root.minimum)
        Binding { target: slider; property: 'value'; value: root.position(root.number); when: !slider.pressed; restoreMode: Binding.RestoreNone }
        wheelEnabled: false
        FaderGestures {
            number: root.number; minimum: root.minimum; maximum: root.maximum
            choices: root.choices; wheelStep: root.wheelStep; choiceStride: root.wheelChoiceStride
            resetToZero: root.resetToZero
            onCommitted: value => root.committed(value)
        }
        onPressedChanged: if(!pressed)backend.flushControlView()
        onMoved: root.committed(root.decoded(value))
        Keys.onUpPressed: root.committed(root.decoded(Math.min(1,root.position(root.number)+slider.stepSize)))
        Keys.onDownPressed: root.committed(root.decoded(Math.max(0,root.position(root.number)-slider.stepSize)))
        Keys.onPressed: event => {
            if(event.key===Qt.Key_Home){root.committed(root.decoded(0));event.accepted=true}
            else if(event.key===Qt.Key_End){root.committed(root.decoded(1));event.accepted=true}
            else event.accepted=false
        }
        background: Rectangle {
            x: root.vertical ? (slider.width-width)/2 : slider.leftPadding
            y: root.vertical ? slider.topPadding : (slider.height-height)/2
            width: root.vertical ? 6 : slider.availableWidth
            height: root.vertical ? slider.availableHeight : 6
            color: Theme.color('#060f15', backend.lightTheme); border.color: Theme.color('#354a58', backend.lightTheme); radius: 3
            Rectangle { anchors.left: parent.left; anchors.bottom: parent.bottom; width: root.vertical ? parent.width : parent.width*slider.position; height: root.vertical ? parent.height*slider.position : parent.height; radius: 3; color: root.accent; opacity: .45 }
        }
        handle: Rectangle {
            x: root.vertical ? (slider.width-width)/2 : slider.leftPadding+slider.visualPosition*(slider.availableWidth-width)
            y: root.vertical ? slider.topPadding+slider.visualPosition*(slider.availableHeight-height) : (slider.height-height)/2
            width: root.vertical ? 30 : 16; height: root.vertical ? 12 : 22; radius: 3
            gradient: Gradient { GradientStop { position: 0; color: Theme.color('#c9dbe3', backend.lightTheme) } GradientStop { position: .5; color: Theme.color('#678191', backend.lightTheme) } GradientStop { position: 1; color: Theme.color('#aec8d5', backend.lightTheme) } }
            border.color: slider.activeFocus ? Theme.color('#8be8fa', backend.lightTheme) : root.accent
            Rectangle { anchors.centerIn: parent; width: parent.width-6; height: 1; color: Theme.color('#142534', backend.lightTheme) }
        }
        Accessible.name: root.label + ' slider'
        ToolTip.visible: hovered && root.hint.length>0; ToolTip.text: root.hint
    }
    Column {
        visible: root.vertical
        x: 8; y: 54; height: root.sliderHeight; width: 32
        Repeater { model: root.scaleDivisions; Label { required property int index; height: root.sliderHeight/root.scaleDivisions; text: root.choiceLabels.length ? (root.decoded(1-index/(root.scaleDivisions-1))===1000000 ? 'Limit' : root.decoded(1-index/(root.scaleDivisions-1)).toFixed(1)) : root.decoded(1-index/(root.scaleDivisions-1)).toFixed(root.decimals>0?1:0); font.pixelSize: 9; color: Theme.color('#688695', backend.lightTheme) } }
    }
    NumberField {
        controlId: root.controlId+'_number'
        visible: root.vertical && root.choiceLabels.length===0
        x: 10; y: 59+root.sliderHeight; width: parent.width-20; fieldHeight: 25
        number: root.displayedNumber; minimum: root.minimum; maximum: root.maximum; step: root.step; decimals: root.decimals
        onCommitted: value => root.committed(value)
    }
}
