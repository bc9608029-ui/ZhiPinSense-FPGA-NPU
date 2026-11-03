#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_dualsdr_common.py -- shared constants + deterministic adaptation for
fix10class24-original-radioml-dualsdr-ab1 (三臂: A 原始 / D 数字无RF / C 双SDR)。

这是 BOARD-PREP 任务: 只做主机侧准备, 不上板、不发射、不训练。本模块把 Phase A
"输入与传输契约" 的确定性适配规则 (1024 -> 53760 循环铺排 + CI16 量化 + RMS2048)
固化为单一来源, 供 TX 导出 / 数字回环 / 判定器 / 主机测试共用。

Red lines (永不违反):
  * 冻结 BF16 JSON/RAW/CKPT SHA、24 类标签序、480 帧选择/类/SNR/hdf5_row_index/SHA;
  * 生产 coarse-CFO + 分数定时 + 广线性恢复、0.100 残差门 + 至多 3 次重捕 + 末次选择;
  * 分类预处理与窗口规则、canonical 训练序列、RMS2048、TX 衰减 <= -40 dB、RX 手动 35 dB、
    中心 2.4 GHz、采样 2.56 Msps、RX/TX 带宽 18 MHz;
  * 不训练 / 不调参 / 不换模型 / 不按类选择恢复或捕获。
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# 冻结身份 (继承自 npu-ab1, 不在此重新推导)
# ---------------------------------------------------------------------------
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

LABEL_ORDER_24 = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]
N_CLASSES = 24

# ---------------------------------------------------------------------------
# 冻结 RF 传输契约 (iq_rf_training_frame.hpp / iq_rf_frame_layout.hpp 权威值)
# ---------------------------------------------------------------------------
RF_FS = 2560000                      # 2.56 Msps
RF_PAYLOAD_COMPLEX = 53760           # kPayloadComplex (生产冻结, 不改)
RF_PREAMBLE_COMPLEX = 1024           # ZC 前导
RF_GUARD_COMPLEX = 2048
RF_TAIL_COMPLEX = 1024
RF_TOTAL_BURST_COMPLEX = 59904       # kTotalBurstComplex
RF_TRAIN_AMP = 2048.0                # kTrainAmp (前导/尾 int16 幅度)
RF_TARGET_RMS = 2048.0               # --rf-tx-target-rms 冻结 (不允许 > 2048)
RF_CENTER_HZ = 2400000000
RF_RX_GAIN_DB = 35.0
RF_TX_BW = 18000000
RF_RX_BW = 18000000
RF_TX_ATTEN_DB_MAX = -40.0           # 硬上限 (生产拒绝 > -40)
RF_RESIDUAL_GATE = 0.100             # 0.100 门 (生产冻结, 本任务不改)
RF_MAX_RECAPTURE = 3                 # 至多 3 次重捕 + 末次选择

# ---------------------------------------------------------------------------
# 固定公开幅度合同 S（评审 39e5 Blocker 1）：TX 数字缩放是**统一公开常数**，不是
# 逐样本 native_rms/tx_scale。S = 1600 / max_complex_magnitude（960 源），使量化后
# 最大分量恰为 1600（远低于 int16 上界 32767，无削顶）。板端以
# payload_tx_scale = S、payload_tx_target_rms = 0 撤销此公开数字缩放，恢复到 native
# 尺度（与数字基线一致），RF 真增益仍由训练块估计、绝不经 manifest 读取。
# ---------------------------------------------------------------------------
TX_MAX_COMPLEX_MAGNITUDE = 23.371109008789062   # max|IQ| over the 960 pilot1 sources
TX_DIGITAL_SCALE = 68.46059377833956            # 1600 / TX_MAX_COMPLEX_MAGNITUDE

# coarse-CFO 无歧义范围 = fs/(2*kPayloadTrainingOffset), kPayloadTrainingOffset=2048
RF_COARSE_CFO_UNAMBIGUOUS_HZ = RF_FS / (2.0 * 2048.0)  # 625 Hz
RF_FINE_CFO_RANGE_HZ = RF_FS / (2.0 * 58880.0)         # ~21.74 Hz

# ---------------------------------------------------------------------------
# 确定性适配规则 (Phase A 结论: 1024 vs 53760 不可直接兼容 -> 循环铺排)
# ---------------------------------------------------------------------------
MODEL_SAMPLES = 1024                 # RadioML [2,1024] f32 -> 1024 复样本
MODEL_TILE_TIMES = RF_PAYLOAD_COMPLEX // MODEL_SAMPLES   # 52
MODEL_TILE_REM = RF_PAYLOAD_COMPLEX % MODEL_SAMPLES      # 512

INT16_MIN = -32768
INT16_MAX = 32767


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_tensor_2x1024(path) -> np.ndarray:
    """[2,1024] f32le -> complex128[1024] (行0=实部 I, 行1=虚部 Q)。"""
    a = np.fromfile(path, dtype="<f4")
    assert a.size == 2 * MODEL_SAMPLES, "%s has %d floats" % (path, a.size)
    x = a.reshape(2, MODEL_SAMPLES)
    return (x[0] + 1j * x[1]).astype(np.complex128)


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    """complex[1024] -> [2,1024] f32le 字节 (与训练契约 ascontiguousarray(X.T) 同构)。"""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == MODEL_SAMPLES
    x = np.empty((2, MODEL_SAMPLES), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def native_rms(iq: np.ndarray) -> float:
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    return float(np.sqrt(np.mean(np.abs(iq) ** 2)))


def cyclic_tile_1024_to_payload(iq: np.ndarray) -> np.ndarray:
    """1024 复样本 -> 53760 复样本循环铺排 (确定性、类无关、保 RMS)。

    规则: payload[k] = iq[k mod 1024], k=0..53759。53760 = 52*1024 + 512,
    因此第 53 个周期在 512 处被截断。任何 1024 长窗口都是一个循环旋转,
    故模型窗口定义为恢复后 payload 的**前 1024 个复样本**。
    """
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == MODEL_SAMPLES
    reps = RF_PAYLOAD_COMPLEX // MODEL_SAMPLES + 1  # 53 个周期
    long_seq = np.tile(iq, reps)                    # 53*1024
    return long_seq[:RF_PAYLOAD_COMPLEX].copy()     # 前 53760


def _round_half_away(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return np.where(x >= 0.0, np.floor(x + 0.5), np.ceil(x - 0.5))


def lround(v) -> np.ndarray:
    """C++ std::lround / std::llround 语义: 四舍五入到最近整数, 平局远离零。

    与 numpy.rint 的「平局到偶」不同, 生产 TX 用 llround(半远离零)。为保证
    payload_sha_post / burst_sha 与板端 C++ 逐字节一致, 本任务统一用此实现。
    复输入对实/虚部分别取整 (与 C++ 对每个 I/Q 分量独立 lround 一致)。
    """
    v = np.asarray(v)
    if np.iscomplexobj(v):
        return _round_half_away(v.real) + 1j * _round_half_away(v.imag)
    return _round_half_away(v)


def quantize_ci16(iq: np.ndarray, scale: float) -> np.ndarray:
    """f32/float 复样本 -> int16 交错 [I0,Q0,...], 与生产 llround+clamp 语义一致。"""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    vals = lround(iq * scale)
    vals = np.clip(vals, INT16_MIN, INT16_MAX)
    out = np.empty(iq.size * 2, dtype="<i2")
    out[0::2] = vals.real.astype("<i2")
    out[1::2] = vals.imag.astype("<i2")
    return out


def deinterleave_int16(interleaved: np.ndarray) -> np.ndarray:
    """int16 交错 [I0,Q0,...] -> complex128 (与 iqrftrain::deinterleave 一致)。"""
    iq = np.asarray(interleaved, dtype=np.int16).ravel()
    assert iq.size % 2 == 0
    n = iq.size // 2
    return (iq[0::2].astype(np.float64) + 1j * iq[1::2].astype(np.float64))


def tx_scale_from_rms(rms: float, target_rms: float = RF_TARGET_RMS) -> float:
    """生产 TX 缩放常数 tx_scale = target_rms / native_rms (rms 为 0 则无缩放)。"""
    if rms > 0.0 and target_rms > 0.0:
        return target_rms / rms
    return 1.0


def complex_corr(a: np.ndarray, b: np.ndarray) -> float:
    """对齐后的 |复相关| (尺度不变): |sum(a conj(b))| / (||a|| ||b||)。"""
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    na = np.sqrt(np.vdot(a, a).real)
    nb = np.sqrt(np.vdot(b, b).real)
    if na == 0.0 or nb == 0.0:
        return float("nan")
    return float(abs(np.vdot(a, b)) / (na * nb))


def complex_nmse(a: np.ndarray, b: np.ndarray) -> float:
    """尺度无关 NMSE = min_g ||a - g*b||^2 / ||a||^2 (LS 复增益对齐)。"""
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    na = np.vdot(a, a).real
    if na == 0.0:
        return float("nan")
    g = np.vdot(a, b) / np.vdot(b, b).real if np.vdot(b, b).real > 0 else 0.0
    return float(np.vdot(a - g * b, a - g * b).real / na)


def short24_selection(frames):
    """short24 固定规则: 每类取 1 帧 @ dataset_snr_db=30 (只验证传输/身份/输出完整性)。

    从 480 帧中确定性选取 (不依赖标签做恢复/预测): 对每个 raw24_class, 取该类别中
    dataset_snr_db==30 且 selection_id 最小的一帧。若某类在 30 dB 层缺失则 fail-closed。
    """
    sel = {}
    for fr in frames:
        c = fr["raw24_class"]
        if fr["dataset_snr_db"] != 30:
            continue
        if c not in sel or fr["selection_id"] < sel[c]["selection_id"]:
            sel[c] = fr
    if len(sel) != N_CLASSES:
        missing = sorted(set(range(N_CLASSES)) - set(sel))
        raise ValueError("short24: missing 30 dB frames for classes %s" % missing)
    return [sel[c] for c in sorted(sel)]
