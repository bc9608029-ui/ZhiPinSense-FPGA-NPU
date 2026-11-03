"""Modal multi-frequency control; opening never creates a Radio or transmits."""
from pathlib import Path
import json
import time
from PyQt5 import QtCore, QtGui, QtWidgets as W
from tx_core import ROOT, CLASSES, defaults, mhz_to_hz
from multi_core import build


class MultiDialog(W.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('智频感知 · 多频点发射候选'); self.resize(1240, 840)
        self.setMinimumSize(980, 650)
        self.proc = None; self.run_dir = None; self.line_count = 0; self.sequence = 0
        self.close_pending = False; self.config_fields = []; self.last_config = None
        shell = W.QVBoxLayout(self); shell.setContentsMargins(16, 12, 16, 12)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(W.QFrame.NoFrame)
        content = W.QWidget(); scroll.setWidget(content); shell.addWidget(scroll, 1)
        outer = W.QVBoxLayout(content); outer.setContentsMargins(10, 10, 10, 10); outer.setSpacing(14)
        title = W.QLabel('多频点发射控制'); title.setStyleSheet('font-size:25px;font-weight:700;color:#17324d;')
        outer.addWidget(title)
        hint = W.QLabel('2–4路独立消息 · 接收端自主巡扫 · 当前为候选功能，真实多路RF待验收')
        hint.setWordWrap(True); hint.setStyleSheet('color:#52647b;'); outer.addWidget(hint)
        settings = W.QGroupBox('01  设备与计划'); form = W.QGridLayout(settings)
        self.count = W.QComboBox(); self.count.addItems(['2路', '3路', '4路'])
        self.uri = W.QLineEdit(parent.uri.text())
        self.gain = W.QDoubleSpinBox(); self.gain.setRange(-89.75, 0); self.gain.setDecimals(2)
        self.gain.setSingleStep(.25); self.gain.setValue(parent.gain.value()); self.gain.setSuffix(' dB')
        self.duration = W.QSpinBox(); self.duration.setRange(1, 3600); self.duration.setValue(120); self.duration.setSuffix(' s')
        self.python = W.QLineEdit(parent.interpreter.text())
        self.dataset = W.QLineEdit(defaults()['dataset']); self.manifest = W.QLineEdit(defaults()['manifest'])
        items = [('路数', self.count), ('TX设备URI', self.uri), ('共同TX增益／衰减', self.gain),
                 ('会话时限', self.duration), ('工作进程Python', self.python)]
        for i, (name, widget) in enumerate(items):
            form.addWidget(W.QLabel(name), i // 3 * 2, i % 3)
            form.addWidget(widget, i // 3 * 2 + 1, i % 3)
        outer.addWidget(settings)
        self.config_fields += [self.count, self.uri, self.gain, self.duration, self.python]
        lane_box = W.QGroupBox('02  每路信号（既有消息集，频率单位MHz）'); grid = W.QGridLayout(lane_box)
        for i, text in enumerate(['本次启用', '频点', '中心频率 / MHz', '调制类型', '消息序号']):
            lab = W.QLabel(text); lab.setStyleSheet('font-weight:600;color:#17324d;'); grid.addWidget(lab, 0, i)
        self.lanes = []
        for i in range(4):
            active = W.QCheckBox(); active.setChecked(True)
            freq = W.QLineEdit(f'{2400 + 3.6 * i:.6f}')
            modulation = W.QComboBox(); modulation.addItems(CLASSES); modulation.setCurrentIndex([4, 12, 3, 21][i])
            message = W.QSpinBox(); message.setRange(1, 10); message.setValue(1)
            name = W.QLabel(chr(65 + i)); name.setStyleSheet('font-size:17px;font-weight:700;color:#087f8c;')
            for j, widget in enumerate([active, name, freq, modulation, message]): grid.addWidget(widget, i + 1, j)
            self.lanes.append(dict(active=active, freq=freq, modulation=modulation, message=message, name=name))
            self.config_fields += [freq, modulation, message]
            active.toggled.connect(self.lane_changed)
        grid.setColumnStretch(2, 2); grid.setColumnStretch(3, 2); outer.addWidget(lane_box)
        note = W.QLabel('相邻频点至少3.2 MHz；频差为1250 Hz整数倍。两路总跨度≤7.2 MHz，三／四路≤12.8 MHz。'
                        '共用一台Pluto和一个硬件增益，各路保持原数字幅度；削顶时拒绝，不自动归一化。')
        note.setWordWrap(True); note.setStyleSheet('color:#52647b;'); outer.addWidget(note)
        scenes = W.QHBoxLayout(); self.scene_buttons = []
        for name, mask in [('全部启用', -1), ('仅A', 1), ('仅B', 2), ('撤去B', -2), ('全部静默', 0)]:
            button = W.QPushButton(name); button.clicked.connect(lambda _, m=mask: self.scene(m))
            scenes.addWidget(button); self.scene_buttons.append(button)
        outer.addLayout(scenes)
        self.summary = W.QLabel('尚未校验。未打开设备，未发射。'); self.summary.setWordWrap(True)
        self.summary.setStyleSheet('background:#e8f2f5;color:#17324d;padding:12px;border-radius:6px;')
        outer.addWidget(self.summary)
        self.log = W.QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(300)
        self.log.setMinimumHeight(110); outer.addWidget(self.log, 1)
        row = W.QHBoxLayout(); self.real = W.QCheckBox('启用真实TX（默认关闭）'); row.addWidget(self.real)
        row.addStretch(); self.preview_button = W.QPushButton('校验合成计划'); self.start_button = W.QPushButton('开始离线演练')
        self.stop_button = W.QPushButton('停止并恢复'); self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet('color:#b82d40;'); row.addWidget(self.preview_button); row.addWidget(self.start_button); row.addWidget(self.stop_button)
        shell.addLayout(row)
        self.preview_button.clicked.connect(self.preview); self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.request_stop)
        self.real.toggled.connect(lambda value: self.start_button.setText('开始真实多路发射' if value else '开始离线演练'))
        self.count.currentIndexChanged.connect(self.update_count)
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(100)
        self.update_count()

    def running(self):
        return self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning

    def append(self, text):
        self.log.appendPlainText(text)

    def update_count(self):
        for i, lane in enumerate(self.lanes):
            for widget in lane.values(): widget.setEnabled(i < self.count.currentIndex() + 2)

    def mask(self):
        return sum(1 << i for i, lane in enumerate(self.lanes[:self.count.currentIndex() + 2]) if lane['active'].isChecked())

    def config(self):
        return dict(real=self.real.isChecked(), uri=self.uri.text().strip(), gain_db=self.gain.value(),
                    max_seconds=self.duration.value(), dataset=self.dataset.text(), manifest=self.manifest.text(),
                    initial_mask=self.mask(), lanes=[dict(hz=mhz_to_hz(l['freq'].text()),
                    **{'class': l['modulation'].currentIndex()}, message=l['message'].value() - 1)
                    for l in self.lanes[:self.count.currentIndex() + 2]])

    def preview(self):
        try:
            c = self.config(); _, report = build(c)
            peaks = max(x['component_peak'] for x in report['scenes'].values())
            self.summary.setText(f"计划有效 · {len(c['lanes'])}路 · TX LO {report['tx_lo_hz']} Hz · "
                                 f"TX {report['tx_sample_rate']/1e6:g} MS/s · 最大分量峰值 {peaks:.1f}/2047\n"
                                 '尚未打开设备或发射；每路仍为2.56 MS/s公共帧。')
            self.append('全部开关组合合成检查通过；真实RF、镜像和接收完整率仍待测试。')
            return c
        except Exception as exc:
            self.summary.setText('校验失败：' + str(exc)); return None

    def lock_fields(self, locked):
        for widget in self.config_fields: widget.setEnabled(not locked)
        self.real.setEnabled(not locked); self.preview_button.setEnabled(not locked); self.start_button.setEnabled(not locked)
        if not locked: self.update_count()
        self.stop_button.setEnabled(locked)

    def start(self):
        if self.running(): return
        c = self.preview()
        if c is None: return
        interpreter = Path(self.python.text())
        if not interpreter.is_file(): self.summary.setText('工作进程Python路径不存在'); return
        self.run_dir = ROOT / 'runs' / ('multi_' + str(time.time_ns())); self.run_dir.mkdir(parents=True)
        self.last_config = c; self.line_count = 0; self.sequence = 0; self.close_pending = False
        (self.run_dir / 'config.json').write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf8')
        self.proc = QtCore.QProcess(self); self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        try:
            from iio_runtime import environment
            updates = environment(interpreter, c['real'])
            env = QtCore.QProcessEnvironment.systemEnvironment()
            for name, value in updates.items(): env.insert(name, value)
            self.proc.setProcessEnvironment(env)
            if 'LIBIIO_LIBRARY' in updates: self.append('工作进程libiio：' + updates['LIBIIO_LIBRARY'])
        except Exception as exc:
            self.summary.setText('驱动环境检查失败，未打开设备：' + str(exc)); return
        self.proc.setWorkingDirectory(str(ROOT)); self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.proc.readyReadStandardOutput.connect(self.drain_output)
        self.lock_fields(True); self.summary.setText('正在准备工作进程；等待实际应用状态。')
        self.proc.start(str(interpreter), ['-u', str(ROOT / 'multi_worker.py'), '--config', str(self.run_dir / 'config.json')])

    def drain_output(self):
        if self.proc:
            text = bytes(self.proc.readAllStandardOutput()).decode('utf8', errors='replace')
            # events.jsonl is authoritative; only surface non-JSON traceback output here.
            for line in text.splitlines():
                if line and not line.startswith('{'): self.append(line)

    def process_error(self, error):
        if error == QtCore.QProcess.FailedToStart:
            self.summary.setText('工作进程未能启动；没有恢复成功证据。'); self.lock_fields(False)

    def scene(self, mask):
        if self.close_pending or (self.run_dir and (self.run_dir / 'stop.request').exists() and self.running()): return
        if mask == -1: mask = (1 << (self.count.currentIndex() + 2)) - 1
        if mask == -2: mask = self.mask() & ~2
        for i, lane in enumerate(self.lanes):
            lane['active'].blockSignals(True); lane['active'].setChecked(bool(mask & (1 << i))); lane['active'].blockSignals(False)
        self.lane_changed()

    def lane_changed(self):
        if self.running() and self.run_dir and not (self.run_dir / 'stop.request').exists():
            self.sequence += 1
            p = self.run_dir / 'command.tmp'
            try:
                p.write_text(json.dumps(dict(seq=self.sequence, mask=self.mask())), encoding='utf8')
                p.replace(self.run_dir / 'command.json')
            except OSError as exc:
                self.summary.setText('开关命令未能写入，不能确认已应用：' + str(exc)); return
            self.summary.setText(f'开关命令#{self.sequence}已发送，等待工作进程确认。')

    def request_stop(self):
        if self.running() and self.run_dir:
            try: (self.run_dir / 'stop.request').touch()
            except OSError as exc:
                self.summary.setText('停止请求未写入，设备状态未确认：' + str(exc)); return
            self.stop_button.setEnabled(False)
            self.summary.setText('停止请求已发送，等待缓冲停止、属性恢复及独立读回。')

    def poll(self):
        if not self.run_dir: return
        p = self.run_dir / 'events.jsonl'
        if not p.exists(): return
        try: lines = p.read_bytes().decode('utf8', errors='replace').splitlines(keepends=True)
        except OSError: return
        for line in lines[self.line_count:]:
            if not line.endswith('\n'): break
            try: row = json.loads(line)
            except ValueError: break
            self.line_count += 1
            if row['event'] == 'scene_applied':
                names = [chr(65+i) for i in range(4) if row['scene'] & (1 << i)]
                text = '＋'.join(names) if names else '全部静默'
                self.summary.setText(('真实TX已应用：' if row['real'] else '离线演练已应用：') + text)
                self.append(f"命令#{row['seq']}已应用：{text}")
            elif row['event'] == 'error': self.append('错误：' + row['message'])

    def finished(self, code, status):
        self.poll(); self.lock_fields(False)
        p = self.run_dir / 'result.json'; ok = False
        if p.exists():
            r = json.loads(p.read_text(encoding='utf8')); ok = code == 0 and not r.get('error') and not r.get('restore_errors')
            self.summary.setText(('会话结束：' if ok else '会话失败：') + r['restore_status'] +
                                 (' · ' + str(r['error']) if r.get('error') else ''))
            self.append('结果：' + str(p))
        else: self.summary.setText('进程退出但缺少结果；停止／恢复状态未确认。')
        if self.close_pending and ok: self.accept()
        elif self.close_pending: self.close_pending = False

    def reject(self):
        if self.running(): self.close_pending = True; self.request_stop()
        else: super().reject()

    def closeEvent(self, event):
        if self.running():
            event.ignore(); self.close_pending = True; self.request_stop()
        else: event.accept()
