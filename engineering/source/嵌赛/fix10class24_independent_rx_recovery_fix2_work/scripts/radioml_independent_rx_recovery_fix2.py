#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""radioml_independent_rx_recovery_fix2.py -- fix1v2-independent-rx-recovery-fix2 A线。

纯离线。修复 fix1 独立接收恢复链的 CFO 估计缺陷：前导两半互相关 CFO 估计器被
ZC chirp 的分数定时耦合污染（板端 coarse_cfo_hz 漂到 ±1000 Hz，真实 ~-100 Hz）。
fix2 在**已知 16QAM 训练块**上做联合 (cfo, τ) 2D 网格，显式拟合广线性模型
r ≈ a·x + b·conj(x)（x 为 τ 移位参考），以增益无关 residual_rel 为目标。

分数定时用 32 抽头 Hann 加窗 sinc FIR（Python/C++ 同公式，无幂 2 约束，逐字节
一致），替代诊断期的 FFT（FFT 22/24，加窗 sinc 23/24，见 a_line_interp_test.py）。

恢复顺序（模型一致）：对齐(整定时) -> 去 CFO -> 广线性逆 -> 分数延迟 -τ -> 1/S。
红线：不上板/不发射/不训练/不改模型；原始载荷 IQ 仅用于恢复参数冻结后的离线诊断。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
import radioml_independent_rx_contract as IRX  # noqa: E402  (frozen fix1 contract)
import radioml_dualsdr_common as C           # noqa: E402  (frozen dualsdr common)

sys.path.insert(0, str(Path(__file__).parent))
from reproduce_fix2_diagnosis import (       # noqa: E402
    FS, K_TOTAL, K_TRAIN, TRAIN_POS, CAPTURE_DIR,
    read_raw_i16, locate_preamble, wide_linear_fit_rel, derot,
)

# ---- 网格常量（与 C++ 逐字一致）------------------------------------------------
K_CFO_COARSE_STEP = 20.0
K_CFO_COARSE_MIN = -1800.0
K_CFO_COARSE_MAX = 1800.0
K_TAU_COARSE_STEP = 0.05
K_TAU_COARSE_MIN = -0.5
K_TAU_COARSE_MAX = 0.5
K_CFO_FINE_STEP = 1.0
K_CFO_FINE_SPAN = 20.0
K_TAU_FINE_STEP = 0.01
K_TAU_FINE_SPAN = 0.05
FRAC_DELAY_HALF = 16            # 半长 M，总抽头 2M+1=33
GATE = 0.100


def _grid(vmin: float, vstep: float, vmax: float) -> list[float]:
    """显式 min + i*step（与 C++ 循环逐位一致，避免 np.arange 累加漂移）。"""
    n = int(round((vmax - vmin) / vstep)) + 1
    return [vmin + i * vstep for i in range(n)]


def frac_delay_sinc(x: np.ndarray, tau: float, half: int = FRAC_DELAY_HALF) -> np.ndarray:
    """加窗 sinc 分数延迟（正 tau = 延迟），FIR，circular 索引。

    y[n] = sum_{m=-M..M} x[(n-m) mod N] * sinc(m-tau) * win(m-tau)
    sinc(t)=sin(pi t)/(pi t)（t=0 -> 1），win(t)=0.5*(1+cos(pi t/M))（Hann）。
    与 C++ iqindepfix2::frac_delay_sinc 同公式。
    """
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    if tau == 0.0:
        # 恒等（分数延迟 0 == 原信号）。不加此特例时 sin(pi*m)（m 为整数 m!=0）
        # 因 pi 非精确双精度而 ~1e-16 而非 0，会把载荷中的精确 0 样本污染成
        # ~1e-17 次正规数，改变恢复张量的 float32 字节（破坏干净数字域 fix1==fix2）。
        return x.copy()
    M = half
    h = np.empty(2 * M + 1, dtype=np.float64)
    for i, m in enumerate(range(-M, M + 1)):
        t = m - tau
        s = 1.0 if t == 0.0 else math.sin(math.pi * t) / (math.pi * t)
        w = 0.5 * (1.0 + math.cos(math.pi * t / M)) if M > 0 else 1.0
        h[i] = s * w
    y = np.zeros(n, dtype=np.complex128)
    for i, m in enumerate(range(-M, M + 1)):
        idx = (np.arange(n) - m) % n
        y += x[idx] * h[i]
    return y


def joint_cfo_tau(aligned: np.ndarray) -> dict:
    """训练段联合 (cfo, τ) 网格（粗 -> 细），返回 best dict。"""
    x_train = IRX.payload_training_complex()
    r_full = aligned[TRAIN_POS:TRAIN_POS + K_TRAIN]

    best = {"cfo": 0.0, "tau": 0.0, "a": 1.0 + 0j, "b": 0j,
            "residual": float("inf"), "residual_rel": float("inf")}

    def scan(cfo_min, cfo_step, cfo_n, tau_min, tau_step, tau_n):
        tau_vals = [tau_min + i * tau_step for i in range(tau_n)]
        refs = [frac_delay_sinc(x_train, t) for t in tau_vals]
        for ic in range(cfo_n):
            cfo = cfo_min + ic * cfo_step
            r_d = derot(r_full, cfo, start=TRAIN_POS)
            for it in range(tau_n):
                a, b, _, rr = wide_linear_fit_rel(refs[it], r_d)
                if rr < best["residual_rel"]:
                    best["cfo"], best["tau"], best["a"], best["b"] = cfo, tau_vals[it], a, b
                    best["residual"] = np.nan  # placeholder, refit below
                    best["residual_rel"] = rr

    n_cfo_c = int(round((K_CFO_COARSE_MAX - K_CFO_COARSE_MIN) / K_CFO_COARSE_STEP)) + 1
    n_tau_c = int(round((K_TAU_COARSE_MAX - K_TAU_COARSE_MIN) / K_TAU_COARSE_STEP)) + 1
    scan(K_CFO_COARSE_MIN, K_CFO_COARSE_STEP, n_cfo_c, K_TAU_COARSE_MIN, K_TAU_COARSE_STEP, n_tau_c)

    n_cfo_f = int(round(2.0 * K_CFO_FINE_SPAN / K_CFO_FINE_STEP)) + 1
    n_tau_f = int(round(2.0 * K_TAU_FINE_SPAN / K_TAU_FINE_STEP)) + 1
    scan(best["cfo"] - K_CFO_FINE_SPAN, K_CFO_FINE_STEP, n_cfo_f,
         best["tau"] - K_TAU_FINE_SPAN, K_TAU_FINE_STEP, n_tau_f)

    # 用最终 (cfo, τ) 重拟合得到真实 residual/residual_rel（非 placeholder）
    r_d = derot(r_full, best["cfo"], start=TRAIN_POS)
    xs = frac_delay_sinc(x_train, best["tau"])
    a, b, res, rr = wide_linear_fit_rel(xs, r_d)
    best["a"], best["b"], best["residual"], best["residual_rel"] = a, b, res, rr
    return best


def estimate_public_reference_fix2(rx: np.ndarray) -> dict:
    """fix2 公共参考估计：整定时 + 联合 (cfo,τ) + 广线性，另保留旧前导 CFO 诊断。"""
    timing = IRX.estimate_timing_offset(rx)
    aligned = np.roll(rx, -timing) if timing else rx
    legacy_cfo = IRX.estimate_coarse_cfo_hz(aligned)
    j = joint_cfo_tau(aligned)
    # 旧（前导 CFO，无 τ）residual_rel，供旧/新对照
    r_d_legacy = derot(aligned, legacy_cfo)
    r_train = r_d_legacy[TRAIN_POS:TRAIN_POS + K_TRAIN]
    _, _, _, legacy_rr = wide_linear_fit_rel(IRX.payload_training_complex(), r_train)
    return {
        "timing_offset": timing,
        "coarse_cfo_hz": j["cfo"],
        "fractional_timing": j["tau"],
        "cfo_preamble_legacy_hz": legacy_cfo,
        "a": j["a"], "b": j["b"],
        "training_residual": j["residual"],
        "training_residual_rel": j["residual_rel"],
        "legacy_training_residual_rel": legacy_rr,
    }


def recover_model_input_fix2(rx: np.ndarray, est: dict) -> np.ndarray:
    """fix2 恢复：对齐 -> 去 CFO -> 广线性逆 -> 分数延迟 -τ -> 1/S。"""
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    n = np.arange(K_TOTAL, dtype=np.float64)
    rx_derot = aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / FS)
    payload = rx_derot[IRX.K_PAYLOAD_START: IRX.K_PAYLOAD_START + IRX.K_PAYLOAD_COMPLEX]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:IRX.GEN.SAMPLE_LENGTH] * IRX.MODEL_INPUT_NORM


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def synthetic_counterexample() -> dict:
    """合成反例：注入已知 (cfo, τ, gain, iq_a, iq_b) -> 联合估计应恢复。"""
    wf = IRX.generate_waveform(4)                 # QPSK
    burst = IRX.build_public_protocol_burst(wf)
    rx0 = C.deinterleave_int16(burst)
    inj_cfo, inj_tau = 137.0, -0.31
    inj_gain = 0.85 + 0.12j
    inj_a, inj_b = 1.0 + 0j, 0.04 + 0.02j
    x = frac_delay_sinc(rx0.astype(np.complex128), inj_tau)   # 分数延迟
    x = inj_gain * (inj_a * x + inj_b * np.conj(x))            # 广线性
    nn = np.arange(len(x), dtype=np.float64)
    rx = x * np.exp(1j * 2.0 * np.pi * inj_cfo * nn / FS)      # CFO
    est = estimate_public_reference_fix2(rx)
    return {"inj_cfo": inj_cfo, "inj_tau": inj_tau,
            "est_cfo": est["coarse_cfo_hz"], "est_tau": est["fractional_timing"],
            "rr": est["training_residual_rel"]}


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("FIX2-SELFTEST %-56s %s%s" %
              (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    # R1: 数字无损伤恢复 == 原始波形（fix2 链）
    max_rel = 0.0
    for ci in range(IRX.N_CLASSES):
        wf = IRX.generate_waveform(ci)
        rx = C.deinterleave_int16(IRX.build_public_protocol_burst(wf))
        est = estimate_public_reference_fix2(rx)
        zi = recover_model_input_fix2(rx, est)
        rel = float(np.sqrt(np.mean(np.abs(wf - zi) ** 2)) /
                    np.sqrt(np.mean(np.abs(wf) ** 2)))
        max_rel = max(max_rel, rel)
    check("R1 fix2 clean recovery rel RMS < 1e-2 (24/24)", max_rel < 1e-2,
          "max_rel=%.3e" % max_rel)

    # R2: 数字域 a~1 b~0 cfo~0 tau~0
    rx = C.deinterleave_int16(IRX.build_public_protocol_burst(IRX.generate_waveform(4)))
    est = estimate_public_reference_fix2(rx)
    check("R2 digital a ~= 1", abs(est["a"] - 1.0) < 1e-3, "a=%.6g+%.6gj" % (est["a"].real, est["a"].imag))
    check("R2 digital b ~= 0", abs(est["b"]) < 1e-3, "|b|=%.3e" % abs(est["b"]))
    check("R2 digital CFO ~= 0", abs(est["coarse_cfo_hz"]) < 1.0, "cfo=%.3e" % est["coarse_cfo_hz"])
    check("R2 digital tau ~= 0", abs(est["fractional_timing"]) < 0.05, "tau=%.3f" % est["fractional_timing"])

    # R3: 合成反例（注入 cfo+τ+gain+iq）恢复
    syn = synthetic_counterexample()
    check("R3 joint CFO recovered (|est-inj|<2 Hz)", abs(syn["est_cfo"] - syn["inj_cfo"]) < 2.0,
          "est=%.2f inj=%.1f" % (syn["est_cfo"], syn["inj_cfo"]))
    check("R3 joint tau recovered (|est-inj|<0.05)", abs(syn["est_tau"] - syn["inj_tau"]) < 0.05,
          "est=%.2f inj=%.2f" % (syn["est_tau"], syn["inj_tau"]))
    check("R3 counterexample residual < 0.05", syn["rr"] < 0.05, "rr=%.4f" % syn["rr"])

    # R4: 旧前导 CFO 在分数定时注入下确实被污染（证明 bug 存在），联合估计无偏
    wf4 = IRX.generate_waveform(4)
    rx_clean = C.deinterleave_int16(IRX.build_public_protocol_burst(wf4))
    rx_shift = frac_delay_sinc(rx_clean.astype(np.complex128), -0.3)  # 注入分数定时
    legacy = IRX.estimate_coarse_cfo_hz(rx_shift)
    est2 = estimate_public_reference_fix2(rx_shift)
    check("R4 legacy preamble CFO biased by tau (|cfo|>100 Hz)",
          abs(legacy) > 100.0, "legacy=%.1f Hz" % legacy)
    check("R4 joint CFO unbiased (|cfo|<10 Hz)",
          abs(est2["coarse_cfo_hz"]) < 10.0, "joint=%.1f Hz" % est2["coarse_cfo_hz"])

    all_ok = all(checks)
    print("RADIOML_INDEPENDENT_RX_RECOVERY_FIX2_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


def real24_metrics() -> list[dict]:
    """真实 24 帧旧/新指标。"""
    rows = []
    for sid in range(1, 25):
        inter = read_raw_i16(CAPTURE_DIR / ("%d.raw.i16" % sid))
        rx_full = C.deinterleave_int16(inter)
        off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
        rx_burst = rx_full[off:off + K_TOTAL].copy()
        est = estimate_public_reference_fix2(rx_burst)
        rows.append({"sid": sid, **est})
    return rows


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--real24", action="store_true")
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.real24:
        rows = real24_metrics()
        below_new = sum(1 for r in rows if r["training_residual_rel"] < GATE)
        below_old = sum(1 for r in rows if r["legacy_training_residual_rel"] < GATE)
        print("%-5s %-12s %-9s %-9s %-12s %-12s" %
              ("sid", "old_cfo_hz", "old_rr", "tau", "new_cfo_hz", "new_rr"))
        for r in rows:
            print("%-5d %-12.2f %-9.4f %-9.2f %-12.2f %-12.4f" %
                  (r["sid"], r["cfo_preamble_legacy_hz"],
                   r["legacy_training_residual_rel"], r["fractional_timing"],
                   r["coarse_cfo_hz"], r["training_residual_rel"]))
        print("\nOLD (preamble CFO, no tau) < 0.100: %d/24" % below_old)
        print("NEW (joint cfo+tau)         < 0.100: %d/24" % below_new)
        print("cfo range old=[%.1f, %.1f]  new=[%.1f, %.1f]"
              % (min(r["cfo_preamble_legacy_hz"] for r in rows),
                 max(r["cfo_preamble_legacy_hz"] for r in rows),
                 min(r["coarse_cfo_hz"] for r in rows),
                 max(r["coarse_cfo_hz"] for r in rows)))
        if args.json:
            import json
            json.dump(rows, open(args.json, "w"), indent=2, sort_keys=True, default=str)
        return 0

    ap.error("specify --self-test or --real24")


if __name__ == "__main__":
    sys.exit(main())
