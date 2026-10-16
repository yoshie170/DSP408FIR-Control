import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme
Item {
    id: root
    required property var sourceView
    required property var strips
    property int firstChannel: 0
    property int channelCount: 4
    readonly property int gutterBleed: 10
    readonly property real scrollY: sourceView.contentItem ? sourceView.contentItem.contentY : 0
    readonly property point viewportOrigin: {
        sourceView.x; sourceView.y; sourceView.parent.x; sourceView.parent.y;
        return sourceView.mapToItem(parent,0,0);
    }
    x: viewportOrigin.x-gutterBleed; y: viewportOrigin.y
    width: sourceView.width+gutterBleed; height: sourceView.height
    clip: true; z: 2
    property var groups: {
        var links=backend.channelLinks;var result=[];
        for(var i=firstChannel;i<firstChannel+channelCount;i++) {
            var info=links[i];
            if(info.linked && info.members[0]===i)result.push(info);
        }
        return result;
    }
    function center(channel) {
        var strip=strips.itemAt(channel-firstChannel);
        if(!strip)return Qt.point(0,0);
        // Explicit dependencies keep the overlay aligned on scroll and relayout.
        scrollY;strip.x;strip.y;strip.height;viewportOrigin;
        return strip.mapToItem(root,0,strip.height/2);
    }
    property int layoutRevision: 0
    function trackGeometry(index) {
        layoutRevision;
        var info=groups[index];var members=info.members;
        var first=center(members[0]);var last=center(members[members.length-1]);
        var lane=0;var maxLane=0;var lanes=[];
        for(var i=0;i<groups.length;i++) {
            var used=[];var start=groups[i].members[0];
            for(var j=0;j<i;j++) {
                var prior=groups[j].members;
                if(prior[prior.length-1]>=start)used[lanes[j]]=true;
            }
            var free=0;while(used[free])free++;
            lanes[i]=free;
            if(i===index)lane=free;
            maxLane=Math.max(maxLane,free);
        }
        // Two crossing groups get6px-separated rails; disjoint groups reuse one.
        var x=first.x+5.5-lane*6/Math.max(1,maxLane);
        // A badge belongs in a row gap, away from another group's branch.
        var next=center(members[0]+1);
        return {info:info,first:first,last:last,x:x,tip:first.x+11,badgeY:(first.y+next.y)/2};
    }
    function repaint() {
        Qt.callLater(function() { root.layoutRevision++;paint.requestPaint() });
    }
    onGroupsChanged: repaint()
    onScrollYChanged: repaint()
    onViewportOriginChanged: repaint()
    onWidthChanged: repaint()
    onHeightChanged: repaint()
    Component.onCompleted: repaint()
    Connections { target: root.strips; function onItemAdded() { root.repaint() } }
    Connections { target: backend; function onThemeChanged() { root.repaint() } }
    Canvas {
        id: paint
        anchors.fill: parent
        onPaint: {
            var ctx=getContext('2d');ctx.reset();
            for(var n=0;n<root.groups.length;n++) {
                var track=root.trackGeometry(n);var info=track.info;var members=info.members;
                var first=track.first;var last=track.last;
                if(!first.x || last.y<=first.y)continue;
                var x=track.x;var tip=track.tip;var r=3;
                // A crossing branch passes over a small gap in the other rail.
                // This avoids a false junction between independent Link groups.
                for(var k=0;k<members.length;k++) {
                    var peer=root.center(members[k]);
                    for(var prior=0;prior<n;prior++) {
                        var back=root.trackGeometry(prior);
                        if(back.x>x && back.x<tip && peer.y>back.first.y && peer.y<back.last.y)
                            ctx.clearRect(back.x-4,peer.y-4,8,8);
                    }
                }
                var accent=Theme.color(info.color,backend.lightTheme);
                ctx.strokeStyle=accent;ctx.lineWidth=1.75;
                ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();
                ctx.moveTo(tip,first.y);ctx.lineTo(x+r,first.y);
                ctx.quadraticCurveTo(x,first.y,x,first.y+r);
                ctx.lineTo(x,last.y-r);ctx.quadraticCurveTo(x,last.y,x+r,last.y);
                ctx.lineTo(tip,last.y);
                for(var k=1;k<members.length-1;k++) {
                    var peer=root.center(members[k]);ctx.moveTo(x,peer.y);ctx.lineTo(tip,peer.y);
                }
                ctx.save();ctx.globalAlpha=0.065;ctx.lineWidth=6;ctx.stroke();
                ctx.globalAlpha=0.14;ctx.lineWidth=3.5;ctx.stroke();ctx.restore();ctx.stroke();
                var cy=track.badgeY;
                ctx.save();ctx.translate(x,cy);
                ctx.strokeStyle=accent;ctx.globalAlpha=0.08;ctx.lineWidth=3;
                ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.stroke();
                ctx.globalAlpha=0.15;ctx.lineWidth=2;
                ctx.beginPath();ctx.arc(0,0,9,0,Math.PI*2);ctx.stroke();
                ctx.globalAlpha=1;ctx.fillStyle='#10232f';ctx.strokeStyle=accent;ctx.lineWidth=1;
                ctx.beginPath();ctx.arc(0,0,8.25,0,Math.PI*2);ctx.fill();ctx.stroke();
                ctx.rotate(-Math.PI/4);ctx.strokeStyle='#e0f6f4';ctx.lineWidth=1.1;
                function link(left) {
                    var top=-2.1;var w=7;var h=4.2;var rad=2.1;
                    ctx.beginPath();ctx.moveTo(left+rad,top);ctx.lineTo(left+w-rad,top);
                    ctx.quadraticCurveTo(left+w,top,left+w,top+rad);
                    ctx.quadraticCurveTo(left+w,top+h,left+w-rad,top+h);
                    ctx.lineTo(left+rad,top+h);ctx.quadraticCurveTo(left,top+h,left,top+rad);
                    ctx.quadraticCurveTo(left,top,left+rad,top);ctx.stroke();
                }
                link(-5.5);link(-1.5);ctx.restore();
            }
        }
    }
    Repeater {
        model: root.groups
        Item {
            required property var modelData
            required property int index
            property var track: root.trackGeometry(index)
            x: track.x-2; y: track.first.y; width: 4; height: Math.max(0,track.last.y-track.first.y)
            HoverHandler { id: hover }
            ToolTip.visible: hover.hovered
            ToolTip.text: modelData.description
        }
    }
}
