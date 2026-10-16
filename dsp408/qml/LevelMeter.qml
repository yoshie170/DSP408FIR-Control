import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Item {
    id: root
    property real level: 0
    property real peak: 0
    property real db: -100
    property string readingText: ''
    property bool showScale: false
    property bool horizontal: false
    property string caption: 'Level meter'
    property string indicatorKind: ''
    property bool reductionActive: false
    property real reductionDb: 0
    // Fast attack and short release interpolate ONLY received values; silence,
    // stale data and disconnect clear immediately. No telemetry polling here.
    property real displayedLevel: level
    Behavior on displayedLevel {
        enabled: backend.meterReadingsAvailable && root.level>0
        NumberAnimation { duration: root.level>root.displayedLevel?35:110; easing.type: Easing.OutCubic }
    }
    property int headerHeight: !horizontal && indicatorKind.length ? 12 : 0
    readonly property real axisWidth: Math.max(0,bar.width-2)
    readonly property var scaleTicks: horizontal?(showScale?(bar.width<160?[-50,-10,0,12]:[-50,-20,-10,-5,0,5,12]):[]):showScale?[-50,-20,-10,-5,0,5,12]:[-50,-10,0,12]
    function position(value) { var bins=backend.meterBreakpoints;if(value<=bins[0])return 0;for(var i=1;i<bins.length;i++)if(value<=bins[i])return (i-1+(value-bins[i-1])/(bins[i]-bins[i-1]))/8;return 1 }
    implicitWidth: horizontal?140:showScale ? 55 : 37
    implicitHeight: horizontal?(showScale?26:12):90
    Rectangle {
        id: bar
        objectName: 'meter_bar'
        x: 0; y: root.headerHeight; width: root.horizontal ? Math.max(1,root.width-(root.indicatorKind==='COMP'?18:root.indicatorKind.length?34:0)) : root.showScale ? 14 : 11; height: root.horizontal && root.showScale?10:parent.height-root.headerHeight
        color: Theme.color('#07131a', backend.lightTheme); border.color: Theme.color('#36515d', backend.lightTheme); radius: 2
        Item {
            id: fillClip
            clip: true
            x: 1; y: root.horizontal?1:1+(1-Math.max(0,Math.min(1,root.displayedLevel)))*(bar.height-2)
            width: root.horizontal?Math.max(0,Math.min(1,root.displayedLevel))*(bar.width-2):bar.width-2
            height: root.horizontal?bar.height-2:Math.max(0,Math.min(1,root.displayedLevel))*(bar.height-2)
            Rectangle {
                objectName: 'meter_solid_fill'
                width: bar.width-2; height: bar.height-2
                y: root.horizontal?0:-(1-Math.max(0,Math.min(1,root.displayedLevel)))*(bar.height-2)
                gradient: Gradient {
                    orientation: root.horizontal?Gradient.Horizontal:Gradient.Vertical
                    GradientStop { position: 0; color: root.horizontal?Theme.color('#00b83f', backend.lightTheme):Theme.color('#ed4138', backend.lightTheme) }
                    GradientStop { position: root.horizontal?root.position(0)-.04:1-root.position(12); color: root.horizontal?Theme.color('#27d967', backend.lightTheme):Theme.color('#ed4138', backend.lightTheme) }
                    GradientStop { position: root.horizontal?root.position(0):1-root.position(0); color: Theme.color('#e5d72a', backend.lightTheme) }
                    GradientStop { position: root.horizontal?root.position(12):1-root.position(0)+.04; color: root.horizontal?Theme.color('#ed4138', backend.lightTheme):Theme.color('#27d967', backend.lightTheme) }
                    GradientStop { position: 1; color: root.horizontal?Theme.color('#ed4138', backend.lightTheme):Theme.color('#00b83f', backend.lightTheme) }
                }
            }
        }
        Rectangle { x: root.horizontal?Math.max(1,Math.min(bar.width-2,1+root.peak*root.axisWidth)):0; width: root.horizontal?2:parent.width; height: root.horizontal?parent.height:2; y: root.horizontal?0:Math.max(0,Math.min(parent.height-2,(1-root.peak)*parent.height)); color: Theme.color('#ebf8ff', backend.lightTheme); visible: root.peak>0 }
    }
    Row {
        visible: root.indicatorKind.length>0; spacing: 3
        x: root.horizontal?bar.width+4:0; y: root.horizontal?(bar.height-10)/2:0
        Rectangle {
            objectName: 'own_reduction_indicator'
            width: root.indicatorKind==='COMP'?14:30; height: 10; radius: 2
            color: root.reductionActive?Theme.color('#ffa346', backend.lightTheme):Theme.color('#392b1f', backend.lightTheme); border.color: root.reductionActive?Theme.color('#ffcc6c', backend.lightTheme):Theme.color('#65503b', backend.lightTheme)
            Label { anchors.centerIn: parent; text: root.indicatorKind==='COMP'?'C':'LIM'; font.pixelSize: 8; font.bold: true; color: root.reductionActive?Theme.color('#241506', backend.lightTheme):Theme.color('#a28b72', backend.lightTheme) }
        }
    }
    Repeater {
        model: root.scaleTicks
        Item {
            id: tick
            required property int modelData
            objectName: 'meter_tick_'+modelData
            x: root.horizontal?1+root.position(modelData)*root.axisWidth:bar.width+1
            y: root.horizontal?bar.y+bar.height:bar.y+Math.max(0,Math.min(bar.height-1,(1-root.position(modelData))*bar.height))
            Rectangle { width: root.horizontal?1:root.showScale ? 5 : 3; height: root.horizontal?3:1; color: Theme.color('#8caaba', backend.lightTheme) }
            Label { x: root.horizontal?Math.max(-tick.x,Math.min(-12,bar.width-24-tick.x)):root.showScale?8:5; y: root.horizontal?3:-5; width: root.horizontal?24:implicitWidth; horizontalAlignment: root.horizontal?Text.AlignHCenter:Text.AlignLeft; text: (modelData>0?'+':'')+modelData; color: Theme.color('#bed1df', backend.lightTheme); font.pixelSize: root.horizontal?8:root.showScale?10:8; font.bold: modelData===0 }
        }
    }
    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; ToolTip.visible: containsMouse; ToolTip.text: root.caption+' · '+(backend.meterReadingsAvailable?(root.readingText.length?root.readingText:root.db.toFixed(1))+' dB\n'+(root.reductionActive?'Dynamics active':'Dynamics inactive'):'No live signal reading') }
    Accessible.name: root.caption+' '+backend.meterSource+' meter'
}
