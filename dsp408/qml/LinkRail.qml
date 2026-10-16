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
            required property var modelData
            required property int index
            property bool member: modelData.members.indexOf(root.channelIndex)>=0
            property int first: modelData.members[0]
            property int last: modelData.members[modelData.members.length-1]
            property color accent: Theme.color(modelData.color,backend.lightTheme)
            visible: root.channelIndex>=first && root.channelIndex<=last
            x: 2+index*3; width: root.width-x; height: root.height
            Rectangle {
                y: root.channelIndex===parent.first?root.height/2:-root.rowGap/2
                width: 2; radius: 1
                height: (root.channelIndex===parent.last?root.height/2:root.height+root.rowGap/2)-y
                color: parent.accent
            }
            Rectangle { visible: parent.member; y: root.height/2-1; width: parent.width; height: 2; radius: 1; color: parent.accent }
            HoverHandler { id: hover }
            ToolTip.visible: hover.hovered
            ToolTip.text: modelData.description
        }
    }
}
