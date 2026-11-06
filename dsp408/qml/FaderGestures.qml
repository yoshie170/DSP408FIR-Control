import QtQuick
Item {
    id: root
    anchors.fill: parent
    property real number: 0
    property real minimum: 0
    property real maximum: 1
    property real wheelStep: .1
    property var choices: []
    property int choiceStride: 1
    property bool resetToZero: false
    property bool horizontal: false
    property Item tapTarget: parent
    signal committed(real value)
    ScrollSteps { id: wheelSteps; pixelsPerStep: 4; horizontal: root.horizontal }
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        scrollGestureEnabled: true
        onWheel: event => {
            if(!root.horizontal && event.pixelDelta.y===0 && event.angleDelta.y===0 && event.pixelDelta.x!==0){event.accepted=false;return}
            event.accepted=true
            var steps=wheelSteps.take(event)
            if(!steps)return
            var value=root.number
            if(root.choices.length && root.wheelStep<=0){
                var best=0
                for(var i=1;i<root.choices.length;i++)if(Math.abs(root.choices[i]-value)<Math.abs(root.choices[best]-value))best=i
                value=root.choices[Math.max(0,Math.min(root.choices.length-1,best+steps*root.choiceStride))]
            } else value=Math.round((value+steps*root.wheelStep)*1000000)/1000000
            value=Math.max(root.minimum,Math.min(root.maximum,value))
            if(value!==root.number){root.committed(value);backend.flushControlView()}
        }
    }
    TapHandler {
        enabled: root.resetToZero
        parent: root.tapTarget
        target: null
        acceptedButtons: Qt.LeftButton
        gesturePolicy: TapHandler.DragThreshold
        onDoubleTapped: {
            if(root.resetToZero && root.minimum<=0 && root.maximum>=0){root.committed(0);backend.flushControlView()}
        }
    }
}
