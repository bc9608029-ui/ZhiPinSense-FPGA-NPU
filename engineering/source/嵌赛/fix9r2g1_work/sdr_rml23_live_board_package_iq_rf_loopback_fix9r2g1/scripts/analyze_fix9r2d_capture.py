#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_fix9r2d_capture.py -- Route F fix9r2d: OFFLINE verdict for the enhanced
diagnostic capture (approved 39e5).  The board now saves EIGHT waveforms per R8
diagnostic file (raw_aligned_rx_training/payload/full_frame + raw_cycle_0/1_full_frame
+ expected_training/payload + provisional_recovered_payload) with a per-slice
provenance proof (mem_slice_sha256 == file sha256) and a per-capture metadata manifest
(capture SHA / frame indices / RMS / DC / peak / clip / CFO / SRO / gain).

This analyzer turns those raw .f32 files into EXACTLY ONE of six verdicts
(requirement 8):

    STABLE_LTI_CHANNEL             the residual is a stable linear time-invariant
                                   channel (equalizer-able)
    CYCLIC_BOUNDARY_TRANSIENT      the residual is concentrated at the burst edges
    CAPTURE_INDEX_MISMATCH         the saved slices do not self-consistently align
    CYCLE_TO_CYCLE_NONSTATIONARY   the channel changed between two adjacent cycles
    TRAINING_PAYLOAD_GAIN_MISMATCH the preamble gain does not carry to the payload
    NOT_IDENTIFIED                 none of the above (provenance/recovery gap)

Requirement-6 analyses (each verdict rests on a falsifiable measurement):

  r6.1  cycle0-vs-cycle1 same-training-segment corr/NMSE
  r6.2  cycle0-vs-cycle1 same-payload-segment  corr/NMSE
  r6.3  training-vs-payload optimal complex gain, gain ratio + phase difference
  r6.4  central/boundary segment residual (edge vs central of the preamble)
  r6.5  whether the raw payload after the EXISTING scalar recovery reproduces the
        saved provisional payload (byte-level, i.e. provisional == scalar(raw rx))
  r6.6  capture index offset +-N-sample scan for a fixed slice misalignment

Decision order (first match wins; documented thresholds below):

  CAPTURE_INDEX_MISMATCH       provenance failed OR internal slice mismatch OR
                               +-N scan finds a non-zero delta with corr gain > margin
  CYCLE_TO_CYCLE_NONSTATIONARY cycle0-vs-cycle1 corr below T_CYC_CORR
  TRAINING_PAYLOAD_GAIN_MISMATCH gain ratio outside [T_GAIN_LO, T_GAIN_HI] or
                               phase diff > T_PHASE_DIFF_DEG
  CYCLIC_BOUNDARY_TRANSIENT    boundary/central residual ratio > T_BOUNDARY_RATIO
  NOT_IDENTIFIED               scalar recovery does NOT reproduce the provisional
  STABLE_LTI_CHANNEL           everything else (stationary, uniform gain, no edge
                               transient, recovery reproduces)

stdlib + numpy only.  Run with:  python -I scripts/analyze_fix9r2d_capture.py ...
"""

import argparse
import json
import math
import sys
import warnings

import numpy as np

FS = 2560000.0
PERIOD = 59904            # kFramePeriodComplex
TRAIN_LEN = 1024          # kTrainingLength
PAYLOAD_START = 3072      # kPayloadOffset
PAYLOAD_LEN = 53760       # kPayloadLength

# --- decision thresholds (documented; tunable) ----------------------------------
T_CYC_CORR = 0.99          # cycle0-vs-cycle1 same-segment corr below this -> nonstationary
T_GAIN_LO = 0.9            # |g_pay|/|g_train| below this -> training/payload gain mismatch
T_GAIN_HI = 1.1            # ... above this -> mismatch
T_PHASE_DIFF_DEG = 10.0    # |arg(g_pay)-arg(g_train)| above this (deg) -> mismatch
T_BOUNDARY_RATIO = 2.0     # edge/central residual above this -> boundary transient
T_INDEX_MARGIN = 0.02      # corr improvement at a non-zero delta above this -> index mismatch
T_REPRO_NMSE = 1e-6        # scalar-recovery reproduction NMSE above this -> NOT_IDENTIFIED
T_SCALAR_FLOOR = 1e-6      # scalar residual below this -> residual is noise floor
INDEX_SCAN_N = 8           # +-N capture-index scan

VERDICTS = (
    "STABLE_LTI_CHANNEL",
    "CYCLIC_BOUNDARY_TRANSIENT",
    "CAPTURE_INDEX_MISMATCH",
    "CYCLE_TO_CYCLE_NONSTATIONARY",
    "TRAINING_PAYLOAD_GAIN_MISMATCH",
    "NOT_IDENTIFIED",
)


# ---------------------------------------------------------------------------
# ComplexWarning guardrail (same safe getattr fallback as the fix9r2c analyzer).
# ---------------------------------------------------------------------------
def _complex_warning_category():
    exc = getattr(np, "exceptions", None)
    if exc is not None:
        cw = getattr(exc, "ComplexWarning", None)
        if cw is not None:
            return cw
    return getattr(np, "ComplexWarning", None)


_COMPLEX_WARNING = _complex_warning_category()
if _COMPLEX_WARNING is not None:
    warnings.filterwarnings("error", category=_COMPLEX_WARNING)


def load_f32(path):
    raw = np.fromfile(path, dtype="<f4")
    if raw.size % 2 != 0:
        raise ValueError("%s: odd float count %d (not interleaved IQ)" % (path, raw.size))
    return (raw[0::2] + 1j * raw[1::2]).astype(np.complex128)


def rms(x):
    return float(np.sqrt(np.mean(np.abs(x) ** 2))) if x.size else 0.0


def normalized_corr(rx, ref):
    den = math.sqrt(float(np.sum(np.abs(rx) ** 2)) * float(np.sum(np.abs(ref) ** 2)))
    if den <= 0.0:
        return 0.0
    return float(abs(np.vdot(ref, rx))) / den


def scalar_fit(rx, ref):
    """LS forward complex gain g for rx ~ g*ref; returns (g, residual)."""
    den = float(np.vdot(ref, ref).real)
    if den <= 0.0:
        return 0.0j, float("inf")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        g = np.vdot(ref, rx) / den
        res = math.sqrt(float(np.sum(np.abs(rx - g * ref) ** 2)) /
                        float(np.sum(np.abs(g * ref) ** 2)))
    return g, res


def corr_nmse(a, b):
    """Magnitude-normalized corr and NMSE ||a-b||^2/||b||^2 for two segments."""
    corr = normalized_corr(a, b)
    den = float(np.sum(np.abs(b) ** 2))
    nmse = float(np.sum(np.abs(a - b) ** 2)) / den if den > 0 else float("inf")
    return corr, nmse


def optimal_gain(rx, ref):
    den = float(np.vdot(ref, ref).real)
    return np.vdot(ref, rx) / den if den > 0 else 0.0j


def boundary_metrics(rx, ref):
    """central 75% vs edge 12.5%+12.5% residual under the scalar model.
    Returns (central_residual, boundary_ratio, scalar_residual)."""
    g, scalar_res = scalar_fit(rx, ref)
    n = ref.size
    m = n // 8
    err = rx - g * ref
    core_rms = rms(err[m:n - m])
    model_core = rms((g * ref)[m:n - m])
    central = (core_rms / model_core) if model_core > 0 else float("inf")
    edge_idx = np.concatenate([np.arange(0, m), np.arange(n - m, n)])
    edge_rms = rms(err[edge_idx])
    ratio = (edge_rms / core_rms) if core_rms > 1e-12 else 1.0
    return central, ratio, scalar_res


# ---------------------------------------------------------------------------
# r6.5: reproduce the EXISTING scalar recovery (provisional_apply_scalar) on the
# aligned full frame.  This is a byte-level reproduction: with CFO/SRO ~ 0 the board
# output is a_inv * raw_payload, so a fabricated or mis-recorded provisional will not
# reproduce.  Mirrors iq_rf_fix9r2b_diagnostic.hpp::provisional_apply_scalar exactly.
# ---------------------------------------------------------------------------
def reproduce_provisional(full, meta):
    gain_mag = float(meta["gain_mag"])
    phase_deg = float(meta["phase_deg"])
    cfo = float(meta["cfo_hz"])
    sro = float(meta["sro_ppm"]) * 1e-6
    mag2 = gain_mag * gain_mag
    a_inv = ((gain_mag / mag2) * np.exp(-1j * math.radians(phase_deg))
             if mag2 > 1e-12 else 1.0j + 0.0)
    out = np.zeros(PAYLOAD_LEN, dtype=np.complex128)
    for k in range(PAYLOAD_LEN):
        src = float(PAYLOAD_START + k) * (1.0 + sro)
        i0 = int(math.floor(src))
        i1 = i0 + 1
        frac = src - float(i0)
        if i1 < full.size:
            x = full[i0] * (1.0 - frac) + full[i1] * frac
        elif i0 < full.size:
            x = full[i0]
        else:
            x = 0.0j
        x *= a_inv
        ph = -2.0 * math.pi * cfo * float(PAYLOAD_START + k) / FS
        out[k] = x * complex(math.cos(ph), math.sin(ph))
    return out


def capture_index_scan(concat, full, timing_offset, n):
    """+-n-sample scan for a fixed slice misalignment (r6.6).
    Returns (best_delta, best_corr, corr_at_0)."""
    period = full.size
    best_delta, best_corr, corr_at_0 = 0, -1.0, None
    for d in range(-n, n + 1):
        start = int(timing_offset) + d
        if start < 0 or start + period > concat.size:
            continue
        c = normalized_corr(full, concat[start:start + period])
        if d == 0:
            corr_at_0 = c
        if c > best_corr:
            best_corr, best_delta = c, d
    return best_delta, best_corr, (corr_at_0 if corr_at_0 is not None else -1.0)


# ---------------------------------------------------------------------------
# Analyze one capture -> requirement-6 metric dict + verdict.
# ---------------------------------------------------------------------------
def analyze_one_capture(w, meta, provenance_ok=True):
    cycle0, cycle1 = w["cycle0"], w["cycle1"]
    full = w["full"]
    train_rx, pay_rx = w["train_rx"], w["pay_rx"]
    train_ref, pay_ref = w["train_ref"], w["pay_ref"]
    provisional = w["provisional"]

    off = int(meta["timing_offset"])
    circ = off % PERIOD

    # r6.1 / r6.2: cycle0-vs-cycle1 same-segment corr/NMSE (same cycle-local offset).
    cyc0_train = cycle0[circ:circ + TRAIN_LEN]
    cyc1_train = cycle1[circ:circ + TRAIN_LEN]
    cyc0_pay = cycle0[circ + PAYLOAD_START:circ + PAYLOAD_START + PAYLOAD_LEN]
    cyc1_pay = cycle1[circ + PAYLOAD_START:circ + PAYLOAD_START + PAYLOAD_LEN]
    cyc_train_corr, cyc_train_nmse = corr_nmse(cyc0_train, cyc1_train)
    cyc_pay_corr, cyc_pay_nmse = corr_nmse(cyc0_pay, cyc1_pay)

    # r6.3: training-vs-payload optimal complex gain.
    g_train = optimal_gain(train_ref, train_rx)
    g_pay = optimal_gain(pay_ref, pay_rx)
    gain_ratio = abs(g_pay) / abs(g_train) if abs(g_train) > 1e-15 else float("inf")
    phase_diff_deg = math.degrees(
        math.atan2((g_pay / g_train).imag, (g_pay / g_train).real)) \
        if abs(g_train) > 1e-15 else 0.0

    # r6.4: central/boundary residual (preamble).
    central_res, boundary_ratio, scalar_res = boundary_metrics(train_rx, train_ref)

    # internal slice consistency: the aligned slices must equal the full-frame slices.
    internal_ok = (
        train_rx.size >= TRAIN_LEN and pay_rx.size >= PAYLOAD_LEN and
        np.array_equal(train_rx, full[:TRAIN_LEN]) and
        np.array_equal(pay_rx, full[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN])
    )

    # r6.6: capture-index +-N scan on concat = cycle0 || cycle1.
    concat = np.concatenate([cycle0, cycle1])
    best_delta, best_corr, corr_at_0 = capture_index_scan(concat, full, off, INDEX_SCAN_N)

    # r6.5: scalar-recovery reproduction of the provisional payload.
    repro = reproduce_provisional(full, meta)
    den = float(np.sum(np.abs(provisional) ** 2))
    repro_nmse = float(np.sum(np.abs(repro - provisional) ** 2)) / den if den > 0 else float("inf")
    reproduces = repro_nmse < T_REPRO_NMSE

    m = {
        "cycle_train_corr": cyc_train_corr, "cycle_train_nmse": cyc_train_nmse,
        "cycle_payload_corr": cyc_pay_corr, "cycle_payload_nmse": cyc_pay_nmse,
        "g_train_mag": abs(g_train), "g_train_phase_deg": math.degrees(math.atan2(g_train.imag, g_train.real)),
        "g_pay_mag": abs(g_pay), "g_pay_phase_deg": math.degrees(math.atan2(g_pay.imag, g_pay.real)),
        "gain_ratio": gain_ratio, "phase_diff_deg": phase_diff_deg,
        "central_residual": central_res, "boundary_ratio": boundary_ratio,
        "scalar_residual": scalar_res,
        "internal_consistent": bool(internal_ok),
        "provenance_ok": bool(provenance_ok),
        "capture_index_best_delta": best_delta,
        "capture_index_corr_at_0": corr_at_0,
        "capture_index_best_corr": best_corr,
        "repro_nmse": repro_nmse, "reproduces_provisional": bool(reproduces),
    }
    m["verdict"] = decide_verdict(m)
    return m


def decide_verdict(m):
    # 1. capture integrity: provenance failed or slices do not self-align, or the
    #    +-N scan finds a non-zero delta that clearly improves the alignment.
    if not m["provenance_ok"] or not m["internal_consistent"]:
        return "CAPTURE_INDEX_MISMATCH"
    if m["capture_index_best_delta"] != 0 and \
            (m["capture_index_best_corr"] - m["capture_index_corr_at_0"]) > T_INDEX_MARGIN:
        return "CAPTURE_INDEX_MISMATCH"
    # 2. cycle-to-cycle stationarity.
    if m["cycle_train_corr"] < T_CYC_CORR or m["cycle_payload_corr"] < T_CYC_CORR:
        return "CYCLE_TO_CYCLE_NONSTATIONARY"
    # 3. training/payload gain uniformity.
    if not (T_GAIN_LO <= m["gain_ratio"] <= T_GAIN_HI and
            abs(m["phase_diff_deg"]) <= T_PHASE_DIFF_DEG):
        return "TRAINING_PAYLOAD_GAIN_MISMATCH"
    # 4. boundary transient (only meaningful when there is a real residual).
    if m["boundary_ratio"] > T_BOUNDARY_RATIO and m["scalar_residual"] > T_SCALAR_FLOOR:
        return "CYCLIC_BOUNDARY_TRANSIENT"
    # 5. provenance of the recovery output: scalar(raw) must reproduce the provisional.
    if not m["reproduces_provisional"]:
        return "NOT_IDENTIFIED"
    # 6. otherwise the channel is a stable LTI system (equalizer-able residual).
    return "STABLE_LTI_CHANNEL"


# ---------------------------------------------------------------------------
# Self-test: inject each of the six causes and assert the verdict.
# ---------------------------------------------------------------------------
def _zc_ref(n=1024, amp=2048.0):
    k = np.arange(n, dtype=np.float64)
    ph = -math.pi * k * (k + 1) / n   # Zadoff-Chu root 1
    return (amp * np.exp(1j * ph)).astype(np.complex128)


def _fft_delay(ref, tau):
    n = ref.size
    k = np.fft.fftfreq(n)
    return np.fft.ifft(np.fft.fft(ref) * np.exp(-1j * 2.0 * math.pi * tau * k))


def _make_refs():
    rng = np.random.default_rng(20261014)
    train_ref = _zc_ref(TRAIN_LEN)
    pay_ref = (rng.standard_normal(PAYLOAD_LEN) +
               1j * rng.standard_normal(PAYLOAD_LEN)).astype(np.complex128)
    return train_ref, pay_ref


def _make_burst(train_ref, pay_ref):
    burst = np.zeros(PERIOD, dtype=np.complex128)
    burst[:TRAIN_LEN] = train_ref
    burst[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN] = pay_ref
    return burst


def _case(train_ref, pay_ref, aligned, full, cycle0, cycle1, provisional,
          meta, off):
    return {
        "cycle0": cycle0, "cycle1": cycle1, "full": full,
        "train_rx": full[:TRAIN_LEN], "pay_rx": full[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
        "train_ref": train_ref, "pay_ref": pay_ref, "provisional": provisional,
    }, meta


def self_test():
    off = 123
    train_ref, pay_ref = _make_refs()
    burst = _make_burst(train_ref, pay_ref)
    meta = {"timing_offset": off, "gain_mag": 1.0, "phase_deg": 0.0,
            "cfo_hz": 0.0, "sro_ppm": 0.0}

    cases = []  # (label, want, w, mt)

    # 1. STABLE_LTI_CHANNEL: a stable amplitude ripple (LTI, |H| ~ 1, no seam).
    #    (A circular fractional delay of a zero-padded frame would wrap the tail into
    #    the preamble at the circular seam, an artifact of the synthetic test, not a
    #    physical fractional sampling offset -- so the LTI case uses a mild ripple.)
    f = np.fft.fftfreq(PERIOD)
    H = 1.0 + 0.05 * np.cos(2.0 * math.pi * 2.0 * f)
    aligned = np.fft.ifft(np.fft.fft(burst) * H)
    w, mt = _case(train_ref, pay_ref, aligned, aligned,
                  np.roll(aligned, off), np.roll(aligned, off),
                  aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN], meta, off)
    cases.append(("STABLE_LTI_CHANNEL", "STABLE_LTI_CHANNEL", w, mt))

    # 2. CYCLIC_BOUNDARY_TRANSIENT: attenuate the preamble edges (both cycles).
    aligned = burst.copy()
    edge = 128
    ramp = np.linspace(0.2, 1.0, edge)
    aligned[:edge] *= ramp
    aligned[TRAIN_LEN - edge:TRAIN_LEN] *= ramp[::-1]
    w, mt = _case(train_ref, pay_ref, aligned, aligned,
                  np.roll(aligned, off), np.roll(aligned, off),
                  aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN], meta, off)
    cases.append(("CYCLIC_BOUNDARY_TRANSIENT", "CYCLIC_BOUNDARY_TRANSIENT", w, mt))

    # 3. CYCLE_TO_CYCLE_NONSTATIONARY: cycle1 sees a different channel.
    H2 = 1.0 + 0.5 * np.cos(2.0 * math.pi * 2.0 * f)
    aligned2 = np.fft.ifft(np.fft.fft(burst) * H2)
    aligned1 = burst.copy()
    w = {
        "cycle0": np.roll(aligned1, off), "cycle1": np.roll(aligned2, off),
        "full": aligned1,
        "train_rx": aligned1[:TRAIN_LEN],
        "pay_rx": aligned1[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
        "train_ref": train_ref, "pay_ref": pay_ref,
        "provisional": aligned1[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
    }
    cases.append(("CYCLE_TO_CYCLE_NONSTATIONARY", "CYCLE_TO_CYCLE_NONSTATIONARY", w, meta))

    # 4. TRAINING_PAYLOAD_GAIN_MISMATCH: a gain/phase step before the payload.
    aligned = burst.copy()
    g2 = 1.5 * np.exp(1j * 0.5)   # +28.6 deg, 1.5x magnitude
    aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN] *= g2
    w, mt = _case(train_ref, pay_ref, aligned, aligned,
                  np.roll(aligned, off), np.roll(aligned, off),
                  aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN], meta, off)
    cases.append(("TRAINING_PAYLOAD_GAIN_MISMATCH", "TRAINING_PAYLOAD_GAIN_MISMATCH", w, mt))

    # 5. CAPTURE_INDEX_MISMATCH: full frame misaligned +3 samples vs the true slices.
    aligned = burst.copy()
    full = np.roll(aligned, 3)
    w = {
        "cycle0": np.roll(aligned, off), "cycle1": np.roll(aligned, off),
        "full": full,
        "train_rx": aligned[:TRAIN_LEN],   # true aligned slice
        "pay_rx": aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
        "train_ref": train_ref, "pay_ref": pay_ref,
        "provisional": aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
    }
    cases.append(("CAPTURE_INDEX_MISMATCH", "CAPTURE_INDEX_MISMATCH", w, meta))

    # 6. NOT_IDENTIFIED: stable channel, but the provisional does not reproduce.
    aligned = burst.copy()
    garbage = (_make_refs()[1] * 0.0 + 1.0j)   # a clearly different signal
    w = {
        "cycle0": np.roll(aligned, off), "cycle1": np.roll(aligned, off),
        "full": aligned,
        "train_rx": aligned[:TRAIN_LEN],
        "pay_rx": aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN],
        "train_ref": train_ref, "pay_ref": pay_ref,
        "provisional": garbage[:PAYLOAD_LEN],
    }
    cases.append(("NOT_IDENTIFIED", "NOT_IDENTIFIED", w, meta))

    # 7. negative control: identity channel -> STABLE_LTI_CHANNEL.
    aligned = burst.copy()
    w, mt = _case(train_ref, pay_ref, aligned, aligned,
                  np.roll(aligned, off), np.roll(aligned, off),
                  aligned[PAYLOAD_START:PAYLOAD_START + PAYLOAD_LEN], meta, off)
    cases.append(("STABLE_LTI_CHANNEL (identity)", "STABLE_LTI_CHANNEL", w, mt))

    fails = 0
    for label, want, w, mt in cases:
        m = analyze_one_capture(w, mt)
        got = m["verdict"]
        ok = (got == want)
        if not ok:
            fails += 1
        print("  self-test %-28s cyc_tr=%.4f cyc_pay=%.4f gain_ratio=%.3f "
              "phase_diff=%.1f boundary=%.2f repro=%.2e internal=%d -> %s %s"
              % (label, m["cycle_train_corr"], m["cycle_payload_corr"],
                 m["gain_ratio"], m["phase_diff_deg"], m["boundary_ratio"],
                 m["repro_nmse"], 1 if m["internal_consistent"] else 0,
                 got, "OK" if ok else "FAIL (want %s)" % want))

    # acceptance gate self-check (requirement 5): every violated precondition must
    # fail-closed (non-empty problems) -- i.e. the analyzer must refuse to emit any
    # verdict token when the capture set is structurally incomplete.
    fails += _self_test_acceptance()
    return fails


def _self_test_acceptance():
    fails = 0
    base_meta = {"timing_offset": 0, "gain_mag": 1.0, "phase_deg": 0.0,
                 "cfo_hz": 0.0, "sro_ppm": 0.0, "complete": 1}
    good_wave = {k: {"path": "x", "sha256": "y", "mem_equality": 1} for k in KIND_MAP}
    good_waves = {"f1": dict(good_wave), "f2": dict(good_wave)}
    good_caps = {"f1": dict(base_meta), "f2": dict(base_meta)}

    # valid -> clean
    if acceptance_problems(good_waves, good_caps):
        fails += 1
        print("  acceptance-gate: valid capture set reported a violation")

    # waveform manifest rows != 16 (missing one file's 8 rows)
    if not acceptance_problems({"f1": dict(good_wave)}, good_caps):
        fails += 1
        print("  acceptance-gate: waveform row-count violation not caught")

    # capture manifest rows != 2
    if not acceptance_problems(good_waves, {"f1": dict(base_meta)}):
        fails += 1
        print("  acceptance-gate: capture row-count violation not caught")

    # provenance equality != 1
    bad_waves = {"f1": dict(good_wave), "f2": dict(good_wave)}
    bad_waves["f2"]["raw_cycle_0_full_frame"] = dict(
        good_wave["raw_cycle_0_full_frame"], mem_equality=0)
    if not acceptance_problems(bad_waves, good_caps):
        fails += 1
        print("  acceptance-gate: provenance equality violation not caught")

    # capture_complete != 1
    bad_caps = {"f1": dict(base_meta), "f2": dict(base_meta, complete=0)}
    if not acceptance_problems(good_waves, bad_caps):
        fails += 1
        print("  acceptance-gate: capture_complete violation not caught")

    # missing waveform kind
    miss_waves = {"f1": dict(good_wave), "f2": dict(good_wave)}
    del miss_waves["f1"]["raw_aligned_rx_payload"]
    if not acceptance_problems(miss_waves, good_caps):
        fails += 1
        print("  acceptance-gate: missing-kind violation not caught")

    # raw slice wrong length (out-of-range/truncated) via load_all_waveforms
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix="f9r2d_acc_")
    try:
        short = os.path.join(tmp, "short.f32")
        np.zeros(100, dtype="<f4").tofile(short)   # 50 complex < 1024
        entries = {k: {"path": short, "sha256": "y", "mem_equality": 1}
                   for k in KIND_MAP}
        w, wprobs = load_all_waveforms(entries)
        if not wprobs:
            fails += 1
            print("  acceptance-gate: wrong-length raw slice not caught")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if fails == 0:
        print("  acceptance-gate: 6/6 PASS")
    return fails


# ---------------------------------------------------------------------------
# Real-data mode: read the fix9r2d waveform + capture manifests.
# ---------------------------------------------------------------------------
def read_waveform_manifest(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        assert header[:2] == ["file_name", "kind"], "unexpected manifest header: %s" % header
        col = {name: i for i, name in enumerate(header)}
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            c = line.split("\t")
            fn, kind = c[0], c[1]
            rows.setdefault(fn, {})[kind] = {
                "path": c[col["path"]],
                "sha256": c[col["sha256"]],
                "mem_equality": int(c[col["mem_equality"]]),
            }
    return rows


def read_capture_manifest(path):
    rows = {}
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        assert header[0] == "file_name", "unexpected capture header: %s" % header
        col = {name: i for i, name in enumerate(header)}
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            c = line.split("\t")
            fn = c[0]
            rows[fn] = {
                "timing_offset": int(c[col["timing_offset"]]),
                "gain_mag": float(c[col["gain_mag"]]),
                "phase_deg": float(c[col["phase_deg"]]),
                "cfo_hz": float(c[col["cfo_hz"]]),
                "sro_ppm": float(c[col["sro_ppm"]]),
                "complete": int(c[col["complete"]]),
            }
    return rows


KIND_MAP = {
    "expected_training": "train_ref",
    "raw_aligned_rx_training": "train_rx",
    "raw_aligned_rx_payload": "pay_rx",
    "raw_aligned_rx_full_frame": "full",
    "raw_cycle_0_full_frame": "cycle0",
    "raw_cycle_1_full_frame": "cycle1",
    "expected_payload": "pay_ref",
    "provisional_recovered_payload": "provisional",
}

# Expected complex-sample count per waveform kind.  A raw rx slice whose saved
# .f32 does not load at exactly this length is truncated/out-of-range (structural
# acceptance failure, NOT a channel verdict).
EXPECTED_SAMPLES = {
    "expected_training": TRAIN_LEN,
    "raw_aligned_rx_training": TRAIN_LEN,
    "raw_aligned_rx_payload": PAYLOAD_LEN,
    "raw_aligned_rx_full_frame": PERIOD,
    "raw_cycle_0_full_frame": PERIOD,
    "raw_cycle_1_full_frame": PERIOD,
    "expected_payload": PAYLOAD_LEN,
    "provisional_recovered_payload": PAYLOAD_LEN,
}


def acceptance_problems(waves, caps):
    """Board-acceptance preconditions (requirement 5).  Returns a list of human-
    readable violations; empty == all preconditions hold.  ANY non-empty list must
    fail-closed (emit no verdict token)."""
    problems = []

    # waveform manifest data rows == 16 (2 samples x 8 waveforms)
    total_rows = sum(len(kinds) for kinds in waves.values())
    if total_rows != 16:
        problems.append("waveform manifest data rows = %d "
                        "(want 16 = 2 samples x 8 waveforms)" % total_rows)

    # capture manifest data rows == 2
    if len(caps) != 2:
        problems.append("capture manifest data rows = %d (want 2)" % len(caps))

    for fn, kinds in sorted(waves.items()):
        missing = sorted(set(KIND_MAP) - set(kinds))
        if missing:
            problems.append("%s: missing waveform kinds %s" % (fn, missing))
        for kind, e in sorted(kinds.items()):
            if e["mem_equality"] != 1:
                problems.append("%s/%s mem_equality=%d (want 1)"
                                % (fn, kind, e["mem_equality"]))

    for fn, c in sorted(caps.items()):
        if c.get("complete", 0) != 1:
            problems.append("%s capture_complete=%d (want 1)"
                            % (fn, c.get("complete", 0)))

    return problems


def load_all_waveforms(entries):
    """Load the 8 kinds with per-kind length verification.  Returns (w, problems);
    a non-empty problems list means a raw slice was empty/truncated/out-of-range."""
    w = {}
    problems = []
    for kind, want in EXPECTED_SAMPLES.items():
        if kind not in entries:
            problems.append("missing waveform kind: %s" % kind)
            continue
        try:
            x = load_f32(entries[kind]["path"])
        except (OSError, ValueError) as e:
            problems.append("%s: cannot load (%s)" % (kind, e))
            continue
        if x.size == 0:
            problems.append("%s: empty (0 samples)" % kind)
        elif x.size != want:
            problems.append("%s: %d samples (want %d) -- out-of-range/truncated"
                            % (kind, x.size, want))
        w[kind] = x
    return w, problems


def analyze_manifests(wave_path, capture_path):
    waves = read_waveform_manifest(wave_path)
    caps = read_capture_manifest(capture_path)

    # --- board-acceptance preconditions (requirement 5, fail-closed) -------------
    # Any violation REJECTS the whole run and emits NO verdict token.  The six
    # verdicts are only meaningful on a structurally complete, provenance-clean,
    # complete capture set.
    problems = acceptance_problems(waves, caps)
    loaded = {}
    if not problems:
        for fn in sorted(waves):
            entries = waves[fn]
            w, wprobs = load_all_waveforms(entries)
            if wprobs:
                problems.extend("%s: %s" % (fn, p) for p in wprobs)
            else:
                loaded[fn] = w

    if problems:
        for p in problems:
            print("  ACCEPTANCE_REJECTED: %s" % p)
        return {"accepted": False, "problems": problems, "per_file": []}

    results = []
    for fn in sorted(loaded):
        entries = waves[fn]
        provenance_ok = all(e["mem_equality"] == 1 for e in entries.values())
        m = analyze_one_capture(loaded[fn], caps[fn], provenance_ok=provenance_ok)
        results.append({"file_name": fn, "metrics": m})
        print("  %-32s cyc_tr=%.6f cyc_pay=%.6f gain_ratio=%.4f phase_diff=%.2f "
              "boundary=%.3f central=%.4f repro_nmse=%.2e internal=%d prov=%d -> %s"
              % (fn, m["cycle_train_corr"], m["cycle_payload_corr"], m["gain_ratio"],
                 m["phase_diff_deg"], m["boundary_ratio"], m["central_residual"],
                 m["repro_nmse"], 1 if m["internal_consistent"] else 0,
                 1 if m["provenance_ok"] else 0, m["verdict"]))
    return {"accepted": True, "problems": [], "per_file": results}


def main():
    ap = argparse.ArgumentParser(description="fix9r2d capture verdict analyzer")
    ap.add_argument("--self-test", action="store_true", help="run synthetic self-test")
    ap.add_argument("--wave-manifest", help="route_f_fix9r2d_waveforms.tsv")
    ap.add_argument("--capture-manifest", help="route_f_fix9r2d_capture.tsv")
    ap.add_argument("--out", help="write per-file JSON results here")
    args = ap.parse_args()

    if args.self_test:
        print("analyze_fix9r2d_capture.py --self-test")
        fails = self_test()
        print("  self-test %s" % ("PASS" if fails == 0 else "FAIL (%d)" % fails))
        return 0 if fails == 0 else 1

    if not (args.wave_manifest and args.capture_manifest):
        ap.error("--self-test OR both --wave-manifest and --capture-manifest required")

    print("analyze_fix9r2d_capture.py wave=%s capture=%s"
          % (args.wave_manifest, args.capture_manifest))
    outcome = analyze_manifests(args.wave_manifest, args.capture_manifest)
    results = outcome["per_file"]
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(outcome, f, indent=2, sort_keys=True)
        print("wrote %s" % args.out)

    # requirement 5: any acceptance violation is a fail-closed REJECTION -- no
    # per-file verdict token, no run verdict token, non-zero exit.
    if not outcome["accepted"]:
        print("FIX9R2D_ACCEPTANCE result=REJECTED (%d precondition violation(s))"
              % len(outcome["problems"]))
        return 2

    for r in results:
        print("FIX9R2D_VERDICT file=%s verdict=%s"
              % (r["file_name"], r["metrics"]["verdict"]))
    if results:
        verdicts = set(r["metrics"]["verdict"] for r in results)
        run_verdict = next(iter(verdicts)) if len(verdicts) == 1 else "NOT_IDENTIFIED"
        print("FIX9R2D_VERDICT verdict=%s (files=%d, distinct=%d)"
              % (run_verdict, len(results), len(verdicts)))
    print("analyzed %d file(s)" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
