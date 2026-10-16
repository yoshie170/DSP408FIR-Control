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
            // Reuse a rail for disjoint spans; crossing groups retain separate lanes.
            property int lane: {
                var n=0;
                for(var i=0;i<index;i++) {
                    var g=root.groups[i].members;
                    if(g[g.length-1]>=first)n++;
                }
                return n;
            }
            property real badgeOffset: {
                var center=(first+last)/2;var count=0;var rank=0;
                for(var i=0;i<root.groups.length;i++) {
                    var g=root.groups[i].members;
                    if((g[0]+g[g.length-1])/2===center) {if(i<index)rank++;count++;}
                }
                return (rank-(count-1)/2)*20;
            }
            opacity: hover.hovered?1:0.9
            visible: root.channelIndex>=first && root.channelIndex<=last
            x: 0; width: root.width; height: root.height
            Canvas {
                id: curve
                // Each row paints its own slice, including half of a badge in the gap.
                // This keeps scrolling/clipping and every existing card rectangle intact.
                y: -root.rowGap/2; width: 26; height: root.height+root.rowGap
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onPaint: {
                    var ctx=getContext('2d');ctx.reset();
                    var mid=root.height/2+root.rowGap/2;
                    var top=root.channelIndex===segment.first;
                    var bottom=root.channelIndex===segment.last;
                    var x=8.5+segment.lane*2;var tip=Math.max(12,x+2);var bend=Math.min(3,tip-x);
                    ctx.strokeStyle=segment.accent;ctx.lineWidth=1.25;
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
                    var cy=mid+((segment.first+segment.last)/2-root.channelIndex)*(root.height+root.rowGap)+segment.badgeOffset;
                    if(cy+12>=0 && cy-12<=height) {
                        // Keep the badge within the fixed gutter, including crossing groups.
                        ctx.save();ctx.beginPath();ctx.rect(0,0,17,height);ctx.clip();ctx.translate(8.5,cy);
                        // Small, low opacity rings provide a restrained halo, no shader.
                        ctx.strokeStyle=segment.accent;ctx.globalAlpha=0.045;ctx.lineWidth=3;
                        ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.stroke();
                        ctx.globalAlpha=0.09;ctx.lineWidth=2;
                        ctx.beginPath();ctx.arc(0,0,9,0,Math.PI*2);ctx.stroke();
                        ctx.globalAlpha=1;ctx.fillStyle='#10232f';ctx.strokeStyle=segment.accent;ctx.lineWidth=1;
                        ctx.beginPath();ctx.arc(0,0,8.25,0,Math.PI*2);ctx.fill();ctx.stroke();
                        ctx.rotate(-Math.PI/4);ctx.strokeStyle='#e0f6f4';ctx.lineWidth=1.1;
                        function link(left) {
                            var top=-2.1;var w=7;var h=4.2;var r=2.1;
                            ctx.beginPath();ctx.moveTo(left+r,top);ctx.lineTo(left+w-r,top);
                            ctx.quadraticCurveTo(left+w,top,left+w,top+r);
                            ctx.quadraticCurveTo(left+w,top+h,left+w-r,top+h);
                            ctx.lineTo(left+r,top+h);ctx.quadraticCurveTo(left,top+h,left,top+r);
                            ctx.quadraticCurveTo(left,top,left+r,top);ctx.stroke();
                        }
                        link(-5.5);link(-1.5);ctx.restore();
                    }
                }
                Connections { target: segment
                    function onAccentChanged() { curve.requestPaint() }
                    function onModelDataChanged() { curve.requestPaint() }
                    function onLaneChanged() { curve.requestPaint() }
                    function onBadgeOffsetChanged() { curve.requestPaint() }
                }
            }
            HoverHandler { id: hover }
            ToolTip.visible: hover.hovered
            ToolTip.text: modelData.description
        }
    }
}
