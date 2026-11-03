#!/usr/bin/env python3
"""analyze_route_d2_4ask.py -- fix7 Task C: Route D2 non-training 4ASK ablation.

Locates and (if possible) fixes the 4ASK Route D reconstruction failure WITHOUT
retraining the model, by ablating the route-D amplitude-mapping step.  Route D
(board_package/synthetic_iq_roundtrip.hpp) reconstructs a frozen RadioML tensor
as:

    [2,1024] fp32 @128k
      -> combine to complex  -> deterministic x20 polyphase BH4 interpolation
         (2.56 MSPS) -> amplitude mapping -> int16 "raw RX"
      -> REAL production PreprocessChain ( /2048 -> NCO off -> decimate x20 ->
         x rec_scale ) -> recovered [2,1024]

The only degree of freedom this task is allowed to touch is the amplitude-mapping
step.  The hypothesis is that 4ASK (a DC-heavy, 4-level amplitude signal) is
destroyed by the baseline mapping -- a per-file RMS normalise to 16 int16 counts,
which quantises the whole signal to a 1/16 model-domain step and lets the large DC
component crowd out the 4 amplitude levels.

The four ablations:

  D0  baseline:      scale_i = 16 / signal_rms_i   (per-file RMS normalise),
                     rec_scale = 2048/16 = 128.   (exactly current route D)
  D1  single global K:  scale = K (ONE constant for every file), rec_scale = 2048/K.
                     Preserves per-file amplitude differences; uses a finer
                     quantisation step 1/K.
  D2  D1 + preserve DC:  subtract each file's DC (complex mean), scale the AC
                     residual by K, re-add the DC, THEN quantise.  The DC never
                     consumes int16 range and is never clipped.
  D3  resample/quant/window sweep:  grid over rms_target (K), edge_policy
                     (zero|reflect) and guard, to attribute any residual error to
                     the resampler FIR / guard / quantisation rather than the
                     amplitude mapping.

The global K (D1/D2) is chosen ONLY from unlabelled measurements on a fixed
calibration subset -- never from a class label and never from the holdout:
  * reconstruction error  (centre NMSE of recovered vs original, delay+gain aligned)
  * quantisation utilisation (int16 RMS / 2048 full scale)
  * clip rate             (fraction of int16 samples clamped)
The chosen K is the largest candidate whose calibration clip rate is ~0 and whose
reconstruction error does not degrade; it is then held FIXED for the independent
holdout, so the holdout result is not a per-file oracle fit.

This script NEVER retrains the model, NEVER runs the NPU, and NEVER issues an
accuracy PASS.  It produces reconstruction-level D0/D1/D2/D3 evidence and a
measurement-only verdict.

fix8 Task E ("truly implement" the non-training 4ASK Route D2) sharpens the
verdict and the sampling: the SAME original RadioML frozen samples as Route A are
used (240 calibration / 240 holdout per class by default), the global K is still
chosen ONLY from unlabelled reconstruction error / quantisation utilisation / clip
rate on the fixed calibration subset and held FIXED on the independent holdout
(never a per-file oracle, never a label search), and the verdict is now

  ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN
      only if the 4ASK holdout clearly recovers (D2 NMSE < D0 NMSE by >=10%, D2
      correlation not lower, D2 clip == 0) AND every OTHER class does not regress
      (D2 NMSE <= D0 NMSE +10%, D2 correlation not lower, D2 clip == 0);
  NON_RETRAINING_4ASK_FIX_NOT_PROVEN
      otherwise.

Classification-level recovery of 4ASK is still confirmed only by a board Route F
D-vs-D2 A/B run; this script's verdict is reconstruction-level and measurement-only.

Inputs:
  --bin-dir DIR      extract_radioml_stage_g.py output dir (input_*.bin + manifest)
  --manifest PATH    default <bin-dir>/manifest_a.tsv
  --classes LIST     comma classes to report per-class (default 4ASK)
  --calib-count N    calibration frames per class for the unlabelled K search
                     (default 240)
  --holdout-count N  independent holdout frames per class (default 240; "240/240")
  --k-candidates     comma int16 RMS target candidates to search (default a dB grid)
  --edge-policy      zero|reflect for D3
  --d2-out-dir DIR   (optional) write the D2 recovered [2,1024] tensors + a
                     d2_recovered_manifest.tsv here (for the Route F A/B board run)
  --json PATH        write full machine-readable JSON here
  --self-test        run the built-in synthetic self-tests and exit
  --synthetic        generate synthetic ASK/tone frames instead of reading .bin

Pure stdlib + numpy.  Run isolated:  python -I analyze_route_d2_4ask.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np

N_SAMPLES = 1024
KADC = 2048.0                 # AD9364 12-bit full scale, post iio convert
INTERP_FACTOR = 20
INTERP_TAPS = 32
INTERP_TOTAL = INTERP_FACTOR * INTERP_TAPS  # 640
INTERP_CUTOFF_HZ = 64000.0
DECIM_DOWN = 20
DECIM_TAPS = 601
EDGE_MARGIN = 32              # valid centre == [32, 1024-32)
DEFAULT_GUARD = 832
DEFAULT_RMS_TARGET = 16.0     # route D baseline (== route C default)

SOURCE_CLASS_INDEX = {
    "OOK": 0, "4ASK": 1, "8ASK": 2, "BPSK": 3, "QPSK": 4, "8PSK": 5,
    "16PSK": 6, "32PSK": 7, "16APSK": 8, "32APSK": 9, "64APSK": 10,
    "128APSK": 11, "16QAM": 12, "32QAM": 13, "64QAM": 14, "128QAM": 15,
    "256QAM": 16, "AM-SSB-WC": 17, "AM-SSB-SC": 18, "AM-DSB-WC": 19,
    "AM-DSB-SC": 20, "FM": 21, "GMSK": 22, "OQPSK": 23,
}
INDEX_TO_CLASS = {v: k for k, v in SOURCE_CLASS_INDEX.items()}


# ---------------------------------------------------------------------------
# FIR replication (bit-for-bit with the C++ chain, in double precision).
# ---------------------------------------------------------------------------
def interpolation_fir() -> np.ndarray:
    """synthetic_iq_roundtrip.hpp::interpolation_fir() -- Blackman-Harris-4
    windowed sinc, N=640, sum(h)==20 (each polyphase branch DC gain ~1.0)."""
    n = np.arange(INTERP_TOTAL, dtype=np.float64)
    centre = (INTERP_TOTAL - 1) / 2.0
    x = (n - centre) / INTERP_FACTOR
    # sinc_rt(x) = sin(pi*x)/(pi*x) == numpy's sinc definition.
    h = INTERP_FACTOR * np.sinc(x / np.pi) * blackman_harris4(n, INTERP_TOTAL)
    h *= INTERP_FACTOR / h.sum()
    return h


def blackman_harris4(n: np.ndarray, N: int) -> np.ndarray:
    a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
    t = 2.0 * np.pi * n / (N - 1)
    return a0 - a1 * np.cos(t) + a2 * np.cos(2.0 * t) - a3 * np.cos(3.0 * t)


def parse_decimation_fir(fir_header: str | None = None) -> np.ndarray:
    """Parse kFir_2p56M (601 taps) out of sdr_adapter/fir_coeffs.h."""
    if fir_header is None:
        fir_header = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "sdr_adapter", "fir_coeffs.h")
    fir_header = os.path.abspath(fir_header)
    with open(fir_header, "r", encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"kFir_2p56M\[\]\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        raise RuntimeError("kFir_2p56M not found in %s" % fir_header)
    vals = [float(x) for x in re.findall(r"[0-9.eE+-]+", m.group(1))]
    h = np.asarray(vals, dtype=np.float64)
    if h.size != DECIM_TAPS:
        raise RuntimeError("kFir_2p56M has %d taps, expected %d" % (h.size, DECIM_TAPS))
    return h


def apply_guard(x: np.ndarray, guard: int, policy: str) -> np.ndarray:
    if policy == "zero":
        return np.concatenate([np.zeros(guard, np.complex128),
                               x, np.zeros(guard, np.complex128)])
    if policy == "reflect":
        if guard > x.size - 1:
            raise ValueError("reflect guard %d exceeds %d usable samples"
                             % (guard, x.size - 1))
        n = x.size
        left = x[1:guard + 1][::-1].copy()
        right = x[n - 1 - guard:n - 1][::-1].copy()
        return np.concatenate([left, x, right])
    raise ValueError("bad edge policy %r" % policy)


def interpolate_20x(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """synthetic_iq_roundtrip.hpp::interpolate_20x -- polyphase FIR, zero-pad."""
    p = h.size // INTERP_FACTOR
    if p * INTERP_FACTOR != h.size:
        raise ValueError("interp FIR length not a multiple of 20")
    out = np.empty(x.size * INTERP_FACTOR, np.complex128)
    for r in range(INTERP_FACTOR):
        out[r::INTERP_FACTOR] = np.convolve(
            x, h[r::INTERP_FACTOR], mode="full")[:x.size]
    return out


def decimate_20(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """StreamResampler (up=1, down=20) outputs y[m]=sum_k h[k] x[20m-k], for the
    m whose newest input index 20m is available (C++ can_produce).  Includes the
    startup transient; the caller discards the first (N-1)=600."""
    conv = np.convolve(x, h, mode="full")  # conv[n] = sum_k h[k] x[n-k]
    max_m = (x.size - 1) // DECIM_DOWN
    idx = np.arange(max_m + 1, dtype=np.int64) * DECIM_DOWN
    return conv[idx]


def quantize_int16(x: np.ndarray, scale: float) -> tuple[np.ndarray, int]:
    """Mirror quantize_int16_signal_rms rounding/clamp (std::lround, +-32767/32768).
    Returns interleaved int16 (I,Q) and the number of clipped samples."""
    ri = x.real * scale
    qi = x.imag * scale
    clipped = int((np.abs(ri) > 32767.0).sum() + (np.abs(qi) > 32767.0).sum())
    ri = np.clip(np.rint(ri), -32768.0, 32767.0).astype(np.int16)
    qi = np.clip(np.rint(qi), -32768.0, 32767.0).astype(np.int16)
    iq = np.empty(x.size * 2, np.int16)
    iq[0::2] = ri
    iq[1::2] = qi
    return iq, clipped


def calibrate_rec_scale(rms_counts: float, target_rms: float = 1.0) -> float:
    if not (rms_counts > 0.0):
        return 1.0
    return target_rms * KADC / rms_counts


# ---------------------------------------------------------------------------
# Route D / D2 reconstruction (the ONLY variant-dependent part is the mapping).
# ---------------------------------------------------------------------------
def reconstruct(x: np.ndarray, variant: str, K: float,
                edge: str = "zero", guard: int = DEFAULT_GUARD,
                decim_h: np.ndarray | None = None) -> dict:
    """Full route-D chain for ONE 1024-complex original; returns the recovered
    stream (2088 valid samples) plus the quantisation statistics.  The only
    variant-dependent part is the amplitude mapping (see module docstring).

    D2 removes the signal's OWN DC (a signal statistic, never a class label) so
    the AC (the amplitude levels) is quantised at fine resolution; the DC is
    restored exactly at the end and is never allowed to clip or crowd out the
    4ASK amplitude levels.
    """
    if decim_h is None:
        decim_h = _decim_fir()
    signal_rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))

    base = x
    dc = 0.0 + 0j
    ac_rms = signal_rms
    if variant == "D0":
        scale = DEFAULT_RMS_TARGET / signal_rms if signal_rms > 0 else 0.0
        rec_scale = calibrate_rec_scale(DEFAULT_RMS_TARGET)
    elif variant == "D1":
        scale = K
        rec_scale = calibrate_rec_scale(K)
    elif variant == "D2":
        dc = x.mean()
        base = x - dc
        ac_rms = float(np.sqrt(np.mean(np.abs(base) ** 2)))
        scale = K / ac_rms if ac_rms > 0 else 0.0
        # The int16 path now carries ONLY the AC (DC is restored separately), so
        # rec_scale must map the AC's int16 RMS (K) back to the AC's MODEL RMS
        # (ac_rms), not to 1.0:  rec_scale = ac_rms * 2048/K.
        rec_scale = ac_rms * calibrate_rec_scale(K)
    else:
        raise ValueError("bad variant %r" % variant)

    guarded = apply_guard(base, guard, edge)
    interp = interpolate_20x(guarded, _interp_fir())
    iq, clipped = quantize_int16(interp * scale, 1.0)
    cx = (iq[0::2].astype(np.float64) + 1j * iq[1::2].astype(np.float64)) / KADC
    decim = decimate_20(cx, decim_h)          # includes 600-sample transient
    valid = decim[DECIM_TAPS - 1:]            # discard startup transient
    recov = valid * rec_scale
    if variant == "D2":
        recov = recov + dc

    int16_rms = float(np.sqrt(np.mean(iq.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(iq.astype(np.float64))))
    return {
        "recovered": recov,
        "signal_rms": signal_rms,
        "rec_scale": rec_scale,
        "quant_rms_counts": int16_rms,
        "quant_utilization": int16_rms / KADC,
        "clip_count": clipped,
        "clip_rate": clipped / float(iq.size),
        "peak_counts": peak,
        # fix9 Task B: expose the AC-only interleaved int16 (the RF TX ci16) and
        # the per-file D2 restore constants (DC + AC RMS) for the artifact builder.
        "iq": iq,
        "dc_i": float(dc.real),
        "dc_q": float(dc.imag),
        "ac_rms": ac_rms,
    }


_interp_cache: np.ndarray | None = None
_decim_cache: np.ndarray | None = None


def _interp_fir() -> np.ndarray:
    global _interp_cache
    if _interp_cache is None:
        _interp_cache = interpolation_fir()
    return _interp_cache


def _decim_fir(fir_header: str | None = None) -> np.ndarray:
    global _decim_cache
    if _decim_cache is None:
        _decim_cache = parse_decimation_fir(fir_header)
    return _decim_cache


# ---------------------------------------------------------------------------
# Alignment + reconstruction metrics (mirrors compute_roundtrip_metrics).
# ---------------------------------------------------------------------------
def align_and_measure(orig: np.ndarray, recov: np.ndarray) -> dict:
    lo, hi = EDGE_MARGIN, N_SAMPLES - EDGE_MARGIN
    dmax = recov.size - N_SAMPLES
    o = orig[lo:hi]
    best_d, best_err = 0, float("inf")
    for d in range(dmax + 1):
        r = recov[d + lo:d + hi]
        den = float(np.vdot(r, r).real)
        if den <= 1e-30:
            continue
        g = np.vdot(o, r).conjugate() / den
        err = float(np.sum(np.abs(o - g * r) ** 2))
        if err < best_err:
            best_d, best_err = d, err
    d = best_d
    r = recov[d + lo:d + hi]
    den = float(np.vdot(r, r).real)
    g = (np.vdot(o, r).conjugate() / den) if den > 1e-30 else (1.0 + 0j)

    full_r = recov[d:d + N_SAMPLES]
    err_c = float(np.sum(np.abs(o - g * r) ** 2))
    ref_c = float(np.sum(np.abs(o) ** 2))
    nmse_c = err_c / ref_c if ref_c > 0 else 0.0
    cc = np.vdot(o, r)
    az = float(np.vdot(o, o).real)
    ar = float(np.vdot(r, r).real)
    corr = abs(cc) / np.sqrt(az * ar) if az * ar > 0 else 0.0

    dc_o = float(abs(orig.mean()))
    dc_r = float(abs(full_r.mean()))
    return {
        "delay": d, "gain_db": 20.0 * np.log10(abs(g) + 1e-300),
        "nmse_center": nmse_c, "evm_center_pct": 100.0 * np.sqrt(nmse_c),
        "corr_center": float(corr),
        "dc_orig": dc_o, "dc_recov": dc_r,
        "dc_error": abs(dc_o - dc_r),
        "rms_orig": float(np.sqrt(np.mean(np.abs(orig) ** 2))),
        "rms_recov": float(np.sqrt(np.mean(np.abs(full_r) ** 2))),
    }


# ---------------------------------------------------------------------------
# Unlabelled global-K selection (calibration subset only, never labels).
# ---------------------------------------------------------------------------
def choose_global_K(calib: list[np.ndarray], k_candidates: list[float],
                    clip_max: float = 0.0) -> tuple[float, list[dict]]:
    """Pick the global K from the calibration subset only (no labels), by the
    three sanctioned criteria: lowest reconstruction error, highest quantiser
    utilisation, zero clipping.  For D1 those three agree (NMSE and utilisation
    are both monotone in K until clipping), so among clip-free candidates we take
    the lowest mean centre NMSE (== largest K == highest utilisation)."""
    rows = []
    for K in k_candidates:
        nmse = []
        clip = []
        util = []
        for x in calib:
            r = reconstruct(x, "D1", K)
            m = align_and_measure(x, r["recovered"])
            nmse.append(m["nmse_center"])
            clip.append(r["clip_rate"])
            util.append(r["quant_utilization"])
        rows.append({"K": K, "nmse": float(np.mean(nmse)),
                     "clip_rate": float(np.mean(clip)),
                     "utilization": float(np.mean(util))})
    ok = [r for r in rows if r["clip_rate"] <= clip_max]
    if not ok:
        # Every candidate clips: fall back to the lowest-clip (safest) candidate.
        chosen = min(rows, key=lambda r: r["clip_rate"])["K"]
    else:
        # Lowest reconstruction error among clip-free candidates.
        best = min(ok, key=lambda r: r["nmse"])
        chosen = best["K"]
    return chosen, rows


# ---------------------------------------------------------------------------
# fix8 Task E: honest D2 verdict + D2 recovered-tensor artifact generation.
# ---------------------------------------------------------------------------
def compute_verdict(per_class: dict, fourask: str = "4ASK",
                    improve_frac: float = 0.10,
                    regress_frac: float = 0.10) -> tuple[str, list[str]]:
    """Route D2 reconstruction-level verdict (fix8 Task E).

    per_class[c] must hold {"D0": {...}, "D1": {...}, "D2": {...}} summary dicts,
    each with numeric keys "nmse", "corr", "clip" (the D0/D2 ones are read).

    Returns (token, components) where token is
      ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN  iff the 4ASK holdout clearly
        recovers AND every other class does not regress;
      NON_RETRAINING_4ASK_FIX_NOT_PROVEN        otherwise.
    This is reconstruction-level, measurement-only: it never asserts a
    classification accuracy and never uses a label to fit the mapping.
    """
    comps: list[str] = []
    if fourask not in per_class:
        return "NON_RETRAINING_4ASK_FIX_NOT_PROVEN", ["4ASK holdout missing"]
    if any(r.get("D0", {}).get("nmse", 0.0) <= 0.0
           or "D2" not in r for r in per_class.values()):
        return "NON_RETRAINING_4ASK_FIX_NOT_PROVEN", \
            ["a class has no D0/D2 holdout result"]

    a = per_class[fourask]
    d0a, d2a = a["D0"], a["D2"]
    recovers = (d2a["nmse"] < d0a["nmse"] * (1.0 - improve_frac)
                and d2a["corr"] >= d0a["corr"] - 1e-12 and d2a["clip"] == 0.0)
    ok = recovers
    if recovers:
        comps.append("4ASK D2 clearly recovered (D0 nmse=%.3e -> D2 nmse=%.3e)"
                     % (d0a["nmse"], d2a["nmse"]))
    else:
        comps.append("4ASK D2 did not clearly recover (D0 nmse=%.3e D2 nmse=%.3e"
                     " corr=%.6f clip=%.5f)"
                     % (d0a["nmse"], d2a["nmse"], d2a["corr"], d2a["clip"]))

    for c, r in per_class.items():
        if c == fourask:
            continue
        d0c, d2c = r["D0"], r["D2"]
        regressed = (d2c["nmse"] > d0c["nmse"] * (1.0 + regress_frac)
                     or d2c["corr"] < d0c["corr"] - 0.01 or d2c["clip"] != 0.0)
        if regressed:
            ok = False
            comps.append("%s regressed under D2 (D0 nmse=%.3e -> D2 nmse=%.3e"
                         " corr=%.6f clip=%.5f)"
                         % (c, d0c["nmse"], d2c["nmse"], d2c["corr"], d2c["clip"]))
    token = ("ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN" if ok
             else "NON_RETRAINING_4ASK_FIX_NOT_PROVEN")
    return token, comps


def recovered_tensor_1024(orig: np.ndarray, recov: np.ndarray) -> np.ndarray:
    """Extract the 1024-sample recovered tensor from the 2088-sample recovered
    stream, aligned the same way roundtrip_radioml does (best integer delay), as
    a planar [2,1024] fp32 array (== the 8192-byte Route-D tensor layout)."""
    d = align_and_measure(orig, recov)["delay"]
    aligned = recov[d:d + N_SAMPLES]
    out = np.empty(2 * N_SAMPLES, np.float32)
    out[:N_SAMPLES] = aligned.real
    out[N_SAMPLES:] = aligned.imag
    return out


def write_d2_artifacts(out_dir: str, samples: list, K: float,
                       edge: str = "zero", guard: int = DEFAULT_GUARD) -> list[str]:
    """Write the D2 recovered [2,1024] tensors (8192 bytes each) + a
    d2_recovered_manifest.tsv (index / class_index / class_name / recovered_file /
    recovered_sha256), returning the list of written manifest lines.  Never
    changes labels, never fits per-file -- the single global K is already fixed."""
    os.makedirs(out_dir, exist_ok=True)
    decim_h = _decim_fir()
    lines = []
    for i, (x, ci, cname, _sid) in enumerate(samples):
        r = reconstruct(x, "D2", K, edge=edge, guard=guard, decim_h=decim_h)
        t = recovered_tensor_1024(x, r["recovered"])
        fname = "recovered_tensor_d2_%06d.f32" % i
        t.tofile(os.path.join(out_dir, fname))
        sha = hashlib.sha256(t.tobytes()).hexdigest()
        lines.append("%d\t%d\t%s\t%s\t%s" % (i, ci, cname, fname, sha))
    with open(os.path.join(out_dir, "d2_recovered_manifest.tsv"),
              "w", encoding="utf-8") as f:
        f.write("index\tclass_index\tclass_name\trecovered_file\t"
                "recovered_sha256\n")
        for ln in lines:
            f.write(ln + "\n")
    return lines


# ---------------------------------------------------------------------------
# Synthetic signals (self-test + --synthetic demo; no HDF5 needed).
# ---------------------------------------------------------------------------
def synth_4ask(n: int = N_SAMPLES, rng: np.random.Generator | None = None,
               levels=(0.2, 0.45, 0.7, 0.95)) -> np.ndarray:
    """Unipolar 4-level ASK (real-valued, DC-heavy), RMS-normalised to 1.0."""
    if rng is None:
        rng = np.random.default_rng(0)
    sym = np.tile(rng.choice(levels, size=max(1, n // 8)), 8)[:n]
    # light pulse shaping to keep it band-limited and deterministic
    w = np.hanning(9)
    shaped = np.convolve(sym, w / w.sum(), mode="same")
    x = shaped.astype(np.float64) + 0j
    x /= float(np.sqrt(np.mean(np.abs(x) ** 2)))
    return x


def synth_tone(n: int = N_SAMPLES, freq_hz: float = 8000.0,
               fs_hz: float = 128000.0, amp: float = 0.9) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / fs_hz
    x = amp * np.exp(1j * 2.0 * np.pi * freq_hz * t)
    x /= float(np.sqrt(np.mean(np.abs(x) ** 2)))
    return x


# ---------------------------------------------------------------------------
# Self-test.
# ---------------------------------------------------------------------------
def self_test() -> int:
    npass = 0

    hi = interpolation_fir()
    hd = parse_decimation_fir()
    if abs(hi.sum() - INTERP_FACTOR) < 1e-6:
        npass += 1
        print("  OK  interpolation FIR sum == 20")
    else:
        print("  BAD interpolation FIR sum = %.9f" % hi.sum())
    if abs(hd.sum() - 1.0) < 1e-6:
        npass += 1
        print("  OK  decimation FIR DC gain == 1")
    else:
        print("  BAD decimation FIR sum = %.9f" % hd.sum())
    if np.allclose(hd, hd[::-1]):
        npass += 1
        print("  OK  decimation FIR symmetric")
    else:
        print("  BAD decimation FIR not symmetric")

    # D0 roundtrip of a clean tone: low reconstruction error, DC preserved.
    tone = synth_tone()
    r0 = reconstruct(tone, "D0", DEFAULT_RMS_TARGET)
    m0 = align_and_measure(tone, r0["recovered"])
    if m0["nmse_center"] < 1e-3 and m0["corr_center"] > 0.999:
        npass += 1
        print("  OK  D0 tone roundtrip nmse=%.3e corr=%.6f"
              % (m0["nmse_center"], m0["corr_center"]))
    else:
        print("  BAD D0 tone roundtrip nmse=%.3e corr=%.6f"
              % (m0["nmse_center"], m0["corr_center"]))

    # 4ASK: D0 is coarse; D1 with a larger K lowers reconstruction error.
    rng = np.random.default_rng(1)
    ask = synth_4ask(rng=rng)
    r0 = reconstruct(ask, "D0", DEFAULT_RMS_TARGET)
    m0 = align_and_measure(ask, r0["recovered"])
    r1 = reconstruct(ask, "D1", 512.0)
    m1 = align_and_measure(ask, r1["recovered"])
    if m1["nmse_center"] < m0["nmse_center"] and r1["clip_rate"] == 0.0:
        npass += 1
        print("  OK  4ASK finer K lowers NMSE (D0 %.3e -> D1(512) %.3e)"
              % (m0["nmse_center"], m1["nmse_center"]))
    else:
        print("  BAD 4ASK D0 %.3e vs D1(512) %.3e clip=%.4f"
              % (m0["nmse_center"], m1["nmse_center"], r1["clip_rate"]))

    # D2 (D1 + preserve DC) isolates the AC from the DC so the 4 amplitude
    # levels get finer quantisation than D1 at the same K (AC step ac_rms/K vs
    # D1's 1/K) -> lower reconstruction NMSE, while the DC is still carried.
    dc = ask.mean()
    r2 = reconstruct(ask, "D2", 512.0)
    m2 = align_and_measure(ask, r2["recovered"])
    if m2["nmse_center"] < m1["nmse_center"] and m2["dc_error"] < 0.05:
        npass += 1
        print("  OK  D2 finer AC (D1 %.3e -> D2 %.3e, dc_err=%.3e)"
              % (m1["nmse_center"], m2["nmse_center"], m2["dc_error"]))
    else:
        print("  BAD D2 nmse=%.3e (D1 %.3e) dc_err=%.3e"
              % (m2["nmse_center"], m1["nmse_center"], m2["dc_error"]))

    # Global-K selection is label-independent (shuffle order -> same K).
    calib = [synth_4ask(rng=np.random.default_rng(i)) for i in range(6)]
    kcand = [16.0, 32.0, 64.0, 128.0, 256.0, 512.0]
    k1, _ = choose_global_K(calib, kcand)
    k2, _ = choose_global_K(calib[::-1], kcand)
    if k1 == k2 and k1 > DEFAULT_RMS_TARGET:
        npass += 1
        print("  OK  global-K selection label-independent (K=%.0f)" % k1)
    else:
        print("  BAD global-K selection K1=%.0f K2=%.0f" % (k1, k2))

    # ---- fix8 Task E: honest verdict + D2 artifact generation ----------------
    # A D2 reconstruction that clearly recovers 4ASK and leaves others untouched
    # must yield ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN.
    per_class_proven = {
        "4ASK": {"D0": {"nmse": 1e-2, "corr": 0.90, "clip": 0.0},
                 "D1": {"nmse": 0.0, "corr": 0.0, "clip": 0.0},
                 "D2": {"nmse": 1e-4, "corr": 0.999, "clip": 0.0}},
        "BPSK": {"D0": {"nmse": 1e-4, "corr": 0.999, "clip": 0.0},
                 "D1": {"nmse": 0.0, "corr": 0.0, "clip": 0.0},
                 "D2": {"nmse": 1e-4, "corr": 0.999, "clip": 0.0}},
        "QPSK": {"D0": {"nmse": 1e-4, "corr": 0.999, "clip": 0.0},
                 "D1": {"nmse": 0.0, "corr": 0.0, "clip": 0.0},
                 "D2": {"nmse": 1.05e-4, "corr": 0.998, "clip": 0.0}},
        "16QAM": {"D0": {"nmse": 5e-4, "corr": 0.98, "clip": 0.0},
                  "D1": {"nmse": 0.0, "corr": 0.0, "clip": 0.0},
                  "D2": {"nmse": 5.2e-4, "corr": 0.98, "clip": 0.0}},
    }
    tok, comps = compute_verdict(per_class_proven)
    if tok == "ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN":
        npass += 1
        print("  OK  verdict PROVEN when 4ASK recovers and others hold")
    else:
        print("  BAD verdict %r (want PROVEN) comps=%r" % (tok, comps))

    # A D2 that regresses QPSK must NOT be PROVEN even though 4ASK recovered.
    per_class_regressed = json.loads(json.dumps(per_class_proven))
    per_class_regressed["QPSK"]["D2"] = {"nmse": 1e-1, "corr": 0.5, "clip": 0.0}
    tok2, comps2 = compute_verdict(per_class_regressed)
    if tok2 == "NON_RETRAINING_4ASK_FIX_NOT_PROVEN":
        npass += 1
        print("  OK  verdict NOT_PROVEN when another class regresses")
    else:
        print("  BAD verdict %r (want NOT_PROVEN) comps=%r" % (tok2, comps2))

    # D2 artifact generation writes 8192-byte tensors + a SHA-consistent manifest.
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp(prefix="route_d2_art_")
    samples = [(synth_4ask(rng=np.random.default_rng(i)), 1, "4ASK", -1)
               for i in range(3)]
    lines = write_d2_artifacts(tmp, samples, 512.0)
    ok_art = (len(lines) == 3
              and os.path.getsize(os.path.join(tmp, "recovered_tensor_d2_000000.f32"))
              == 2 * N_SAMPLES * 4)
    if ok_art:
        with open(os.path.join(tmp, "d2_recovered_manifest.tsv"), "r",
                  encoding="utf-8") as f:
            manifest = f.read().splitlines()
        hdr = manifest[0].split("\t")
        ok_art = ok_art and hdr == ["index", "class_index", "class_name",
                                    "recovered_file", "recovered_sha256"]
        # manifest sha matches the written file
        rec = manifest[1].split("\t")
        with open(os.path.join(tmp, rec[3]), "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
        ok_art = ok_art and (got == rec[4])
    shutil.rmtree(tmp, ignore_errors=True)
    if ok_art:
        npass += 1
        print("  OK  D2 artifact gen (8192-byte tensors + SHA-consistent manifest)")
    else:
        print("  BAD D2 artifact generation")

    # ---- fix9 Task A: header/no-header / dup-index / SHA / first-row-not-lost --
    tmpm = tempfile.mkdtemp(prefix="route_d2_manifest_")
    try:
        binname = "input_0000.bin"
        payload = np.arange(2 * N_SAMPLES, dtype=np.float32).tobytes()
        with open(os.path.join(tmpm, binname), "wb") as fh:
            fh.write(payload)
        good_sha = hashlib.sha256(payload).hexdigest()
        hdr = ("index\tsource_index\thdf5_label\tsnr_db\tclass_index\t"
               "class_name\tbin_file\tbin_sha256\n")
        row0 = "0\t1000\t1\t20.0\t1\t4ASK\t%s\t%s\n" % (binname, good_sha)

        # 1. header present -> the (only) data row is parsed.
        with open(os.path.join(tmpm, "m_header.tsv"), "w", encoding="utf-8") as fh:
            fh.write(hdr + row0)
        got = parse_manifest(os.path.join(tmpm, "m_header.tsv"), tmpm)
        if len(got) == 1 and got[0]["index"] == 0:
            npass += 1
            print("  OK  manifest header detected (1 row parsed)")
        else:
            print("  BAD manifest header detection")

        # 2. no header -> the single data row is parsed (detected as data).
        with open(os.path.join(tmpm, "m_noheader.tsv"), "w", encoding="utf-8") as fh:
            fh.write(row0)
        if len(parse_manifest(os.path.join(tmpm, "m_noheader.tsv"), tmpm)) == 1:
            npass += 1
            print("  OK  headerless manifest parsed")
        else:
            print("  BAD headerless manifest")

        # 3. duplicate index -> fail-closed ValueError.
        with open(os.path.join(tmpm, "m_dup.tsv"), "w", encoding="utf-8") as fh:
            fh.write(hdr + row0 +
                     "0\t1001\t1\t20.0\t1\t4ASK\t%s\t%s\n" % (binname, good_sha))
        try:
            parse_manifest(os.path.join(tmpm, "m_dup.tsv"), tmpm)
            print("  BAD duplicate index not detected")
        except ValueError:
            npass += 1
            print("  OK  duplicate index detected")

        # 4. SHA mismatch -> fail-closed ValueError.
        with open(os.path.join(tmpm, "m_badsha.tsv"), "w", encoding="utf-8") as fh:
            fh.write(hdr + "0\t1000\t1\t20.0\t1\t4ASK\t%s\t%s\n"
                     % (binname, "0" * 64))
        try:
            parse_manifest(os.path.join(tmpm, "m_badsha.tsv"), tmpm)
            print("  BAD bin SHA mismatch not detected")
        except ValueError:
            npass += 1
            print("  OK  bin SHA mismatch detected")

        # 5. first-row-not-lost: a headerless 2-row manifest keeps BOTH rows in
        # order (the fix8 parser dropped the first line unconditionally).
        with open(os.path.join(tmpm, "m_two.tsv"), "w", encoding="utf-8") as fh:
            fh.write(row0 +
                     "1\t1001\t1\t20.0\t1\t4ASK\t%s\t%s\n" % (binname, good_sha))
        got2 = parse_manifest(os.path.join(tmpm, "m_two.tsv"), tmpm)
        if [r["index"] for r in got2] == [0, 1]:
            npass += 1
            print("  OK  headerless first row not lost")
        else:
            print("  BAD headerless first row lost: %r"
                  % [r["index"] for r in got2])
    finally:
        shutil.rmtree(tmpm, ignore_errors=True)

    print("self-test: %d/15 correct" % npass)
    return 0 if npass == 15 else 1


# ---------------------------------------------------------------------------
# Manifest + main.
# ---------------------------------------------------------------------------
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest(path: str, bin_dir: str | None = None) -> list[dict]:
    """Parse manifest_a.tsv with header/no-header detection and fail-closed
    validation (fix9 Task A).

    The fix8 parser unconditionally dropped the first line as a "header", so a
    headerless manifest silently LOST its first data row.  This parser detects a
    header by inspecting the first field ("index" == literal header, else an
    integer data row) and never drops a data row.  Each row is validated
    fail-closed: index and source_index uniqueness, class_name <-> class_index
    consistency (INDEX_TO_CLASS), and (when bin_dir is given) the .bin file's
    existence / exact 8192 bytes / SHA256.  Any violation raises ValueError --
    nothing is silently dropped, so the caller can truthfully report dropped=0.
    """
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        return rows
    # Header detection: a header's first field is the literal "index"; a data
    # row's first field is a base-10 integer.  Never assume a header.
    start = 0
    first = lines[0].split("\t")
    if first and first[0] == "index":
        start = 1
    seen_index = set()
    seen_source = set()
    for line in lines[start:]:
        if not line:
            continue
        p = line.split("\t")
        if len(p) < 8:
            raise ValueError("bad manifest row (want >=8 cols): %r" % line)
        idx = int(p[0])
        sidx = int(p[1])
        ci = int(p[4])
        cname = p[5]
        if idx in seen_index:
            raise ValueError("duplicate index %d in %s" % (idx, path))
        if sidx in seen_source:
            raise ValueError("duplicate source_index %d in %s" % (sidx, path))
        if INDEX_TO_CLASS.get(ci) != cname:
            raise ValueError("class_name %r does not match class_index %d "
                             "(expected %r) in %s"
                             % (cname, ci, INDEX_TO_CLASS.get(ci), path))
        seen_index.add(idx)
        seen_source.add(sidx)
        rows.append({
            "index": idx, "source_index": sidx,
            "hdf5_label": int(p[2]), "snr_db": float(p[3]),
            "class_index": ci, "class_name": cname,
            "bin_file": p[6], "bin_sha256": p[7],
        })
    if bin_dir:
        _validate_bin_files(rows, bin_dir)
    return rows


def _validate_bin_files(rows: list[dict], bin_dir: str) -> None:
    """Fail-closed .bin validation: existence, exact 8192 bytes, SHA256 match."""
    want = 2 * N_SAMPLES * 4
    for r in rows:
        p = os.path.join(bin_dir, r["bin_file"])
        if not os.path.isfile(p):
            raise ValueError("bin file missing: %s" % p)
        if os.path.getsize(p) != want:
            raise ValueError("bin file %s: %d bytes, want %d"
                             % (p, os.path.getsize(p), want))
        if sha256_file(p) != r["bin_sha256"]:
            raise ValueError("bin file SHA mismatch: %s" % p)


def read_tensor(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype="<f4")
    if data.size != 2 * N_SAMPLES:
        raise ValueError("%s: %d floats, want %d" % (path, data.size, 2 * N_SAMPLES))
    return (data[:N_SAMPLES] + 1j * data[N_SAMPLES:]).astype(np.complex128)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin-dir", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--classes", default="4ASK")
    ap.add_argument("--calib-count", type=int, default=240)
    ap.add_argument("--holdout-count", type=int, default=240)
    ap.add_argument("--k-candidates", default=None)
    ap.add_argument("--edge-policy", default="zero")
    ap.add_argument("--d2-out-dir", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    for c in classes:
        if c not in SOURCE_CLASS_INDEX:
            ap.error("unknown class %r; allowed %s" % (c, sorted(SOURCE_CLASS_INDEX)))

    if args.k_candidates:
        kcand = [float(x) for x in args.k_candidates.split(",") if x.strip()]
    else:
        kcand = [16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0]

    # Gather (tensor, class) pairs -- synthetic or extracted.
    samples = []
    manifest_rows = None
    if args.synthetic:
        rng = np.random.default_rng(7)
        for c in classes:
            ci = SOURCE_CLASS_INDEX[c]
            for i in range(args.calib_count + args.holdout_count):
                x = synth_4ask(rng=rng) if c == "4ASK" else synth_tone()
                samples.append((x, ci, c, -1))
    else:
        if not args.bin_dir:
            ap.error("--bin-dir is required unless --synthetic or --self-test")
        manifest = args.manifest or os.path.join(args.bin_dir, "manifest_a.tsv")
        rows = parse_manifest(manifest, args.bin_dir)
        manifest_rows = rows
        by_class = {}
        for r in rows:
            by_class.setdefault(r["class_index"], []).append(r)
        for c in classes:
            ci = SOURCE_CLASS_INDEX[c]
            if ci not in by_class:
                ap.error("class %s has no frames in %s" % (c, manifest))
            want = args.calib_count + args.holdout_count
            for r in by_class[ci][:want]:
                samples.append(
                    (read_tensor(os.path.join(args.bin_dir, r["bin_file"])),
                     ci, c, r["source_index"]))

    # Partition: fixed calibration subset (unlabelled K search) + holdout.
    calib, calib_src, holdout = [], [], []
    seen = {}
    for x, ci, c, sidx in samples:
        k = (ci, c)
        if seen.get(k, 0) < args.calib_count:
            calib.append(x)
            calib_src.append(sidx)
        else:
            holdout.append((x, ci, c, sidx))
        seen[k] = seen.get(k, 0) + 1

    if manifest_rows is not None:
        # fix9 Task A: fail-closed input audit.  dropped is 0 because
        # parse_manifest RAISES on any invalid row instead of silently dropping;
        # overlap is 0 by source_index uniqueness + the deterministic positional
        # split (a source_index belongs to exactly one (class, position)).
        holdout_src = {sidx for (_, _, _, sidx) in holdout}
        overlap = len(set(calib_src) & holdout_src)
        consumed = len(calib) + len(holdout)
        dropped = 0
        print("ROUTE_D2_INPUT_AUDIT rows=%d consumed=%d dropped=%d overlap=%d "
              "result=%s"
              % (len(manifest_rows), consumed, dropped, overlap,
                 "PASS" if overlap == 0 else "FAIL"))
        if overlap != 0:
            print("analyze_route_d2_4ask: FAIL: calib/holdout source_index "
                  "overlap", file=sys.stderr)
            return 1

    print("analyze_route_d2_4ask: %d calib + %d holdout frames (%s)"
          % (len(calib), len(holdout), ",".join(classes)))
    print("  k_candidates=%s edge_policy=%s guard=%d"
          % (kcand, args.edge_policy, DEFAULT_GUARD))

    K, krows = choose_global_K(calib, kcand)
    print("== global-K search (calibration subset, unlabelled) ==")
    for r in krows:
        print("  K=%7.0f  nmse=%.3e  clip=%.5f  util=%.4f"
              % (r["K"], r["nmse"], r["clip_rate"], r["utilization"]))
    print("  chosen K = %.0f" % K)

    # Holdout: D0 baseline vs D1 (global K) vs D2 (global K + preserve DC).
    results = {}
    for c in classes:
        ci = SOURCE_CLASS_INDEX[c]
        rows = {"D0": [], "D1": [], "D2": []}
        for x, hci, hc, _sid in holdout:
            if hci != ci:
                continue
            for variant in ("D0", "D1", "D2"):
                r = reconstruct(x, variant, K, edge=args.edge_policy)
                m = align_and_measure(x, r["recovered"])
                rows[variant].append({
                    "nmse": m["nmse_center"], "corr": m["corr_center"],
                    "dc_error": m["dc_error"], "util": r["quant_utilization"],
                    "clip": r["clip_rate"], "rms_recov": m["rms_recov"],
                })
        results[c] = {
            v: {
                "nmse": float(np.mean([e["nmse"] for e in rows[v]])),
                "corr": float(np.mean([e["corr"] for e in rows[v]])),
                "dc_error": float(np.mean([e["dc_error"] for e in rows[v]])),
                "util": float(np.mean([e["util"] for e in rows[v]])),
                "clip": float(np.mean([e["clip"] for e in rows[v]])),
            } for v in ("D0", "D1", "D2") if rows[v]
        }
        print("== class %s (holdout) ==" % c)
        for v in ("D0", "D1", "D2"):
            s = results[c][v]
            print("  %s  nmse=%.3e corr=%.6f dc_err=%.3e util=%.4f clip=%.5f"
                  % (v, s["nmse"], s["corr"], s["dc_error"], s["util"], s["clip"]))

        # D3: grid over edge_policy x guard for D2 at the chosen K.  This
        # attributes any residual error to the resampler FIR / guard / quantiser
        # rather than to the amplitude mapping: if the NMSE is flat across the
        # grid, the residual is a fixed reconstruction floor, not a D0/D1/D2
        # amplitude-mapping artefact (measurement-only, no labels).
        d3_grid = {}
        for edge in ("zero", "reflect"):
            for guard in (768, 832, 896):
                nm = []
                for x, hci, hc, _sid in holdout:
                    if hci != ci:
                        continue
                    r = reconstruct(x, "D2", K, edge=edge, guard=guard)
                    nm.append(align_and_measure(x, r["recovered"])["nmse_center"])
                d3_grid["%s/g%d" % (edge, guard)] = float(np.mean(nm))
        results[c]["D3"] = {
            "nmse_min": min(d3_grid.values()),
            "nmse_max": max(d3_grid.values()),
            "grid": d3_grid,
        }
        print("  D3  sweep nmse in [%.3e, %.3e] over %d (edge x guard) grids"
              % (results[c]["D3"]["nmse_min"], results[c]["D3"]["nmse_max"],
                 len(d3_grid)))

    verdict, verdict_components = compute_verdict(results)
    print("== overall ==")
    print("  global_K=%.0f  edge_policy=%s" % (K, args.edge_policy))
    for comp in verdict_components:
        print("  - %s" % comp)
    print("  verdict = %s (classification recovery still requires a board "
          "Route F D-vs-D2 A/B run)" % verdict)

    if args.d2_out_dir:
        n_written = write_d2_artifacts(args.d2_out_dir, holdout, K,
                                       edge=args.edge_policy)
        print("  wrote %d D2 recovered tensors + d2_recovered_manifest.tsv to %s"
              % (len(n_written), args.d2_out_dir))

    if args.json:
        out = {"global_K": K, "k_search": krows,
               "per_class": results, "verdict": verdict,
               "components": verdict_components}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
