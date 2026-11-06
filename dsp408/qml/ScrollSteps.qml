import QtQuick

QtObject {
    // Pixel and angle deltas describe the same event: use only one source.
    // Each control chooses its pixel sensitivity; PEQ plot Q defaults to 40.
    property real remainder: 0
    property bool pixels: false
    property real pixelsPerStep: 40
    property bool horizontal: false
    function reset() { remainder=0 }
    function take(event) {
        if(event.phase===Qt.ScrollBegin || event.phase===Qt.ScrollEnd)reset()
        var usePixels=event.pixelDelta.x!==0 || event.pixelDelta.y!==0
        if(usePixels!==pixels){reset();pixels=usePixels}
        var pixelDelta=horizontal && Math.abs(event.pixelDelta.x)>Math.abs(event.pixelDelta.y)?event.pixelDelta.x:event.pixelDelta.y
        remainder+=usePixels?pixelDelta/pixelsPerStep:event.angleDelta.y/120
        var steps=Math.trunc(remainder)
        remainder-=steps
        return steps
    }
}
