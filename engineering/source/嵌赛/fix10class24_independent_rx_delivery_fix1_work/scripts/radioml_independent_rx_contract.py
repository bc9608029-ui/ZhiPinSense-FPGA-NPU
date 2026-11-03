#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_independent_rx_contract.py -- fix10class24-independent-rx-delivery-fix1
公共协议（public protocol）独立接收契约：核心可执行单一来源。

修正 blind-clean1 的「无帧盲采 + 固定窗口」交付缺口，把主验收臂换成
**公共协议**：所有类别共用同一套同步/训练/固定帧结构（复用 dualsdr 冻结
`build_burst`：ZC 前导 + settling-zero + 16QAM 载荷训练块 + 载荷 + guard-zero +
ZC 尾），接收端只用**公共参考**（前导/尾估 CFO·定时、载荷训练块估增益·IQ 补偿）
定位 1024 点载荷窗口，再用**统一、类别无关**的幅度合同归一化到模型域。

    A 原始波形     = generate_class(name, seed)                  (离线对齐参考，不进接收推理)
    B 公共协议恢复 = 公共参考估计 -> 恢复载荷[:1024] * (1/S)      (数字域主验收臂)
    C 板端模型输入 = 板端 C++ 生产恢复链输出（板测时回传，本任务离线不产 C）

幅度合同（第 2 节）三量分离、逐条记录，删掉 blind-clean1 的
「数字量化逆变换证明 RF 幅度已恢复」论证：

  1. tx_digital_scale   S = 1600/max_peak（统一、类别无关）      ci16 = lround(wf*S)
  2. rx_gain_estimate   a（广线性系数，从载荷训练块已知幅度估计；数字域 a≈1）
  3. model_input_norm   1/S（统一反缩放）                        model_input = wl_inv(payload,a,b)/S

诚实边界：数字域 a≈1、b≈0 只证明「TX->模型归一化链路自洽」，**不**证明 RF 模拟
增益 G 已恢复；RF 路径的 G 由公共参考估计 a≈G，是否成立需板端训练块残差单独核验。

本模块**纯离线**：不上板、不发射、不训练、不自动增加 480 帧或新算法实验。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as GEN      # noqa: E402  (frozen clean2a generator)
import radioml_dualsdr_common as C        # noqa: E402  (frozen dualsdr common)
import radioml_dualsdr_burst as BURST     # noqa: E402  (frozen public burst)

TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1"

# ---------------------------------------------------------------------------
# 冻结常量（第 1/2 节：公共协议 + 幅度合同）
# ---------------------------------------------------------------------------
SEED_BASE = 3000000                       # 与 blind-clean1 相同 24 波形种子（不新增帧）
TX_DIGITAL_SCALE = 117.84922023433009     # S = 1600/max_peak（统一、类别无关）
MODEL_INPUT_NORM = 1.0 / TX_DIGITAL_SCALE # 统一反缩放 1/S
MAX_PEAK = 13.576670230134553             # 24 生产种子 max|waveform|（AM-SSB-WC seed 3000017）
ADC_FULL_SCALE = 2048.0                   # 训练块参考幅度基准（非载荷幅度）
SAMPLE_RATE_HZ = 2560000.0                # 2.56 Msps（= C.RF_FS）
N_CLASSES = 24

# 公共协议布局（复用 dualsdr 冻结 burst；权威 C++ iq_rf_training_frame.hpp）
K_PREAMBLE_COMPLEX = BURST.K_PREAMBLE_COMPLEX          # 1024
K_GUARD_COMPLEX = BURST.K_GUARD_COMPLEX                # 2048
K_TAIL_COMPLEX = BURST.K_TAIL_COMPLEX                  # 1024
K_PAYLOAD_COMPLEX = BURST.K_PAYLOAD_COMPLEX            # 53760
K_PAYLOAD_START = BURST.K_PAYLOAD_START                # 3072
K_TAIL_START = BURST.K_TAIL_START                      # 58880
K_TOTAL_BURST_COMPLEX = BURST.K_TOTAL_BURST_COMPLEX    # 59904
K_PAYLOAD_TRAINING_COMPLEX = BURST.K_PAYLOAD_TRAINING_COMPLEX  # 1024
K_PAYLOAD_TRAINING_OFFSET = BURST.K_PAYLOAD_TRAINING_OFFSET      # 2048
K_PAYLOAD_TRAINING_AMP = BURST.K_PAYLOAD_TRAINING_AMP            # 2896.309375740099

# 载荷训练块在 burst 内的复样本起点（preamble 1024 + settling-zero 1024）
PAYLOAD_TRAINING_POS = K_PREAMBLE_COMPLEX + (K_PAYLOAD_TRAINING_OFFSET - K_PREAMBLE_COMPLEX)

SOURCE_ID = "fix1-public-protocol-24waveforms"   # 源身份（第 4 节同源绑定）
CONVERSION_VERSION = "v1"                        # 转换版本（第 4 节同源绑定）


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    """complex[1024] -> [2,1024] f32le（模型输入契约，行0=实部）。"""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == GEN.SAMPLE_LENGTH
    x = np.empty((2, GEN.SAMPLE_LENGTH), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def quantize_ci16(iq: np.ndarray, scale: float) -> np.ndarray:
    """complex -> 交错 int16 LE [I0,Q0,...]，lround（半远离零）+ clamp。"""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    vals = np.clip(C.lround(iq * scale), C.INT16_MIN, C.INT16_MAX)
    out = np.empty(iq.size * 2, dtype="<i2")
    out[0::2] = vals.real.astype("<i2")
    out[1::2] = vals.imag.astype("<i2")
    return out


# ---------------------------------------------------------------------------
# 公共协议 TX 侧（第 1/2 节）
# ---------------------------------------------------------------------------
def generate_waveform(class_index: int) -> np.ndarray:
    """按类索引生成 1024 点纯净调制波形（复用 blind-clean1 同种子，不新增帧）。"""
    name = GEN.LABEL_ORDER_24[class_index]
    wf = GEN.generate_class(name, SEED_BASE + class_index)
    assert wf.size == GEN.SAMPLE_LENGTH
    return wf


def build_public_protocol_burst(waveform: np.ndarray) -> np.ndarray:
    """纯净波形 -> 公共协议 burst（int16 交错，119808 int16）。

    载荷 = cyclic_tile(waveform, 53760) 以统一 S 量化；训练块（16QAM，幅度
    2896.309）作为增益参考与载荷同 burst，但处于**不同** int16 幅度——这正是
    幅度合同三量分离的依据（训练块已知幅度估增益，载荷统一 S 归一化）。
    """
    tiled = C.cyclic_tile_1024_to_payload(waveform)     # 53760 复
    payload_i16 = quantize_ci16(tiled, TX_DIGITAL_SCALE)
    return BURST.build_burst(payload_i16)


def payload_training_complex() -> np.ndarray:
    """载荷训练块（16QAM）参考，complex128（接收端增益/IQ 估计的已知符号）。"""
    return C.deinterleave_int16(BURST.payload_gain_training_int16())


# ---------------------------------------------------------------------------
# 公共协议接收端（第 1/5 节）：公共参考估计 + 恢复
# ---------------------------------------------------------------------------
def _preamble_complex() -> np.ndarray:
    return C.deinterleave_int16(BURST.preamble_int16())


def _tail_complex() -> np.ndarray:
    return C.deinterleave_int16(BURST.tail_int16())


def estimate_timing_offset(rx: np.ndarray, search_span: int = 512) -> int:
    """用 ZC 前导互相关定位 burst 起点（数字域应为 0）。"""
    pre = _preamble_complex()
    best = -1
    best_v = -1.0
    for d in range(-search_span, search_span + 1):
        if d < 0:
            seg = rx[: K_PREAMBLE_COMPLEX + d]
            ref = pre[-d:]
        else:
            seg = rx[d: d + K_PREAMBLE_COMPLEX]
            ref = pre[: K_PREAMBLE_COMPLEX - d] if d else pre
        if seg.size != ref.size:
            continue
        v = float(np.abs(np.vdot(seg, ref)))
        if v > best_v:
            best_v = v
            best = d
    return best


def estimate_coarse_cfo_hz(rx: np.ndarray) -> float:
    """前导两半互相关相位差估 coarse CFO（无歧义 ±Fs/(2·512)=±2500 Hz）。

    cA 质心 n≈255.5、cB 质心 n≈767.5，angle(cB/cA) ≈ -φ·512 -> cfo = -dphi·Fs/(2π·512)。
    该无歧义范围覆盖典型模拟 CFO（远大于 fine 段 ±21.74 Hz 的 preamble↔tail 方法）。
    """
    pre = _preamble_complex()
    half = K_PREAMBLE_COMPLEX // 2
    cA = np.vdot(rx[:half], pre[:half])                       # complex
    cB = np.vdot(rx[half:K_PREAMBLE_COMPLEX], pre[half:K_PREAMBLE_COMPLEX])
    if cA == 0.0:
        return 0.0
    dphi = float(np.angle(cB / cA))
    return -dphi * SAMPLE_RATE_HZ / (2.0 * np.pi * half)


def wide_linear_fit(x: np.ndarray, r: np.ndarray):
    """LS 拟合 r ≈ a*x + b*conj(x)，返回 (a, b, residual)。"""
    x = np.asarray(x, dtype=np.complex128).ravel()
    r = np.asarray(r, dtype=np.complex128).ravel()
    P = float(np.vdot(x, x).real)              # Σ|x|^2（实）
    Cc = np.sum(x * x)                          # Σ x^2（复，二阶矩）
    lhs = np.array([[P, np.conj(Cc)], [Cc, P]], dtype=np.complex128)
    rhs = np.array([np.vdot(x, r), np.sum(x * r)], dtype=np.complex128)
    det = P * P - (Cc * np.conj(Cc)).real
    if abs(det) < 1e-300:
        return 1.0 + 0.0j, 0.0 + 0.0j, float("inf")
    a = (P * rhs[0] - np.conj(Cc) * rhs[1]) / det
    b = (P * rhs[1] - Cc * rhs[0]) / det
    resid = float(np.sqrt(np.vdot(r - a * x - b * np.conj(x),
                                  r - a * x - b * np.conj(x)).real / P))
    return a, b, resid


def wide_linear_inverse(r: np.ndarray, a: complex, b: complex) -> np.ndarray:
    """广线性逆：x = (conj(a)*r - b*conj(r)) / (|a|^2 - |b|^2)。"""
    r = np.asarray(r, dtype=np.complex128)
    denom = (abs(a) ** 2 - abs(b) ** 2)
    if abs(denom) < 1e-300:
        return np.full_like(r, np.nan)
    return (np.conj(a) * r - b * np.conj(r)) / denom


def estimate_public_reference(rx: np.ndarray):
    """公共参考估计：定时 + coarse CFO + 广线性增益/IQ（载荷训练块）。

    rx: complex128，长度 == 59904（已按 timing_offset 对齐的整 burst）。
    返回 dict：timing_offset / coarse_cfo_hz / a / b / training_residual。
    """
    timing = estimate_timing_offset(rx)
    rx_aligned = np.roll(rx, -timing) if timing else rx
    cfo = estimate_coarse_cfo_hz(rx_aligned)
    # 去 CFO（相位斜坡）
    n = np.arange(K_TOTAL_BURST_COMPLEX, dtype=np.float64)
    rx_derot = rx_aligned * np.exp(-1j * 2.0 * np.pi * cfo * n / SAMPLE_RATE_HZ)
    # 广线性拟合（载荷训练块已知符号）
    x_train = payload_training_complex()
    s0 = PAYLOAD_TRAINING_POS
    r_train = rx_derot[s0: s0 + K_PAYLOAD_TRAINING_COMPLEX]
    a, b, resid = wide_linear_fit(x_train, r_train)
    return {
        "timing_offset": timing,
        "coarse_cfo_hz": cfo,
        "a": a,
        "b": b,
        "training_residual": resid,
    }


def recover_model_input(rx: np.ndarray, est: dict) -> np.ndarray:
    """恢复模型输入（complex1024）：载荷[:1024] 广线性逆 + 统一归一化 1/S。"""
    timing = est["timing_offset"]
    rx_aligned = np.roll(rx, -timing) if timing else rx
    n = np.arange(K_TOTAL_BURST_COMPLEX, dtype=np.float64)
    rx_derot = rx_aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / SAMPLE_RATE_HZ)
    payload = rx_derot[K_PAYLOAD_START: K_PAYLOAD_START + K_PAYLOAD_COMPLEX]
    wl = wide_linear_inverse(payload, est["a"], est["b"])
    return wl[:GEN.SAMPLE_LENGTH] * MODEL_INPUT_NORM


# ---------------------------------------------------------------------------
# 反例注入（第 5/6 节）：已知 CFO/增益/IQ 不平衡，验证接收端恢复
# ---------------------------------------------------------------------------
def apply_rx_impairment(rx: np.ndarray, cfo_hz: float, gain: complex,
                        iq_a: complex, iq_b: complex) -> np.ndarray:
    """向（纯净）burst 注入已知模拟损伤：IQ 不平衡+增益 -> 再 CFO 相位斜坡。

    前向模型：r[n] = gain * (iq_a*x[n] + iq_b*conj(x[n])) * exp(j*2*pi*cfo*n/Fs)。
    """
    x = np.asarray(rx, dtype=np.complex128).copy()
    x = gain * (iq_a * x + iq_b * np.conj(x))
    n = np.arange(x.size, dtype=np.float64)
    return x * np.exp(1j * 2.0 * np.pi * cfo_hz * n / SAMPLE_RATE_HZ)


def three_layer_stats(waveform: np.ndarray, model_input: np.ndarray):
    """A<->B 逐层统计：RMS / DC / 对齐相关 / 归一化残差。"""
    a = np.asarray(waveform, dtype=np.complex128).ravel()
    b = np.asarray(model_input, dtype=np.complex128).ravel()
    rms = float(np.sqrt(np.mean(np.abs(b) ** 2)))
    dc_re = float(np.mean(b.real))
    dc_im = float(np.mean(b.imag))
    na = float(np.sqrt(np.sum(np.abs(a) ** 2)))
    nb = float(np.sqrt(np.sum(np.abs(b) ** 2)))
    corr = float(np.abs(np.vdot(a, b))) / (na * nb) if (na > 0 and nb > 0) else 0.0
    resid = float(np.sqrt(np.sum(np.abs(b - a) ** 2))) / na if na > 0 else 0.0
    return {"rms": rms, "dc_real": dc_re, "dc_imag": dc_im,
            "corr": corr, "residual": resid}


# ---------------------------------------------------------------------------
# CLI / self-test
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    ap.error("only --self-test is supported (this module is a library + self-test)")


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-52s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # R1: 数字无损伤公共协议恢复 == 原始波形（全部 24 类）
    max_rel = 0.0
    for ci in range(N_CLASSES):
        wf = generate_waveform(ci)
        burst = build_public_protocol_burst(wf)
        rx = C.deinterleave_int16(burst)
        assert rx.size == K_TOTAL_BURST_COMPLEX
        est = estimate_public_reference(rx)
        zi = recover_model_input(rx, est)
        rel = float(np.sqrt(np.mean(np.abs(wf - zi) ** 2)) /
                    np.sqrt(np.mean(np.abs(wf) ** 2)))
        max_rel = max(max_rel, rel)
    check("R1 public-protocol recovery rel RMS < 1e-2 (24/24)", max_rel < 1e-2,
          "max_rel=%.3e" % max_rel)

    # 数字域幅度合同：a≈1、b≈0（第 2 节「数字逆变换不证明 RF 恢复」的量化断言）
    wf = generate_waveform(4)                       # QPSK
    rx = C.deinterleave_int16(build_public_protocol_burst(wf))
    est = estimate_public_reference(rx)
    check("digital a ~= 1 (gain est = 1, no analog info)", abs(est["a"] - 1.0) < 1e-3,
          "a=%.6g+%.6gj" % (est["a"].real, est["a"].imag))
    check("digital b ~= 0 (no IQ imbalance)", abs(est["b"]) < 1e-3,
          "b=%.3e" % abs(est["b"]))
    check("digital CFO ~= 0", abs(est["coarse_cfo_hz"]) < 1.0,
          "cfo=%.3e Hz" % est["coarse_cfo_hz"])
    check("digital timing offset == 0", est["timing_offset"] == 0,
          "off=%d" % est["timing_offset"])

    # R2: 注入已知 CFO/增益/IQ 不平衡 -> 接收端恢复
    inj_cfo = 120.0
    inj_gain = 0.9 + 0.2j
    inj_a = 1.0 + 0.0j
    inj_b = 0.05 + 0.02j
    rx_imp = apply_rx_impairment(rx, inj_cfo, inj_gain, inj_a, inj_b)
    est2 = estimate_public_reference(rx_imp)
    check("R2 CFO recovered (|est-inj|<1 Hz)", abs(est2["coarse_cfo_hz"] - inj_cfo) < 1.0,
          "est=%.4f inj=%.4f" % (est2["coarse_cfo_hz"], inj_cfo))
    # a ≈ gain*iq_a, b ≈ gain*iq_b（组合系数）
    check("R2 wide-linear a ~ gain*iq_a", abs(est2["a"] - inj_gain * inj_a) < 0.02,
          "a=%.4f+%.4fj want~%.4f+%.4fj" %
          (est2["a"].real, est2["a"].imag, (inj_gain * inj_a).real, (inj_gain * inj_a).imag))
    check("R2 wide-linear b ~ gain*iq_b", abs(est2["b"] - inj_gain * inj_b) < 0.02,
          "|b|=%.4f want~%.4f" % (abs(est2["b"]), abs(inj_gain * inj_b)))
    zi2 = recover_model_input(rx_imp, est2)
    rel2 = float(np.sqrt(np.mean(np.abs(wf - zi2) ** 2)) /
                 np.sqrt(np.mean(np.abs(wf) ** 2)))
    check("R2 recovered model input ~ waveform (rel<2e-2)", rel2 < 2e-2,
          "rel=%.3e" % rel2)

    # R3: 三层统计一致性
    st = three_layer_stats(wf, zi2)
    check("R3 corr ~ 1", st["corr"] > 0.99, "corr=%.6f" % st["corr"])

    all_ok = all(checks)
    print("RADIOML_INDEPENDENT_RX_CONTRACT_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
