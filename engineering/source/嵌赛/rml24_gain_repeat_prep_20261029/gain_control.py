"""Gain configuration for an isolated experiment. No module import touches IIO."""
import math
import time

def number(value):
    result=float(str(value).split()[0])
    if not math.isfinite(result):raise ValueError('nonfinite device readback')
    return result

def configure(radio,mode,gain,settle_seconds=1.0):
    if mode not in ('manual','slow_attack'):raise ValueError('unsupported gain mode')
    if mode=='manual' and (gain is None or not math.isfinite(gain) or not 0<=gain<=73):
        raise ValueError('manual gain must be in [0,73] dB')
    radio.set(radio.rx,'gain_control_mode',mode)
    if radio.get(radio.rx,'gain_control_mode').strip()!=mode:raise RuntimeError('gain mode readback mismatch')
    if mode=='manual':
        radio.set(radio.rx,'hardwaregain',gain)
        if abs(number(radio.get(radio.rx,'hardwaregain'))-gain)>.1:raise RuntimeError('manual gain readback mismatch')
    time.sleep(settle_seconds)
    return snapshot(radio)

def snapshot(radio):
    return dict(mode=radio.get(radio.rx,'gain_control_mode').strip(),
                gain_db=number(radio.get(radio.rx,'hardwaregain')),
                monotonic_ns=time.monotonic_ns())
