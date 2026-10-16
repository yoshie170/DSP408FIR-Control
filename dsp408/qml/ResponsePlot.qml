import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: root
    property var currentData: backend.current
    property bool phase: false
    property var curveData: backend.curve
    property bool channelView: false
    property var channelResponse: ({values:[],available:false})
    property bool showBands: true
    property bool showBandCurves: true
    property bool fineQ: false
    onShowBandCurvesChanged: plot.requestPaint()
    property int band: 0
    property var spectrum: []
    property var comparisons: []
    property real amplitudeLimit: showBands ? 12 : 18
    property real axisLimit: phase ? 180 : amplitudeLimit
    property real magnitudeMinimum: -amplitudeLimit
    property real magnitudeMaximum: amplitudeLimit
    property real magnitudeStep: amplitudeLimit/3
    property int magnitudeDecimals: 0
    property real axisMinimum: phase ? -180 : magnitudeMinimum
    property real axisMaximum: phase ? 180 : magnitudeMaximum
    property real axisStep: phase ? 60 : magnitudeStep
    onAxisMinimumChanged: plot.requestPaint()
    onAxisMaximumChanged: plot.requestPaint()
    onAxisStepChanged: plot.requestPaint()
    onAxisLimitChanged: plot.requestPaint()
    property real selectedNodeRadius: 11
    onBandChanged: plot.requestPaint()
    signal bandSelected(int index)
    color: Theme.color('#09151c', backend.lightTheme); radius: 5; border.color: Theme.color('#2d4655', backend.lightTheme)
    Canvas {
        id: plot
        objectName: root.showBands ? 'peq_response_canvas' : 'coefficient_response_canvas'
            Connections { target: backend; function onThemeChanged() {plot.requestPaint()} }
        anchors.fill: parent; anchors.margins: 12
        property var points: root.channelView ? root.channelResponse.values : root.curveData
        property var eqPoints: root.curveData
        onEqPointsChanged: requestPaint()
        property var traces: root.showBands ? backend.bandCurves : []
        property var rta: root.spectrum
        property var overlays: root.comparisons
        onOverlaysChanged: requestPaint()
        onRtaChanged: requestPaint()
        onTracesChanged: requestPaint()
        property var bands: root.showBands ? root.currentData.filters : []
        onPointsChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        function plotWidth() { return width-(rta.length?88:root.phase && root.showBands?84:48) }
        function fx(f) { return 36+Math.log(f/backend.options.frequencyMin)/Math.log(backend.options.frequencyMax/backend.options.frequencyMin)*plotWidth() }
        function gy(g) { return 20+(root.axisMaximum-g)/(root.axisMaximum-root.axisMinimum)*(height-42) }
        // Magnitude uses one dB axis for nodes, bands and the channel sum.
        // Only Phase needs a separate gain axis for editing nodes.
        function nodeY(g) { return root.phase ? 20+(root.amplitudeLimit-g)/(2*root.amplitudeLimit)*(height-42) : gy(g) }
        function gainAtY(y) { return root.phase ? root.amplitudeLimit-(y-20)/(height-42)*2*root.amplitudeLimit : root.axisMaximum-(y-20)/(height-42)*(root.axisMaximum-root.axisMinimum) }
        function bounded(g) { return Math.max(root.axisMinimum,Math.min(root.axisMaximum,g)) }
        function eqY(g) { return gy(bounded(g)) }
        onPaint: {
            var ctx=getContext('2d');ctx.reset();var left=36,top=20,w=plotWidth(),h=height-42
            ctx.font="10px 'Segoe UI'";ctx.fillStyle=Theme.color('#8aa2b3', backend.lightTheme)
            var gridCount=Math.floor((root.axisMaximum-root.axisMinimum)/root.axisStep)
            for(var grid=0;grid<=gridCount;grid++) {var g=root.axisMinimum+grid*root.axisStep;var zero=Math.abs(g)<root.axisStep*.001;var y=gy(g);ctx.strokeStyle=zero?Theme.color('#406376', backend.lightTheme):Theme.color('#233744', backend.lightTheme);ctx.setLineDash(zero?[3,4]:[]);ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(left+w,y);ctx.stroke();ctx.fillText((zero?0:g).toFixed(root.phase?0:root.magnitudeDecimals),0,y+3)}
            ctx.setLineDash([])
            var ticks=[20,50,100,200,500,1000,2000,5000,10000,20000]
            for(var j=0;j<ticks.length;j++){var x=fx(ticks[j]);ctx.strokeStyle=Theme.color('#233744', backend.lightTheme);ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,top+h);ctx.stroke();ctx.fillText(ticks[j]>=1000?ticks[j]/1000+'k':String(ticks[j]),x-9,top+h+16)}
            if(root.phase && root.showBands){
                ctx.fillStyle=Theme.color('#8aa2b3',backend.lightTheme);ctx.fillText('points: gain dB',Math.max(left,left+w-85),10)
                for(var gain=-12;gain<=12;gain+=4)ctx.fillText((gain>0?'+':'')+gain,left+w+8,nodeY(gain)+3)
            }
            var colors=[Theme.color('#38aeff', backend.lightTheme),Theme.color('#48e77c', backend.lightTheme),Theme.color('#ff6774', backend.lightTheme),Theme.color('#c66cf5', backend.lightTheme),Theme.color('#f9cf42', backend.lightTheme),Theme.color('#40d9c4', backend.lightTheme),Theme.color('#ed934b', backend.lightTheme),Theme.color('#a5d76b', backend.lightTheme),Theme.color('#aa99ef', backend.lightTheme)]
            if(rta.length) {
                ctx.beginPath();ctx.moveTo(left,top+h)
                for(var bin=0;bin<rta.length;bin++)ctx.lineTo(left+bin/(rta.length-1)*w,top-rta[bin]/90*h)
                ctx.lineTo(left+w,top+h);ctx.closePath();ctx.fillStyle=Theme.color('#7b91a4', backend.lightTheme);ctx.globalAlpha=.25;ctx.fill();ctx.globalAlpha=1
                ctx.strokeStyle=Theme.color('#91aabc', backend.lightTheme);ctx.lineWidth=1;ctx.beginPath()
                for(bin=0;bin<rta.length;bin++){var ry=top-rta[bin]/90*h;if(bin===0)ctx.moveTo(left,ry);else ctx.lineTo(left+bin/(rta.length-1)*w,ry)}ctx.stroke()
                ctx.fillStyle=Theme.color('#8baabd', backend.lightTheme);ctx.fillText('RTA',left+w-85,12)
                for(var db=-90;db<=0;db+=15)ctx.fillText(String(db),left+w+8,top-db/90*h+3)
            }
            if(root.showBands && root.showBandCurves && !root.phase)for(var t=0;t<traces.length;t++) {
                var tr=traces[t];if(!tr.length)continue
                // Unity-gain bands otherwise repeatedly overpaint the 0 dB reference.
                if(tr.every(v=>Math.abs(v)<.001))continue
                ctx.beginPath();ctx.moveTo(left,eqY(0))
                for(var n=0;n<tr.length;n++)ctx.lineTo(left+n/(tr.length-1)*w,eqY(tr[n]))
                ctx.lineTo(left+w,eqY(0));ctx.closePath();ctx.fillStyle=colors[t];ctx.globalAlpha=t===root.band?.16:.07;ctx.fill()
                ctx.strokeStyle=colors[t];ctx.globalAlpha=t===root.band?.95:.70;ctx.lineWidth=t===root.band?1.8:1.3
                ctx.setLineDash([3,3])
                ctx.beginPath()
                for(n=0;n<tr.length;n++){var ty=eqY(tr[n]);if(n===0)ctx.moveTo(left,ty);else ctx.lineTo(left+n/(tr.length-1)*w,ty)}ctx.stroke()
            }
            ctx.globalAlpha=1;ctx.setLineDash([])
            for(var o=0;o<overlays.length;o++){
                var trace=overlays[o];ctx.strokeStyle=Theme.color(trace.color,backend.lightTheme);ctx.lineWidth=2;ctx.setLineDash([6,3]);ctx.beginPath()
                for(var i=0;i<trace.values.length;i++){var yy=eqY(trace.values[i]);if(i===0)ctx.moveTo(left,yy);else ctx.lineTo(left+i/(trace.values.length-1)*w,yy)}ctx.stroke()
            }ctx.setLineDash([])
            if(root.channelView){
                ctx.strokeStyle=Theme.color('#25bddb',backend.lightTheme);ctx.lineWidth=1.5;ctx.setLineDash([2,3]);ctx.beginPath()
                for(i=0;i<eqPoints.length;i++){yy=eqY(eqPoints[i]);if(i===0)ctx.moveTo(left,yy);else ctx.lineTo(left+i/(eqPoints.length-1)*w,yy)}ctx.stroke();ctx.setLineDash([])
                if(!root.channelResponse.available){ctx.fillStyle=Theme.color('#e2bd72',backend.lightTheme);ctx.fillText('XOVER response unavailable · PEQ remains editable',left+4,top+h-8)}
            }
            // Draw the combined response last, with a dark outline so coincident
            // band and comparison traces cannot disguise the main curve.
            ctx.save();ctx.beginPath();ctx.rect(left,top,w,h);ctx.clip();ctx.lineJoin='round';ctx.beginPath()
            // Clip the real response at the plot boundary; do not flatten
            // out-of-scale crossover attenuation onto the -12 dB grid line.
            for(i=0;i<points.length;i++){yy=gy(points[i]);var px=left+i/(points.length-1)*w;if(i===0 || (root.phase && Math.abs(points[i]-points[i-1])>180))ctx.moveTo(px,yy);else ctx.lineTo(px,yy)}
            ctx.strokeStyle=Theme.color('#09151c', backend.lightTheme);ctx.lineWidth=5;ctx.stroke()
            ctx.strokeStyle=Theme.color('#f0faff', backend.lightTheme);ctx.lineWidth=2.8;ctx.stroke()
            ctx.restore()
            if(root.showBands && !root.phase && (eqPoints.some(v=>Math.abs(v)>root.amplitudeLimit) || overlays.some(t=>t.values.some(v=>Math.abs(v)>root.amplitudeLimit)))){
                ctx.fillStyle=Theme.color('#e2bd72', backend.lightTheme);ctx.fillText('Σ exceeds ±'+root.amplitudeLimit+' dB scale',left+4,12)
            }
            for(var b=0;b<bands.length;b++) {
                var f=bands[b];if(!f.enabled)continue
                var selected=b===root.band,radius=selected?root.selectedNodeRadius:6
                if(selected){ctx.strokeStyle=Theme.color('#e9f7ff', backend.lightTheme);ctx.lineWidth=2;ctx.beginPath();ctx.arc(fx(f.frequency),nodeY(f.gain),radius+4,0,Math.PI*2);ctx.stroke()}
                ctx.fillStyle=colors[b];ctx.beginPath();ctx.arc(fx(f.frequency),nodeY(f.gain),radius,0,Math.PI*2);ctx.fill()
                ctx.fillStyle=Theme.onTrace(backend.lightTheme);ctx.font=(selected?'bold 12px':'10px')+" 'Segoe UI'";ctx.textAlign='center';ctx.fillText(String(b+1),fx(f.frequency),nodeY(f.gain)+4);ctx.textAlign='left'
            }
            ctx.font="10px 'Segoe UI'"
            ctx.fillStyle=Theme.color('#7b98ac', backend.lightTheme);ctx.fillText(root.phase?'deg':root.channelView?'XOVER + PEQ · dB':'dB',0,9);ctx.fillText('Hz',width-16,height-1)
        }
        MouseArea {
            id: dragArea
            objectName: root.showBands ? 'peq_drag_area' : 'coefficient_plot_mouse'
            anchors.fill: parent
            enabled: root.showBands
            acceptedButtons: Qt.LeftButton; preventStealing: true; scrollGestureEnabled: false
            property int dragged: -1
            property int channelIndex: -1
            property bool moved: false
            property real pressX: 0
            property real pressY: 0
            property bool pending: false
            property real pendingFrequency: 1000
            property real pendingGain: 0
            property int wheelChannel: -1
            property int wheelBand: -1
            property real wheelRemainder: 0
            function queuePoint(x,y) {
                pendingFrequency=Math.max(backend.options.frequencyMin,Math.min(backend.options.frequencyMax,backend.options.frequencyMin*Math.pow(backend.options.frequencyMax/backend.options.frequencyMin,(x-36)/plot.plotWidth())))
                pendingGain=Math.max(-12,Math.min(12,plot.gainAtY(y)))
                pending=true;if(!dragCommit.running)dragCommit.start()
            }
            function flushPoint() {
                dragCommit.stop()
                if(pending && dragged>=0 && channelIndex===backend.selected)backend.editPeqPoint(channelIndex,dragged,pendingFrequency,pendingGain)
                pending=false
            }
            Timer { id: dragCommit; interval: 16; repeat: false; onTriggered: dragArea.flushPoint() }
            onPressed: mouse => {
                var best=21;dragged=-1;channelIndex=backend.selected;pending=false
                moved=false;pressX=mouse.x;pressY=mouse.y
                for(var i=0;i<plot.bands.length;i++){var f=plot.bands[i];if(!f.enabled)continue;var dist=Math.hypot(mouse.x-plot.fx(f.frequency),mouse.y-plot.nodeY(f.gain));if(dist<best){best=dist;dragged=i}}
                if(dragged>=0){root.bandSelected(dragged);wheelChannel=channelIndex;wheelBand=dragged;wheelRemainder=0}
            }
            onWheel: wheel => {
                if(wheelChannel!==backend.selected || wheelBand!==root.band || !plot.bands[root.band] || !plot.bands[root.band].enabled){wheel.accepted=false;return}
                wheel.accepted=true
                wheelRemainder+=wheel.angleDelta.y
                var steps=Math.trunc(wheelRemainder/120);wheelRemainder-=steps*120
                var choices=backend.options.qValues, stride=(wheel.modifiers & Qt.ShiftModifier)?1:5
                var q=root.currentData.filters[root.band].q, next=q
                if(root.fineQ){
                    next=Math.max(.4,Math.min(128,Math.round((q+steps*.10)*100)/100))
                    if(next!==q){backend.edit(backend.selected,'filters.q',next,root.band);backend.flushControlView()}
                    return
                }
                while(steps!==0){
                    if(steps>0){for(var j=0;j<choices.length;j++)if(choices[j]>next+0.000001){next=choices[Math.min(choices.length-1,j+stride-1)];break}}
                    else {for(j=choices.length-1;j>=0;j--)if(choices[j]<next-0.000001){next=choices[Math.max(0,j-stride+1)];break}}
                    steps+=steps>0?-1:1
                }
                if(next!==q)backend.edit(backend.selected,'filters.q',next,root.band)
            }
            onDoubleClicked: mouse => {
                if(dragged<0 || channelIndex!==backend.selected)return
                dragCommit.stop();pending=false;moved=false
                backend.edit(backend.selected,'filters.gain',0,dragged);backend.flushControlView()
            }
            onPositionChanged: mouse => {
                if(!pressed || dragged<0)return
                if(!moved && Math.hypot(mouse.x-pressX,mouse.y-pressY)<1)return
                moved=true
                queuePoint(mouse.x,mouse.y)
            }
            onReleased: mouse => {if(dragged>=0 && moved){queuePoint(mouse.x,mouse.y);flushPoint();backend.flushControlView()}dragged=-1}
            onCanceled: {flushPoint();backend.flushControlView();dragged=-1}
        }
    }
}
