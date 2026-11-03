#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_waveform_correct_v2.py -- 波形正确性 v2（修 F1/F2/F3 + 物理定义检验）。
纯离线、只读审计 + 新版本生成；不改历史（v1 冻结 `radioml_clean_contract.py` 逐字不动）。

本模块 = 物理定义（第 1 步）+ 修正后的 AM 族生成（新版本）+ 定义检验（合成/解析信号
先证定义，再落到 24 类）。只覆盖 4 个 AM 类（F1/F2/F3 只影响它们）；其余 20 类
逐字复用冻结生成器，label order / 种子 / RMS 全部不变。

--------------------------------------------------------------------------
一、物理定义与检验判据（第 1 步，先写清定义再生成）
--------------------------------------------------------------------------
Hilbert 变换（离散）：实信号 a[n] 的 Hilbert 变换 H{a} 定义为频域
  H(f) = -j·sign(f)·A(f)（f≠0），H(0)=0。
  实现（FFT 域）：H{a} = ifft(A · h)，h[0]=1、h[1:N/2]=2、h[N/2]=1（N 偶）、
  h[N/2+1:]=0，取 **.imag**（虚部）。解析信号 z = a + j·H{a} 频域
  Z(f) = A(f)·(1+sign(f))：f<0 处为 0（单边带）。F1 缺陷 = 取 `.real`（恒等）而非 `.imag`。

USB / LSB（单边带）：
  USB（上边带） z = a + j·H{a}   -> 只有正频率（负频能量≈0）
  LSB（下边带） z = a - j·H{a}   -> 只有负频率（正频能量≈0）
  RadioML 冻结生成器注释声明 AM-SSB 为 USB（"analytic audio -> USB sideband"），
  v2 沿用 USB 定义。

DSB（双边带）：实载波 cos(2π fc t) 被实消息 m(t) 调制 -> 频谱在 ±fc 对称（正/负边带
  能量相等）。带载波 WC：x=(1+m·m(t))·cos(2π fc t)；抑制载波 SC：x=m·m(t)·cos(2π fc t)。

SC（抑制载波）：载波项移除。
  SSB-SC：DC（0 Hz）载波移除 -> x = m·z·e^{jπ/4}（无 DC，|mean|≈0）
  DSB-SC：±fc 载波移除   -> x = m·s(t)·cos(2π fc t)·e^{jπ/4}
  WC 与 SC 的区别必须是**载波存在性**，不是调制指数（v1 F3 缺陷：两者都保留载波，仅 m 不同）。

检验判据（频谱/正交性）：
  C1 Hilbert 正交性：  <a, H{a}> / (||a||·||H{a}||) ≈ 0（<1e-6）
  C2 SSB 单边性：      z=a+j·H{a} 负频能量占比 ≈ 0（USB）；z=a-j·H{a} 正频占比 ≈ 0（LSB）
  C3 DSB 对称性：      正/负边带能量 |pos-neg|/(pos+neg) ≈ 0（<1e-3）
  C4 SC 载波抑制：     SSB-SC DC/边带 < -30 dB；DSB-SC ±fc 载波/边带 < -30 dB
  C5 WC 载波存在：     SSB-WC DC/边带 > +10 dB；DSB-WC ±fc 载波/边带 > +10 dB
--------------------------------------------------------------------------
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

TOKEN = "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2"

SEED_BASE = 3000000
FS = GEN.SAMPLE_RATE_HZ
N = GEN.SAMPLE_LENGTH
FC = GEN.ANALOG_CARRIER_HZ

# AM 类（F1/F2/F3 影响范围），其余类走冻结生成器。
AM_CLASSES = ("AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC")

# ---------------------------------------------------------------------------
# 定义实现
# ---------------------------------------------------------------------------
def true_hilbert(a: np.ndarray) -> np.ndarray:
    """正确的离散 Hilbert 变换（解析信号虚部），与 true_hilbert 判据 C1 一致。"""
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


def analytic_usb(a: np.ndarray) -> np.ndarray:
    """上边带解析信号 z = a + j·H{a}（负频≈0）。"""
    return a + 1j * true_hilbert(a)


def analytic_lsb(a: np.ndarray) -> np.ndarray:
    """下边带解析信号 z = a - j·H{a}（正频≈0）。"""
    return a - 1j * true_hilbert(a)


# ---------------------------------------------------------------------------
# v2 修正后的 AM 生成（新版本，不改 GEN）
# ---------------------------------------------------------------------------
def _am_ssb_v2(rng: np.random.Generator, carrier: bool) -> np.ndarray:
    """AM-SSB v2：真解析 USB + SC 真抑制 DC 载波（F1+F2+F3 修复）。

    与冻结 _am_ssb 逐字同 rng 消费（先 _audio），只改 Hilbert（.imag）与 SC 载波。
    """
    a = GEN._audio(rng, N, FS)                       # 与冻结逐字同 rng 消费
    z = analytic_usb(a)                              # F1+F2：真解析 -> USB
    m = 0.06 if carrier else 0.09
    if carrier:
        x = (1.0 + m * z) * np.exp(1j * GEN.CLEAN_PHASE)   # WC：DC 载波 + USB
    else:
        x = (m * z) * np.exp(1j * GEN.CLEAN_PHASE)         # SC：抑制 DC 载波
    return GEN._scale_rms(x, GEN.TARGET_RMS["AM-SSB-WC" if carrier else "AM-SSB-SC"])


def _am_dsb_v2(rng: np.random.Generator, carrier: bool) -> np.ndarray:
    """AM-DSB v2：SC 真抑制 ±fc 载波（F3 修复，同时覆盖 DSB-SC）。

    与冻结 _am_dsb 逐字同 rng 消费（先 _sawtooth），只改 SC 载波项移除。
    """
    s = GEN._sawtooth(rng)                           # 与冻结逐字同 rng 消费
    tt = np.arange(N) / FS
    m = 0.10 if carrier else 0.15
    cosc = np.cos(2 * np.pi * FC * tt)
    if carrier:
        x = (1.0 + m * s) * cosc * np.exp(1j * GEN.CLEAN_PHASE)   # WC：±fc 载波 + 边带
    else:
        x = (m * s) * cosc * np.exp(1j * GEN.CLEAN_PHASE)         # SC：抑制 ±fc 载波
    return GEN._scale_rms(x, GEN.TARGET_RMS["AM-DSB-WC" if carrier else "AM-DSB-SC"])


def generate_class_v2(name: str, seed: int) -> np.ndarray:
    """v2 生成器：4 个 AM 类走修正实现，其余 20 类逐字复用冻结生成器。"""
    if name not in GEN.LABEL_ORDER_24:
        raise ValueError(f"unknown class {name!r}")
    if name == "AM-SSB-WC":
        return _am_ssb_v2(GEN._rng(seed), carrier=True)
    if name == "AM-SSB-SC":
        return _am_ssb_v2(GEN._rng(seed), carrier=False)
    if name == "AM-DSB-WC":
        return _am_dsb_v2(GEN._rng(seed), carrier=True)
    if name == "AM-DSB-SC":
        return _am_dsb_v2(GEN._rng(seed), carrier=False)
    return GEN.generate_class(name, seed)


# ---------------------------------------------------------------------------
# 检验（第 1 步：合成/解析信号验证定义 + 24 类落地）
# ---------------------------------------------------------------------------
def hilbert_orthogonality(a: np.ndarray, h: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nh = float(np.linalg.norm(h))
    if na == 0.0 or nh == 0.0:
        return float("nan")
    return float(np.vdot(a, h).real) / (na * nh)


def ssb_sideband_energy(x: np.ndarray):
    X = np.fft.fft(x)
    n = len(x)
    dc = float(np.abs(X[0]) ** 2)
    pos = float(np.sum(np.abs(X[1:n // 2]) ** 2))
    neg = float(np.sum(np.abs(X[n // 2 + 1:]) ** 2))
    return dc, pos, neg


def dsb_carrier_sideband(x: np.ndarray, fc_hz: float):
    # fc 精确落在整数 bin（6250 = Fs/32，N=1024 -> bin 32），载波无谱泄漏，
    # 只测 ±fc 精确 bin（k 与 n-k）；±1 bin 是锯形消息基频边带（Fs/N≈195Hz），不算载波。
    X = np.fft.fft(x)
    n = len(x)
    k = int(round(fc_hz * n / FS))
    carrier = float(np.abs(X[k]) ** 2) + float(np.abs(X[n - k]) ** 2)
    sideband = float(np.sum(np.abs(X) ** 2)) - carrier
    return carrier, sideband


def measure(name: str, seed: int) -> dict:
    x = generate_class_v2(name, seed)
    if name.startswith("AM-SSB"):
        dc, pos, neg = ssb_sideband_energy(x)
        sideband = pos + neg
        carrier_db = 10.0 * np.log10(dc / sideband) if sideband > 0 else float("inf")
        neg_frac = neg / (pos + neg) if (pos + neg) > 0 else float("nan")
        # Hilbert 正交性：用独立音频（与生成同 rng 消费）核对 H{a}
        rng = GEN._rng(seed)
        a = GEN._audio(rng, N, FS)
        return {
            "class": name, "seed": seed,
            "dc_power": dc, "pos_energy": pos, "neg_energy": neg,
            "neg_frac": neg_frac,
            "carrier_sideband_db": carrier_db,
            "mean_real": float(np.mean(x.real)),
            "hilbert_ortho_true": hilbert_orthogonality(a, true_hilbert(a)),
            "hilbert_ortho_identity": hilbert_orthogonality(a, a),
        }
    # AM-DSB
    carrier, sideband = dsb_carrier_sideband(x, FC)
    carrier_db = 10.0 * np.log10(carrier / sideband) if sideband > 0 else float("inf")
    _, pos, neg = ssb_sideband_energy(x)
    sym = abs(pos - neg) / (pos + neg) if (pos + neg) > 0 else float("nan")
    return {
        "class": name, "seed": seed,
        "carrier_power": carrier, "sideband_power": sideband,
        "carrier_sideband_db": carrier_db,
        "dsb_symmetry": sym,
        "mean_real": float(np.mean(x.real)),
    }


def run_report() -> dict:
    ssb = {name: measure(name, SEED_BASE + GEN.LABEL_ORDER_24.index(name))
           for name in ("AM-SSB-WC", "AM-SSB-SC")}
    dsb = {name: measure(name, SEED_BASE + GEN.LABEL_ORDER_24.index(name))
           for name in ("AM-DSB-WC", "AM-DSB-SC")}
    wc, sc = ssb["AM-SSB-WC"], ssb["AM-SSB-SC"]
    dwc, dsc = dsb["AM-DSB-WC"], dsb["AM-DSB-SC"]

    checks = [
        {"id": "C1-hilbert-orthogonal", "criterion": "<a,H{a}>≈0 (<1e-6)",
         "measured": "ortho(true)=%.2e (identity=%.2f)" %
                     (wc["hilbert_ortho_true"], wc["hilbert_ortho_identity"]),
         "verdict": "PASS" if abs(wc["hilbert_ortho_true"]) < 1e-6 else "FAIL"},
        {"id": "C2-ssb-one-sided-usb", "criterion": "SSB-SC 负频占比 ≈0 (USB)",
         "measured": "SSB-SC neg_frac=%.3e  SSB-WC neg_frac=%.3e" %
                     (sc["neg_frac"], wc["neg_frac"]),
         "verdict": "PASS" if sc["neg_frac"] < 1e-3 and wc["neg_frac"] < 1e-3 else "FAIL"},
        {"id": "C3-dsb-symmetric", "criterion": "DSB-SC 正/负边带 |pos-neg|/(pos+neg)≈0",
         "measured": "DSB-SC sym=%.3e  DSB-WC sym=%.3e" %
                     (dsc["dsb_symmetry"], dwc["dsb_symmetry"]),
         "verdict": "PASS" if dsc["dsb_symmetry"] < 1e-3 else "FAIL"},
        {"id": "C4-sc-carrier-suppressed", "criterion": "SSB-SC/DSB-SC 载波/边带 < -30 dB",
         "measured": "SSB-SC %+.1f dB  DSB-SC %+.1f dB" %
                     (sc["carrier_sideband_db"], dsc["carrier_sideband_db"]),
         "verdict": "PASS" if (sc["carrier_sideband_db"] < -30.0 and
                              dsc["carrier_sideband_db"] < -30.0) else "FAIL"},
        {"id": "C5-wc-carrier-present", "criterion": "SSB-WC/DSB-WC 载波/边带 > +10 dB",
         "measured": "SSB-WC %+.1f dB  DSB-WC %+.1f dB" %
                     (wc["carrier_sideband_db"], dwc["carrier_sideband_db"]),
         "verdict": "PASS" if (wc["carrier_sideband_db"] > 10.0 and
                              dwc["carrier_sideband_db"] > 10.0) else "FAIL"},
    ]
    return {
        "token": TOKEN,
        "am_ssb": ssb, "am_dsb": dsb, "checks": checks,
        "verdict": ("v2 修复 F1(.imag)/F2(真USB)/F3(SC 真抑制载波) 并覆盖 DSB-SC；"
                    "仅 AM 4 类变更，其余 20 类逐字复用冻结生成器；v1 历史不动。"),
    }


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    rep = run_report()
    for c in rep["checks"]:
        print("[%s] %-30s %s  (%s)" % (c["id"], c["criterion"], c["verdict"],
                                       c["measured"]))
    print("V2_WAVEFORM_VERDICT " + rep["verdict"])
    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, sort_keys=True)
        print("wrote %s" % args.out_json)
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # 第 1 步：合成信号先验证定义（不依赖 AM 生成）。
    a = np.random.default_rng(12345).standard_normal(1024)
    check("C1 true Hilbert orthogonal", hilbert_orthogonality(a, true_hilbert(a)) < 1e-6)
    check("C1 identity NOT orthogonal (detects F1)",
          abs(hilbert_orthogonality(a, a) - 1.0) < 1e-12)
    zusb = analytic_usb(a)
    zlsb = analytic_lsb(a)
    _, _, neg_u = ssb_sideband_energy(zusb)
    _, pos_l, _ = ssb_sideband_energy(zlsb)
    pu = float(np.sum(np.abs(np.fft.fft(zusb)) ** 2))
    pl = float(np.sum(np.abs(np.fft.fft(zlsb)) ** 2))
    check("C2 USB one-sided (neg≈0)", neg_u / pu < 1e-6)
    check("C2 LSB one-sided (pos≈0)", pos_l / pl < 1e-6)

    # 24 类落地（4 AM 类修正，其余 20 类逐字复用冻结）。
    for ci, name in enumerate(GEN.LABEL_ORDER_24):
        x = generate_class_v2(name, SEED_BASE + ci)
        check("v2 %-12s 1024 samples finite" % name,
              x.size == N and np.all(np.isfinite(x)))
    # 非 AM 类逐字一致（GMSK/OQPSK 红线 + 任意数字类）。
    for name in ("GMSK", "OQPSK", "BPSK", "64QAM"):
        ci = GEN.LABEL_ORDER_24.index(name)
        check("v2 %-12s byte-identical to frozen" % name,
              np.array_equal(generate_class_v2(name, SEED_BASE + ci),
                             GEN.generate_class(name, SEED_BASE + ci)))

    # 24 类落地判据。
    rep = run_report()
    for c in rep["checks"]:
        check(c["id"] + " " + c["criterion"], c["verdict"] == "PASS", c["measured"])

    all_ok = all(checks)
    print("RADIOML_WAVEFORM_CORRECT_V2_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
