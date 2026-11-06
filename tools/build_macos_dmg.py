"""Package the verified own .app with PolyForm Shield 1.0.0/notices; mount and verify the DMG."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_macos import native_target
from tools.verify_macos_bundle import verify


def sha256(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def render_background(directory):
    # Keep the installer artwork editable as SVG; render both Retina densities.
    from PySide6.QtCore import QRectF,Qt
    from PySide6.QtGui import QGuiApplication,QImage,QPainter
    from PySide6.QtSvg import QSvgRenderer
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    app=QGuiApplication.instance() or QGuiApplication([])
    renderer=QSvgRenderer(str(ROOT/'packaging/macos/dmg-background.svg'))
    if not renderer.isValid():raise ValueError('Invalid DMG background SVG')
    for scale,suffix in ((1,''),(2,'@2x')):
        image=QImage(720*scale,480*scale,QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter=QPainter(image)
        try:renderer.render(painter,QRectF(0,0,image.width(),image.height()))
        finally:painter.end()
        if not image.save(str(directory/f'background{suffix}.png')):raise OSError('Cannot render DMG background')
    return directory/'background.png'


def build(arch=None):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    arch=native_target(arch)
    version=runpy.run_path(str(ROOT/'dsp408/version.py'))
    config=runpy.run_path(str(ROOT/'packaging/macos/bundle_config.py'))
    dist=ROOT/'dist/macos'/arch
    app=dist/(config['APP_NAME']+'.app')
    output=ROOT/'work'/('macos-'+arch+'-verification')
    output.mkdir(parents=True,exist_ok=True)
    name=f"DSP408FIR-Control-{version['VERSION']}-build{version['BUILD']}-macOS-{arch}"
    image=dist/(name+'.dmg')
    def run(*args,**kwargs):
        return subprocess.run(list(map(str,args)),check=True,**kwargs)
    import PySide6
    run('/usr/bin/chflags','-R','nohidden',Path(PySide6.__file__).parent/'Qt')
    from dmgbuild import build_dmg
    from ds_store import DSStore
    artwork=ROOT/'build/macos/dmg';artwork.mkdir(parents=True,exist_ok=True)
    background=render_background(artwork)
    icon=app/'Contents/Resources/dsp408.icns'
    positions={app.name:(180,214),'Applications':(540,214),'Licenses':(630,402)}
    # Stage outside Desktop/iCloud: File Provider can recreate FinderInfo on
    # .app/.framework folders while codesign is examining them.
    with tempfile.TemporaryDirectory(prefix='dsp408-dmg-stage-') as temporary:
        stage=Path(temporary)
        run('/usr/bin/ditto','--noextattr','--norsrc',app,stage/app.name)
        documents=stage/'Licenses';documents.mkdir()
        shutil.copyfile(ROOT/'LICENSE',documents/'LICENSE.txt')
        shutil.copytree(ROOT/'dsp408/assets/licenses',documents/'Third-party licenses')
        (documents/'Install.txt').write_text(
            f"DSP408FIR Control {version['VERSION']} (build {version['BUILD']})\n"
            "Copyright © 2026 Łukasz Białas · https://gremium.tech\n\n"
            "INSTALACJA / INSTALLATION\n"
            "1. Przeciągnij DSP408FIR Control.app na Applications.\n"
            "   Drag DSP408FIR Control.app onto Applications.\n"
            "2. Wysuń obraz DMG i uruchom aplikację z Applications.\n"
            "   Eject the DMG and launch the app from Applications.\n\n"
            "Apple Silicon (M1/M2/M3/M4/M5 and later), macOS 14.4+.\n"
            "Python, Qt and USB HIDAPI are included; no Terminal setup needed.\n\n"
            "LICENSE\n"
            "The application uses the same PolyForm Shield 1.0.0 license as the Windows project.\n"
            "See LICENSE.txt. Third-party libraries retain their own licenses;\n"
            "full texts are in Third-party licenses and Help > Licenses and Notices.\n"
            "Project: https://github.com/yoshie170/DSP408FIR-Control\n\n"
            "This build is ad-hoc signed, without Apple Developer ID/notarization.\n"
            "If macOS blocks opening it, review it in System Settings >\n"
            "Privacy & Security > Open Anyway. Do not disable Gatekeeper.\n",
            encoding='utf-8')
        run('/usr/bin/chflags','-R','nohidden',stage)
        run('/usr/bin/xattr','-cr',stage/app.name)
        verify(stage/app.name,arch,output,reference=app)
        build_dmg(str(image),config['APP_NAME'],settings={
            'format':'UDZO','filesystem':'HFS+',
            'files':[str(stage/app.name),str(documents)],
            'symlinks':{'Applications':'/Applications'},
            'icon':str(icon),'background':str(background),
            'default_view':'icon-view','window_rect':((180,180),(720,512)),
            'show_status_bar':False,'show_toolbar':False,'show_sidebar':False,
            'show_pathbar':False,'show_tab_view':False,'show_icon_preview':False,
            'icon_size':96,'text_size':13,'grid_spacing':80,
            'arrange_by':None,'icon_locations':positions,
        })
    run('/usr/bin/xcrun','swift','-module-cache-path',artwork/'swift-module-cache',
        ROOT/'tools/set_macos_file_icon.swift',icon,image)
    finder_info=bytes.fromhex(subprocess.check_output(['/usr/bin/xattr','-px','com.apple.FinderInfo',str(image)],text=True))
    assert int.from_bytes(finder_info[8:10],'big') & 0x0400,'DMG custom icon flag missing'
    assert subprocess.check_output(['/usr/bin/xattr','-px','com.apple.ResourceFork',str(image)]).strip(),'DMG icon resource missing'
    run('/usr/bin/hdiutil','verify',image)
    mounted=None
    try:
        attached=run('/usr/bin/hdiutil','attach','-readonly','-nobrowse','-plist',image,capture_output=True)
        entities=plistlib.loads(attached.stdout)['system-entities']
        mounted=next(Path(e['mount-point']) for e in entities if 'mount-point' in e)
        packed=mounted/app.name
        run('/usr/bin/codesign','--verify','--deep','--strict',packed)
        assert (mounted/'Licenses/LICENSE.txt').read_bytes()==(ROOT/'LICENSE').read_bytes()
        assert (mounted/'Applications').is_symlink() and os.readlink(mounted/'Applications')=='/Applications'
        assert (mounted/'.VolumeIcon.icns').read_bytes()==icon.read_bytes()
        with DSStore.open(str(mounted/'.DS_Store'),'r') as store:
            assert store['.']['icvp']['backgroundType']==2
            assert store['.']['icvp']['iconSize']==96
            for filename,position in positions.items():
                assert tuple(store[filename]['Iloc'][:2])==position
        with (packed/'Contents/Info.plist').open('rb') as stream:info=plistlib.load(stream)
        assert info['CFBundleVersion']==str(version['BUILD'])
        for source in app.rglob('*'):
            if source.is_file() and not source.is_symlink():
                assert sha256(source)==sha256(packed/source.relative_to(app)),str(source.relative_to(app))
        for source in (ROOT/'dsp408/assets/licenses').rglob('*'):
            if source.is_file():
                assert source.read_bytes()==(mounted/'Licenses/Third-party licenses'/source.relative_to(ROOT/'dsp408/assets/licenses')).read_bytes()
    finally:
        if mounted is not None:run('/usr/bin/hdiutil','detach',mounted)
    digest=sha256(image)
    image.with_suffix('.dmg.sha256').write_text(digest+'  '+image.name+'\n',encoding='ascii')
    result={'passed':True,'dmg':image.name,'sha256':digest,'architecture':arch,
            'version':version['VERSION'],'build':version['BUILD'],'license':'PolyForm Shield 1.0.0',
            'image_verified':True,'mounted_bundle_verified':True,'third_party_licenses_equal':True,
            'custom_file_icon':True,'custom_volume_icon':True,'graphical_install_layout':True,
            'codesign_verified':True,'notarization_verified':False,'device_io':False}
    (output/'dmg-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return image


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch',choices=('arm64','x86_64'));args=parser.parse_args()
    print(build(args.arch))
