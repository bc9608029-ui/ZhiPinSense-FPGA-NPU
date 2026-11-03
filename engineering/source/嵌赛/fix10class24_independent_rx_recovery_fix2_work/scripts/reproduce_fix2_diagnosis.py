#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reproduce_fix2_diagnosis.py -- fix1v2-independent-rx-recovery-fix2 A线 复现+诊断。

纯离线。读 24 份真实双 SDR 捕获的 `<sid>.raw.i16`，复现板端
`locate_preamble -> slice(59904) -> estimate_public_reference -> recover` 全链，
逐帧对照板端 `board_independent_rx_results.tsv` 的 coarse_cfo_hz / a / b /
timing_offset / training_residual / training_residual_rel / model_input_sha256，
并诊断 CFO 估计机制（分数定时×chirp 前导耦合、训练段 refit、联合 CFO+分数定时、
估计/验证分离、合成反例）。

红线：不上板/不发射/不训练/不改模型；原始载荷 IQ 仅用于恢复参数冻结后的离线诊断。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_dualsdr_common as C           # noqa: E402

FS = IRX.SAMPLE_RATE_HZ                       # 2560000.0
K_TOTAL = IRX.K_TOTAL_BURST_COMPLEX           # 59904
K_PREAMBLE = IRX.K_PREAMBLE_COMPLEX           # 1024
K_TRAIN = IRX.K_PAYLOAD_TRAINING_COMPLEX      # 1024
TRAIN_POS = IRX.PAYLOAD_TRAINING_POS          # 2048 (burst 内训练块起点)
V2_TX_SCALE = 71.609111379029812
V2_UNSCALE = 1.0 / V2_TX_SCALE

CAPTURE_DIR = Path(r"F:\嵌赛\board_capture\rml24_independent_v2_dual_1773374217_210")
RESULTS_TSV = CAPTURE_DIR / "board_independent_rx_results.tsv"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_raw_i16(path: Path) -> np.ndarray:
    return np.frombuffer(path.read_bytes(), dtype="<i2")


def locate_preamble(rx: np.ndarray, max_offset: int):
    """复刻 C++ locate_preamble + preamble_sync_score（归一化 ZC 前导互相关）。"""
    pre = IRX._preamble_complex()
    K = len(pre)
    pre_energy = float(np.vdot(pre, pre).real)
    max_end = len(rx) - K
    limit = min(int(max_offset), max_end)
    best_off, best_score = 0, 0.0
    for off in range(limit + 1):
        seg = rx[off:off + K]
        v = float(abs(np.vdot(seg, pre)))
        r_energy = float(np.vdot(seg, seg).real)
        score = v / np.sqrt(pre_energy * r_energy) if r_energy > 0.0 else 0.0
        if score > best_score:
            best_score, best_off = score, off
    return best_off, best_score


def wide_linear_fit_rel(x: np.ndarray, r: np.ndarray):
    """复刻 C++ wide_linear_fit：返回 (a, b, residual, residual_rel)。"""
    x = np.asarray(x, dtype=np.complex128).ravel()
    r = np.asarray(r, dtype=np.complex128).ravel()
    n = min(len(x), len(r))
    x = x[:n]
    r = r[:n]
    P = float(np.vdot(x, x).real)
    R = float(np.vdot(r, r).real)
    Cc = np.sum(x * x)
    rhs0 = np.vdot(x, r)
    rhs1 = np.sum(x * r)
    det = P * P - abs(Cc) ** 2
    if abs(det) < 1e-300:
        return 1.0 + 0j, 0.0 + 0j, float("inf"), float("inf")
    a = (P * rhs0 - np.conj(Cc) * rhs1) / det
    b = (P * rhs1 - Cc * rhs0) / det
    e = r - a * x - b * np.conj(x)
    num = float(np.vdot(e, e).real)
    residual = np.sqrt(num / P) if P > 0 else float("inf")
    residual_rel = np.sqrt(num / R) if R > 0 else float("inf")
    return a, b, residual, residual_rel


def frac_delay(x: np.ndarray, tau: float) -> np.ndarray:
    """FFT 分数延迟（正 tau = 向右延迟），周期边界，用于诊断级精细定时。"""
    x = np.asarray(x, dtype=np.complex128).ravel()
    n = len(x)
    f = np.fft.fftfreq(n)
    return np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * tau * f))


def derot(x: np.ndarray, cfo: float, start: int = 0) -> np.ndarray:
    n = np.arange(len(x), dtype=np.float64) + start
    return x * np.exp(-1j * 2.0 * np.pi * cfo * n / FS)


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def load_board_rows() -> list[dict]:
    lines = RESULTS_TSV.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        rows.append(dict(zip(header, f)))
    return rows


def reproduce_one(sid: int) -> dict:
    """复现一帧：读 raw -> locate -> slice -> estimate -> recover。"""
    raw_path = CAPTURE_DIR / ("%d.raw.i16" % sid)
    inter = read_raw_i16(raw_path)
    rx_full = C.deinterleave_int16(inter)          # 136192 complex
    raw_sha = sha256_bytes(inter.tobytes())

    off, score = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
    rx_burst = rx_full[off:off + K_TOTAL].copy()   # 59904 complex

    est = IRX.estimate_public_reference(rx_burst)
    # C++ 另算 residual_rel（Python 契约只算 residual）
    x_train = IRX.payload_training_complex()
    r_train = rx_burst[TRAIN_POS:TRAIN_POS + K_TRAIN]
    # 与 C++ 一致：r_train 来自 derot 后的 burst
    aligned = np.roll(rx_burst, -est["timing_offset"]) if est["timing_offset"] else rx_burst
    derot_burst = derot(aligned, est["coarse_cfo_hz"])
    r_train_derot = derot_burst[TRAIN_POS:TRAIN_POS + K_TRAIN]
    a2, b2, res2, resrel2 = wide_linear_fit_rel(x_train, r_train_derot)

    zi = IRX.recover_model_input(rx_burst, est)     # v1 norm（S 无关诊断用）
    zi_v2 = recover_v2(rx_burst, est)               # v2 norm（与板端 tensor 对齐）
    mi_sha_v2 = sha256_bytes(tensor_to_bytes(zi_v2))

    return {
        "sid": sid, "off": off, "score": score, "raw_sha": raw_sha,
        "timing": est["timing_offset"], "cfo": est["coarse_cfo_hz"],
        "a": est["a"], "b": est["b"],
        "residual": est["training_residual"], "residual_rel": resrel2,
        "a2": a2, "b2": b2, "res2": res2,
        "mi_sha_v2": mi_sha_v2, "rx_burst": rx_burst,
    }


def recover_v2(rx: np.ndarray, est: dict) -> np.ndarray:
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    n = np.arange(K_TOTAL, dtype=np.float64)
    derot_burst = aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / FS)
    payload = derot_burst[IRX.K_PAYLOAD_START:IRX.K_PAYLOAD_START + IRX.K_PAYLOAD_COMPLEX]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    return wl[:IRX.GEN.SAMPLE_LENGTH] * V2_UNSCALE


def diagnose_joint(rx_burst: np.ndarray):
    """训练段联合 (cfo, tau) 网格搜索 + 估计/验证分离。"""
    x_train = IRX.payload_training_complex()
    r_full = rx_burst[TRAIN_POS:TRAIN_POS + K_TRAIN]

    # 分数定时参考（预计算 21 个 tau 的移位参考）
    tau_grid = np.arange(-0.5, 0.5 + 1e-9, 0.05)
    # CFO 粗网格：±1800 Hz @ 20 Hz（训练块 1024 样本无歧义 ±1250，但前导粗估不可靠，
    # 扫宽以覆盖 ±1000 的粗估误差 + 真实 CFO ±150）
    cfo_grid = np.arange(-1800.0, 1800.0 + 1e-9, 20.0)

    best = {"cfo": None, "tau": None, "resid_rel": float("inf"), "a": None, "b": None}
    for tau in tau_grid:
        x_shift = frac_delay(x_train, tau)
        for cfo in cfo_grid:
            r_d = derot(r_full, cfo, start=TRAIN_POS)
            a, b, _, rr = wide_linear_fit_rel(x_shift, r_d)
            if rr < best["resid_rel"]:
                best = {"cfo": cfo, "tau": tau, "resid_rel": rr, "a": a, "b": b}

    # 估计/验证分离：用训练块前半 [0:512] 估 (cfo,tau,a,b)，后半 [512:1024] 验证
    half = K_TRAIN // 2
    r_est = r_full[:half]
    r_val = r_full[half:]
    x_est_ref = x_train[:half]
    x_val_ref = x_train[half:]
    split_best = {"cfo": None, "tau": None, "resid_rel_est": float("inf"),
                  "resid_rel_val": float("inf"), "a": None, "b": None}
    for tau in tau_grid:
        x_est = frac_delay(x_est_ref, tau)
        x_val = frac_delay(x_val_ref, tau)
        for cfo in cfo_grid:
            r_d_est = derot(r_est, cfo, start=TRAIN_POS)
            a, b, _, rr_est = wide_linear_fit_rel(x_est, r_d_est)
            if rr_est < split_best["resid_rel_est"]:
                # 用该 (cfo,tau,a,b) 在验证半段算残差
                r_d_val = derot(r_val, cfo, start=TRAIN_POS + half)
                e = r_d_val - a * x_val - b * np.conj(x_val)
                rr_val = float(np.sqrt(np.vdot(e, e).real / np.vdot(r_d_val, r_d_val).real))
                split_best = {"cfo": cfo, "tau": tau, "resid_rel_est": rr_est,
                              "resid_rel_val": rr_val, "a": a, "b": b}
    return best, split_best


def synthetic_counterexample() -> dict:
    """合成反例：注入已知 (cfo, tau, gain, iq_a, iq_b) -> 联合估计应恢复。"""
    wf = IRX.generate_waveform(4)                 # QPSK
    burst = IRX.build_public_protocol_burst(wf)
    rx0 = C.deinterleave_int16(burst)
    inj_cfo, inj_tau = 137.0, -0.31
    inj_gain = 0.85 + 0.12j
    inj_a, inj_b = 1.0 + 0.0j, 0.04 + 0.02j
    # 前向：x -> 分数延迟 -> 广线性 -> CFO
    x = frac_delay(rx0.astype(np.complex128), inj_tau)
    x = inj_gain * (inj_a * x + inj_b * np.conj(x))
    n = np.arange(len(x), dtype=np.float64)
    rx = x * np.exp(1j * 2.0 * np.pi * inj_cfo * n / FS)

    # 用联合估计（在训练块上）
    x_train = IRX.payload_training_complex()
    r_full = rx[TRAIN_POS:TRAIN_POS + K_TRAIN]
    tau_grid = np.arange(-0.5, 0.5 + 1e-9, 0.05)
    cfo_grid = np.arange(-400.0, 400.0 + 1e-9, 2.0)
    best = {"cfo": None, "tau": None, "rr": float("inf")}
    for tau in tau_grid:
        xs = frac_delay(x_train, tau)
        for cfo in cfo_grid:
            r_d = derot(r_full, cfo, start=TRAIN_POS)
            _, _, _, rr = wide_linear_fit_rel(xs, r_d)
            if rr < best["rr"]:
                best = {"cfo": cfo, "tau": tau, "rr": rr}
    return {"inj_cfo": inj_cfo, "inj_tau": inj_tau,
            "est_cfo": best["cfo"], "est_tau": best["tau"], "est_rr": best["rr"]}


def main() -> int:
    board_rows = load_board_rows()
    by_sid = {int(r["source_index"]): r for r in board_rows}
    out = []
    max_cfo_err = 0.0
    max_resid_err = 0.0
    mi_match = 0
    for sid in range(1, 25):
        r = reproduce_one(sid)
        br = by_sid[sid]
        cfo_err = abs(r["cfo"] - float(br["coarse_cfo_hz"]))
        resid_err = abs(r["residual_rel"] - float(br["training_residual_rel"]))
        max_cfo_err = max(max_cfo_err, cfo_err)
        max_resid_err = max(max_resid_err, resid_err)
        if r["mi_sha_v2"] == br["model_input_sha256"]:
            mi_match += 1
        out.append(r)
        print("sid=%02d off=%d score=%.4f timing=%d cfo=%9.4f(board %9.4f) "
              "resid_rel=%.6f(board %.6f) mi_sha=%s" %
              (sid, r["off"], r["score"], r["timing"], r["cfo"],
               float(br["coarse_cfo_hz"]), r["residual_rel"],
               float(br["training_residual_rel"]),
               "OK" if r["mi_sha_v2"] == br["model_input_sha256"] else "MISMATCH"))

    print("\nREPRO max_cfo_err=%.3e max_resid_rel_err=%.3e model_input_sha_match=%d/24"
          % (max_cfo_err, max_resid_err, mi_match))

    # 诊断：联合 CFO+分数定时
    print("\n=== joint (cfo, tau) grid + estimation/validation split ===")
    joint_rows = []
    for r in out:
        best, split = diagnose_joint(r["rx_burst"])
        joint_rows.append({"sid": r["sid"], **best, **split})
        print("sid=%02d old_cfo=%9.4f joint_cfo=%9.4f joint_tau=%+.2f "
              "joint_rr=%.6f | split_rr_est=%.6f split_rr_val=%.6f" %
              (r["sid"], r["cfo"], best["cfo"], best["tau"], best["resid_rel"],
               split["resid_rel_est"], split["resid_rel_val"]))

    n_below = sum(1 for j in joint_rows if j["resid_rel"] < 0.100)
    n_split_below = sum(1 for j in joint_rows if j["resid_rel_val"] < 0.100)
    print("\njoint same-segment resid_rel < 0.100: %d/24" % n_below)
    print("split validation-half resid_rel < 0.100: %d/24" % n_split_below)

    syn = synthetic_counterexample()
    print("\nsynthetic: inj_cfo=%.1f est=%.1f inj_tau=%+.2f est=%+.2f rr=%.2e"
          % (syn["inj_cfo"], syn["est_cfo"], syn["inj_tau"], syn["est_tau"],
             syn["est_rr"]))

    json.dump({"joint": joint_rows, "synthetic": syn},
              open(Path(__file__).parent / "fix2_diagnosis.json", "w"),
              indent=2, sort_keys=True, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
