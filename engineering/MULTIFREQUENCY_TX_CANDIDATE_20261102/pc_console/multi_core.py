"""Dual-frequency TX: frozen per-lane public frame, no receiver communication."""
from pathlib import Path
import hashlib
import math
import numpy as np
from scipy.signal import resample_poly
from tx_core import defaults, prepare, FS, BW

def validate(c):
    if type(c.get('real')) is not bool:
        raise ValueError('真实发射开关必须为布尔值')
    if not str(c.get('uri', '')).strip():
        raise ValueError('必须填写并确认TX设备URI')
    if not math.isfinite(float(c['gain_db'])) or not -89.75 <= float(c['gain_db']) <= 0:
        raise ValueError('TX增益应为 −89.75 至 0 dB')
    if not math.isfinite(float(c['max_seconds'])) or not 1 <= float(c['max_seconds']) <= 3600:
        raise ValueError('会话时限应为1至3600秒')
    lanes=c.get('lanes',[])
    if not 2<=len(lanes)<=4:raise ValueError('本候选支持2至4路')
    for lane in lanes:
        f=lane['hz']
        if type(f) is not int or not 70_000_000<=f<=6_000_000_000:
            raise ValueError('每路频率须为70–6000 MHz，精确到整数Hz')
        if type(lane['class']) is not int or not 0<=lane['class']<24:raise ValueError('调制类别无效')
        if type(lane['message']) is not int or not 0<=lane['message']<10:raise ValueError('消息序号应为1至10')
    freqs=sorted(l['hz'] for l in lanes)
    if any(b-a<3_200_000 for a,b in zip(freqs,freqs[1:])):
        raise ValueError('相邻频点至少相隔3.2 MHz，避免主频谱重叠')
    # 10.24 or 20.48 MS/s cyclic buffers both have 156.25 Hz FFT spacing.
    # Integer offsets divisible by 625 Hz preserve the periodic frequency shift.
    if any((f-freqs[0])%1250 for f in freqs):
        raise ValueError('各路频差须为1250 Hz整数倍，例如3.6 MHz')
    span=freqs[-1]-freqs[0]
    if span>(7_200_000 if len(lanes)==2 else 12_800_000):
        raise ValueError('两路总跨度最多7.2 MHz，三／四路总跨度最多12.8 MHz')
    mask=c.get('initial_mask')
    if type(mask) is not int or not 0<=mask<1<<len(lanes):raise ValueError('路开关配置无效')
    return c


def build(c):
    validate(c)
    freqs=[l['hz'] for l in c['lanes']]
    # Round midpoint to a common 625-Hz offset grid, retaining actual lane Hz.
    lo=min(freqs)+((max(freqs)-min(freqs))//1250)*625
    upsample=4 if len(freqs)==2 else 8
    tx_fs=FS*upsample
    shifted=[];identities=[]
    for lane in c['lanes']:
        cfg=defaults()
        cfg.update(dataset=c['dataset'],manifest=c['manifest'],mode='single',
                   class_index=lane['class'],message_index=lane['message'],real=False)
        item=prepare(cfg)[0];frame=np.asarray(item['frame'])
        if len(frame)!=16384 or not np.isfinite(frame).all():raise ValueError('公共帧长度或数值无效')
        up=resample_poly(frame,upsample,1);offset=lane['hz']-lo
        shifted.append(up*np.exp(2j*np.pi*offset*np.arange(len(up))/tx_fs))
        identities.append(dict(name=item['name'],source_sha256=item['source_sha256'],center_hz=lane['hz'],offset_hz=offset))
    waves={};stats={}
    for mask in range(1<<len(shifted)):
        w=sum((z for i,z in enumerate(shifted) if mask & (1<<i)),np.zeros_like(shifted[0]))
        peak=float(max(abs(w.real).max(),abs(w.imag).max()))
        if not np.isfinite(w).all() or peak>2047:
            raise ValueError(f'组合{mask}合成幅度超出冻结量化范围，拒绝发射；不自动归一化')
        iq=np.column_stack((np.rint(w.real),np.rint(w.imag))).astype('<i2')*16
        waves[mask]=w;stats[str(mask)]=dict(samples=len(w),component_peak=peak,device_sha256=hashlib.sha256(iq.tobytes()).hexdigest())
    report=dict(tx_lo_hz=lo,tx_sample_rate=tx_fs,per_lane_rate=FS,tx_bandwidth_hz=BW,
                lanes=identities,scenes=stats,rf_validated=False,known_limitations=[
                    '实际2至4路RF与接收漏检尚待测试；频差限制不是分离能力验收',
                    '既有双路方案存在采样镜像，曾离线测得首镜像约−28 dBc；新参数组合需重新实测',
                    '每路沿用公开幅度，不对类别或样本做自动归一化；四路不是已验收能力',
                    '不承诺同频、重叠信号分离或全频段多路同时接收'])
    return waves,report
