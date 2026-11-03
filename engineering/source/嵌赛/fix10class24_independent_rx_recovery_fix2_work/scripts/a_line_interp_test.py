#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a_line_interp_test.py -- A线决策脚本：分数定时插值方法对比。

纯离线。对真实 24 帧做联合 (cfo, tau) 网格搜索，比较三种分数延迟插值
（FFT 基线 / 线性 / 三次 Lagrange），回答：
  Q1 线性/三次插值能否复现 FFT 的 22/24 < 0.100 结果？（决定 C++ 是否要自带 FFT）
  Q2 细网格（更宽 tau + 更细 cfo）能否修好 sid=04 / sid=18 两帧？
输出 fix2 实现决策依据。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_dualsdr_common as C           # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from reproduce_fix2_diagnosis import (       # noqa: E402
    FS, K_TOTAL, K_TRAIN, TRAIN_POS, CAPTURE_DIR,
    read_raw_i16, locate_preamble, wide_linear_fit_rel, derot,
)

THRESH = 0.100


def frac_delay_fft(x: np.ndarray, tau: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    f = np.fft.fftfreq(n)
    return np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * tau * f))


def frac_delay_linear(x: np.ndarray, tau: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    idx = np.arange(n, dtype=np.float64) - tau       # 想取 x[n - tau]
    k = np.floor(idx).astype(np.int64)
    alpha = idx - k
    k0 = k % n
    k1 = (k + 1) % n
    return (1.0 - alpha) * x[k0] + alpha * x[k1]


def frac_delay_sinc(x: np.ndarray, tau: float, taps: int = 32) -> np.ndarray:
    """加窗 sinc 分数延迟（正 tau = 延迟），FIR 形式，Python/C++ 同公式可逐字节一致。

    y[n] = sum_{m=-M..M} x[n-m] * sinc(m-tau) * win(m-tau)，M=taps//2，
    sinc(t)=sin(pi t)/(pi t)，win(t)=0.5*(1+cos(pi t/M))（Hann）。
    """
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    M = taps // 2
    m = np.arange(-M, M + 1, dtype=np.float64)
    d = m - tau
    with np.errstate(divide="ignore", invalid="ignore"):
        sinc = np.sin(np.pi * d) / (np.pi * d)
    sinc[d == 0.0] = 1.0
    win = 0.5 * (1.0 + np.cos(np.pi * d / M)) if M > 0 else np.ones_like(d)
    h = sinc * win
    idx = (np.arange(n)[:, None] - m[None, :].astype(np.int64)) % n
    return (x[idx] * h[None, :]).sum(axis=1)


def frac_delay_cubic(x: np.ndarray, tau: float) -> np.ndarray:
    """4 点三次 Lagrange 插值（circular），x_shift[n] = x[n - tau]。"""
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    idx = np.arange(n, dtype=np.float64) - tau
    k = np.floor(idx).astype(np.int64)               # 基点 k（x[k],x[k+1] 之间）
    d = idx - k                                      # 小数部分 [0,1)
    # 取 x[k-1], x[k], x[k+1], x[k+2]
    km1 = (k - 1) % n
    k0 = k % n
    k1 = (k + 1) % n
    k2 = (k + 2) % n
    xm1, x0, x1, x2 = x[km1], x[k0], x[k1], x[k2]
    # 三次 Lagrange（Catmull-Rom 型，t=d）:
    #  y(t) = -0.5*t(t-1)(t-2)*xm1 + 0.5*(t^2-1)(t-2)*x0
    #         -0.5*t(t+1)(t-2)*x1 + 0.5*t(t^2-1)*x2
    c0 = -0.5 * d * (d - 1.0) * (d - 2.0)
    c1 = 0.5 * (d * d - 1.0) * (d - 2.0)
    c2 = -0.5 * d * (d + 1.0) * (d - 2.0)
    c3 = 0.5 * d * (d * d - 1.0)
    return c0 * xm1 + c1 * x0 + c2 * x1 + c3 * x2


def joint_grid(rx_burst: np.ndarray, fdelay, tau_grid, cfo_grid):
    """训练段联合 (cfo, tau) 网格，返回 (best_dict, n_eval)。"""
    x_train = IRX.payload_training_complex()
    r_full = rx_burst[TRAIN_POS:TRAIN_POS + K_TRAIN]
    refs = [fdelay(x_train, t) for t in tau_grid]
    best = {"cfo": None, "tau": None, "rr": float("inf"), "a": None, "b": None}
    n_eval = 0
    for ti, xs in enumerate(refs):
        for cfo in cfo_grid:
            r_d = derot(r_full, cfo, start=TRAIN_POS)
            a, b, _, rr = wide_linear_fit_rel(xs, r_d)
            n_eval += 1
            if rr < best["rr"]:
                best = {"cfo": cfo, "tau": tau_grid[ti], "rr": rr, "a": a, "b": b}
    return best, n_eval


def main() -> int:
    tau_coarse = np.arange(-0.5, 0.5 + 1e-9, 0.05)      # 21
    cfo_coarse = np.arange(-1800.0, 1800.0 + 1e-9, 20.0)  # 181

    rows = []
    for sid in range(1, 25):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        rx_burst = rx_full[off:off + K_TOTAL].copy()
        rows.append((sid, rx_burst))

    print("=== Q1 插值方法对比（粗网格 cfo±1800@20, tau±0.5@0.05）===")
    print("%-6s %-22s %-10s %-8s %-12s" %
          ("sid", "method", "cfo", "tau", "rr"))
    methods = [("fft", frac_delay_fft), ("linear", frac_delay_linear),
               ("cubic", frac_delay_cubic),
               ("sinc32", lambda x, t: frac_delay_sinc(x, t, 32)),
               ("sinc64", lambda x, t: frac_delay_sinc(x, t, 64))]
    summary = {}
    for name, fn in methods:
        below = 0
        for sid, rb in rows:
            best, _ = joint_grid(rb, fn, tau_coarse, cfo_coarse)
            if best["rr"] < THRESH:
                below += 1
            if sid in (1, 4, 18):
                print("%-6d %-22s %-10.2f %-8.2f %-12.6f" %
                      (sid, name, best["cfo"], best["tau"], best["rr"]))
        summary[name] = below
        print("%-6s %-22s -> <0.100: %d/24" % ("", name, below))

    # Q2 细网格修 sid=04 / sid=18
    print("\n=== Q2 细网格修 FFT 失败帧（sid=04/18）===")
    tau_fine = np.arange(-0.75, 0.75 + 1e-9, 0.01)       # 151
    cfo_fine = np.arange(-200.0, 200.0 + 1e-9, 1.0)      # 401
    for sid in (4, 18):
        rb = dict(rows)[sid]
        best, _ = joint_grid(rb, frac_delay_fft, tau_fine, cfo_fine)
        print("sid=%02d fine: cfo=%+.2f tau=%+.2f rr=%.6f (%.0f vs %s)"
              % (sid, best["cfo"], best["tau"], best["rr"],
                 best["rr"], "PASS" if best["rr"] < THRESH else "FAIL"))

    # 一致性：线性/三次相对 FFT 的 (cfo,tau,rr) 偏差
    print("\n=== 线性/三次 vs FFT 的 (cfo,tau,rr) 偏差（代表性帧 sid=1,5,17）===")
    fft_best = {}
    for sid in (1, 5, 17):
        rb = dict(rows)[sid]
        fft_best[sid], _ = joint_grid(rb, frac_delay_fft, tau_coarse, cfo_coarse)
    for name, fn in [("linear", frac_delay_linear), ("cubic", frac_delay_cubic)]:
        for sid in (1, 5, 17):
            rb = dict(rows)[sid]
            b, _ = joint_grid(rb, fn, tau_coarse, cfo_coarse)
            fb = fft_best[sid]
            print("%-6s sid=%02d dcfo=%+8.2f dtau=%+7.3f drr=%.3e" %
                  (name, sid, b["cfo"] - fb["cfo"], b["tau"] - fb["tau"],
                   b["rr"] - fb["rr"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
