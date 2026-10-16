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
    signal committed(real value)
    WheelHandler {
        target: null
        property real remainder: 0
        onWheel: event => {
            event.accepted=true
            remainder+=event.angleDelta.y
            var steps=Math.trunc(remainder/120);remainder-=steps*120
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
        parent: root.parent
        target: null
        acceptedButtons: Qt.LeftButton
        gesturePolicy: TapHandler.DragThreshold
        onDoubleTapped: {
            if(root.resetToZero && root.minimum<=0 && root.maximum>=0){root.committed(0);backend.flushControlView()}
        }
    }
}
