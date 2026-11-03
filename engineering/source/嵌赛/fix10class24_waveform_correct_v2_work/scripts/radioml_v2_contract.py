#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_v2_contract.py -- 波形正确性 v2 的公共协议 + 幅度合同（新版本，不动 v1）。

复用 fix1 的公共协议 burst 结构与独立接收流程（estimate_public_reference /
wide_linear_inverse / quantize_ci16 / tensor_to_bytes / sha256 / K_* 布局），
只替换两处为 v2：
  1. 波形源：generate_waveform_v2 用 radioml_waveform_correct_v2（4 个 AM 类修正，
     其余 20 类逐字复用冻结生成器）。
  2. 幅度合同：MAX_PEAK_v2 / S_v2=1600/MAX_PEAK_v2 / 1/S_v2（AM 波形变 -> max_peak 变，
     故 S 是 v2 自己的常数；结构同 fix1 三量分离）。

source_id / conversion_version 独立为 v2，绝不冒充 v1 或 480 帧配对。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_independent_rx_contract as V1     # noqa: E402  (vendored fix1, 只读)
import radioml_clean_contract as GEN             # noqa: E402  (frozen, 只读)
import radioml_waveform_correct_v2 as WV2        # noqa: E402  (v2 修正 AM)

TOKEN = "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2-CONTRACT"

# ---- v2 身份（第 4 节同源绑定，独立于 v1）----------------------------------
SEED_BASE = 3000000                                       # 同种子（类别无关，复用）
SOURCE_ID_V2 = "fix1v2-waveform-corrected-24waveforms"
CONVERSION_VERSION_V2 = "v2"
N_CLASSES = 24

# ---- v2 幅度合同：max_peak / S / 1/S（AM 波形变 -> 常数变）-----------------
def _all_waveforms():
    return [WV2.generate_class_v2(GEN.LABEL_ORDER_24[ci], SEED_BASE + ci)
            for ci in range(N_CLASSES)]

_ALL_WF = _all_waveforms()
MAX_PEAK_V2 = float(max(np.max(np.abs(w)) for w in _ALL_WF))
TX_DIGITAL_SCALE_V2 = 1600.0 / MAX_PEAK_V2
MODEL_INPUT_NORM_V2 = 1.0 / TX_DIGITAL_SCALE_V2
MAX_PEAK_CLASS_V2 = GEN.LABEL_ORDER_24[
    int(np.argmax([np.max(np.abs(w)) for w in _ALL_WF]))]


# ---- 复用 fix1 的公共协议 / 恢复，只换波形源 + 幅度常数 --------------------
def generate_waveform_v2(class_index: int) -> np.ndarray:
    name = GEN.LABEL_ORDER_24[class_index]
    wf = WV2.generate_class_v2(name, SEED_BASE + class_index)
    assert wf.size == GEN.SAMPLE_LENGTH
    return wf


def build_public_protocol_burst_v2(waveform: np.ndarray) -> np.ndarray:
    """v2：波形 cyclic_tile -> lround(wf·S_v2) -> 公共协议 burst（结构同 fix1）。"""
    tiled = V1.C.cyclic_tile_1024_to_payload(waveform)
    payload_i16 = V1.quantize_ci16(tiled, TX_DIGITAL_SCALE_V2)
    return V1.BURST.build_burst(payload_i16)


def recover_model_input_v2(rx: np.ndarray, est: dict) -> np.ndarray:
    """v2：恢复链同 fix1，仅最终归一化用 1/S_v2。"""
    timing = est["timing_offset"]
    rx_aligned = np.roll(rx, -timing) if timing else rx
    n = np.arange(V1.K_TOTAL_BURST_COMPLEX, dtype=np.float64)
    rx_derot = rx_aligned * np.exp(-1j * 2.0 * np.pi * est["coarse_cfo_hz"] * n / V1.SAMPLE_RATE_HZ)
    payload = rx_derot[V1.K_PAYLOAD_START: V1.K_PAYLOAD_START + V1.K_PAYLOAD_COMPLEX]
    wl = V1.wide_linear_inverse(payload, est["a"], est["b"])
    return wl[:GEN.SAMPLE_LENGTH] * MODEL_INPUT_NORM_V2


def recover_from_burst_v2(burst_bytes: bytes) -> np.ndarray:
    inter = np.frombuffer(burst_bytes, dtype="<i2")
    assert inter.size == 2 * V1.K_TOTAL_BURST_COMPLEX
    rx = V1.C.deinterleave_int16(inter)
    est = V1.estimate_public_reference(rx)
    return recover_model_input_v2(rx, est)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    ap.error("only --self-test is supported (library + self-test)")


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    check("v2 has its own S (differs from v1 S)",
          abs(TX_DIGITAL_SCALE_V2 - V1.TX_DIGITAL_SCALE) > 1e-9,
          "S_v2=%.9f S_v1=%.9f" % (TX_DIGITAL_SCALE_V2, V1.TX_DIGITAL_SCALE))
    check("v2 identity distinct from v1",
          SOURCE_ID_V2 != V1.SOURCE_ID and CONVERSION_VERSION_V2 != V1.CONVERSION_VERSION,
          "src_v2=%s v2=%s" % (SOURCE_ID_V2, CONVERSION_VERSION_V2))

    # 数字无损伤：公共协议恢复 == v2 原始波形（24/24）
    max_rel = 0.0
    for ci in range(N_CLASSES):
        wf = generate_waveform_v2(ci)
        burst = build_public_protocol_burst_v2(wf)
        rx = V1.C.deinterleave_int16(burst)
        est = V1.estimate_public_reference(rx)
        zi = recover_model_input_v2(rx, est)
        rel = float(np.sqrt(np.mean(np.abs(wf - zi) ** 2)) /
                    np.sqrt(np.mean(np.abs(wf) ** 2)))
        max_rel = max(max_rel, rel)
    check("R1 v2 public-protocol recovery rel RMS < 1e-2 (24/24)", max_rel < 1e-2,
          "max_rel=%.3e" % max_rel)

    # 幅度合同三量：数字域 a≈1、b≈0
    wf = generate_waveform_v2(4)
    rx = V1.C.deinterleave_int16(build_public_protocol_burst_v2(wf))
    est = V1.estimate_public_reference(rx)
    check("v2 digital a ~= 1", abs(est["a"] - 1.0) < 1e-3,
          "a=%.6g" % est["a"].real)
    check("v2 digital b ~= 0", abs(est["b"]) < 1e-3, "|b|=%.2e" % abs(est["b"]))

    # 关键反例：固定 512 旋转（blind-clean1 反例）在 v2 也应被公共协议避免
    zb = recover_model_input_v2(rx, est)
    zr = np.roll(zb, 512)
    check("v2 fixed-512 rotation changes samples (counterexample mechanism)",
          not np.allclose(zb, zr))

    all_ok = all(checks)
    print("RADIOML_V2_CONTRACT_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
