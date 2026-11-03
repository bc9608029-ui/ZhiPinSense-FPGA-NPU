#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix10class24-dualsdr-rxrecovery2 — Phase 1 offline feasibility (replay only, no
production edits).

Reproduces the latest 4ASK failed sample (clean_4ask_a413e2d4.ci16) exactly, then
compares 5 candidate RX-compensation schemes on the payload-domain training block
(first-half 512 fit / second-half 512 validate):

  1. scalar                          (baseline, rxrecovery1 scalar path)
  2. wide-linear  y=a*x+b*conj(x)    (rxrecovery1)
  3. residual linear phase drift     (scalar + per-block phase ramp)
  4. fixed 5-tap complex FIR, ridge  (frequency-selective)
  5. wide-linear + 5-tap FIR joint
"""
import hashlib
import numpy as np

FS = 2560000.0
NPRE = 1024
PT_OFF = 2048
PT_LEN = 1024
ROOT = 1
KTRAIN_AMP = 2048.0
CANONICAL_PT_SHA = "f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca"

BF = 42252
FINE = -10.1649
FT = -0.435547
SRO_PPM = 0.0
RADIUS = 12


def read_cf64(path):
    raw = np.fromfile(path, dtype="<f8")
    return raw[0::2] + 1j * raw[1::2]


def sinc_pi(x):
    x = np.asarray(x, dtype=np.float64)
    out = np.ones_like(x)
    nz = np.abs(x) >= 1e-12
    px = np.pi * x[nz]
    out[nz] = np.sin(px) / px
    return out


def sample_fractional(x, at):
    at = float(at)
    center = int(np.floor(at))
    out = 0.0 + 0.0j
    wsum = 0.0
    for m in range(center - RADIUS + 1, center + RADIUS + 1):
        if m < 0 or m >= len(x):
            continue
        d = at - float(m)
        if abs(d) >= RADIUS:
            continue
        w = sinc_pi(d) * sinc_pi(d / RADIUS)
        out += x[m] * w
        wsum += w
    return out / wsum if abs(wsum) > 1e-12 else out


def ls_gain(obs, basis):
    """a = sum(obs*conj(basis)) / sum(|basis|^2)  (complex least squares)."""
    num = np.sum(obs * np.conj(basis))
    den = np.sum(np.abs(basis) ** 2)
    return num / den if den > 0 else 0.0 + 0.0j


def residual(obs, model):
    num = np.sum(np.abs(obs - model) ** 2)
    den = np.sum(np.abs(model) ** 2)
    return np.sqrt(num / den) if den > 0 else 0.0


def main():
    base = ("/mnt/f/嵌赛/fix10class24_dualsdr_rxrecovery2_work/evidence_run2/"
            "rml24_rxrecovery1_short2_run2_1773373740/failed_rx/500")
    derot = read_cf64(base + "/coarse_corrected_rx_cf64le.bin")
    full_iq = np.fromfile(base + "/expected_full_burst_ci16le.bin", dtype="<i2")

    pt_iq = full_iq[PT_OFF * 2: (PT_OFF + PT_LEN) * 2]
    pt_sha = hashlib.sha256(pt_iq.tobytes()).hexdigest()
    assert pt_sha == CANONICAL_PT_SHA, "payload-training reference not canonical!"
    rk = pt_iq[0::2].astype(np.float64) + 1j * pt_iq[1::2].astype(np.float64)
    print("payload-training reference: canonical (SHA %s)" % pt_sha[:16])

    # ---- de-ramped payload-training block --------------------------------------
    kk = np.arange(PT_LEN)
    ph = 2.0 * np.pi * FINE * (PT_OFF + kk) / FS
    derot_ph = np.exp(-1j * ph)
    x = np.empty(PT_LEN, dtype=np.complex128)
    for i in range(PT_LEN):
        x[i] = sample_fractional(derot, BF + PT_OFF + i + FT)
    xc = x * derot_ph

    # ---- scalar (full-block) reproduction --------------------------------------
    a_pay = ls_gain(xc, rk)
    corr = np.abs(np.vdot(xc, rk)) / np.sqrt(np.vdot(xc, xc).real * np.vdot(rk, rk).real)
    print("\n=== reproduction ===")
    print("payload_gain_mag          = %.9f  (board 0.0309098)" % abs(a_pay))
    print("payload_training_corr     = %.9f  (board 0.993258)" % corr)
    print("payload_training_residual = %.9f  (board 0.116713)" % residual(xc, a_pay * rk))

    half = PT_LEN // 2
    fit = np.arange(0, half)
    val = np.arange(half, PT_LEN)

    def wl_model(idx, a_, b_):
        return a_ * rk[idx] + b_ * np.conj(rk[idx])

    # ---- wide-linear reproduction ----------------------------------------------
    c_sc = ls_gain(xc[:half], rk[:half])
    S0 = np.vdot(rk[:half], rk[:half]).real
    S2 = np.sum(rk[:half] * rk[:half])
    d0 = np.sum(np.conj(rk[:half]) * xc[:half])
    d1 = np.sum(rk[:half] * xc[:half])
    det = S0 * S0 - np.abs(S2) ** 2
    a_wl = (S0 * d0 - np.conj(S2) * d1) / det
    b_wl = (S0 * d1 - S2 * d0) / det
    print("scalar_validation_residual = %.9f  (board 0.124185)"
          % residual(xc[val], c_sc * rk[val]))
    print("wide-linear validation      = %.9f  (board 0.107171)"
          % residual(xc[val], wl_model(val, a_wl, b_wl)))
    print("image_ratio                 = %.9f  (board 0.067623)"
          % (abs(b_wl) / abs(a_wl)))

    # ---- 5-candidate comparison ------------------------------------------------
    print("\n=== 5-candidate comparison (fit 0..512, validate 512..1024) ===")

    def report(name, f_r, v_r, note):
        print("%-26s fit=%.9f  val=%.9f  %s" % (name, f_r, v_r, note))

    # 1. scalar
    c1 = ls_gain(xc[fit], rk[fit])
    report("1 scalar", residual(xc[fit], c1 * rk[fit]),
           residual(xc[val], c1 * rk[val]), "|a|=%.6f" % abs(c1))

    # 2. wide-linear
    S0f = np.vdot(rk[fit], rk[fit]).real
    S2f = np.sum(rk[fit] * rk[fit])
    d0f = np.sum(np.conj(rk[fit]) * xc[fit])
    d1f = np.sum(rk[fit] * xc[fit])
    detf = S0f * S0f - np.abs(S2f) ** 2
    a2 = (S0f * d0f - np.conj(S2f) * d1f) / detf
    b2 = (S0f * d1f - S2f * d0f) / detf
    report("2 wide-linear", residual(xc[fit], wl_model(fit, a2, b2)),
           residual(xc[val], wl_model(val, a2, b2)),
           "|b|/|a|=%.6f" % (abs(b2) / abs(a2)))

    # 3. residual linear phase drift: xc = a*exp(j*2*pi*f_res*k/fs)*rk
    def drift_model(idx, a_, f_):
        return a_ * np.exp(1j * 2.0 * np.pi * f_ * idx / FS) * rk[idx]
    best = (1e9, 0.0)
    for f_ in np.linspace(-200.0, 200.0, 40001):
        basis = rk[fit] * np.exp(1j * 2.0 * np.pi * f_ * fit / FS)
        a_ = ls_gain(xc[fit], basis)
        rr = residual(xc[fit], drift_model(fit, a_, f_))
        if rr < best[0]:
            best = (rr, f_)
    f3 = best[1]
    basis3 = rk[fit] * np.exp(1j * 2.0 * np.pi * f3 * fit / FS)
    a3 = ls_gain(xc[fit], basis3)
    report("3 phase drift", residual(xc[fit], drift_model(fit, a3, f3)),
           residual(xc[val], drift_model(val, a3, f3)),
           "f_res=%.4f Hz" % f3)

    # 4. fixed 5-tap complex FIR (ridge)
    NTAP = 5
    X = np.empty((half, NTAP), dtype=np.complex128)
    Xv = np.empty((half, NTAP), dtype=np.complex128)
    for m in range(NTAP):
        X[:, m] = rk[np.clip(fit - m, 0, PT_LEN - 1)]
        Xv[:, m] = rk[np.clip(val - m, 0, PT_LEN - 1)]
    A4 = X.conj().T @ X
    tr4 = np.trace(A4).real
    for lam_scale in (1e-6, 1e-4, 1e-2):
        lam = lam_scale * tr4 / NTAP
        h = np.linalg.solve(A4 + lam * np.eye(NTAP), X.conj().T @ xc[fit])
        report("4 FIR5 ridge=%.0e*tr/N" % lam_scale,
               residual(xc[fit], X @ h), residual(xc[val], Xv @ h),
               "cond=%.2e" % np.linalg.cond(A4 + lam * np.eye(NTAP)))

    # 5. wide-linear + 5-tap FIR joint
    Xj = np.empty((half, 2 * NTAP), dtype=np.complex128)
    Xjv = np.empty((half, 2 * NTAP), dtype=np.complex128)
    for m in range(NTAP):
        Xj[:, m] = rk[np.clip(fit - m, 0, PT_LEN - 1)]
        Xj[:, NTAP + m] = np.conj(rk[np.clip(fit - m, 0, PT_LEN - 1)])
        Xjv[:, m] = rk[np.clip(val - m, 0, PT_LEN - 1)]
        Xjv[:, NTAP + m] = np.conj(rk[np.clip(val - m, 0, PT_LEN - 1)])
    A5 = Xj.conj().T @ Xj
    tr5 = np.trace(A5).real
    for lam_scale in (1e-6, 1e-4, 1e-2):
        lam = lam_scale * tr5 / (2 * NTAP)
        h = np.linalg.solve(A5 + lam * np.eye(2 * NTAP), Xj.conj().T @ xc[fit])
        report("5 WL+FIR5 ridge=%.0e*tr/N" % lam_scale,
               residual(xc[fit], Xj @ h), residual(xc[val], Xjv @ h),
               "cond=%.2e" % np.linalg.cond(A5 + lam * np.eye(2 * NTAP)))

    # ---- residual structure ----------------------------------------------------
    e = xc - a_pay * rk
    print("\n=== scalar-fit residual structure ===")
    print("corr(e, rk)       = %.6f" % (abs(np.vdot(e, rk)) /
          np.sqrt(np.vdot(e, e).real * np.vdot(rk, rk).real)))
    print("corr(e, conj(rk)) = %.6f" % (abs(np.vdot(e, np.conj(rk))) /
          np.sqrt(np.vdot(e, e).real * np.vdot(rk, rk).real)))
    print("corr(e, rk>>1)    = %.6f" % (abs(np.vdot(e, np.roll(rk, -1))) /
          np.sqrt(np.vdot(e, e).real * np.vdot(rk, rk).real)))
    E = np.fft.fftshift(np.fft.fft(e * np.hanning(PT_LEN), 4096))
    freqs = np.fft.fftshift(np.fft.fftfreq(4096, 1.0 / FS))
    P = np.abs(E) ** 2
    peak_bin = int(np.argmax(P))
    nb = np.abs(freqs) <= 80000
    print("e peak at %.1f Hz; energy inside +/-80 kHz = %.3f"
          % (freqs[peak_bin], P[nb].sum() / P.sum()))


if __name__ == "__main__":
    main()
