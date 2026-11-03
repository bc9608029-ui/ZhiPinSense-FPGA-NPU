#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a_line_split_validation.py -- A线诚实负结论：估计区 vs 独立验证区分离。

对真实 24 帧：训练块前半 [0:512] 估 (cfo,tau,a,b)，后半 [512:1024] 独立验证，
用 sinc32 分数延迟。回答「联合估计是否过拟合到估计段」——若验证段 residual_rel
仍 >> 0.100，则 CFO+τ+广线性模型之外还有时变/非线性分量。
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
from radioml_independent_rx_recovery_fix2 import (  # noqa: E402
    frac_delay_sinc, _grid, K_CFO_COARSE_STEP, K_CFO_COARSE_MIN, K_CFO_COARSE_MAX,
    K_TAU_COARSE_STEP, K_TAU_COARSE_MIN, K_TAU_COARSE_MAX,
    K_CFO_FINE_STEP, K_CFO_FINE_SPAN, K_TAU_FINE_STEP, K_TAU_FINE_SPAN,
)


def split_validation(aligned: np.ndarray) -> dict:
    x_train = IRX.payload_training_complex()
    r_full = aligned[TRAIN_POS:TRAIN_POS + K_TRAIN]
    half = K_TRAIN // 2
    r_est = r_full[:half]
    r_val = r_full[half:]
    x_est = x_train[:half]
    x_val = x_train[half:]

    best = {"cfo": 0.0, "tau": 0.0, "rr_est": float("inf"),
            "rr_val": float("inf"), "a": 1.0 + 0j, "b": 0j}

    def scan(cfo_min, cfo_step, cfo_n, tau_min, tau_step, tau_n):
        tau_vals = [tau_min + i * tau_step for i in range(tau_n)]
        est_refs = [frac_delay_sinc(x_est, t) for t in tau_vals]
        val_refs = [frac_delay_sinc(x_val, t) for t in tau_vals]
        for ic in range(cfo_n):
            cfo = cfo_min + ic * cfo_step
            r_d_est = derot(r_est, cfo, start=TRAIN_POS)
            r_d_val = derot(r_val, cfo, start=TRAIN_POS + half)
            for it in range(tau_n):
                a, b, _, rr_est = wide_linear_fit_rel(est_refs[it], r_d_est)
                if rr_est < best["rr_est"]:
                    e = r_d_val - a * val_refs[it] - b * np.conj(val_refs[it])
                    rr_val = float(np.sqrt(np.vdot(e, e).real /
                                           np.vdot(r_d_val, r_d_val).real))
                    best.update({"cfo": cfo, "tau": tau_vals[it], "rr_est": rr_est,
                                 "rr_val": rr_val, "a": a, "b": b})

    n_c = int(round((K_CFO_COARSE_MAX - K_CFO_COARSE_MIN) / K_CFO_COARSE_STEP)) + 1
    n_t = int(round((K_TAU_COARSE_MAX - K_TAU_COARSE_MIN) / K_TAU_COARSE_STEP)) + 1
    scan(K_CFO_COARSE_MIN, K_CFO_COARSE_STEP, n_c, K_TAU_COARSE_MIN, K_TAU_COARSE_STEP, n_t)
    n_f = int(round(2.0 * K_CFO_FINE_SPAN / K_CFO_FINE_STEP)) + 1
    n_tf = int(round(2.0 * K_TAU_FINE_SPAN / K_TAU_FINE_STEP)) + 1
    scan(best["cfo"] - K_CFO_FINE_SPAN, K_CFO_FINE_STEP, n_f,
         best["tau"] - K_TAU_FINE_SPAN, K_TAU_FINE_STEP, n_tf)
    return best


def main() -> int:
    below = 0
    print("%-5s %-9s %-7s %-10s %-10s" % ("sid", "cfo", "tau", "rr_est", "rr_val"))
    vals = []
    for sid in range(1, 25):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        rx_burst = rx_full[off:off + K_TOTAL].copy()
        timing = IRX.estimate_timing_offset(rx_burst)
        aligned = np.roll(rx_burst, -timing) if timing else rx_burst
        s = split_validation(aligned)
        vals.append(s["rr_val"])
        if s["rr_val"] < 0.100:
            below += 1
        print("%-5d %-9.2f %-7.2f %-10.4f %-10.4f" %
              (sid, s["cfo"], s["tau"], s["rr_est"], s["rr_val"]))
    print("\nsplit validation-half residual_rel < 0.100: %d/24" % below)
    print("validation residual_rel floor: [%.3f, %.3f]" % (min(vals), max(vals)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
