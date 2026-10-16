import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme
Item {
    id: root
    required property int channelIndex
    property int rowGap: 6
    property var groups: {
        var links=backend.channelLinks; var result=[];
        var first=channelIndex<4?0:4; var end=channelIndex<4?4:12;
        for(var i=first;i<end;i++) {
            var info=links[i];
            if(info.linked && info.members[0]===i)result.push(info);
        }
        return result;
    }
    Repeater {
        model: root.groups
        Item {
            id: segment
            required property var modelData
            required property int index
            property bool member: modelData.members.indexOf(root.channelIndex)>=0
            property int first: modelData.members[0]
            property int last: modelData.members[modelData.members.length-1]
            property color accent: Theme.color(modelData.color,backend.lightTheme)
            opacity: hover.hovered?1:0.65
            visible: root.channelIndex>=first && root.channelIndex<=last
            x: 1+index*2; width: root.width-x; height: root.height
            Canvas {
                id: curve
                y: -root.rowGap/2; width: parent.width; height: root.height+root.rowGap
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onPaint: {
                    var ctx=getContext('2d');ctx.reset();
                    var mid=root.height/2+root.rowGap/2;
                    var top=root.channelIndex===segment.first;
                    var bottom=root.channelIndex===segment.last;
                    var x=1;var tip=width-1;var bend=Math.min(4,tip-x);
                    ctx.strokeStyle=segment.accent;ctx.lineWidth=1.5;
                    ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();
                    if(top) {
                        ctx.moveTo(tip,mid);ctx.lineTo(x+bend,mid);
                        ctx.quadraticCurveTo(x,mid,x,mid+bend);
                    } else ctx.moveTo(x,0);
                    if(bottom) {
                        ctx.lineTo(x,mid-bend);ctx.quadraticCurveTo(x,mid,x+bend,mid);ctx.lineTo(tip,mid);
                    } else ctx.lineTo(x,height);
                    if(segment.member && !top && !bottom) {ctx.moveTo(x,mid);ctx.lineTo(tip,mid);}
                    ctx.stroke();
                }
                Connections { target: segment
                    function onAccentChanged() { curve.requestPaint() }
                    function onModelDataChanged() { curve.requestPaint() }
                }
            }
            HoverHandler { id: hover }
            ToolTip.visible: hover.hovered
            ToolTip.text: modelData.description
        }
    }
}
