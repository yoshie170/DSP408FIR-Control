import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QTabWidget, QFormLayout, QDoubleSpinBox,
    QCheckBox, QComboBox, QGridLayout, QFileDialog, QMessageBox, QGroupBox, QScrollArea)
from dsp408.model import DeviceModel

STYLE = '''
QWidget { background: #141a23; color: #e6edf6; font: 12px "Segoe UI"; }
QMainWindow { background: #10151e; }
QLabel#title { font-size: 22px; font-weight: 700; color: #f6f9ff; }
QLabel#subtitle { color: #7e96ae; }
QPushButton { background: #243247; border: 1px solid #35485e; border-radius: 6px; padding: 9px 13px; }
QPushButton:hover { background: #30445c; }
QPushButton#accent { background: #008eaa; border-color: #11b6cc; font-weight: 700; }
QListWidget { background: #182230; border: 1px solid #2c3a4c; border-radius: 8px; padding: 5px; }
QListWidget::item { padding: 12px; border-radius: 5px; }
QListWidget::item:selected { background: #087d9a; }
QTabWidget::pane { border: 1px solid #2d3c4f; border-radius: 7px; }
QTabBar::tab { background: #202d3d; padding: 11px 19px; margin-right: 3px; }
QTabBar::tab:selected { background: #087d9a; }
QGroupBox { border: 1px solid #344358; border-radius: 8px; margin-top: 16px; padding: 13px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QDoubleSpinBox, QComboBox { background: #1e2b3b; border: 1px solid #40546b; border-radius: 5px; padding: 7px; min-width: 115px; }
QCheckBox { spacing: 10px; }
'''

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = DeviceModel()
        self.setWindowTitle('DSP408FIR Control - DEMO')
        self.resize(1280, 790)
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(20, 18, 20, 16); outer.setSpacing(15)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel('DSP408  /  CONTROL CENTER'); title.setObjectName('title')
        sub = QLabel('t.racks FIR DSP 408   •   OFFLINE DEMO   •   Hardware communication disabled'); sub.setObjectName('subtitle')
        titles.addWidget(title); titles.addWidget(sub); header.addLayout(titles); header.addStretch()
        save = QPushButton('Save preset'); save.clicked.connect(self.save_preset)
        load = QPushButton('Load preset'); load.clicked.connect(self.load_preset)
        header.addWidget(load); header.addWidget(save)
        outer.addLayout(header)
        content = QHBoxLayout(); content.setSpacing(14)
        side = QVBoxLayout(); side.addWidget(QLabel('CHANNELS'))
        self.channels = QListWidget(); self.channels.addItems([f'IN {i+1}' for i in range(4)] + [f'OUT {i+1}' for i in range(8)])
        self.channels.currentRowChanged.connect(self.refresh); self.channels.setFixedWidth(180)
        side.addWidget(self.channels); content.addLayout(side)
        self.tabs = QTabWidget(); content.addWidget(self.tabs, 1)
        self.basic = self.make_basic(); self.tabs.addTab(self.basic, 'CHANNEL')
        self.eq = self.make_eq(); self.tabs.addTab(self.eq, 'PEQ')
        self.cross = self.make_crossover(); self.tabs.addTab(self.cross, 'CROSSOVER')
        self.routing_tab = self.make_routing(); self.tabs.addTab(self.routing_tab, 'ROUTING')
        self.fir_tab = self.make_fir(); self.tabs.addTab(self.fir_tab, 'FIR')
        outer.addLayout(content, 1)
        self.statusBar().showMessage('DEMO MODE • No data is sent to a physical processor')
        self.channels.setCurrentRow(0)

    def current(self):
        index = max(self.channels.currentRow(), 0)
        return (self.model.inputs + self.model.outputs)[index]

    def spin(self, low, high, step, suffix='', decimals=2):
        s = QDoubleSpinBox(); s.setRange(low, high); s.setSingleStep(step); s.setDecimals(decimals); s.setSuffix(suffix)
        return s

    def make_basic(self):
        w = QWidget(); layout = QVBoxLayout(w)
        group = QGroupBox('Channel parameters'); form = QFormLayout(group)
        self.gain = self.spin(-60, 24, .5, ' dB'); self.gain.valueChanged.connect(lambda x: setattr(self.current(), 'gain', x))
        self.delay = self.spin(0, 2000, .1, ' ms'); self.delay.valueChanged.connect(lambda x: setattr(self.current(), 'delay_ms', x))
        self.mute = QCheckBox('Mute channel'); self.mute.toggled.connect(lambda x: setattr(self.current(), 'mute', x))
        self.polarity = QCheckBox('Invert polarity'); self.polarity.toggled.connect(lambda x: setattr(self.current(), 'polarity_inverted', x))
        for name, control in [('Gain', self.gain), ('Delay', self.delay), ('Mute', self.mute), ('Polarity', self.polarity)]: form.addRow(name, control)
        layout.addWidget(group); layout.addStretch(); return w

    def make_eq(self):
        w = QWidget(); layout = QVBoxLayout(w)
        note = QLabel('8 editable PEQ bands per channel — demo data only'); note.setObjectName('subtitle'); layout.addWidget(note)
        self.eq_controls = []
        grid = QGridLayout();
        for j, name in enumerate(['Band', 'Enabled', 'Type', 'Frequency', 'Gain', 'Q']): grid.addWidget(QLabel(name), 0, j)
        for i in range(8):
            enabled = QCheckBox(); kind = QComboBox(); kind.addItems(['Bell', 'Low shelf', 'High shelf'])
            freq = self.spin(20, 20000, 10, ' Hz', 1); gain = self.spin(-24, 24, .5, ' dB'); q = self.spin(.1, 20, .1)
            grid.addWidget(QLabel(str(i+1)), i+1, 0)
            for j, widget in enumerate((enabled, kind, freq, gain, q), 1): grid.addWidget(widget, i+1, j)
            enabled.toggled.connect(lambda value, band=i: setattr(self.current().filters[band], 'enabled', value))
            kind.currentTextChanged.connect(lambda value, band=i: setattr(self.current().filters[band], 'kind', value))
            freq.valueChanged.connect(lambda value, band=i: setattr(self.current().filters[band], 'frequency', value))
            gain.valueChanged.connect(lambda value, band=i: setattr(self.current().filters[band], 'gain', value))
            q.valueChanged.connect(lambda value, band=i: setattr(self.current().filters[band], 'q', value))
            self.eq_controls.append((enabled, kind, freq, gain, q))
        layout.addLayout(grid); layout.addStretch(); return w

    def make_crossover(self):
        w = QWidget(); layout = QVBoxLayout(w); group = QGroupBox('Crossover frequencies'); form = QFormLayout(group)
        self.hpf = self.spin(10, 20000, 10, ' Hz'); self.lpf = self.spin(10, 20000, 10, ' Hz')
        self.hpf.valueChanged.connect(lambda v: setattr(self.current(), 'hpf_hz', v))
        self.lpf.valueChanged.connect(lambda v: setattr(self.current(), 'lpf_hz', v))
        form.addRow('HPF', self.hpf); form.addRow('LPF', self.lpf)
        layout.addWidget(group); layout.addWidget(QLabel('Filter slopes/types will be added after confirming DSP capabilities.')); layout.addStretch(); return w

    def make_routing(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.addWidget(QLabel('Output × Input routing (demo matrix)'))
        grid = QGridLayout()
        for col in range(4): grid.addWidget(QLabel(f'IN {col+1}'), 0, col+1)
        self.routes = []
        for out in range(8):
            grid.addWidget(QLabel(f'OUT {out+1}'), out+1, 0)
            row = []
            for inp in range(4):
                check = QCheckBox(); check.toggled.connect(lambda value, o=out, i=inp: self.model.routing[o].__setitem__(i, value))
                grid.addWidget(check, out+1, inp+1); row.append(check)
            self.routes.append(row)
        layout.addLayout(grid); layout.addStretch(); return w

    def make_fir(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.addWidget(QLabel('FIR — local file preview only; hardware upload NOT implemented'))
        self.fir_label = QLabel('No FIR file selected'); layout.addWidget(self.fir_label)
        btn = QPushButton('Choose CSV / TXT'); btn.clicked.connect(self.select_fir); layout.addWidget(btn)
        layout.addWidget(QLabel('Coefficient validation and transmission require verification against the original editor.'))
        layout.addStretch(); return w

    def select_fir(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose FIR coefficients', '', 'FIR files (*.csv *.txt)')
        if path:
            self.model.fir_path = path
            self.fir_label.setText(Path(path).name + '  (selected, not uploaded)')

    def refresh(self, _=None):
        c = self.current()
        for widget, value in [(self.gain,c.gain),(self.delay,c.delay_ms),(self.mute,c.mute),(self.polarity,c.polarity_inverted),(self.hpf,c.hpf_hz),(self.lpf,c.lpf_hz)]:
            widget.blockSignals(True); widget.setValue(value) if isinstance(widget, QDoubleSpinBox) else widget.setChecked(value); widget.blockSignals(False)
        for controls, flt in zip(self.eq_controls, c.filters):
            for widget, value in zip(controls, (flt.enabled,flt.kind,flt.frequency,flt.gain,flt.q)):
                widget.blockSignals(True)
                if isinstance(widget, QCheckBox): widget.setChecked(value)
                elif isinstance(widget, QComboBox): widget.setCurrentText(value)
                else: widget.setValue(value)
                widget.blockSignals(False)
        for out, row in enumerate(self.routes):
            for inp, widget in enumerate(row):
                widget.blockSignals(True); widget.setChecked(self.model.routing[out][inp]); widget.blockSignals(False)
        self.fir_label.setText(Path(self.model.fir_path).name if self.model.fir_path else 'No FIR file selected')

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save demo preset', '', 'JSON preset (*.json)')
        if path:
            try: self.model.save(path)
            except Exception as e: QMessageBox.critical(self, 'Save failed', str(e))

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Load demo preset', '', 'JSON preset (*.json)')
        if path:
            try: self.model = DeviceModel.load(path); self.refresh()
            except Exception as e: QMessageBox.critical(self, 'Load failed', str(e))

def main():
    app = QApplication(sys.argv); app.setStyleSheet(STYLE)
    window = MainWindow(); window.show()
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())

