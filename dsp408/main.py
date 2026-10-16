import argparse,sys
from pathlib import Path
from PySide6.QtCore import QUrl,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from dsp408.controller import Controller
from dsp408.branding import application_icon

def create_engine(controller):
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent/'qml/Main.qml')))
    if not engine.rootObjects():raise RuntimeError('QML failed to load')
    engine.rootObjects()[0].setIcon(application_icon())
    return engine

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--screenshot');parser.add_argument('--width',type=int,default=1366);parser.add_argument('--height',type=int,default=768)
    parser.add_argument('--smoke',action='store_true');parser.add_argument('--preset');parser.add_argument('--tab',type=int,default=11)
    parser.add_argument('--channel',type=int,default=0);parser.add_argument('--rta',action='store_true',help=argparse.SUPPRESS);parser.add_argument('--compare',type=int,default=-1)
    parser.add_argument('--local-protocol',action='store_true',help='Explicit in-memory source test; no hardware I/O')
    parser.add_argument('--diagnostics',action='store_true',help='Show archived research and hardware diagnostic tools')
    parser.add_argument('--verify-package',help=argparse.SUPPRESS)
    parser.add_argument('--theme',choices=('dark','light'),help='Preview theme without saving the preference')
    parser.add_argument('--connection-dialog',action='store_true');args=parser.parse_args()
    QQuickStyle.setStyle('Basic');app=QApplication(sys.argv)
    app.setApplicationName('DSP408FIR Control');app.setWindowIcon(application_icon())
    for font in ('segoeui.ttf','segoeuib.ttf'):
        font_path=Path('C:/Windows/Fonts')/font
        if font_path.exists(): QFontDatabase.addApplicationFont(str(font_path))
    controller=Controller();controller._developer_tools=args.diagnostics;app.aboutToQuit.connect(controller.shutdown)
    if args.theme:controller._theme=args.theme
    if args.preset: controller.loadPath(args.preset)
    controller.select(args.channel)
    if 0<=args.compare<8:controller.compareXover(args.compare+4,True)
    if args.local_protocol:controller.setLocalProtocol(True)
    engine=create_engine(controller);window=engine.rootObjects()[0];window.resize(args.width,args.height);window.setProperty('tab',args.tab)
    window.setProperty('rtaRequested',args.rta);window.setProperty('comparisonRequested',args.compare)
    window.setProperty('showConnection',args.connection_dialog)
    if args.verify_package:
        def verify_package():
            try:
                from dsp408.release_check import verify
                verify(controller,window,args.verify_package)
                if args.screenshot and not window.grabWindow().save(args.screenshot):raise RuntimeError('Screenshot failed')
            except Exception as error:
                import json
                Path(args.verify_package).write_text(json.dumps({'error':str(error)}),encoding='utf-8')
                app.exit(2);return
            app.exit(0)
        QTimer.singleShot(1200,verify_package)
    elif args.screenshot:
        def capture():
            result=window.grabWindow().save(args.screenshot);print('Screenshot saved' if result else 'Screenshot failed');app.exit(0 if result else 2)
        QTimer.singleShot(1200,capture)
    elif args.smoke:QTimer.singleShot(1000,app.quit)
    result=app.exec()
    import shiboken6
    shiboken6.delete(window);shiboken6.delete(engine)
    return result

if __name__=='__main__':sys.exit(main())
