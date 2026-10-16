"""Render the canonical QML brand SVG to PNG sizes and a PNG-backed Windows ICO.

Local file conversion only. No Pillow, external tool or device/network I/O.
"""
import os,struct,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QGuiApplication,QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from dsp408.branding import ICON_DIRECTORY

SIZES=(16,24,32,48,64,128,256,512)


def build_icons(directory=ICON_DIRECTORY):
    directory=Path(directory);renderer=QSvgRenderer(str(directory/'dsp408.svg'))
    if not renderer.isValid():raise ValueError('Invalid brand SVG')
    pngs=[]
    for size in SIZES:
        image=QImage(size,size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image)
        try:renderer.render(painter,QRectF(0,0,size,size))
        finally:painter.end()
        path=directory/f'dsp408-{size}.png'
        if not image.save(str(path),'PNG'):raise OSError(f'Cannot save {path.name}')
        if size<=256:pngs.append((size,path.read_bytes()))
    offset=6+16*len(pngs);entries=[];payloads=[]
    for size,payload in pngs:
        entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(payload),offset))
        payloads.append(payload);offset+=len(payload)
    (directory/'dsp408.ico').write_bytes(struct.pack('<HHH',0,1,len(pngs))+b''.join(entries)+b''.join(payloads))


if __name__=='__main__':
    app=QGuiApplication.instance() or QGuiApplication([])
    build_icons();print('Generated PNG16/24/32/48/64/128/256/512 and ICO16…256 from dsp408.svg')
