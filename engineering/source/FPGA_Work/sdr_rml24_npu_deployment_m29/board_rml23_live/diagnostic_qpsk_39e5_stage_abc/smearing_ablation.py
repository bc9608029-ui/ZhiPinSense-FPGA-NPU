#!/usr/bin/env python3
"""smearing_ablation.py -- controlled experiment: which channel component turns a
clean RRC QPSK's |x|^2 symbol line into a flat/smeared spectrum?

Generate a clean 8-sps RRC(beta=0.35) QPSK (like the real signal), then apply,
one at a time, the components RadioML2018 bakes in:
  clean  -> baseline (should have a clean line at Rs)
  + CFO  -> constant center-frequency offset
  + SRO  -> constant fractional sample-rate offset
  + 2-tap multipath (non-integer delay)
  + flat Rician (single-tap, no delay)
Measure the |x|^2 symbol-line prominence (top/2nd, same metric as Stage B:
>1.5 == clean line).  Purely local, no model, no board.
"""
import numpy as np

FS = 128000.0
N = 1024
SPS = 8
BETA = 0.35


def rrc(sps, beta, span=10):
    T = float(sps)
    n = int(span * T)
    t = (np.arange(n + 1) - n / 2.0) / T          # in symbol periods, centered
    h = np.zeros_like(t)
    num = np.sin(np.pi * t * (1 - beta)) + 4 * beta * t * np.cos(np.pi * t * (1 + beta))
    den = np.pi * t * (1 - (4 * beta * t) ** 2)
    nz = np.abs(den) > 1e-9
    h[nz] = num[nz] / den[nz]
    h[np.abs(t) < 1e-9] = 1.0 - beta + 4.0 * beta / np.pi
    tc = 1.0 / (4.0 * beta)
    idx = np.abs(np.abs(t) - tc) < 1e-6
    h[idx] = (beta / np.sqrt(2.0)) * (
        (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
        + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta)))
    h = h / np.sqrt(np.sum(h ** 2) * sps)          # unit-energy pulse
    return h


def make_qpsk(sps=SPS, beta=BETA):
    rng = np.random.default_rng(7)
    nsym = N // sps
    sym = (2 * rng.integers(0, 2, nsym) - 1) + 1j * (2 * rng.integers(0, 2, nsym) - 1)
    sym = sym / np.sqrt(2.0)
    up = np.zeros(N, dtype=complex)
    up[::sps] = sym
    h = rrc(sps, beta)
    x = np.convolve(up, h, mode="same")
    return x


def prominence(x):
    e = np.abs(x) ** 2
    e = e - e.mean()
    S = np.abs(np.fft.fft(e))
    half = N // 2
    seg = S[1:half]
    order = np.argsort(seg)[::-1]
    pk_hz = (order[0] + 1) * FS / N
    top2 = seg[order[0]] / seg[order[1]]
    return pk_hz, top2


def sro_resample(x, eps):
    # constant fractional sample-rate offset: resample time axis by (1+eps)
    n = np.arange(N)
    t_new = n / (1.0 + eps)
    return np.interp(t_new, n, x.real) + 1j * np.interp(t_new, n, x.imag)


x = make_qpsk()
print("=== |x|^2 symbol-line prominence (top/2nd, >1.5 == clean) ===")
pk, p = prominence(x)
print("clean RRC QPSK (8 sps, b=0.35)      : peak=%6.0f Hz  prominence=%.3f" % (pk, p))

# + constant CFO (envelope should be invariant)
cfo = x * np.exp(1j * 2 * np.pi * 5000.0 * np.arange(N) / FS)
pk, p = prominence(cfo)
print("+ CFO 5 kHz (constant)              : peak=%6.0f Hz  prominence=%.3f" % (pk, p))

# + constant SRO
sro = sro_resample(x, 0.01)
pk, p = prominence(sro)
print("+ SRO +1%% (constant)               : peak=%6.0f Hz  prominence=%.3f" % (pk, p))

# + 2-tap multipath (non-integer delay 3.5 samples)
mp = 1.0 * x + 0.6 * np.roll(x, 3) + 0.0j
# use a fractional delay via linear interp
d = 3.5
x2 = np.interp(np.arange(N) - d, np.arange(N), x.real) + 1j * np.interp(np.arange(N) - d, np.arange(N), x.imag)
mp = 1.0 * x + 0.6 * x2
pk, p = prominence(mp)
print("+ 2-tap multipath (delay 3.5 samp)  : peak=%6.0f Hz  prominence=%.3f" % (pk, p))

# + flat Rician (single tap, no delay)
flat = (1.2 + 0.4j) * x
pk, p = prominence(flat)
print("+ flat Rician (single tap, no delay): peak=%6.0f Hz  prominence=%.3f" % (pk, p))

print("\nreference: real capture top/2nd = 2.79 (clean), RadioML = ~1.01 (smeared)")
