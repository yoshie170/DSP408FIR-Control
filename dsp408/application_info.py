"""Local Help UI, curated diagnostics and notices. Never opens a DSP transport."""
from pathlib import Path
import platform
import sys
import PySide6
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, qVersion
from PySide6.QtGui import QDesktopServices, QGuiApplication
from dsp408.version import VERSION, BUILD

NAME = 'DSP408FIR Control'
AUTHOR = 'Łukasz Białas'
COPYRIGHT = 'Copyright © 2026 '+AUTHOR
GITHUB = 'https://github.com/yoshie170/DSP408-Control'
INDEPENDENCE = ('Independent software for the t.racks FIR DSP 408. '
                'Not officially affiliated with, endorsed by or supported by the device manufacturer.')
SAFETY_NOTICE = ('Incorrect DSP settings can damage loudspeakers, amplifiers or other connected equipment. '
                 'Verify routing, gain, crossover and limiter settings before enabling audio. '
                 'Start with a low signal level and use appropriate protection.\n\n'+INDEPENDENCE)
ASSETS = Path(__file__).resolve().parent/'assets'
ROOT = Path(__file__).resolve().parents[1]


def document_text(key):
    # Only fixed application documents or enumerated license files can be read.
    originals = {'license': ('LICENSE','LICENSE.txt'), 'changelog': ('CHANGELOG.md','CHANGELOG.md')}
    if key in originals:
        source, bundled = originals[key]
        path = ASSETS/'info'/bundled if getattr(sys,'frozen',False) else ROOT/source
    elif key == 'notices':
        path = ASSETS/'licenses/THIRD_PARTY_NOTICES.txt'
    else:
        licenses = ASSETS/'licenses'
        paths = {p.relative_to(licenses).as_posix():p for p in licenses.rglob('*.txt') if p.is_file()}
        if key not in paths:return 'Document unavailable.'
        path = paths[key]
    try:
        with path.open(encoding='utf-8-sig') as stream:
            return stream.read(2*1024*1024)
    except (OSError,UnicodeError):return 'Document unavailable. Reinstall the application to restore bundled notices.'


def diagnostics(controller):
    # Do not copy connectionLabel/status/error/raw identity: they may later
    # contain user text. Never serialize the model, target or worker object.
    active = bool(controller.usbReadActive)
    connected = bool(controller.usbReadConnected)
    medium = 'Ethernet' if controller.activeTransport == 'ethernet' else 'USB' if active else 'None'
    mode = 'Control' if active and controller.usbControlMode else 'Read only' if active else 'Offline'
    return '\n'.join((NAME, f'Version: {VERSION}', f'Build: {BUILD}',
        f'OS: {platform.system()} {platform.release()} ({platform.version()})',
        f'Architecture: {platform.machine()}', f'Python: {platform.python_version()}',
        f'PySide6: {PySide6.__version__}', f'Qt: {qVersion()}',
        'DSP model: t.racks FIR DSP 408',
        'Connection: '+('Connected' if connected else 'Session open' if active else 'Disconnected'),
        'Transport: '+medium, 'Mode: '+mode,
        'Editing locked: '+('Yes' if controller.editingLocked else 'No'),
        f'VU request interval: {controller.meterPollMs} ms',
        'Privacy: addresses, serial numbers, passwords, configuration names and paths omitted.'))


class ApplicationInfo(QObject):
    changed = Signal()
    def __init__(self,controller,preferences):
        super().__init__(controller)
        self._controller=controller;self._preferences=preferences;self._status=''
        self._notice_dismissed=preferences.safety_notice_dismissed()
        self._show_notice=not self._notice_dismissed

    @Property('QVariantMap',constant=True)
    def metadata(self):
        return {'name':NAME,'version':VERSION,'build':BUILD,'author':AUTHOR,'copyright':COPYRIGHT,
                'license':'MIT','github':GITHUB,'website':'https://gremium.tech',
                'technologies':f'Python {platform.python_version()} · PySide6 {PySide6.__version__} · Qt {qVersion()} / QML',
                'independence':INDEPENDENCE,
                'qtCopyright':'Qt / Qt for Python © The Qt Company Ltd. and other contributors. See Open Source Licenses.'}

    @Property('QVariantList',constant=True)
    def licenseDocuments(self):
        base=ASSETS/'licenses'
        files=sorted(p.relative_to(base).as_posix() for p in base.rglob('*.txt') if p.is_file())
        return [{'title':'Application — MIT','key':'license'}, {'title':'Third-party notices','key':'notices'}]+[
            {'title':name,'key':name} for name in files if name!='THIRD_PARTY_NOTICES.txt']

    @Property(str,notify=changed)
    def status(self):return self._status
    @Property(bool,notify=changed)
    def showSafetyNotice(self):return self._show_notice
    @Property(bool,notify=changed)
    def safetyNoticeDismissed(self):return self._notice_dismissed
    @Property(str,constant=True)
    def safetyText(self):return SAFETY_NOTICE
    @Slot(str,result=str)
    def document(self,key):return document_text(key)
    @Slot(result=bool)
    def copyDiagnostics(self):
        clipboard=QGuiApplication.clipboard()
        if clipboard is None:self._status='Clipboard unavailable.';self.changed.emit();return False
        clipboard.setText(diagnostics(self._controller))
        self._status='Diagnostics copied. No addresses, passwords or configuration data included.'
        self.changed.emit();return True
    @Slot(bool,result=bool)
    def acknowledgeSafety(self,dont_show_again):
        if type(dont_show_again) is not bool:return False
        success=True
        if dont_show_again!=self._notice_dismissed:
            try:
                self._preferences.save_safety_notice_dismissed(dont_show_again)
                self._notice_dismissed=dont_show_again
            except OSError:
                self._status='Could not save this preference. The previous startup choice is unchanged.'
                success=False
        self._show_notice=False;self.changed.emit();return success
    @Slot(result=bool)
    def openGithub(self):return self._open_url(GITHUB)
    @Slot(result=bool)
    def reportIssue(self):return self._open_url(GITHUB+'/issues/new')
    def _open_url(self,url):
        ok=QDesktopServices.openUrl(QUrl(url))
        self._status='' if ok else 'Could not open the browser. Use the GitHub link shown in About.'
        self.changed.emit();return ok
