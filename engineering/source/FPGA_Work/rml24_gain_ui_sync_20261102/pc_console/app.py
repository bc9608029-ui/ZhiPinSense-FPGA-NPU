"""RML24 desktop TX console. Opening the application never transmits."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
from PyQt5 import QtCore,QtGui,QtWidgets as W
from tx_core import ROOT,CLASSES,defaults,mhz_to_hz,prepare,spectrum,validate

COLORS=dict(bg='#f0f4f8',surface='#ffffff',text='#182a40',muted='#52647b',
            primary='#006b73',nav='#14263d',outline='#ced9e3',error='#b82d40')

class Spectrum(W.QWidget):
    def __init__(self):
        super().__init__();self.values=None;self.setMinimumHeight(190)
        self.setAccessibleName('实际载荷数字频谱预览，非射频测量')
    def paintEvent(self,event):
        p=QtGui.QPainter(self);p.setRenderHint(p.Antialiasing)
        r=self.rect().adjusted(42,15,-18,-30);p.fillRect(self.rect(),QtGui.QColor('#12253c'))
        p.setPen(QtGui.QColor('#31445b'))
        for i in range(5):
            y=r.top()+r.height()*i/4;p.drawLine(QtCore.QPointF(r.left(),y),QtCore.QPointF(r.right(),y))
        p.setPen(QtGui.QColor('#b7c7d7'));p.setFont(QtGui.QFont('Segoe UI',9))
        for i,s in enumerate(['0','−20','−40','−60','−80']):p.drawText(5,int(r.top()+r.height()*i/4+5),s)
        for i,s in enumerate(['−1.28','0','+1.28 MHz']):p.drawText(int(r.left()+i*r.width()/2-12),self.height()-8,s)
        if self.values is None:
            p.drawText(r,QtCore.Qt.AlignCenter,'点击“校验与预览”载入实际数字波形');return
        y=np.maximum(-80,np.minimum(0,self.values));path=QtGui.QPainterPath()
        for i,v in enumerate(y):
            point=QtCore.QPointF(r.left()+i*r.width()/(len(y)-1),r.top()-v*r.height()/80)
            if i==0:path.moveTo(point)
            else:path.lineTo(point)
        p.setPen(QtGui.QPen(QtGui.QColor('#54d6c7'),1.3));p.drawPath(path)

def label(text,object_name=''):
    l=W.QLabel(text);l.setWordWrap(True)
    if object_name:l.setObjectName(object_name)
    return l

class Window(W.QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('RML24 · 信号发射控制台');self.resize(1280,850)
        self.setMinimumSize(1000,760);self.proc=None;self.run_dir=None;self.buffer='';self.validated=False
        self.close_pending=False;self.started=0;self.scanning=False;self.was_real=False;self.event_lines=0
        self.seen_events=set();self.pipe_buffer=''
        self.c=defaults();self.fields=[]
        base=W.QWidget();self.setCentralWidget(base);outer=W.QHBoxLayout(base);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        nav=W.QFrame();nav.setObjectName('nav');nav.setFixedWidth(205);nv=W.QVBoxLayout(nav);nv.setContentsMargins(23,30,23,25)
        nv.addWidget(label('RML24','brand'));nv.addWidget(label('SIGNAL LAB','navSub'));nv.addSpacing(32)
        nv.addWidget(label('发射控制台','navActive'));nv.addWidget(label('TX CONTROL','navSub'));nv.addSpacing(25)
        nv.addWidget(label('独立发射\n接收端自主识别','navInfo'));nv.addStretch()
        nv.addWidget(label('固定公共帧\n2.56 MS/s · 18 MHz\n1024 点载荷 × 8','navInfo'))
        nv.addSpacing(18);nv.addWidget(label('PC → Pluto TX\n同轴测试配置','navSub'));outer.addWidget(nav)
        page=W.QWidget();layout=W.QVBoxLayout(page);layout.setContentsMargins(28,24,28,20);layout.setSpacing(16);outer.addWidget(page)
        header=W.QHBoxLayout();titles=W.QVBoxLayout();titles.addWidget(label('信号发射控制台','title'));titles.addWidget(label('配置波形，查看计划，再开始一次独立发射。','subtitle'));header.addLayout(titles);header.addStretch()
        self.badge=label('●  离线就绪','badge');header.addWidget(self.badge);layout.addLayout(header)
        body=W.QHBoxLayout();body.setSpacing(18);layout.addLayout(body,1)
        card=W.QFrame();card.setObjectName('card');cl=W.QVBoxLayout(card);cl.setContentsMargins(22,20,22,20);cl.setSpacing(13)
        cl.addWidget(label('01   发射配置','section'))
        form=W.QFormLayout();form.setSpacing(12);form.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.mode=W.QComboBox();self.mode.addItems(['单类重复','24类轮播']);form.addRow('信号计划',self.mode)
        self.modulation=W.QComboBox();self.modulation.addItems(CLASSES);self.modulation.setCurrentIndex(4);form.addRow('调制类型',self.modulation)
        self.message_bank=W.QComboBox();self.message_bank.addItems(['\u65e2\u6709\u6d88\u606f / 10\u6761','\u65b0\u79cd\u5b50\u6d88\u606f / 2\u6761 / \u5f85RF\u9a8c\u8bc1']);form.addRow('\u6d88\u606f\u96c6',self.message_bank)
        self.message=W.QSpinBox();self.message.setRange(1,10);self.message.setValue(1);form.addRow('\u6d88\u606f\u5e8f\u53f7 / \u65e2\u6709\u6837\u672c',self.message)
        self.frequency=W.QLineEdit('2400.000000');self.frequency.setAccessibleName('中心频率，MHz');form.addRow('中心频率 / MHz',self.frequency)
        self.gain=W.QDoubleSpinBox();self.gain.setRange(-89.75,0);self.gain.setDecimals(2);self.gain.setSingleStep(.25);self.gain.setValue(-40);self.gain.setSuffix(' dB');self.gain.setToolTip('数值越接近0，发射通常越强；这是硬件增益／衰减，不是dBm，也不是数字幅度。');form.addRow('TX增益 / 衰减',self.gain)
        self.duration=W.QDoubleSpinBox();self.duration.setRange(1,3600);self.duration.setValue(60);self.duration.setSuffix(' s');form.addRow('会话时限',self.duration)
        self.hold=W.QDoubleSpinBox();self.hold.setRange(.2,600);self.hold.setValue(6);self.hold.setSuffix(' s / 样本');form.addRow('单次保持',self.hold)
        self.uri=W.QLineEdit('usb:1.9.5');form.addRow('TX设备 URI',self.uri)
        cl.addLayout(form)
        self.scan=W.QPushButton('检测 USB 设备');self.scan.clicked.connect(self.scan_usb);cl.addWidget(self.scan)
        more=W.QGroupBox('数据源与环境');mf=W.QFormLayout(more)
        self.dataset=W.QLineEdit(self.c['dataset']);self.manifest=W.QLineEdit(self.c['manifest'])
        self.interpreter=W.QLineEdit(self.find_radio_python())
        for name,widget in [('IQ目录',self.dataset),('清单文件',self.manifest),('运行解释器',self.interpreter)]:
            row=W.QWidget();rl=W.QHBoxLayout(row);rl.setContentsMargins(0,0,0,0);rl.addWidget(widget)
            browse=W.QPushButton('…');browse.setFixedWidth(34)
            browse.clicked.connect(lambda _,w=widget,n=name:self.browse(w,n));rl.addWidget(browse);mf.addRow(name,row)
        advanced=W.QPushButton('数据源与运行环境  ▸');advanced.setCheckable(True)
        advanced.toggled.connect(more.setVisible);cl.addWidget(advanced);more.setVisible(False);cl.addWidget(more)
        self.multi=W.QPushButton('多信号同时发射 · 待链路验收');self.multi.setEnabled(False);cl.addWidget(self.multi)
        cl.addWidget(label('冻结IQ与公共帧，载荷重复8次。数字幅度固定；TX硬件增益不是dBm。接收端独立调节RX增益。','hint'));cl.addStretch()
        # The configuration must scroll on small laptop screens and at 150% DPI.
        for form_layout in (form,mf):
            form_layout.setVerticalSpacing(12)
            for row_index in range(form_layout.rowCount()):
                field=form_layout.itemAt(row_index,W.QFormLayout.FieldRole)
                caption=form_layout.itemAt(row_index,W.QFormLayout.LabelRole)
                if field and field.widget():field.widget().setMinimumHeight(44)
                if caption and caption.widget():caption.widget().setMinimumHeight(32)
        card.setMinimumWidth(390)
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        scroll=W.QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(W.QFrame.NoFrame)
        scroll.setWidget(card);body.addWidget(scroll,5)
        right_widget=W.QWidget();right=W.QVBoxLayout(right_widget);right.setContentsMargins(0,0,0,0);right.setSpacing(14)
        right.setSizeConstraint(W.QLayout.SetMinimumSize)
        right_scroll=W.QScrollArea();right_scroll.setWidgetResizable(True);right_scroll.setFrameShape(W.QFrame.NoFrame)
        right_scroll.setWidget(right_widget);body.addWidget(right_scroll,6)
        summary=W.QFrame();summary.setObjectName('card');sl=W.QVBoxLayout(summary);sl.setContentsMargins(22,18,22,18)
        sl.addWidget(label('02   本次发射','section'));self.big=label('2400.000000 MHz','frequency');sl.addWidget(self.big)
        self.summary=label('QPSK  /  单类重复\n2.56 MS/s   ·   18 MHz   ·   TX −40 dB','subtitle');sl.addWidget(self.summary)
        self.status=label('尚未打开设备，也没有发射。','status');sl.addWidget(self.status)
        summary.setMinimumHeight(200);sl.setSizeConstraint(W.QLayout.SetMinimumSize)
        self.summary.setMinimumHeight(58);self.status.setMinimumHeight(44)
        self.badge.setFixedHeight(42)
        right.addWidget(summary)
        self.plot=Spectrum();self.plot.setMinimumHeight(240);right.addWidget(self.plot)
        right.addWidget(label('实际载荷频谱 · 归一化dB，非实测RF','hint'))
        self.log=W.QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(1200);self.log.setMinimumHeight(130);self.log.setAccessibleName('发射运行日志');right.addWidget(self.log,1)
        right_widget.setMinimumWidth(430)
        for i in range(right.count()):
            item=right.itemAt(i)
            if item.widget() and isinstance(item.widget(),W.QLabel):item.widget().setMinimumHeight(30)
        action=W.QFrame();action.setObjectName('card');al=W.QHBoxLayout(action);al.setContentsMargins(18,14,18,14)
        self.real=W.QCheckBox('启用真实TX（默认关闭）');al.addWidget(self.real);al.addStretch()
        self.check=W.QPushButton('校验与预览');self.check.clicked.connect(self.preview);al.addWidget(self.check)
        self.start=W.QPushButton('开始离线演练');self.start.setObjectName('primary');self.start.clicked.connect(self.begin);al.addWidget(self.start)
        self.stop=W.QPushButton('停止');self.stop.setObjectName('danger');self.stop.setEnabled(False);self.stop.clicked.connect(self.request_stop);al.addWidget(self.stop);layout.addWidget(action)
        self.footer=label('就绪   /   未启动TX   ·   Esc停止   ·   Ctrl+Enter开始','hint');layout.addWidget(self.footer)
        self.fields=[self.message_bank,self.message,self.mode,self.modulation,self.frequency,self.gain,self.duration,self.hold,self.uri,self.dataset,self.manifest,self.interpreter,self.real]
        self.message.valueChanged.connect(self.update_summary);self.message_bank.currentIndexChanged.connect(self.change_message_bank)
        self.mode.currentIndexChanged.connect(self.update_summary);self.modulation.currentIndexChanged.connect(self.update_summary)
        self.frequency.textChanged.connect(self.update_summary);self.gain.valueChanged.connect(self.update_summary);self.real.toggled.connect(self.update_summary)
        W.QShortcut(QtGui.QKeySequence('Escape'),self,activated=self.request_stop)
        W.QShortcut(QtGui.QKeySequence('Ctrl+Return'),self,activated=self.begin)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(200)
        self.apply_theme();self.update_summary()
    def find_radio_python(self):
        p=Path('D:/radioconda/python.exe');return str(p) if p.is_file() else sys.executable
    def browse(self,w,name):
        if name=='IQ目录':p=W.QFileDialog.getExistingDirectory(self,'选择IQ目录',w.text())
        else:p,_=W.QFileDialog.getOpenFileName(self,'选择'+name,w.text())
        if p:w.setText(p)
    def apply_theme(self):
        self.setStyleSheet('''
        QWidget {font-family:"Microsoft YaHei UI","Segoe UI"; font-size:16px; color:#182a40;}
        QMainWindow,QWidget#central {background:#f0f4f8;}
        QFrame#nav {background:#14263d;} QFrame#nav QLabel {color:#c2d0df;}
        QFrame#nav QLabel#brand {font-size:30px;font-weight:700;color:white;}
        QFrame#nav QLabel#navActive {font-size:20px;color:#70e0cf;font-weight:600;}
        QFrame#nav QLabel#navSub {font-size:12px;color:#b3c5d8;}
        QFrame#nav QLabel#navInfo {font-size:16px;color:#d8e3ed;}
        QFrame#card {background:white;border:1px solid #ced9e3;border-radius:12px;}
        QLabel#title {font-size:28px;font-weight:700;} QLabel#subtitle {color:#52647b;}
        QLabel#section {font-size:16px;font-weight:600;color:#006b73;}
        QLabel#frequency {font-size:28px;font-weight:700;}
        QLabel#hint {font-size:12px;color:#52647b;} QLabel#status {color:#00616a;padding-top:8px;}
        QLabel#badge {background:#e1f1ee;color:#075e56;border-radius:14px;padding:8px 15px;font-size:14px;}
        QLineEdit,QComboBox,QDoubleSpinBox {background:#f8fafc;border:1px solid #bac9d7;border-radius:6px;padding:7px;min-height:23px;}
        QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus,QPushButton:focus {border:2px solid #007e86;}
        QPushButton {background:#f6f9fb;border:1px solid #bac9d7;border-radius:7px;padding:9px 14px;min-height:24px;}
        QPushButton:hover {background:#e6eff4;} QPushButton#primary {background:#006b73;color:white;border:1px solid #006b73;font-weight:600;}
        QPushButton#primary:hover {background:#00565c;} QPushButton#danger {color:#b82d40;border-color:#d49aa2;}
        QPushButton:disabled {color:#7b8794;background:#edf1f4;border-color:#d6dfe7;}
        QPlainTextEdit {background:white;border:1px solid #ced9e3;border-radius:8px;padding:10px;font-family:Consolas;font-size:13px;}
        QGroupBox {border:1px solid #ced9e3;border-radius:7px;margin-top:12px;padding-top:15px;font-size:14px;}
        QGroupBox::title {subcontrol-origin:margin;left:10px;padding:0 5px;}
        ''')
        self.centralWidget().setAutoFillBackground(True)
        pal=self.centralWidget().palette();pal.setColor(QtGui.QPalette.Window,QtGui.QColor(COLORS['bg']));self.centralWidget().setPalette(pal)
    def change_message_bank(self,*args):
        if self.message_bank.currentIndex()==1:
            base=ROOT.parent/'new_messages';self.dataset.setText(str(base));self.manifest.setText(str(base/'manifest.json'));self.message.setMaximum(2)
        else:
            c=defaults();self.dataset.setText(c['dataset']);self.manifest.setText(c['manifest']);self.message.setMaximum(10)
        self.update_summary()
    def config(self):
        c=defaults();c.update(dataset=self.dataset.text(),manifest=self.manifest.text(),uri=self.uri.text().strip(),
          center_hz=mhz_to_hz(self.frequency.text()),gain_db=self.gain.value(),hold_sec=self.hold.value(),
          max_seconds=self.duration.value(),mode='single' if self.mode.currentIndex()==0 else 'cycle',
          class_index=self.modulation.currentIndex(),message_index=self.message.value()-1,real=self.real.isChecked())
        return validate(c)
    def update_summary(self,*args):
        self.validated=False
        self.big.setText(self.frequency.text()+' MHz')
        name=CLASSES[self.modulation.currentIndex()] if self.mode.currentIndex()==0 else '24 类轮播'
        self.summary.setText(f'{name}  /  {self.mode.currentText()}\n2.56 MS/s   ·   18 MHz   ·   TX {self.gain.value():g} dB')
        self.start.setText('开始真实发射' if self.real.isChecked() else '开始离线演练')
    def append(self,text):self.log.appendPlainText(time.strftime('%H:%M:%S')+'  '+text)
    def preview(self):
        try:
            c=self.config();plan=prepare(c);self.plot.values=spectrum(plan[0]['frame']);self.plot.update()
            self.validated=True;self.status.setText(f'资产与SHA已校验 · {len(plan)} 类 · 尚未发射')
            self.append(f'校验通过：{len(plan)}类；公共帧与固定尺度保持原样。')
            if c['mode']=='cycle' and c['max_seconds']<24*(c['hold_sec']+c['gap_sec']):
                self.append(f'提示：完整24类一轮约需 {24*(c["hold_sec"]+c["gap_sec"]):g} 秒，当前时限会提前结束。')
            return True
        except Exception as exc:self.status.setText('校验失败：'+str(exc));self.append('错误：'+str(exc));return False
    def running(self):return self.proc is not None and self.proc.state()!=QtCore.QProcess.NotRunning
    def launch(self,args):
        self.proc=QtCore.QProcess(self);self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        env=QtCore.QProcessEnvironment.systemEnvironment();env.insert('PYTHONIOENCODING','utf-8');env.insert('PYTHONUTF8','1')
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self.read_output);self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.buffer='';self.pipe_buffer='';self.seen_events=set();self.proc.setWorkingDirectory(str(ROOT));self.proc.start(self.interpreter.text(),args)
        for w in self.fields:w.setEnabled(False)
        self.check.setEnabled(False);self.start.setEnabled(False);self.scan.setEnabled(False);self.stop.setEnabled(not self.scanning)
    def begin(self):
        if self.running() or not self.preview():return
        if not Path(self.interpreter.text()).is_file():self.append('运行解释器不存在');return
        c=self.config();self.was_real=c['real'];self.scanning=False
        self.run_dir=ROOT/'runs'/(time.strftime('%Y%m%d_%H%M%S')+'_'+str(time.time_ns()%1000000))
        self.run_dir.mkdir(parents=True);(self.run_dir/'config.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf8')
        self.started=time.monotonic();self.status.setText('启动真实TX中…' if c['real'] else '离线演练中 · 不访问SDR')
        self.event_lines=0
        self.badge.setText('●  真实TX启动中' if c['real'] else '●  离线演练')
        self.launch(['-u',str(ROOT/'tx_worker.py'),'--config',str(self.run_dir/'config.json')])
    def scan_usb(self):
        if self.running():return
        self.scanning=True;self.run_dir=None;self.was_real=False
        self.scan_result=ROOT/'runs'/('scan_'+str(time.time_ns())+'.json')
        self.scan_result.parent.mkdir(exist_ok=True)
        self.append('扫描USB设备（只读检测）…')
        self.launch(['-u',str(ROOT/'tx_worker.py'),'--scan','--scan-out',str(self.scan_result)])
    def request_stop(self):
        if not self.running() or self.scanning:return
        (self.run_dir/'stop.request').touch();self.stop.setEnabled(False)
        self.status.setText('停止请求已发送，等待TX缓冲停止与属性恢复…');self.append('请求停止；等待工作进程完成清理。')
    def read_output(self):
        self.pipe_buffer+=bytes(self.proc.readAllStandardOutput()).decode('utf8',errors='replace')
        while '\n' in self.pipe_buffer:
            line,self.pipe_buffer=self.pipe_buffer.split('\n',1)
            self.buffer+=line+'\n'
        self.consume_rows()
    def consume_rows(self):
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            try:
                row=json.loads(line);event=row['event']
                identity=row.get('time_ns')
                if identity is not None:
                    if identity in self.seen_events:continue
                    self.seen_events.add(identity)
                if event=='devices':
                    uris=row['uris'];self.append('设备：'+(', '.join(uris) or '未找到USB SDR'))
                    if len(uris)==1:self.uri.setText(uris[0])
                elif event in ('transmitting','preview'):
                    self.status.setText(('正在真实发射' if event=='transmitting' else '离线演练')+' · '+row['name'])
                    self.badge.setText('●  真实发射中' if event=='transmitting' else '●  离线演练')
                    self.append(('TX ' if event=='transmitting' else '演练 ')+row['name']+' · '+str(row['center_hz'])+' Hz')
                elif event=='finished':
                    self.append('结束：'+row['restore_status']+(('；错误 '+str(row['error'])) if row['error'] else ''))
                    message='离线演练已结束' if not row['real'] else ('已停止 · 设备属性已恢复并读回确认' if not row['restore_errors'] else '停止后属性恢复异常，请核查设备')
                    if row['error']:message='会话失败：'+row['error']
                    self.status.setText(message);self.badge.setText('▲  会话异常' if row['error'] or row['restore_errors'] else '●  已结束')
                elif event=='error':self.status.setText('错误：'+row['message']);self.append('错误：'+row['message'])
                elif event=='configured':self.append('设备参数已写入并回读确认。')
                elif event=='muted':self.status.setText('TX缓冲已停止 · 切换间隔')
                else:self.append(line)
            except (ValueError,KeyError,TypeError):self.append(line)
    def read_event_file(self):
        if self.scanning or not self.run_dir:return
        path=self.run_dir/'events.jsonl'
        if not path.is_file():return
        # File log is authoritative and survives Windows QProcess pipe quirks.
        # Only complete JSONL lines are consumed; a partial tail waits one tick.
        lines=path.read_bytes().splitlines(keepends=True)
        complete=[line.decode('utf8') for line in lines if line.endswith(b'\n')]
        fresh=complete[self.event_lines:];self.event_lines=len(complete)
        if fresh:
            self.buffer+=''.join(fresh);self.consume_rows()
    def process_error(self,error):
        self.append('工作进程错误：'+self.proc.errorString())
        if error==QtCore.QProcess.FailedToStart:self.finished(-1,QtCore.QProcess.CrashExit)
    def finished(self,code,status):
        self.read_output()
        self.read_event_file()
        if self.scanning and self.scan_result.is_file():
            self.buffer+=self.scan_result.read_text(encoding='utf8')+'\n';self.consume_rows()
        for w in self.fields:w.setEnabled(True)
        self.check.setEnabled(True);self.start.setEnabled(True);self.scan.setEnabled(True);self.stop.setEnabled(False)
        result=self.run_dir/'result.json' if self.run_dir else None
        if not self.scanning and (not result or not result.is_file()):
            self.status.setText('进程异常退出，真实TX停止/恢复状态未确认' if self.was_real else '离线进程失败，检查日志')
            self.badge.setText('▲  状态待核实' if self.was_real else '▲  运行失败')
        self.append(f'工作进程退出：{code}')
        if self.close_pending:
            self.close_pending=False
            if not self.was_real:self.close()
            elif result and result.is_file():
                outcome=json.loads(result.read_text(encoding='utf8'))
                if not outcome['restore_errors']:self.close()
                else:self.append('恢复异常：窗口保持打开，请核查设备状态。')
    def tick(self):
        if self.running() and not self.scanning:
            self.read_event_file()
            self.footer.setText(f'运行 {time.monotonic()-self.started:.1f} s  /  时限 {self.duration.value():g} s  ·  Esc停止  ·  日志：{self.run_dir.name}')
    def closeEvent(self,event):
        if self.running():
            event.ignore();self.close_pending=True
            if not self.scanning:self.request_stop()
            else:self.status.setText('等待USB检测结束后关闭…')
        else:event.accept()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--screenshot',type=Path);ap.add_argument('--preview',action='store_true');a=ap.parse_args()
    W.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app=W.QApplication(sys.argv[:1]);QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc');app.setFont(QtGui.QFont('Microsoft YaHei',10));window=Window();window.show()
    if a.preview:QtCore.QTimer.singleShot(100,window.preview)
    if a.screenshot:
        def save():window.grab().save(str(a.screenshot));app.quit()
        QtCore.QTimer.singleShot(900,save)
    return app.exec_()
if __name__=='__main__':sys.exit(main())
