import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Rectangle {
    id: root
    required property string section
    property bool kneeHeld: false
    property var state: backend.current[section]
    // Original ipGate/ipComp/ipLimit axes, not telemetry or threshold limits.
    readonly property real low: -100
    readonly property real high: 20
    property var signalData: { backend.meters; backend.revision; backend.dynamicsDisplayEnabled; return backend.dynamicsSample(section) }
    property var curve: { backend.revision; return backend.transferCurve(section,low,high) }
    property bool displayActive: false
    property string presentationReason: ''
    property string sampleContext: ''
    property bool interpolate: false
    property real displayInput: low
    readonly property real displayOutput: {
        backend.revision
        return displayActive ? backend.dynamicsOutput(section,displayInput) : low
    }
    readonly property bool pointInRange: displayInput>=low && displayInput<=high && displayOutput>=low && displayOutput<=high
    function refreshSample(snap, freshnessOnly) {
        var current=backend.dynamicsSample(section)
        var key=backend.selected+':'+section+':'+current.source
        if(!freshnessOnly) {
            interpolate=displayActive && sampleContext===key && !snap
            sampleContext=key
        }
        displayActive=visible && current.available===true && isFinite(current.input) && isFinite(current.output) && isFinite(current.reduction)
        presentationReason=current.reason
        if(displayActive && !freshnessOnly)displayInput=current.input
    }
    onSignalDataChanged: refreshSample(false)
    onVisibleChanged: refreshSample(true)
    Component.onCompleted: refreshSample(true)
    Behavior on displayInput {
        enabled: root.interpolate && root.displayActive
        NumberAnimation { duration: 90; easing.type: Easing.Linear }
    }
    // Watch freshness only. No transport polling and no Canvas repaint.
    Timer { interval: 100; repeat: true; running: root.visible && root.signalData.available; onTriggered: root.refreshSample(false,true) }
    color: Theme.color('#09151c', backend.lightTheme); radius: 6; border.color: Theme.color('#2a424f', backend.lightTheme)
    Canvas {
        id: graph
            Connections { target: backend; function onThemeChanged() {graph.requestPaint()} }
        objectName: 'dynamics_static_'+root.section
        property int paintCount: 0
        anchors.fill: parent; anchors.margins: 12
        property var values: root.curve
        property var currentState: root.state
        onValuesChanged: requestPaint()
        onCurrentStateChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        function px(v) { return 35+(v-root.low)/(root.high-root.low)*(width-48) }
        function py(v) { return height-26-(v-root.low)/(root.high-root.low)*(height-42) }
        function clamp(v) { return Math.max(root.low,Math.min(root.high,v)) }
        onPaint: {
            paintCount++
            var c=getContext('2d');c.reset();c.font="9px 'Segoe UI'"
            for(var value=root.low;value<=root.high;value+=20) {
                c.strokeStyle=value===0?Theme.color('#405866', backend.lightTheme):Theme.color('#20343e', backend.lightTheme);c.lineWidth=1;c.beginPath()
                c.moveTo(px(value),16);c.lineTo(px(value),height-26)
                c.moveTo(35,py(value));c.lineTo(width-13,py(value));c.stroke()
                c.fillStyle=Theme.color('#91aebd', backend.lightTheme);c.fillText(String(value),2,py(value)+3);c.fillText(String(value),px(value)-7,height-12)
            }
            if(root.section!=='gate') {
                c.beginPath();c.moveTo(px(root.low),py(root.low));c.lineTo(px(root.high),py(root.high))
                for(var i=values.length-1;i>=0;i--)c.lineTo(px(root.low+i/(values.length-1)*(root.high-root.low)),py(clamp(values[i])))
                c.closePath();c.fillStyle='rgba(185,146,36,0.12)';c.fill()
            }
            c.strokeStyle=Theme.color('#526c79', backend.lightTheme);c.setLineDash([4,4]);c.beginPath()
            c.moveTo(px(root.low),py(root.low));c.lineTo(px(root.high),py(root.high));c.stroke();c.setLineDash([])
            var threshold=root.state.threshold
            if(root.section!=='gate' && root.state.knee>0){
                var left=Math.max(35,px(threshold-root.state.knee/2)),right=Math.min(width-13,px(threshold+root.state.knee/2))
                c.fillStyle='rgba(216,173,82,0.13)';c.fillRect(left,16,Math.max(0,right-left),height-42)
            }
            c.strokeStyle=Theme.color('#d8ad52', backend.lightTheme);c.setLineDash([5,4]);c.beginPath()
            c.moveTo(35,py(threshold));c.lineTo(width-13,py(threshold))
            c.moveTo(px(threshold),16);c.lineTo(px(threshold),height-26);c.stroke();c.setLineDash([])
            c.fillStyle=Theme.color('#f6c65b', backend.lightTheme);c.fillText('T '+threshold.toFixed(1)+' dB',Math.max(38,Math.min(width-90,px(threshold)+6)),22)
            c.strokeStyle=root.section==='gate'?Theme.color('#53db9f', backend.lightTheme):Theme.color('#36b5d6', backend.lightTheme);c.lineWidth=2.5;c.beginPath()
            for(var j=0;j<values.length;j++) {
                var x=root.low+j/(values.length-1)*(root.high-root.low),y=clamp(values[j])
                if(j===0)c.moveTo(px(x),py(y));else c.lineTo(px(x),py(y))
            }c.stroke()
            c.fillStyle=Theme.color('#f6c65b', backend.lightTheme);c.beginPath()
            c.arc(px(threshold),py(clamp(backend.dynamicsOutput(root.section,threshold))),3.5,0,2*Math.PI);c.fill()
            c.fillStyle=Theme.color('#92afc0', backend.lightTheme);c.fillText('OUT dB',0,9);c.fillText('IN dB',width-46,height-1)
        }
        Item {
            id: operatingPoint
            objectName: 'dynamics_point_'+root.section
            anchors.fill: parent
            visible: root.displayActive && root.pointInRange
            readonly property real pointX: graph.px(graph.clamp(root.displayInput))
            readonly property real pointY: graph.py(graph.clamp(root.displayOutput))
            Rectangle { x: 35; y: operatingPoint.pointY; width: Math.max(0,operatingPoint.pointX-35); height: 1; color: Theme.color('#4045cce6', backend.lightTheme) }
            Rectangle { x: operatingPoint.pointX; y: operatingPoint.pointY; width: 1; height: Math.max(0,parent.height-26-operatingPoint.pointY); color: Theme.color('#4045cce6', backend.lightTheme) }
            Rectangle { x: operatingPoint.pointX-10; y: operatingPoint.pointY-10; width: 20; height: 20; radius: 10; color: Theme.color('#2245cce6', backend.lightTheme) }
            Rectangle { x: operatingPoint.pointX-6; y: operatingPoint.pointY-6; width: 12; height: 12; radius: 6; color: Theme.color('#5045cce6', backend.lightTheme) }
            Rectangle { x: operatingPoint.pointX-3.5; y: operatingPoint.pointY-3.5; width: 7; height: 7; radius: 3.5; color: Theme.color('#87efff', backend.lightTheme); border.color: Theme.color('#d7fbff', backend.lightTheme) }
        }
        MouseArea {
            anchors.fill: parent
            function change(x) { var value=root.low+(x-35)/(width-48)*(root.high-root.low);backend.edit(backend.selected,root.section+'.threshold',Math.round(Math.max(-90,Math.min(root.section==='gate'?0:20,value))*2)/2,-1) }
            onPressed: mouse => change(mouse.x)
            onPositionChanged: mouse => {if(pressed)change(mouse.x)}
        }
        KneeDetail {
            objectName: 'knee_detail_'+root.section; section: root.section
            visible: root.kneeHeld && root.section!=='gate'
            x: 45; y: 22; width: Math.min(174,parent.width*.42); height: Math.min(100,parent.height-48)
        }
    }
}
