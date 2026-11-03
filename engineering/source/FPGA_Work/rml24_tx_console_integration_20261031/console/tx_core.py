"""Offline configuration and immutable public-frame preparation. No IIO import."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
CLASSES = ['OOK','4ASK','8ASK','BPSK','QPSK','8PSK','16PSK','32PSK',
           '16APSK','32APSK','64APSK','128APSK','16QAM','32QAM','64QAM',
           '128QAM','256QAM','AM-SSB-WC','AM-SSB-SC','AM-DSB-WC','AM-DSB-SC',
           'FM','GMSK','OQPSK']
FS = 2_560_000
BW = 18_000_000

def mhz_to_hz(text):
    try:
        v = Decimal(str(text)) * 1_000_000
    except InvalidOperation:
        raise ValueError('频率格式无效') from None
    if not v.is_finite() or v != v.to_integral_value() or not 70_000_000 <= v <= 6_000_000_000:
        raise ValueError('频率须为70–6000 MHz，精确到整数Hz')
    return int(v)

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def defaults():
    bundled=(ROOT/'assets/manifest_240.json').is_file()
    return dict(dataset=str(ROOT/'assets' if bundled else WORKSPACE/'rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset'),
                manifest=str(ROOT/'assets/manifest_240.json' if bundled else WORKSPACE/'rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json'),
                radio_root=str(ROOT/'vendor'), uri='usb:1.8.5',
                center_hz=2_400_000_000, gain_db=-40.0, hold_sec=6.0, gap_sec=.25,
                mode='single', class_index=4, message_index=0, max_seconds=60.0, real=False)

def validate(c):
    if type(c.get('real')) is not bool:raise ValueError('真实TX开关须为布尔值')
    if c['mode'] not in ('single','cycle'): raise ValueError('仅支持单类或24类轮播')
    if type(c['center_hz']) is not int or not 70_000_000 <= c['center_hz'] <= 6_000_000_000:
        raise ValueError('中心频率超出界面支持范围')
    for key,low,high in [('gain_db',-89.75,-10),('hold_sec',.2,600),
                         ('gap_sec',.05,60),('max_seconds',1,3600)]:
        value=float(c[key])
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{key} 须在 {low} 至 {high} 之间')
    if type(c['class_index']) is not int or not 0 <= c['class_index'] < 24:
        raise ValueError('调制类型无效')
    if type(c.get('message_index',0)) is not int or not 0<=c.get('message_index',0)<10:raise ValueError('Message index must be 0..9')
    if not str(c['uri']).strip(): raise ValueError('请填写TX设备URI')
    return c

def verify_vendor():
    identity=json.loads((ROOT/'vendor_identity.json').read_text(encoding='utf8'))
    for name,expected in identity.items():
        if hashlib.sha256((ROOT/'vendor'/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('冻结TX依赖校验失败: '+name)

def prepare(c):
    validate(c);verify_vendor()
    dataset=Path(c['dataset']).resolve()
    doc=json.loads(Path(c['manifest']).read_text(encoding='utf-8-sig'))
    rows=doc.get('records',[])
    selected={};seen=set()
    for row in rows:
        seq=int(row['seq'])
        if seq in seen:raise ValueError('清单seq重复')
        seen.add(seq)
        try: label=int(Path(row['file']).stem.split('_')[0])
        except ValueError:raise ValueError('无法从冻结资产文件名获得PC端类别')
        if not 0<=label<24:raise ValueError('资产类别编号错误')
        selected.setdefault(label,[]).append(row)
    wanted=[c['class_index']] if c['mode']=='single' else list(range(24))
    if any(i not in selected for i in wanted):raise ValueError('清单缺少所选类别')
    frame_module=load_module('frozen_frame',ROOT/'vendor/frame_builder.py')
    # Importing pilot_recovery builds common references only; does not access SDR.
    public=load_module('frozen_public',ROOT/'vendor/pilot_recovery.py')
    plan=[]
    for i in wanted:
        index=c.get('message_index',0)
        if index>=len(selected[i]):raise ValueError('Selected message unavailable for class '+str(i))
        row=selected[i][index];path=(dataset/row['file']).resolve()
        try:path.relative_to(dataset)
        except ValueError:raise ValueError('资产路径越出数据目录')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['source_sha256']:raise ValueError('资产SHA不符: '+str(path))
        frame=frame_module.build_frame(raw,public.train,public.tail)
        plan.append(dict(class_index=i,name=CLASSES[i],seq=row['seq'],
                         source_sha256=row['source_sha256'],frame=frame))
    return plan

def spectrum(frame):
    n=2048
    # First actual 1024-sample payload, after settle(2048) + train(2048).
    x=np.asarray(frame[4096:5120],dtype=np.complex128)
    p=abs(np.fft.fftshift(np.fft.fft(x*np.hanning(len(x)),n)))**2
    return 10*np.log10(np.maximum(p,1e-12)/max(float(p.max()),1e-12))
