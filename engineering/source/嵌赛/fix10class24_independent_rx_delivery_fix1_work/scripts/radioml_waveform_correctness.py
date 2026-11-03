#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_waveform_correctness.py -- fix1 第 3 节：波形正确性核查（只读审计，不改生成器）。

对冻结生成器 radioml_clean_contract.py 的 AM-SSB / AM-DSB 族做**声明 vs 实现**
一致性核查，发现并如实报告三处不一致（历史生成器与结果**保持不变**）：

  F1  Hilbert 伴非 Hilbert：`_hilbert(a)` 返回 `ifft(A*h).real` = 原信号 a 本身
      （解析信号实部 == 原信号），而非 Hilbert 变换 `...imag`。后果：`z = a + 1j*_hilbert(a)`
      == a*(1+1j)，是实信号乘 (1+j)，**不是**解析/单边带信号。
  F2  SSB 实为 DSB：因 F1，AM-SSB 的正/负频能量相等（pos≈neg），是双边带而非
      上边带（USB）；Hilbert 正交性 = 1.0（应 ≈ 0）。
  F3  SC 未抑制载波：AM-SSB-SC 与 AM-SSB-WC 都有强 DC 载波（|mean|≫0，载波/边带
      ≈18/21 dB），二者只差调制指数 m（WC=0.06/SC=0.09）；AM-DSB-SC 同理只差 m
      （WC=0.10/SC=0.15），±6250 Hz 载波 cos 项都保留。与「SC=suppressed carrier」
      命名不一致，也与 docstring「AM-SSB near zero mean |mean|~0.08」矛盾。

需要修正时应**新增版本**（如真正的抑制载波 SSB/DSB），重新生成输入与数字基线，
不悄悄替换历史资产。本模块只审计 + 落盘证据，不修改 radioml_clean_contract.py。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as GEN  # noqa: E402  (frozen, 只读)

TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-WAVEFORM-CORRECTNESS"
SEED_BASE = 3000000
FS = GEN.SAMPLE_RATE_HZ
N = GEN.SAMPLE_LENGTH


def true_hilbert(a: np.ndarray) -> np.ndarray:
    """正确的离散 Hilbert 变换（解析信号虚部）。用于对照审计，不改生成器。"""
    A = np.fft.fft(a)
    n = len(a)
    h = np.zeros_like(A)
    h[0] = 1.0
    if n % 2 == 0:
        h[1:n // 2] = 2.0
        h[n // 2] = 1.0
    else:
        h[1:(n + 1) // 2] = 2.0
    return np.fft.ifft(A * h).imag


def hilbert_orthogonality(a: np.ndarray, h: np.ndarray) -> float:
    """归一化内积 <a,h>/(||a||·||h||)（应 ≈ 0 若 h 是真 Hilbert 伴；==1 若 h==a）。"""
    na = float(np.linalg.norm(a))
    nh = float(np.linalg.norm(h))
    if na == 0.0 or nh == 0.0:
        return float("nan")
    return float(np.vdot(a, h).real) / (na * nh)


def ssb_sideband_energy(x: np.ndarray):
    """正/负频带能量与 DC 载波能量。"""
    X = np.fft.fft(x)
    n = len(x)
    dc = float(np.abs(X[0]) ** 2)
    pos = float(np.sum(np.abs(X[1:n // 2]) ** 2))
    neg = float(np.sum(np.abs(X[n // 2 + 1:]) ** 2))
    return dc, pos, neg


def measure_am_ssb(name: str, seed: int) -> dict:
    x = GEN.generate_class(name, seed)
    rng = GEN._rng(seed)
    a = GEN._audio(rng, N, FS)          # 与 _am_ssb 相同的音频源（首个 rng 消费）
    gen_h = GEN._hilbert(a)             # 生成器实际使用的“Hilbert”
    dc, pos, neg = ssb_sideband_energy(x)
    sideband = pos + neg
    ratio = 10.0 * np.log10(dc / sideband) if sideband > 0 else float("inf")
    return {
        "mean_real": float(np.mean(x.real)),
        "mean_imag": float(np.mean(x.imag)),
        "dc_power": dc,
        "pos_energy": pos,
        "neg_energy": neg,
        "sideband_power": sideband,
        "carrier_sideband_db": ratio,
        "hilbert_ortho_gen": hilbert_orthogonality(a, gen_h),
        "hilbert_ortho_true": hilbert_orthogonality(a, true_hilbert(a)),
    }


def measure_am_dsb(name: str, seed: int) -> dict:
    x = GEN.generate_class(name, seed)
    X = np.fft.fft(x)
    n = len(x)
    k = int(round(GEN.ANALOG_CARRIER_HZ * n / FS))
    lo, hi = max(1, k - 1), min(n - 1, k + 1)
    p_plus = float(np.sum(np.abs(X[lo:hi + 1]) ** 2))
    p_minus = float(np.sum(np.abs(X[n - hi:n - lo + 1]) ** 2))
    carrier = p_plus + p_minus
    sideband = float(np.sum(np.abs(X) ** 2)) - carrier
    ratio = 10.0 * np.log10(carrier / sideband) if sideband > 0 else float("inf")
    return {
        "mean_real": float(np.mean(x.real)),
        "mean_imag": float(np.mean(x.imag)),
        "carrier_power": carrier,
        "sideband_power": sideband,
        "carrier_sideband_db": ratio,
    }


def run_report() -> dict:
    ssb = {name: measure_am_ssb(name, SEED_BASE + GEN.LABEL_ORDER_24.index(name))
           for name in ("AM-SSB-WC", "AM-SSB-SC")}
    dsb = {name: measure_am_dsb(name, SEED_BASE + GEN.LABEL_ORDER_24.index(name))
           for name in ("AM-DSB-WC", "AM-DSB-SC")}

    wc, sc = ssb["AM-SSB-WC"], ssb["AM-SSB-SC"]
    dwc, dsc = dsb["AM-DSB-WC"], dsb["AM-DSB-SC"]

    findings = [
        {
            "id": "F1-hilbert-is-identity",
            "declared": "AM-SSB z = a + 1j*Hilbert(a)（解析/单边带伴）",
            "measured": "GEN._hilbert(a) == a（ortho=1.0，真 Hilbert 应 ortho≈0）",
            "verdict": "DEFECT: _hilbert 返回 .real（原信号）非 .imag（Hilbert 变换）",
        },
        {
            "id": "F2-ssb-is-dsb",
            "declared": "SSB（上边带 USB，负频≈0）",
            "measured": "AM-SSB-WC pos=%.3g neg=%.3g（pos≈neg → 双边带）"
                       % (wc["pos_energy"], wc["neg_energy"]),
            "verdict": "DEFECT: 因 F1，AM-SSB 实为双边带，非 USB",
        },
        {
            "id": "F3-sc-not-suppressed",
            "declared": "SC = suppressed carrier（抑制载波）",
            "measured": "SSB-SC 载波/边带 %+.1f dB、DSB-SC %+.1f dB（载波仍强）"
                       % (sc["carrier_sideband_db"], dsc["carrier_sideband_db"]),
            "verdict": "DEFECT: SC 未抑制载波，仅调制指数 m 更大",
        },
    ]
    return {
        "token": TOKEN,
        "am_ssb": ssb,
        "am_dsb": dsb,
        "findings": findings,
        "verdict": ("F1/F2/F3：Hilbert 伴是恒等、SSB 实为 DSB、SC 未抑制载波——"
                    "生成器声明与实现不一致；历史资产保持不变，修正需新增版本。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    rep = run_report()
    for name, m in rep["am_ssb"].items():
        print("%-10s mean_real=%.4f carrier/sideband=%+.2f dB ortho(gen)=%.3f "
              "ortho(true)=%.2e" %
              (name, m["mean_real"], m["carrier_sideband_db"],
               m["hilbert_ortho_gen"], m["hilbert_ortho_true"]))
    for name, m in rep["am_dsb"].items():
        print("%-10s carrier/sideband=%+.2f dB" %
              (name, m["carrier_sideband_db"]))
    for f in rep["findings"]:
        print("[%s] %s" % (f["id"], f["verdict"]))
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, sort_keys=True)
        print("wrote %s" % args.out_json)
    return 0


def self_test() -> int:
    """验证检测逻辑自身正确（用已知合成信号），并确认三处缺陷被稳定复现。"""
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # 检测逻辑自证：真 Hilbert 正交、恒等不正交。
    a = np.random.default_rng(12345).standard_normal(1024)
    check("true Hilbert is orthogonal (metric works)", hilbert_orthogonality(a, true_hilbert(a)) < 1e-6)
    check("identity is NOT orthogonal (metric detects identity)",
          abs(hilbert_orthogonality(a, a) - 1.0) < 1e-12)
    # 生成器的 _hilbert 实为恒等（复现 F1）。
    check("GEN._hilbert(a) == a (F1 reproduced)", np.allclose(GEN._hilbert(a), a))
    # 真解析信号单边带（负频≈0），供 F2 对照。
    z = a + 1j * true_hilbert(a)
    _, pos_t, neg_t = ssb_sideband_energy(z)
    check("true analytic signal is one-sided (neg≈0)", neg_t / (pos_t + neg_t) < 1e-6)
    # 报告稳定复现三处缺陷。
    rep = run_report()
    ids = {f["id"] for f in rep["findings"]}
    check("report finds F1+F2+F3", ids == {"F1-hilbert-is-identity",
                                           "F2-ssb-is-dsb", "F3-sc-not-suppressed"})
    wc, sc = rep["am_ssb"]["AM-SSB-WC"], rep["am_ssb"]["AM-SSB-SC"]
    check("F2 pos≈neg reproduced", abs(wc["pos_energy"] - wc["neg_energy"]) /
          (wc["pos_energy"] + wc["neg_energy"]) < 0.05)
    check("F3 SC carrier strong reproduced", sc["carrier_sideband_db"] > 10.0)

    all_ok = all(checks)
    print("RADIOML_WAVEFORM_CORRECTNESS_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
