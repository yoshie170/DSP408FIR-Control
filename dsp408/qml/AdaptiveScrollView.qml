import QtQuick
import QtQuick.Controls
ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth
    readonly property bool verticalOverflow: contentHeight>availableHeight+1
    readonly property bool horizontalOverflow: contentWidth>availableWidth+1
    ScrollBar.horizontal.policy: horizontalOverflow?ScrollBar.AsNeeded:ScrollBar.AlwaysOff
    ScrollBar.vertical.policy: verticalOverflow?ScrollBar.AsNeeded:ScrollBar.AlwaysOff
    Binding { target: root.contentItem; property: 'interactive'; value: root.verticalOverflow || root.horizontalOverflow; when: root.contentItem!==null }
    Binding { target: root.contentItem; property: 'boundsBehavior'; value: Flickable.StopAtBounds; when: root.contentItem!==null }
    Binding { target: root.contentItem; property: 'flickableDirection'; value: root.horizontalOverflow?(root.verticalOverflow?Flickable.HorizontalAndVerticalFlick:Flickable.HorizontalFlick):Flickable.VerticalFlick; when: root.contentItem!==null }
    Binding { target: root.contentItem; property: 'contentY'; value: root.contentItem?root.contentItem.originY:0; when: root.contentItem!==null && !root.verticalOverflow; restoreMode: Binding.RestoreNone }
    Binding { target: root.contentItem; property: 'contentX'; value: root.contentItem?root.contentItem.originX:0; when: root.contentItem!==null && !root.horizontalOverflow; restoreMode: Binding.RestoreNone }
}
