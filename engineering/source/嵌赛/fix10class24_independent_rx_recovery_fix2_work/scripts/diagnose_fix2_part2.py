#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnose_fix2_part2.py -- A线第2步：验证高效 CFO 估计器 + 残差地板特征。

纯离线。回答：
  Q1 训练块共轭积 CFO 估计器是否对分数定时无偏（合成注入 CFO+τ 反例）。
  Q2 该估计器在真实 24 帧上是否恢复到 ~-100 Hz（与 2D 网格一致）。
  Q3 完美 (cfo,τ) 后的残差地板（细网格）与逐半 CFO 漂移（时变分量）。
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
    read_raw_i16, locate_preamble, wide_linear_fit_rel, frac_delay, derot,
)


def train_block_cfo(rx_burst: np.ndarray, seg_len: int = K_TRAIN,
                    start: int = TRAIN_POS) -> float:
    """训练块共轭积 CFO（对分数定时一阶无偏）：p=conj(r)*x，p[n]*conj(p[n-1]) 相位。"""
    x = IRX.payload_training_complex()
    r = rx_burst[start:start + seg_len]
    x = x[:seg_len]
    p = np.conj(r) * x
    s = np.sum(p[1:] * np.conj(p[:-1]))
    return float(np.angle(s)) * FS / (2.0 * np.pi)


def one_tau_resid(rx_burst, cfo, tau):
    """给定 (cfo, tau)，返回训练块拟合 (a,b,residual,residual_rel)。"""
    x_train = IRX.payload_training_complex()
    r_full = rx_burst[TRAIN_POS:TRAIN_POS + K_TRAIN]
    x_shift = frac_delay(x_train, tau)
    r_d = derot(r_full, cfo, start=TRAIN_POS)
    return wide_linear_fit_rel(x_shift, r_d)


def fine_joint(rx_burst, cfo0, tau0):
    """在 (cfo0, tau0) 附近细网格联合搜索。"""
    best = {"cfo": None, "tau": None, "rr": float("inf"), "a": None, "b": None}
    for cfo in np.arange(cfo0 - 30.0, cfo0 + 30.0 + 1e-9, 1.0):
        for tau in np.arange(tau0 - 0.1, tau0 + 0.1 + 1e-9, 0.01):
            a, b, _, rr = one_tau_resid(rx_burst, cfo, tau)
            if rr < best["rr"]:
                best = {"cfo": cfo, "tau": tau, "rr": rr, "a": a, "b": b}
    return best


def main() -> int:
    # ---- Q1 合成反例：分数定时下训练块 CFO 估计器是否无偏 ----
    print("=== Q1 synthetic: train-block CFO unbiased under fractional timing ===")
    wf = IRX.generate_waveform(4)
    burst = IRX.build_public_protocol_burst(wf)
    rx0 = C.deinterleave_int16(burst)
    for (inj_cfo, inj_tau) in [(137.0, -0.31), (-90.0, 0.45), (250.0, 0.0),
                               (-400.0, -0.5)]:
        x = frac_delay(rx0.astype(np.complex128), inj_tau)
        g = 0.85 + 0.12j
        x = g * (1.0 * x + 0.04 * np.conj(x))
        n = np.arange(len(x), dtype=np.float64)
        rx = x * np.exp(1j * 2.0 * np.pi * inj_cfo * n / FS)
        est = train_block_cfo(rx)
        print("inj_cfo=%+7.1f inj_tau=%+.2f -> est_cfo=%+7.2f (err %+6.2f)"
              % (inj_cfo, inj_tau, est, est - inj_cfo))

    # ---- Q2 真实 24 帧：训练块 CFO vs 2D 网格 ----
    print("\n=== Q2 real 24: train-block CFO vs grid ===")
    grid_cfo = {}   # from part-1 joint (recompute coarse)
    from reproduce_fix2_diagnosis import diagnose_joint
    for sid in range(1, 25):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, score = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        rx_burst = rx_full[off:off + K_TOTAL].copy()
        cfo_tb = train_block_cfo(rx_burst)
        joint, _ = diagnose_joint(rx_burst)
        print("sid=%02d train_block_cfo=%+8.2f  grid_cfo=%+8.2f  grid_tau=%+.2f"
              % (sid, cfo_tb, joint["cfo"], joint["tau"]))

    # ---- Q3 细网格残差地板 + 逐半 CFO 漂移（3 代表帧）----
    print("\n=== Q3 fine-grid residual floor + per-half CFO drift ===")
    for sid in (1, 5, 17):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        rx_burst = rx_full[off:off + K_TOTAL].copy()
        cfo0 = train_block_cfo(rx_burst)
        best = fine_joint(rx_burst, cfo0, 0.0)
        half = K_TRAIN // 2
        cfo_h1 = train_block_cfo(rx_burst, seg_len=half, start=TRAIN_POS)
        cfo_h2 = train_block_cfo(rx_burst, seg_len=half, start=TRAIN_POS + half)
        print("sid=%02d fine_cfo=%+8.2f fine_tau=%+.3f fine_rr=%.6f | "
              "cfo_h1=%+8.2f cfo_h2=%+8.2f drift=%+7.2f"
              % (sid, best["cfo"], best["tau"], best["rr"], cfo_h1, cfo_h2,
                 cfo_h2 - cfo_h1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
