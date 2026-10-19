import QtQuick
import "Theme.js" as Theme
Rectangle {
    id: root
    required property string section
    property var detail: {backend.revision;return backend.kneePreview(section)}
    visible: section!=='gate' && (detail.knee || 0)>0
    color: Theme.color('#10212b',backend.lightTheme); radius: 4; border.color: Theme.color('#526c79',backend.lightTheme)
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; preventStealing: true; onWheel: wheel=>wheel.accepted=true }
    Canvas {
        id: plot; objectName: 'knee_detail_canvas'; anchors.fill: parent; anchors.margins: 6
        property var preview: root.detail
        property int curvePaintCount: 0
        onPreviewChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: backend; function onThemeChanged(){plot.requestPaint()} }
        function px(value){return 6+(value-preview.low)/(preview.high-preview.low)*(width-12)}
        function py(value){return height-16-(value-preview.low)/(preview.high-preview.low)*(height-36)}
        onPaint: {
            var c=getContext('2d');c.reset();if(!preview.actual)return
            curvePaintCount++
            c.font="9px '"+backend.uiFontFamily+"'";c.fillStyle=Theme.color('#e7b458',backend.lightTheme)
            c.fillText('KNEE '+preview.knee.toFixed(1)+' dB',2,9)
            c.fillStyle='rgba(216,173,82,0.13)';c.fillRect(px(preview.threshold-preview.knee/2),16,px(preview.threshold+preview.knee/2)-px(preview.threshold-preview.knee/2),height-32)
            c.strokeStyle=Theme.color('#526c79',backend.lightTheme);c.lineWidth=1;c.beginPath();c.moveTo(px(preview.threshold),16);c.lineTo(px(preview.threshold),height-16);c.stroke()
            for(var line=0;line<2;line++){
                var values=line===0?preview.hard:preview.actual
                c.setLineDash(line===0?[3,3]:[]);c.strokeStyle=line===0?Theme.color('#91aebd',backend.lightTheme):Theme.color('#36b5d6',backend.lightTheme);c.lineWidth=line===0?1:2.3;c.beginPath()
                for(var i=0;i<values.length;i++){
                    var x=px(preview.low+i/120*(preview.high-preview.low)),y=py(Math.max(preview.low,Math.min(preview.high,values[i])))
                    if(!i)c.moveTo(x,y);else c.lineTo(x,y)
                }c.stroke()
            }
            c.setLineDash([]);c.fillStyle=Theme.color('#91aebd',backend.lightTheme);c.font="8px '"+backend.uiFontFamily+"'"
            c.fillText('16 dB · dashed: hard',2,height-2)
        }
    }
}
