#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Characterize the wide-linear residual of the 4ASK failed sample (diagnostic only,
not a candidate). Determines the nature of the remaining ~0.107 residual so the
Phase-1 NO-GO report states WHY the 5 fixed candidates cannot cross 0.100."""
import hashlib
import numpy as np

FS = 2560000.0
NPRE = 1024
PT_OFF = 2048
PT_LEN = 1024
CANONICAL_PT_SHA = "f06e9b3de0f51594d8db0501a03918350072d4bc0e5a56f955053bafa35663ca"
BF = 42252
FINE = -10.1649
FT = -0.435547
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
    num = np.sum(obs * np.conj(basis))
    den = np.sum(np.abs(basis) ** 2)
    return num / den if den > 0 else 0.0 + 0.0j


def resid(obs, model):
    num = np.sum(np.abs(obs - model) ** 2)
    den = np.sum(np.abs(model) ** 2)
    return np.sqrt(num / den) if den > 0 else 0.0


def corr_abs(a, b):
    d = np.sqrt(np.vdot(a, a).real * np.vdot(b, b).real)
    return abs(np.vdot(a, b)) / d if d > 0 else 0.0


def main():
    base = ("/mnt/f/嵌赛/fix10class24_dualsdr_rxrecovery2_work/evidence_run2/"
            "rml24_rxrecovery1_short2_run2_1773373740/failed_rx/500")
    derot = read_cf64(base + "/coarse_corrected_rx_cf64le.bin")
    full_iq = np.fromfile(base + "/expected_full_burst_ci16le.bin", dtype="<i2")
    pt_iq = full_iq[PT_OFF * 2:(PT_OFF + PT_LEN) * 2]
    assert hashlib.sha256(pt_iq.tobytes()).hexdigest() == CANONICAL_PT_SHA
    rk = pt_iq[0::2].astype(np.float64) + 1j * pt_iq[1::2].astype(np.float64)

    kk = np.arange(PT_LEN)
    ph = 2.0 * np.pi * FINE * (PT_OFF + kk) / FS
    derot_ph = np.exp(-1j * ph)
    x = np.empty(PT_LEN, dtype=np.complex128)
    for i in range(PT_LEN):
        x[i] = sample_fractional(derot, BF + PT_OFF + i + FT)
    xc = x * derot_ph

    # full-block wide-linear fit
    S0 = np.vdot(rk, rk).real
    S2 = np.sum(rk * rk)
    d0 = np.sum(np.conj(rk) * xc)
    d1 = np.sum(rk * xc)
    det = S0 * S0 - np.abs(S2) ** 2
    a = (S0 * d0 - np.conj(S2) * d1) / det
    b = (S0 * d1 - S2 * d0) / det
    e = xc - (a * rk + b * np.conj(rk))

    print("wide-linear full-block residual = %.9f" % resid(xc, a * rk + b * np.conj(rk)))
    print("image_ratio |b|/|a| = %.6f" % (abs(b) / abs(a)))

    print("\n=== correlation of WL residual with candidate explanatory terms ===")
    terms = {
        "rk": rk,
        "conj(rk)": np.conj(rk),
        "rk>>1": np.roll(rk, -1),
        "rk>>2": np.roll(rk, -2),
        "rk^2": rk * rk,
        "conj(rk)^2": np.conj(rk) * np.conj(rk),
        "|rk|^2*rk": np.abs(rk) ** 2 * rk,
        "|rk|^2*conj(rk)": np.abs(rk) ** 2 * np.conj(rk),
        "rk * phase(k)": rk * (kk - PT_LEN / 2) * 1j,
    }
    for name, t in terms.items():
        print("  corr(e, %-16s) = %.6f" % (name, corr_abs(e, t)))

    # spectrum
    E = np.fft.fftshift(np.fft.fft(e * np.hanning(PT_LEN), 4096))
    freqs = np.fft.fftshift(np.fft.fftfreq(4096, 1.0 / FS))
    P = np.abs(E) ** 2
    nb = np.abs(freqs) <= 80000
    print("\nWL residual: energy inside +/-80 kHz = %.3f, peak at %.1f Hz"
          % (P[nb].sum() / P.sum(), freqs[int(np.argmax(P))]))

    # time profile: residual magnitude in 4 quarters
    for q in range(4):
        seg = e[q * 256:(q + 1) * 256]
        print("  quarter %d |e| rms = %.6f (vs block %.6f)"
              % (q, np.sqrt(np.mean(np.abs(seg) ** 2)), np.sqrt(np.mean(np.abs(e) ** 2))))

    # diagnostic (NOT candidates): wider FIR / quadratic, to identify the residual nature
    half = PT_LEN // 2
    fit = np.arange(0, half)
    val = np.arange(half, PT_LEN)
    def fir_design(idx, ntap, wide):
        cols = []
        for m in range(ntap):
            s = np.clip(idx - m, 0, PT_LEN - 1)
            cols.append(rk[s])
            if wide:
                cols.append(np.conj(rk[s]))
        return np.column_stack(cols)

    def ridge_solve(Xd, y, lam_scale):
        A = Xd.conj().T @ Xd
        tr = np.trace(A).real
        lam = lam_scale * tr / Xd.shape[1]
        return np.linalg.solve(A + lam * np.eye(Xd.shape[1]), Xd.conj().T @ y)

    print("\n=== diagnostic wider models (to identify residual nature, NOT candidates) ===")
    for ntap in (5, 9, 17):
        for wide in (False, True):
            Xf = fir_design(fit, ntap, wide)
            Xv = fir_design(val, ntap, wide)
            h = ridge_solve(Xf, xc[fit], 1e-4)
            print("  FIR%d%s: fit=%.6f val=%.6f" %
                  (ntap, "+WL" if wide else "", resid(xc[fit], Xf @ h), resid(xc[val], Xv @ h)))

    # quadratic (nonlinear) diagnostic
    Bq = np.column_stack([rk[fit], np.conj(rk[fit]), rk[fit] ** 2, np.abs(rk[fit]) ** 2 * rk[fit]])
    Bqv = np.column_stack([rk[val], np.conj(rk[val]), rk[val] ** 2, np.abs(rk[val]) ** 2 * rk[val]])
    hq = ridge_solve(Bq, xc[fit], 1e-4)
    print("  WL+quadratic(nonlin): fit=%.6f val=%.6f" %
          (resid(xc[fit], Bq @ hq), resid(xc[val], Bqv @ hq)))


if __name__ == "__main__":
    main()
