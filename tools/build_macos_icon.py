"""Render the existing vector identity as an iconset; iconutil runs on macOS."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICONSET = {'icon_16x16.png':16, 'icon_16x16@2x.png':32,
           'icon_32x32.png':32, 'icon_32x32@2x.png':64,
           'icon_128x128.png':128, 'icon_128x128@2x.png':256,
           'icon_256x256.png':256, 'icon_256x256@2x.png':512,
           'icon_512x512.png':512, 'icon_512x512@2x.png':1024}


def render_iconset(directory):
    directory=Path(directory);directory.mkdir(parents=True, exist_ok=True)
    renderer=QSvgRenderer(str(ROOT/'dsp408/assets/icons/dsp408.svg'))
    if not renderer.isValid():raise ValueError('Invalid application SVG')
    for name,size in ICONSET.items():
        image=QImage(size,size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image)
        try:renderer.render(painter,QRectF(0,0,size,size))
        finally:painter.end()
        if not image.save(str(directory/name),'PNG'):raise OSError('Cannot save '+name)
    return directory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/macos/icons')
    args=parser.parse_args()
    if sys.platform!='darwin':parser.error('ICNS compilation requires macOS iconutil.')
    app=QGuiApplication.instance() or QGuiApplication([])
    args.output.mkdir(parents=True,exist_ok=True)
    source=render_iconset(args.output/'dsp408.iconset')
    subprocess.run(['/usr/bin/iconutil','-c','icns',str(source),'-o',str(args.output/'dsp408.icns')],check=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
