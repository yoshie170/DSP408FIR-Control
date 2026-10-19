import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id: root
    property var currentData: backend.current
    function refreshView() {
        currentData=backend.current
        root.plotData=backend.crossoverComparisonPlot(root.includeEq);
    }
    Component.onCompleted: refreshView()
    onVisibleChanged: if(visible)refreshView()
    Connections { target: backend; function onChanged() {if(root.visible)root.refreshView()} }
    onIncludeEqChanged: if(visible)refreshView()
    property bool includeEq: true
    property var plotData: { backend.revision; return backend.crossoverComparisonPlot(includeEq) }
    property string cursorText: ''
    onPlotDataChanged: cursorText=''
    spacing: 7
    RowLayout {
        Layout.fillWidth: true
        Label { text: 'CROSSOVER + PEQ'; font.pixelSize: 16; font.bold: true; Layout.fillWidth: true }
        Label { text: root.currentData.name; color: Theme.color('#25bddb', backend.lightTheme); font.pixelSize: 11 }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 7
        ComboBox { enabled: backend.parameterEditingAllowed; objectName: 'xover_mode'; implicitHeight: 30; Layout.preferredWidth: 85; model: ['IIR','FIR']; currentIndex: model.indexOf(root.currentData.crossover_mode); onActivated: {backend.edit(backend.selected,'crossover_mode',model[currentIndex],-1);currentIndex=Qt.binding(()=>model.indexOf(root.currentData.crossover_mode))} }
        ConsoleCheck { objectName: 'xover_include_eq'; text: 'Include PEQ'; checked: root.includeEq; onClicked: root.includeEq=checked }
        Item { Layout.fillWidth: true }
        Label { text: 'White: current sum · dashed: selected outputs'; color: Theme.color('#819dad', backend.lightTheme); font.pixelSize: 10 }
    }
    Flow {
        objectName: 'xover_compare_flow'; Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; spacing: 3
        Label { text: 'COMPARE'; height: 24; verticalAlignment: Text.AlignVCenter; color: Theme.color('#86a4b7', backend.lightTheme); font.pixelSize: 10 }
        Repeater {
            model: 8
            ConsoleCheck {
                required property int index
                objectName: 'xover_compare_'+(index+4)
                compact: true; leftPadding: 1; rightPadding: 1
                property color traceColor: [Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme),Theme.color('#ff89c5', backend.lightTheme),Theme.color('#b8d6ee', backend.lightTheme),Theme.color('#d7b68c', backend.lightTheme)][index]
                text: 'OUT '+(index+1); enabled: backend.selected!==index+4
                checked: backend.xoverCompared.indexOf(index+4)>=0
                onClicked: backend.compareXover(index+4,checked)
                accent: traceColor
                contentItem: Text { text: parent.text; leftPadding: 24; color: parent.enabled?parent.traceColor:Theme.color('#718b9b', backend.lightTheme); font: parent.font; verticalAlignment: Text.AlignVCenter }
                ToolTip.visible: hovered; ToolTip.text: {backend.revision;return backend.channel(index+4).name}
            }
        }
    }
    Rectangle {
        objectName: 'xover_plot'
        property var curvesData: root.plotData
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: root.currentData.crossover_mode==='FIR'?128:160; Layout.preferredHeight: root.currentData.crossover_mode==='FIR'?160:240
        color: Theme.color('#09151c', backend.lightTheme); border.color: Theme.color('#2a4655', backend.lightTheme); radius: 6
        Canvas {
            id: plot
            Connections { target: backend; function onThemeChanged() {plot.requestPaint()} }
            anchors.fill: parent; anchors.margins: 12
            property var curvesData: root.plotData
            onCurvesDataChanged: requestPaint()
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            function px(hz) { return 36+Math.log(hz/backend.options.frequencyMin)/Math.log(backend.options.frequencyMax/backend.options.frequencyMin)*(width-49) }
            function py(db) { return 20+(18-Math.max(-60,Math.min(18,db)))/78*(height-42) }
            onPaint: {
                var c=getContext('2d');c.reset();c.font="9px '"+backend.uiFontFamily+"'"
                var gridStep=height-42<150?12:6
                for(var db=-60;db<=18;db+=gridStep){c.strokeStyle=db===0?Theme.color('#47606b', backend.lightTheme):Theme.color('#253a46', backend.lightTheme);c.lineWidth=1;c.beginPath();c.moveTo(36,py(db));c.lineTo(width-13,py(db));c.stroke();c.fillStyle=Theme.color('#8eaabb', backend.lightTheme);c.fillText(String(db),3,py(db)+3)}
                var ticks=[20,50,100,200,500,1000,2000,5000,10000,20000]
                for(var t=0;t<ticks.length;t++){var x=px(ticks[t]);c.strokeStyle=Theme.color('#253a46', backend.lightTheme);c.beginPath();c.moveTo(x,20);c.lineTo(x,height-22);c.stroke();c.fillStyle=Theme.color('#8eaabb', backend.lightTheme);c.fillText(ticks[t]>=1000?ticks[t]/1000+'k':String(ticks[t]),x-8,height-6)}
                for(var line=0;line<curvesData.traces.length;line++){
                    var trace=curvesData.traces[line];var combined=trace.label.indexOf('combined')>=0;c.strokeStyle=combined&&!trace.comparison?Theme.color('#e0f6ff', backend.lightTheme):Theme.color(trace.color,backend.lightTheme);c.lineWidth=combined?2.4:1.2;c.setLineDash(trace.comparison?[6,3]:combined?[]:[2,3]);c.beginPath()
                    for(var i=0;i<trace.values.length;i++){var y=py(trace.values[i]);var xx=36+i/(trace.values.length-1)*(width-49);if(i===0)c.moveTo(xx,y);else c.lineTo(xx,y)}c.stroke()
                }c.setLineDash([])
                for(var p=0;p<curvesData.crossings.length;p++){var point=curvesData.crossings[p];c.strokeStyle=Theme.color(point.color,backend.lightTheme)||Theme.color('#e8f2ff', backend.lightTheme);c.setLineDash([2,4]);c.beginPath();c.moveTo(px(point.hz),20);c.lineTo(px(point.hz),height-22);c.stroke();c.setLineDash([]);c.fillStyle=Theme.color(point.color,backend.lightTheme)||Theme.color('#ffffff', backend.lightTheme);c.beginPath();c.arc(px(point.hz),py(point.db),4,0,Math.PI*2);c.fill();if(p<3)c.fillText(point.hz.toFixed(0)+' Hz',Math.min(width-65,px(point.hz)+6),30+p*12)}
                c.fillStyle=Theme.color('#8eaabb', backend.lightTheme);c.fillText('dB',0,10)
                if(!curvesData.traces.length)c.fillText('FIR preview unavailable for the current settings / coefficients',45,height/2)
            }
            MouseArea {
                anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton
                onPositionChanged: mouse => {
                    var position=Math.max(0,Math.min(1,(mouse.x-36)/(plot.width-49)));var index=Math.round(position*240)
                    var hz=backend.options.frequencyMin*Math.pow(backend.options.frequencyMax/backend.options.frequencyMin,position);var totals=root.plotData.traces.filter(t=>t.label.indexOf('combined')>=0)
                    root.cursorText=hz.toFixed(1)+' Hz · '+totals.map(t=>t.label.replace(' · combined','')+': '+t.values[index].toFixed(2)+' dB').join(' / ')
                }
                onExited: root.cursorText=''
            }
        }
    }
    Flow {
        Layout.fillWidth: true; Layout.preferredHeight: implicitHeight; spacing: 9
        Repeater { model: root.plotData.traces; Label { required property var modelData; text: modelData.label; color: modelData.label.indexOf('combined')>=0&&!modelData.comparison?Theme.color('#e0f6ff', backend.lightTheme):Theme.color(modelData.color,backend.lightTheme); font.pixelSize: 10 } }
    }
    Label { objectName: 'xover_intersections'; text: root.cursorText.length ? root.cursorText : root.plotData.crossings.length ? 'Intersection: '+root.plotData.crossings.slice(0,3).map(p=>(p.label?p.label+': ':'')+p.hz.toFixed(1)+' Hz / '+p.db.toFixed(2)+' dB').join(' · ') : 'No distinct crossing in the displayed range'; color: Theme.color('#c5e4ed', backend.lightTheme); font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
    Repeater {
        model: ['hpf','lpf']
        RowLayout {
            required property string modelData
            Layout.fillWidth: true; spacing: 9; visible: root.currentData.crossover_mode==='IIR'
            ParameterFader { label: modelData==='hpf'?'High pass':'Low pass'; controlId: 'xover_'+modelData; number: root.currentData[modelData+'_hz']; minimum: backend.options.frequencyMin; maximum: backend.options.frequencyMax; logarithmic: true; step: 1; decimals: 1; unit: 'Hz'; Layout.fillWidth: true; onCommitted: value => backend.edit(backend.selected,modelData+'_hz',value,-1) }
            ComboBox { Layout.preferredWidth: 160; implicitHeight: 32; model: backend.options.crossover; currentIndex: model.indexOf(root.currentData[parent.modelData+'_type']); onActivated: backend.edit(backend.selected,parent.modelData+'_type',model[currentIndex],-1) }
            ConsoleCheck { text: 'Bypass'; checked: root.currentData[parent.modelData+'_bypass']; onClicked: backend.edit(backend.selected,parent.modelData+'_bypass',checked,-1) }
        }
    }
    FirPanel { enabled: backend.modelEditingAllowed; embedded: true; visible: backend.selected>=4 && root.currentData.crossover_mode==='FIR' && !backend.usbReadActive; Layout.fillWidth: true }
    FirCrossoverEditor { visible: backend.selected>=4 && root.currentData.crossover_mode==='FIR' && backend.usbReadActive; Layout.fillWidth: true }
    Label { text: root.plotData.notice; color: Theme.color('#7695a7', backend.lightTheme); font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
}
