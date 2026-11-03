#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_dualsdr_burst.py -- 冻结训练帧 build_burst 的 Python 逐字重实现
(fix10class24-original-radioml-dualsdr-ab1)。

把板端 C++ `iq_rf_training_frame.hpp` 的确定性训练帧构建器 (ZC 前导/尾 + settling-zero
+ payload-domain 增益训练块 + guard-zero) 在 Python 侧逐字重实现, 供:
  * 主机侧核验「canonical burst SHA/scale」与「payload_sha_pre/post」;
  * 契约文档固化 (singlesdr fork 复用);
  * 板测时与板端独立重建的 burst_sha 对齐的**期望值**。

诚实边界: 这是**规范重实现**(逐字对照 C++ 常量与舍入), 不是 C++ 二进制产物的等效物。
最终 burst_sha 的权威仲裁者是板端 C++ `build_burst`(板端会独立重建并比对 SHA);
本模块的产物仅在板测前用于主机侧预演, 若与板端不一致即失败关闭。

舍入: 全部用 C.lround (半远离零), 与 C++ std::lround/llround 一致。
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dualsdr_common as C  # noqa: E402

# ---- 冻结常量 (iq_rf_training_frame.hpp, 逐字) -------------------------------
K_PREAMBLE_COMPLEX = 1024
K_GUARD_COMPLEX = 2048
K_TAIL_COMPLEX = 1024
K_PAYLOAD_COMPLEX = 53760            # == C.RF_PAYLOAD_COMPLEX
K_PAYLOAD_START = K_PREAMBLE_COMPLEX + K_GUARD_COMPLEX                 # 3072
K_TAIL_START = K_PAYLOAD_START + K_PAYLOAD_COMPLEX + K_GUARD_COMPLEX   # 58880
K_TOTAL_BURST_COMPLEX = K_TAIL_START + K_TAIL_COMPLEX                  # 59904

K_TRAIN_AMP = 2048.0
K_ZADOFF_CHU_ROOT = 1
K_TAIL_ZADOFF_CHU_ROOT = 3

K_PAYLOAD_TRAINING_COMPLEX = 1024
K_PAYLOAD_TRAINING_OFFSET = 2048
K_PAYLOAD_TRAINING_SEED = 0x2A9E1B7D
K_PAYLOAD_TRAINING_SAMPLES_PER_SYMBOL = 32
K_PAYLOAD_TRAINING_AMP = 2896.309375740099   # sqrt(2)*2048 (复 RMS)


def _zadoff_chu(root: int, n: int = K_PREAMBLE_COMPLEX) -> np.ndarray:
    """长度 n 的 Zadoff-Chu 单位包络: u[k] = exp(-j*pi*root*k^2/n), k=0..n-1。"""
    k = np.arange(n, dtype=np.float64)
    ph = -np.pi * root * k * k / n
    return np.cos(ph) + 1j * np.sin(ph)


def _quantize_block(complex_vals: np.ndarray, amp: float) -> np.ndarray:
    """复块 -> 交错 int16 [I0,Q0,...], 幅度 amp, lround。"""
    vals = C.lround(complex_vals * amp)
    vals = np.clip(vals, C.INT16_MIN, C.INT16_MAX)
    out = np.empty(complex_vals.size * 2, dtype="<i2")
    out[0::2] = vals.real.astype("<i2")
    out[1::2] = vals.imag.astype("<i2")
    return out


def preamble_int16() -> np.ndarray:
    """ZC 前导 (root=1), int16 交错, 幅度 kTrainAmp=2048。"""
    return _quantize_block(_zadoff_chu(K_ZADOFF_CHU_ROOT), K_TRAIN_AMP)


def tail_int16() -> np.ndarray:
    """ZC 尾 (root=3), int16 交错, 幅度 kTrainAmp=2048。"""
    return _quantize_block(_zadoff_chu(K_TAIL_ZADOFF_CHU_ROOT), K_TRAIN_AMP)


def payload_gain_training_int16() -> np.ndarray:
    """payload-domain 增益训练块 (16QAM/sqrt10, LCG 种子冻结), int16 交错。"""
    inv_sqrt10 = 1.0 / np.sqrt(10.0)
    levels = np.array([-3, -1, 1, 3], dtype=np.float64)
    n_sym = K_PAYLOAD_TRAINING_COMPLEX // K_PAYLOAD_TRAINING_SAMPLES_PER_SYMBOL

    s = K_PAYLOAD_TRAINING_SEED & 0xFFFFFFFF
    sym = np.empty((n_sym,), dtype=np.complex128)
    for m in range(n_sym):
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        i = levels[(s >> 30) & 3]
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        q = levels[(s >> 30) & 3]
        sym[m] = complex(i * inv_sqrt10, q * inv_sqrt10)

    energy = float(np.sum(sym.real ** 2 + sym.imag ** 2))
    rms = np.sqrt(energy / n_sym)
    scale = K_PAYLOAD_TRAINING_AMP / rms if rms > 0.0 else 1.0
    z = sym * scale
    I = C.lround(np.clip(z.real, -32768.0, 32767.0)).astype(np.int16)
    Q = C.lround(np.clip(z.imag, -32768.0, 32767.0)).astype(np.int16)

    out = np.empty(K_PAYLOAD_TRAINING_COMPLEX * 2, dtype="<i2")
    for m in range(n_sym):
        base = m * K_PAYLOAD_TRAINING_SAMPLES_PER_SYMBOL
        out[(base * 2 + 0):(base * 2 + K_PAYLOAD_TRAINING_SAMPLES_PER_SYMBOL * 2):2] = I[m]
        out[(base * 2 + 1):(base * 2 + K_PAYLOAD_TRAINING_SAMPLES_PER_SYMBOL * 2):2] = Q[m]
    return out


def build_burst(payload_i16: np.ndarray) -> np.ndarray:
    """完整训练帧 burst (int16 交错), 与 C++ build_burst 逐字一致。

    布局: [preamble 1024][settling-zero 1024][payload-training 1024][payload 53760]
          [guard-zero 2048][tail 1024]  == 59904 复 = 119808 int16。
    """
    payload_i16 = np.asarray(payload_i16, dtype="<i2").ravel()
    assert payload_i16.size == K_PAYLOAD_COMPLEX * 2, "payload must be 53760 complex"
    pre = preamble_int16()
    pt = payload_gain_training_int16()
    tail = tail_int16()
    b = np.concatenate([
        pre,
        np.zeros((K_PAYLOAD_TRAINING_OFFSET - K_PREAMBLE_COMPLEX) * 2, dtype="<i2"),
        pt,
        payload_i16,
        np.zeros(K_GUARD_COMPLEX * 2, dtype="<i2"),
        tail,
    ])
    assert b.size == K_TOTAL_BURST_COMPLEX * 2
    return b


def wrapper_sha256s() -> dict:
    """payload 无关的确定性包装块 SHA (供契约固化)。"""
    return {
        "preamble_sha256": C.sha256_bytes(preamble_int16().tobytes()),
        "settling_zero_sha256": C.sha256_bytes(
            np.zeros((K_PAYLOAD_TRAINING_OFFSET - K_PREAMBLE_COMPLEX) * 2,
                     dtype="<i2").tobytes()),
        "payload_training_sha256": C.sha256_bytes(payload_gain_training_int16().tobytes()),
        "guard_zero_sha256": C.sha256_bytes(
            np.zeros(K_GUARD_COMPLEX * 2, dtype="<i2").tobytes()),
        "tail_sha256": C.sha256_bytes(tail_int16().tobytes()),
    }


def build_tx_burst_from_payload(payload_i16: np.ndarray, target_rms: float) -> dict:
    """与 C++ build_tx_burst_from_frozen 语义一致: 载入 payload ci16 -> 算 native_rms
    -> 应用 target_rms 缩放 (llround+clamp) -> build_burst -> 返回
    payload_sha_pre/post / burst_sha / tx_scale。"""
    payload_i16 = np.asarray(payload_i16, dtype="<i2").ravel()
    assert payload_i16.size == K_PAYLOAD_COMPLEX * 2
    payload_sha_pre = C.sha256_bytes(payload_i16.tobytes())

    iq = C.deinterleave_int16(payload_i16)          # complex128, 值为 int16 counts
    native_rms = C.native_rms(iq)
    peak_pre = float(np.abs(iq).max())
    peak_post = peak_pre
    clip_pre = peak_pre >= 32767.0
    clip_post = clip_pre
    tx_scale = 1.0
    if target_rms > 0.0 and native_rms > 0.0:
        want = target_rms / native_rms
        peak_post = peak_pre * want
        clip_post = peak_post >= 32767.0
        if not clip_post:
            tx_scale = want
            iq = np.clip(C.lround(iq * tx_scale), C.INT16_MIN, C.INT16_MAX)

    # 重新交错为 int16 (clip_post 时保持原样, 即 tx_scale==1 无缩放)
    scaled = iq.astype(np.complex128)
    out = np.empty(K_PAYLOAD_COMPLEX * 2, dtype="<i2")
    out[0::2] = np.clip(C.lround(scaled.real), C.INT16_MIN, C.INT16_MAX).astype("<i2")
    out[1::2] = np.clip(C.lround(scaled.imag), C.INT16_MIN, C.INT16_MAX).astype("<i2")
    payload_sha_post = C.sha256_bytes(out.tobytes())
    burst = build_burst(out)
    return {
        "payload_sha_pre": payload_sha_pre,
        "payload_sha_post": payload_sha_post,
        "burst_sha": C.sha256_bytes(burst.tobytes()),
        "native_rms": native_rms,
        "target_rms": target_rms,
        "tx_scale": tx_scale,
        "peak_pre": peak_pre,
        "peak_post": peak_post,
        "clip_pre": clip_pre,
        "clip_post": clip_post,
    }
