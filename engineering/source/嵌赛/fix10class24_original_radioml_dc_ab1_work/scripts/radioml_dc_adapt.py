#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_dc_adapt.py -- 单/双 SDR 最小 DC 适配的**单一共享实现**
(fix10class24-original-radioml-dc-ab1)。

这是 BOARD-PREP 任务: 只做主机侧准备, 不上板、不发射、不训练。本模块把 DC 适配
(direct vs dc-transport) 固化为**一份**代码, 单 SDR 与双 SDR 的 TX 导出、数字回环、
板端 loader/runner 都调用这同一份实现 —— 绝无两套计算。

## 两个适配路径

  direct        现有行为 (原始 IQ 直传), 逐字节不变:
                iq -> cyclic tile 1024->53760 -> CI16(RMS2048) -> 恢复 -> 前 1024 * unscale

  dc-transport  移除原始 IQ 均值 (DC), 只传 AC 分量, RX 恢复后按冻结参数还原尺度 + 加回 DC:
                dc = mean(iq)                 (复均值: I/Q 分别取均值)
                ac = iq - dc                  (去 DC)
                ac -> cyclic tile 1024->53760 -> CI16(ac, scale = 2048/ac_rms)
                RX 生产恢复 (不变) -> 恢复的 AC counts[:1024]
                ac_r = counts[:1024] * inverse_scale     (阶段 2: TX 尺度还原)
                iq_r = ac_r + dc                          (阶段 3: DC 加回)

## 三段式 (阶段 1/2/3 严格分离, 严禁双重尺度还原)

  阶段 1  RF 链路增益恢复  = 板端 recover_payload_with_coarse_cfo (payload-training 16QAM
         增益块 + wide-linear + coarse/fine CFO + 分数定时), 与 direct **完全一致**,
         direct/dc 共用同一 expected.tx_scale (~1.0, 因为 .i16 已预缩放到 RMS2048)。
  阶段 2  TX 尺度还原      = 单次乘法 * unscale (direct) / * inverse_scale (dc-transport),
         把恢复的 CI16 counts 映回目标 f32 幅度域。
  阶段 3  DC 加回          = 仅 dc-transport: + (dc_i + j*dc_q)。

  * inverse_scale 不是 unscale 的二次处理: 二者是同一「counts -> 目标 f32 域」的尺度,
    direct 目标域 = 原始 IQ 域 (unscale = native_rms(iq)/2048), dc-transport 目标域 = AC
    域 (inverse_scale = ac_rms/2048)。恢复链路内部的 gain 恢复是 RF 链路增益 (阶段 1),
    与这单次乘法 (阶段 2) 是不同量, 绝无双重还原。

## 红绳 (永不违反)

  * 冻结 BF16 JSON/RAW/CKPT SHA、24 类标签序、480/24 帧身份;
  * 生产 coarse-CFO + 分数定时 + 广线性恢复、0.100 门 + 至多 3 次重捕 + 末次选择;
  * 模型窗口位置/长度、canonical 训练序列、RMS2048、TX 衰减 <= -40 dB、RX 手动 35 dB、
    中心 2.4 GHz、采样 2.56 Msps、RX/TX 带宽 18 MHz;
  * direct 行为逐字节不变 (无秘密改尺度); 不新增滤波/重采样/参考窗搜索;
  * DC 参数 (dc_i/dc_q/ac_rms/inverse_scale) 绑定输入 SHA, 绝不绑定类别/识别结果。
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dualsdr_common as C  # noqa: E402

# 冻结 DC 适配标签 (板端 loader 逐字节比对, fail-closed)。
ADAPTATION_DIRECT = "cyclic_tile_1024_to_53760_rms2048_ci16"
ADAPTATION_DC_TRANSPORT = "dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16"


def adapt_forward(iq: np.ndarray):
    """DC 前向: 计算 dc / ac / dc_i / dc_q / ac_rms / tiled / CI16 / 尺度证据。

    返回 dict:
      dc, dc_i, dc_q, ac_rms, ac_tiled, tx_scale, inverse_scale, payload_i16,
      peak_pre, peak_post, clip_pre, clip_post
    RMS 口径: ac_rms = sqrt(mean(|ac|^2)) = **复 RMS** (与生产 native_rms 一致,
    不是 per-I/Q 分量 RMS)。TX AC 目标 RMS2048 = 复 RMS 2048。
    """
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == C.MODEL_SAMPLES, "dc-transport expects 1024 complex samples"

    dc = complex(np.mean(iq.real), np.mean(iq.imag))
    ac = iq - dc
    ac_rms = C.native_rms(ac)

    # 阶段 2/3 的尺度: TX 量化 scale = 2048/ac_rms; inverse_scale = ac_rms/2048。
    tx_scale = C.tx_scale_from_rms(ac_rms, C.RF_TARGET_RMS)
    inverse_scale = ac_rms / C.RF_TARGET_RMS if tx_scale > 0 else 0.0

    ac_tiled = C.cyclic_tile_1024_to_payload(ac)       # 铺排的是 AC (不是原 IQ)
    payload_i16 = C.quantize_ci16(ac_tiled, tx_scale)  # CI16(AC, 2048/ac_rms)

    peak_pre = float(np.abs(ac).max())
    peak_post = float(np.abs(payload_i16).max())
    return {
        "dc": dc,
        "dc_i": float(dc.real),
        "dc_q": float(dc.imag),
        "ac_rms": ac_rms,
        "ac_tiled": ac_tiled,
        "tx_scale": tx_scale,
        "inverse_scale": inverse_scale,
        "payload_i16": payload_i16,
        "peak_pre": peak_pre,
        "peak_post": peak_post,
        "clip_pre": peak_pre >= 32767.0,
        "clip_post": peak_post >= 32767.0,
    }


def adapt_inverse(recovered_ac_counts: np.ndarray, dc: complex,
                  inverse_scale: float) -> np.ndarray:
    """DC 逆向 (阶段 2 + 阶段 3): 恢复的 AC counts -> * inverse_scale -> + dc。

    recovered_ac_counts 是恢复后 payload 的前 1024 复样本 (CI16 counts 域, 即生产恢复
    输出的 ccr.payload[:1024])。返回 [1024] 复样本, 应在原始 IQ 的 f32 域。
    """
    counts = np.asarray(recovered_ac_counts, dtype=np.complex128).ravel()
    assert counts.size == C.MODEL_SAMPLES, "dc-transport inverse expects 1024 complex counts"
    ac_restored = counts * inverse_scale          # 阶段 2: TX 尺度还原
    return ac_restored + dc                       # 阶段 3: DC 加回


def direct_ideal_roundtrip(iq: np.ndarray):
    """direct 数字理想往返 (逐字复用 direct 契约)。返回 (recovered, evidence)。"""
    rms = C.native_rms(iq)
    scale = C.tx_scale_from_rms(rms, C.RF_TARGET_RMS)
    tiled = C.cyclic_tile_1024_to_payload(iq)
    ci16 = C.quantize_ci16(tiled, scale)
    counts = C.deinterleave_int16(ci16)
    window = counts[:C.MODEL_SAMPLES]
    unscale = rms / C.RF_TARGET_RMS
    recovered = window * unscale
    return recovered, {
        "unscale": unscale,
        "native_rms": rms,
    }


def dc_ideal_roundtrip(iq: np.ndarray):
    """dc-transport 数字理想往返 (无 RF, 恢复退化为恒等)。返回 (recovered, evidence)。

    诚实边界: 生产恢复在数字无 RF 情形下退化为恒等 (CFO=0/定时精确/无 IQ 不平衡/链路
    增益=1), 这里不做 C++ 恢复的 Python 等效声明 —— 只证明 DC 适配本身的确定性往返。
    """
    fwd = adapt_forward(iq)
    counts = C.deinterleave_int16(fwd["payload_i16"])       # 理想接收 = 量化 AC counts
    window = counts[:C.MODEL_SAMPLES]
    recovered = adapt_inverse(window, fwd["dc"], fwd["inverse_scale"])
    return recovered, fwd
