#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oracle_common.py -- M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1 共享模块（纯离线）。

提供：v2 源波形、生产恢复链（fix2 / old）逐字节复现、冻结 BF16 主机推理、
数字基线预测、oracle 级别 O0-O5 的均匀施加、门/残差读取。

红线：本模块仅供离线诊断；oracle 使用原始载荷 x_true 只用于拟合修正，绝不进入
生产恢复，绝不按标签挑选逐帧最优 oracle。禁止训练 / 上板 / 发射 / 改生产门。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

# ---- 只读基线脚本目录（不修改，仅 import 复用） -------------------------------
_V1_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
_FIX2_DIR = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work\scripts"
_V2_DIR = r"F:\嵌赛\fix10class24_waveform_correct_v2_work\scripts"
for _d in (_V1_DIR, _FIX2_DIR, _V2_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import radioml_independent_rx_contract as IRX       # noqa: E402  (v1 契约)
import radioml_dualsdr_common as C                  # noqa: E402  (公共常量)
import radioml_v2_contract as V2                    # noqa: E402  (v2 波形+幅度合同)
import radioml_waveform_correct_v2 as WV2           # noqa: E402  (v2 AM 修正生成器)
import radioml_clean_contract as GEN                # noqa: E402  (冻结 24 类标签序)
import radioml_independent_rx_recovery_fix2 as FIX2  # noqa: E402  (fix2 恢复链)

# ---- 常量 --------------------------------------------------------------------
FS = float(IRX.SAMPLE_RATE_HZ)                       # 2560000.0
K_TOTAL = int(IRX.K_TOTAL_BURST_COMPLEX)             # 59904
K_PAYLOAD = int(IRX.K_PAYLOAD_COMPLEX)               # 53760
K_PAYLOAD_START = int(IRX.K_PAYLOAD_START)           # 3072
N = int(GEN.SAMPLE_LENGTH)                           # 1024
GATE = 0.100
V2_UNSCALE = 1.0 / 71.609111379029812                # 1/S_v2（板端 tensor 对齐用）

# 两会话（各自独立恢复链，禁止合并统计）
SESSION_FIX2 = {
    "name": "rf_fix2_target",
    "capture_dir": r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244",
    "chain": "fix2",
}
SESSION_OLD = {
    "name": "rf_independent_v2",
    "capture_dir": r"F:\嵌赛\board_capture\rml24_independent_v2_dual_1773374217_210",
    "chain": "old",
}
SESSIONS = [SESSION_FIX2, SESSION_OLD]

# 冻结 BF16 模型
MODEL_DIR = (
    r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
    r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16")
MODEL_JSON = Path(MODEL_DIR) / "rml24_adamrv11_bf16.json"
MODEL_RAW = Path(MODEL_DIR) / "rml24_adamrv11_bf16.raw"
MODEL_NETWORK = "model_24class"
ICRAFT_RUN = Path(r"D:\icraft\bin\icraft-run.exe")

# 冻结 v2 数字基线预测（v2_digital_baseline_frozen.json，orig_pred 逐源 1..24）。
# 唯一误分类：source 21 (AM-DSB-SC) -> 16 (256QAM)。这是模型与新波形域失配，
# 属数字域固有上界，oracle 不得要求超过之（label 上界 23/24）。
DIGITAL_BASELINE_PRED = list(range(20)) + [16, 21, 22, 23]   # 索引 = source-1
DIGITAL_BASELINE_LABEL_ACCURACY = 23
LABEL_ORDER_24 = list(GEN.LABEL_ORDER_24)


# ---- 基础工具 ----------------------------------------------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tensor_to_bytes(iq) -> bytes:
    """complex[1024] -> [2,1024] f32le（模型输入契约，行 0=实部）。"""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == N
    x = np.empty((2, N), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def read_raw_complex(raw_path: Path) -> np.ndarray:
    inter = np.frombuffer(raw_path.read_bytes(), dtype="<i2")
    return C.deinterleave_int16(inter)


def locate_preamble(rx: np.ndarray, max_offset: int):
    """复刻 C++ locate_preamble（归一化 ZC 前导互相关）。"""
    pre = IRX._preamble_complex()
    K = len(pre)
    pre_energy = float(np.vdot(pre, pre).real)
    limit = min(int(max_offset), len(rx) - K)
    best_off, best_score = 0, 0.0
    for off in range(limit + 1):
        seg = rx[off:off + K]
        v = float(abs(np.vdot(seg, pre)))
        r_energy = float(np.vdot(seg, seg).real)
        score = v / np.sqrt(pre_energy * r_energy) if r_energy > 0.0 else 0.0
        if score > best_score:
            best_score, best_off = score, off
    return best_off, best_score


def recover_fix2(rx_burst: np.ndarray, est: dict) -> np.ndarray:
    """fix2 恢复：align -> derot(joint cfo) -> WL_inv -> frac_delay(-tau) -> 1/S_v2。"""
    timing = est["timing_offset"]
    aligned = np.roll(rx_burst, -timing) if timing else rx_burst
    n = np.arange(K_TOTAL, dtype=np.float64)
    derot = aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / FS)
    payload = derot[K_PAYLOAD_START:K_PAYLOAD_START + K_PAYLOAD]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = FIX2.frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:N] * V2_UNSCALE


def recover_old(rx_burst: np.ndarray, est: dict) -> np.ndarray:
    """old 恢复：align -> derot(preamble cfo) -> WL_inv -> 1/S_v2（无 frac_delay）。"""
    timing = est["timing_offset"]
    aligned = np.roll(rx_burst, -timing) if timing else rx_burst
    n = np.arange(K_TOTAL, dtype=np.float64)
    derot = aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / FS)
    payload = derot[K_PAYLOAD_START:K_PAYLOAD_START + K_PAYLOAD]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    return wl[:N] * V2_UNSCALE


def recover_o0(chain: str, rx_burst: np.ndarray, est: dict) -> np.ndarray:
    return recover_fix2(rx_burst, est) if chain == "fix2" else recover_old(rx_burst, est)


# ---- 载荷 oracle（离线诊断专用，禁止进生产恢复） ------------------------------
def true_waveform(source_index: int) -> np.ndarray:
    """原始 1024 点 v2 载荷波形（模型数字真值）。class_index = source_index-1。"""
    return V2.generate_waveform_v2(source_index - 1)


def cyclic_align(z: np.ndarray, ref: np.ndarray):
    """O1（只改窗）：返回 (shift, aligned)，aligned = roll(z, shift) 使 |vdot| 最大。

    shift 为整数循环位移（模型窗 = 载荷周期 1024 的循环相位）。
    """
    z = np.asarray(z, dtype=np.complex128).ravel()
    ref = np.asarray(ref, dtype=np.complex128).ravel()
    n = len(z)
    best_d, best_c = 0, -1.0
    for d in range(n):
        zd = np.roll(z, d)
        c = float(abs(np.vdot(zd, ref)))
        if c > best_c:
            best_c, best_d = c, d
    return best_d, np.roll(z, best_d)


def apply_scale(z: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """O2（只改尺度，payload-oracle 复标量）：z / s，s = vdot(ref,z)/vdot(ref,ref)。

    注意：这是对原始载荷的复数 LS 标量拟合，**不是** manifest 发送尺度。manifest 尺度
    S_v2 已在生产恢复（×1/S_v2）中施加，故「纯 manifest 尺度」oracle 与 O0 退化等价。
    """
    z = np.asarray(z, dtype=np.complex128).ravel()
    ref = np.asarray(ref, dtype=np.complex128).ravel()
    s = np.vdot(ref, z) / np.vdot(ref, ref)
    return z / s


def apply_dc(z: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """O3（只改直流）：减去虚假直流（保留原始载荷合法直流）：z - (mean(z) - mean(ref))。"""
    z = np.asarray(z, dtype=np.complex128).ravel()
    ref = np.asarray(ref, dtype=np.complex128).ravel()
    return z - (np.mean(z) - np.mean(ref))


def apply_combined(z: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """O4（窗+尺度+直流组合）：先循环对齐，再联合拟合 ref ≈ s*z1 + c（尺度与直流一次
    LS 求解，避免顺序 scale->dc 时 DC 污染尺度拟合）。返回 s*z1 + c。"""
    _, z1 = cyclic_align(z, ref)
    A = np.column_stack([z1, np.ones(len(z1), dtype=np.complex128)])
    coef, *_ = np.linalg.lstsq(A, ref, rcond=None)
    s, c = coef[0], coef[1]
    return s * z1 + c


def _affine_fit(z_seg: np.ndarray, ref_seg: np.ndarray):
    """fit ref ≈ p*z + q*conj(z) + c（复 LS），返回 (p, q, c)。"""
    A = np.column_stack([z_seg, np.conj(z_seg), np.ones(len(z_seg), dtype=np.complex128)])
    coef, *_ = np.linalg.lstsq(A, ref_seg, rcond=None)
    return coef[0], coef[1], coef[2]


def _affine_apply(z_seg: np.ndarray, coef) -> np.ndarray:
    p, q, c = coef
    return p * z_seg + q * np.conj(z_seg) + c


def apply_affine_crossval(z: np.ndarray, ref: np.ndarray):
    """O5（真正交叉验证仿射）：生成交叉拟合张量 + 各自未参与拟合半段的残差。

    - 前 512 点用「后 512 点拟合」的参数修正；
    - 后 512 点用「前 512 点拟合」的参数修正；
    - 拼成 1024 点后分类；
    - 残差只计算各自未参与拟合的半段（NMSE/NRMSE）。

    返回 (z_cross, nmse, nrmse)。
    """
    z = np.asarray(z, dtype=np.complex128).ravel()
    ref = np.asarray(ref, dtype=np.complex128).ravel()
    half = len(z) // 2
    # 前半段用后半段拟合
    coef_from_second = _affine_fit(z[half:], ref[half:])
    first_corrected = _affine_apply(z[:half], coef_from_second)
    # 后半段用前半段拟合
    coef_from_first = _affine_fit(z[:half], ref[:half])
    second_corrected = _affine_apply(z[half:], coef_from_first)
    z_cross = np.concatenate([first_corrected, second_corrected])

    e_first = first_corrected - ref[:half]
    e_second = second_corrected - ref[half:]
    num = float(np.vdot(e_first, e_first).real + np.vdot(e_second, e_second).real)
    den = float(np.vdot(ref, ref).real)
    nmse = num / den if den > 0 else float("inf")
    nrmse = float(np.sqrt(nmse))
    return z_cross, nmse, nrmse


def nmse_nrmse(z: np.ndarray, ref: np.ndarray):
    """参考归一化误差：NMSE = |z-ref|²/|ref|²，NRMSE = sqrt(NMSE)。

    注意：与生产门 training_residual_rel（训练段、接收能量归一化 sqrt(|e|²/|r_train|²)）
    定义不同，二者不可直接比较（见 LIMITATIONS）。
    """
    z = np.asarray(z, dtype=np.complex128).ravel()
    ref = np.asarray(ref, dtype=np.complex128).ravel()
    e = z - ref
    den = float(np.vdot(ref, ref).real)
    nmse = float(np.vdot(e, e).real) / den if den > 0 else float("inf")
    return nmse, float(np.sqrt(nmse))


# ---- 冻结 BF16 主机推理 -------------------------------------------------------
def host_infer(tensor_bytes: bytes, workdir: Path) -> np.ndarray:
    """icraft-run 主机 BF16 推理，返回 24 维 logits（f32）。"""
    inp = workdir / "input.bin"
    inp.write_bytes(tensor_bytes)
    log_path = workdir / "logs"
    shutil.rmtree(log_path, ignore_errors=True)
    cmd = [str(ICRAFT_RUN), "--json", str(MODEL_JSON), "--raw", str(MODEL_RAW),
           "--network", MODEL_NETWORK, "--input", str(inp),
           "--backends", "Host", "--dump_output", "--log_path", str(log_path)]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("icraft-run exit %d: %s"
                         % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / MODEL_NETWORK / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        raise SystemExit("expected exactly 1 ftmp, got %d" % len(ftmps))
    raw = ftmps[0].read_bytes()
    if len(raw) != 24 * 4:
        raise SystemExit("ftmp %s is %d bytes (want 96)" % (ftmps[0].name, len(raw)))
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def argmax_pred(logits: np.ndarray) -> int:
    return int(np.argmax(logits))


# ---- 板端结果 TSV 读取 --------------------------------------------------------
def load_board_rows(cap_dir: str) -> dict:
    path = Path(cap_dir) / "board_independent_rx_results.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    hdr = lines[0].rstrip("\n").split("\t")
    return {int(f[0]): dict(zip(hdr, f)) for ln in lines[1:] if ln.strip()
            for f in [ln.rstrip("\n").split("\t")]}
