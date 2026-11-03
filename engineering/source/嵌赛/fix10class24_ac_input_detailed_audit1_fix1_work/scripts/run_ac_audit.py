#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_ac_audit.py -- fix10class24-ac-input-detailed-audit1 end-to-end pipeline.

DIRECT A<->C feature audit (NOT B<->C residual).  Pure offline, read-only on all
inputs.  Six phases:

  P1 identity verification   -> results/input_inventory.tsv
  P2 A reference (test split, per class per SNR) -> a_reference_index.tsv,
       a_reference_by_class_snr.tsv (+ cache/a_reference_features.npz)
  P3 C per-sample features   -> results/per_sample_features.tsv
  P4 A<->C difference        -> results/ac_difference_by_class.tsv
  P5 correct-vs-wrong        -> results/correct_wrong_comparison.tsv
  P6 evidence grading + summary + figures + metric_definitions.md

Run:  python -I scripts/run_ac_audit.py
"""
from __future__ import annotations

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ac_common as ac  # noqa: E402

# classification outcome sources (read-only)
FULL24_RAW24_LOGITS = (
    r"F:/嵌赛/fix10class24_full24_accuracy1_work/"
    r"sdr_rml24_fix10class24_full24_accuracy1/results/full24_accuracy1/raw24_logits.tsv"
)
REPEAT3_RAW24_LOGITS = (
    r"F:/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/results/host_inference/raw24_logits.tsv"
)

METRICS = ac.metric_names()


def fatal(msg):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


# --------------------------------------------------------------------------
# Phase 1: identity verification
# --------------------------------------------------------------------------
def phase1():
    os.makedirs(ac.RESULTS, exist_ok=True)
    os.makedirs(ac.FIGURES, exist_ok=True)
    print("[P1] identity verification")

    ident = {
        "a_hdf5_sha256": ac.FROZEN_A_HDF5_SHA,
        "a_hdf5_sha_method": "inherited frozen SHA + size + mtime_ns (21 GiB full rehash skipped)",
        "split_sha256": None,
        "split_sha_method": "recomputed here (small file)",
    }
    # A HDF5 identity via size + mtime (SHA inherited from audit.json authority)
    st = os.stat(ac.A_HDF5)
    if st.st_size != ac.HDF5_SIZE_BYTES:
        fatal("HDF5 size %d != frozen %d" % (st.st_size, ac.HDF5_SIZE_BYTES))
    if st.st_mtime_ns != ac.HDF5_MTIME_NS:
        fatal("HDF5 mtime_ns %d != frozen %d" % (st.st_mtime_ns, ac.HDF5_MTIME_NS))
    ident["a_hdf5_size_bytes"] = st.st_size
    ident["a_hdf5_mtime_ns"] = st.st_mtime_ns

    # split npz SHA (small file -> full recompute)
    split_sha = ac.sha256_file(ac.SPLIT_NPZ)
    if split_sha != ac.FROZEN_SPLIT_SHA:
        fatal("split npz SHA %s != frozen %s" % (split_sha, ac.FROZEN_SPLIT_SHA))
    ident["split_sha256"] = split_sha

    # HDF5 internal shape/dtype
    try:
        import h5py
        f = h5py.File(ac.A_HDF5, "r")
        ident["hdf5_X_shape"] = list(f["X"].shape)
        ident["hdf5_Y_shape"] = list(f["Y"].shape)
        ident["hdf5_Z_shape"] = list(f["Z"].shape)
        ident["hdf5_X_dtype"] = str(f["X"].dtype)
        f.close()
        if list(ident["hdf5_X_shape"]) != [ac.HDF5_N, 1024, 2]:
            fatal("HDF5 X shape mismatch")
    except Exception as e:  # noqa: BLE001
        fatal("h5py open failed: %s" % e)

    # C tensor enumeration (58) from matched_rf_samples.tsv
    header, rows = ac.read_tsv(ac.MATCHED_RF_SAMPLES)
    assert header[0] == "round" and header[1] == "source_index", "matched_rf header changed"
    c_samples = []
    for r in rows:
        c_samples.append({
            "round": r[0], "source_index": int(r[1]), "raw24_class": int(r[2]),
            "modulation": r[3],
        })
    if len(c_samples) != 58:
        fatal("C tensor enumeration = %d (want 58)" % len(c_samples))

    # load + verify each C tensor
    inventory = []
    n_ok = 0
    for s in c_samples:
        if s["round"] == "full24_r1":
            path = os.path.join(ac.FULL24_EXPORT, str(s["source_index"]),
                                "wide_linear_model_input_f32le.bin")
        else:
            path = os.path.join(ac.REPEAT3_EXPORT, s["round"],
                                str(s["source_index"]), "model_input_f32le.bin")
        if not os.path.exists(path):
            fatal("missing C tensor %s" % path)
        raw = np.fromfile(path, dtype=np.float32)
        nfloats = raw.size
        layout_ok = (nfloats == 2048)
        finite = bool(np.isfinite(raw).all())
        sha = ac.sha256_file(path)
        if not (layout_ok and finite):
            fatal("C tensor identity failure %s n=%d finite=%s" % (path, nfloats, finite))
        n_ok += 1
        inventory.append({
            "round": s["round"], "source_index": s["source_index"],
            "raw24_class": s["raw24_class"], "modulation": s["modulation"],
            "file": path, "n_floats": nfloats, "bytes": nfloats * 4,
            "layout_2x1024": int(layout_ok), "finite": int(finite), "sha256": sha,
        })
    assert n_ok == 58

    ac.write_tsv(
        os.path.join(ac.RESULTS, "input_inventory.tsv"),
        ["round", "source_index", "raw24_class", "modulation", "file",
         "n_floats", "bytes", "layout_2x1024", "finite", "sha256"],
        [[i["round"], i["source_index"], i["raw24_class"], i["modulation"],
          i["file"], i["n_floats"], i["bytes"], i["layout_2x1024"], i["finite"],
          i["sha256"]] for i in inventory],
    )
    print("  A HDF5 identity OK (size+mtime; sha inherited)  split SHA OK")
    print("  %d C tensors: layout/finite/SHA verified" % n_ok)
    return c_samples, ident, inventory


# --------------------------------------------------------------------------
# Phase 2: A reference (test split, per class per SNR, N=100)
# --------------------------------------------------------------------------
def _a_complex(X):
    return (X[:, 0] + 1j * X[:, 1]).astype(np.complex128)


def phase2():
    print("[P2] A reference (test split, per class per SNR, N=%d)" % ac.PER_CLASS_SNR)
    import h5py
    z = np.load(ac.SPLIT_NPZ, allow_pickle=False)
    tidx = z["test_indices"].astype(np.int64)
    tlab = z["test_labels"].astype(np.int64)
    tsnr = z["test_snrs"].astype(np.float64)

    rng = np.random.default_rng(ac.SELECT_SEED)
    f = h5py.File(ac.A_HDF5, "r")

    a_rows = {}       # (cls, snr) -> np.array(row idx)
    a_feats = {}      # (cls, snr) -> {metric: np.array}
    for snr in ac.SELECT_SNRS:
        for cls in range(ac.N_CLASSES):
            pos = np.flatnonzero((tlab == cls) & (np.isclose(tsnr, snr)))
            if len(pos) < ac.PER_CLASS_SNR:
                fatal("stratum class=%d snr=%d has %d < %d" % (cls, snr, len(pos), ac.PER_CLASS_SNR))
            order = rng.permutation(len(pos))
            chosen = pos[order[: ac.PER_CLASS_SNR]]
            rows = tidx[chosen]
            key = (cls, snr)
            a_rows[key] = rows.astype(np.int64)
            feats = {m: np.full(ac.PER_CLASS_SNR, np.nan) for m in METRICS}
            for k, ridx in enumerate(rows):
                iq = _a_complex(f["X"][int(ridx)])
                m = ac.full_metrics(iq)
                for mm in METRICS:
                    feats[mm][k] = m[mm]
            a_feats[key] = feats
    f.close()

    # index tsv
    idx_rows = []
    for snr in ac.SELECT_SNRS:
        for cls in range(ac.N_CLASSES):
            for ridx in a_rows[(cls, snr)]:
                idx_rows.append([cls, snr, int(ridx), ac.LABEL_ORDER_24[cls]])
    ac.write_tsv(os.path.join(ac.RESULTS, "a_reference_index.tsv"),
                 ["raw24_class", "snr_db", "hdf5_row_index", "modulation"], idx_rows)

    # per-class-per-SNR summary (median + q05 + q95)
    summ = []
    for snr in ac.SELECT_SNRS:
        for cls in range(ac.N_CLASSES):
            row = [cls, snr, ac.PER_CLASS_SNR, ac.LABEL_ORDER_24[cls]]
            for m in METRICS:
                v = a_feats[(cls, snr)][m]
                row += [np.nanmedian(v), np.nanquantile(v, 0.05), np.nanquantile(v, 0.95)]
            summ.append(row)
    hdr = ["raw24_class", "snr_db", "n_samples", "modulation"]
    for m in METRICS:
        hdr += ["%s_med" % m, "%s_q05" % m, "%s_q95" % m]
    ac.write_tsv(os.path.join(ac.RESULTS, "a_reference_by_class_snr.tsv"), hdr, summ)

    # cache per-sample features for reuse
    cache = {"row_index": np.zeros((ac.N_CLASSES, len(ac.SELECT_SNRS), ac.PER_CLASS_SNR), np.int64)}
    for snr_i, snr in enumerate(ac.SELECT_SNRS):
        for cls in range(ac.N_CLASSES):
            cache["row_index"][cls, snr_i] = a_rows[(cls, snr)]
    for m in METRICS:
        arr = np.full((ac.N_CLASSES, len(ac.SELECT_SNRS), ac.PER_CLASS_SNR), np.nan)
        for snr_i, snr in enumerate(ac.SELECT_SNRS):
            for cls in range(ac.N_CLASSES):
                arr[cls, snr_i] = a_feats[(cls, snr)][m]
        cache["feat_" + m] = arr
    np.savez_compressed(os.path.join(ac.CACHE, "a_reference_features.npz"), **cache)
    print("  %d reference frames cached" % (ac.N_CLASSES * len(ac.SELECT_SNRS) * ac.PER_CLASS_SNR))
    return a_feats, a_rows


# --------------------------------------------------------------------------
# Phase 3: C per-sample features
# --------------------------------------------------------------------------
def _load_outcomes():
    """Return {(round_or_None, source_index): (pred, correct, gate_status)}"""
    out = {}
    # full24 -> variant=wide_linear from raw24_logits
    h, rows = ac.read_tsv(FULL24_RAW24_LOGITS)
    si = h.index("source_index"); vi = h.index("variant"); pi = h.index("raw24_pred")
    for r in rows:
        if r[vi] != "wide_linear":
            continue
        sid = int(r[si])
        pred = int(float(r[pi]))
        out[("full24_r1", sid)] = (pred, int(pred == int(r[h.index("source_class")])), "DIAGNOSTIC_BYPASS")
    # repeat3 -> per_sample_results (round, source_index, raw24_pred, label_correct, gate_pass)
    h2, rows2 = ac.read_tsv(ac.REPEAT3_PER_SAMPLE)
    ri2 = h2.index("round"); si2 = h2.index("source_index")
    pi2 = h2.index("raw24_pred"); ci2 = h2.index("label_correct"); gi2 = h2.index("gate_pass")
    for r in rows2:
        out[(r[ri2], int(r[si2]))] = (int(r[pi2]), int(r[ci2]),
                                      "GATED" if r[gi2] == "1" else "DIAGNOSTIC_BYPASS")
    return out


def phase3(c_samples):
    print("[P3] C per-sample features")
    outcomes = _load_outcomes()
    feats_rows = []
    per_sample = []
    for s in c_samples:
        key = (s["round"], s["source_index"])
        pred, correct, gate = outcomes.get(key, (-1, -1, "UNKNOWN"))
        if s["round"] == "full24_r1":
            path = os.path.join(ac.FULL24_EXPORT, str(s["source_index"]),
                                "wide_linear_model_input_f32le.bin")
        else:
            path = os.path.join(ac.REPEAT3_EXPORT, s["round"],
                                str(s["source_index"]), "model_input_f32le.bin")
        iq = ac.load_tensor_2x1024(path)
        m = ac.full_metrics(iq)
        rec = {
            "round": s["round"], "source_index": s["source_index"],
            "raw24_class": s["raw24_class"], "modulation": s["modulation"],
            "snr_db": float("nan"), "wl_enabled": 1, "gate_status": gate,
            "raw24_pred": pred, "correct": correct, "iq": iq, "metrics": m,
        }
        per_sample.append(rec)
        feats_rows.append([s["round"], s["source_index"], s["raw24_class"],
                           s["modulation"], gate, pred, correct] +
                          [m[x] for x in METRICS])
    ac.write_tsv(os.path.join(ac.RESULTS, "per_sample_features.tsv"),
                 ["round", "source_index", "raw24_class", "modulation",
                  "gate_status", "raw24_pred", "correct"] + METRICS, feats_rows)
    print("  %d C samples feature-extracted" % len(per_sample))
    return per_sample


# --------------------------------------------------------------------------
# Phase 4: A<->C difference (C value + per-SNR percentile / z-score)
# --------------------------------------------------------------------------
def phase4(per_sample, a_feats):
    print("[P4] A<->C difference")
    snr_idx = {s: i for i, s in enumerate(ac.SELECT_SNRS)}
    rows = []
    for rec in per_sample:
        cls = rec["raw24_class"]
        for m in METRICS:
            cval = rec["metrics"][m]
            row = [rec["round"], rec["source_index"], cls, rec["modulation"], m, cval]
            for snr in ac.SELECT_SNRS:
                dist = a_feats[(cls, snr)][m]
                med = np.nanmedian(dist)
                q05 = np.nanquantile(dist, 0.05)
                q95 = np.nanquantile(dist, 0.95)
                sd = np.nanstd(dist)
                pct = float((dist <= cval).mean()) if np.isfinite(cval) else float("nan")
                zz = float((cval - np.nanmean(dist)) / sd) if (sd > 0 and np.isfinite(cval)) else float("nan")
                row += [med, q05, q95, pct, zz]
            rows.append(row)
    hdr = ["round", "source_index", "raw24_class", "modulation", "metric", "c_value"]
    for snr in ac.SELECT_SNRS:
        hdr += ["a_med_%d" % snr, "a_q05_%d" % snr, "a_q95_%d" % snr,
                "pct_%d" % snr, "z_%d" % snr]
    ac.write_tsv(os.path.join(ac.RESULTS, "ac_difference_by_class.tsv"), hdr, rows)
    print("  %d (sample, metric) rows" % len(rows))
    return rows


# --------------------------------------------------------------------------
# Phase 5: correct-vs-wrong comparison (per class, top-3 differences)
# --------------------------------------------------------------------------
def phase5(per_sample, a_feats):
    print("[P5] correct-vs-wrong comparison (per class, per metric, correct/wrong separated)")
    classes = dict(ac.FOCUS_CLASSES)
    classes.update(ac.CONTROL_CLASSES)
    by_class = {}
    for rec in per_sample:
        if rec["raw24_class"] in classes:
            by_class.setdefault(rec["raw24_class"], []).append(rec)

    def _finite(vals):
        return [v for v in vals if np.isfinite(v)]

    rows = []
    for cls in sorted(classes):
        recs = by_class.get(cls, [])
        mod = classes[cls]
        n_unique = len({rec["source_index"] for rec in recs})
        for m in METRICS:
            cvals = _finite([rec["metrics"][m] for rec in recs])
            correct_vals = _finite([rec["metrics"][m] for rec in recs if rec["correct"] == 1])
            wrong_vals = _finite([rec["metrics"][m] for rec in recs if rec["correct"] == 0])
            # best-matching A SNR stratum = the stratum whose |z| is SMALLEST for this
            # class's C samples (a descriptive reference; NOT an SNR assignment to C).
            best_snr, best_medz = None, float("inf")
            for snr in ac.SELECT_SNRS:
                dist = np.asarray(a_feats[(cls, snr)][m], float)
                med = np.nanmedian(dist); sd = np.nanstd(dist)
                zs = [abs((cv - med) / sd) for cv in cvals if sd > 0]
                mz = float(np.nanmedian(zs)) if zs else float("nan")
                if np.isfinite(mz) and mz < best_medz:
                    best_medz, best_snr = mz, snr
            if best_snr is not None:
                dist = np.asarray(a_feats[(cls, best_snr)][m], float)
                pcts = [float((dist <= cv).mean()) for cv in cvals]
                best_pct = float(np.nanmedian(pcts)) if pcts else float("nan")
            else:
                best_pct = float("nan")
            medval = float(np.nanmedian(cvals)) if cvals else float("nan")
            rows.append({
                "cls": cls, "mod": mod, "metric": m, "medval": medval,
                "best_snr": best_snr, "best_medz": best_medz, "best_pct": best_pct,
                "n": len(recs), "n_unique": n_unique,
                "n_correct": len(correct_vals), "n_wrong": len(wrong_vals),
                "correct_vals": correct_vals, "wrong_vals": wrong_vals,
            })

    # rank within class by median |z| at the best-matching stratum (largest = top
    # difference). This is ONLY a "which feature differs most from A" listing -- NOT
    # a causal or correlation claim.
    rank_map = {}
    for cls in classes:
        cls_rows = [r for r in rows if r["cls"] == cls]
        order = sorted(cls_rows, key=lambda r: (-(r["best_medz"] if np.isfinite(r["best_medz"]) else -1.0)))
        for i, r in enumerate(order):
            rank_map[(r["cls"], r["metric"])] = i + 1

    def fmt(vals):
        return ",".join("" if not np.isfinite(v) else "%.6g" % v for v in vals)

    hdr = ["raw24_class", "modulation", "role", "metric", "c_median_value",
           "best_a_snr", "median_abs_z_at_best_snr", "c_pct_at_best_snr",
           "n_c_samples", "n_unique_sources", "n_correct", "n_wrong",
           "correct_c_values", "wrong_c_values", "rank_in_class", "is_top3"]
    out_rows = []
    for r in rows:
        role = "focus" if r["cls"] in ac.FOCUS_CLASSES else "control"
        rank = rank_map[(r["cls"], r["metric"])]
        out_rows.append([
            r["cls"], r["mod"], role, r["metric"],
            r["medval"], r["best_snr"], r["best_medz"], r["best_pct"],
            r["n"], r["n_unique"], r["n_correct"], r["n_wrong"],
            fmt(r["correct_vals"]), fmt(r["wrong_vals"]),
            rank, int(rank <= 3),
        ])
    ac.write_tsv(os.path.join(ac.RESULTS, "correct_wrong_comparison.tsv"), hdr, out_rows)
    print("  %d (class, metric) rows; correct/wrong C values listed separately" % len(out_rows))
    return out_rows


# --------------------------------------------------------------------------
# Phase 6: evidence grading + summary + figures + metric_definitions
# --------------------------------------------------------------------------
def phase6(per_sample, a_feats, ident):
    print("[P6] evidence grading + summary + figures + metric_definitions")

    classes = dict(ac.FOCUS_CLASSES)
    classes.update(ac.CONTROL_CLASSES)
    by_class = {}
    for rec in per_sample:
        if rec["raw24_class"] in classes:
            by_class.setdefault(rec["raw24_class"], []).append(rec)

    n_classes_covered = len({rec["raw24_class"] for rec in per_sample})

    def _cls_stats(cls, m, snr):
        dist = np.asarray(a_feats[(cls, snr)][m], float)
        return float(np.nanmedian(dist)), float(np.nanquantile(dist, 0.05)), \
               float(np.nanquantile(dist, 0.95))

    def _cls_c_med_pct(cls, m, snr):
        recs = by_class.get(cls, [])
        vals = [r["metrics"][m] for r in recs if np.isfinite(r["metrics"][m])]
        if not vals:
            return float("nan"), float("nan")
        cmed = float(np.nanmedian(vals))
        dist = np.asarray(a_feats[(cls, snr)][m], float)
        pct = float((dist <= cmed).mean())
        return cmed, pct

    evidence = []

    # (1) spectral cleanliness -- per class, referenced to each class's OWN A SNR20
    parts = []
    for cls in sorted(classes):
        cmed, pct = _cls_c_med_pct(cls, "peak_to_floor_db", 20)
        a_med, _, _ = _cls_stats(cls, "peak_to_floor_db", 20)
        parts.append("%s C=%.1f dB vs own A20 med=%.1f dB (pct %.2f)"
                     % (classes[cls], cmed, a_med, pct))
    evidence.append(["%d classes" % n_classes_covered, "-", "peak_to_floor_db", "已直接测得",
                     "spectral cleanliness (peak vs outer-band median) differs from A, with "
                     "magnitude varying BY CLASS: " + "; ".join(parts)])

    # (2) flatness (no additive floor) -- per class vs own A SNR20
    parts = []
    for cls in sorted(classes):
        cmed, pct = _cls_c_med_pct(cls, "flatness", 20)
        a_med, _, _ = _cls_stats(cls, "flatness", 20)
        parts.append("%s C=%.3e vs A20 med=%.3e (pct %.2f)"
                     % (classes[cls], cmed, a_med, pct))
    evidence.append(["%d classes" % n_classes_covered, "-", "flatness", "已直接测得",
                     "spectral flatness (no additive floor) differs from A, by class: " +
                     "; ".join(parts)])

    # (3) continuous bandwidth / amplitude rate / phase-increment std --
    # per-class values that are NOT uniform across classes (retracts the earlier
    # "all differences small and within the reference distribution" generalization).
    for m, label in [("bw99_cont", "continuous 99% bandwidth"),
                     ("amp_roc_mean", "mean amplitude rate-of-change"),
                     ("phase_inc_std", "phase-increment std")]:
        parts = []
        for cls in (14, 15, 16):  # 64QAM, 128QAM, 256QAM
            cmed, pct = _cls_c_med_pct(cls, m, 20)
            a_med, _, _ = _cls_stats(cls, m, 20)
            parts.append("%s C=%.5g vs A20 med=%.5g (pct %.2f)"
                         % (classes[cls], cmed, a_med, pct))
        evidence.append(["64QAM/128QAM/256QAM", "-", m, "已直接测得",
                         "%s differs from A and its A-SNR20 percentile is NOT uniform "
                         "across classes: %s" % (label, "; ".join(parts))])

    # (4) correlation / discrimination -- explicitly NOT performed (retraction)
    evidence.append(["all", "-", "(none)", "与错误相关",
                     "NO correlation or class-discrimination test was performed. The prior "
                     "claim '0 of 50 metrics correlates with the 64QAM/128QAM->256QAM "
                     "collapse' is RETRACTED. Feature differences are descriptive only; "
                     "whether any specific feature causes the misclassification is UNKNOWN."])

    # (5) possible explanation -- none asserted
    evidence.append(["all", "-", "(none)", "可能的解释",
                     "None asserted. The A<->C feature differences above do NOT by "
                     "themselves attribute the misclassification to any feature; a separate "
                     "controlled sensitivity test would be required (out of scope)."])

    # (6) indeterminate
    evidence.append(["GMSK", 22, "run2/run3 collapse", "现有证据无法确定",
                     "only 1 C tensor (full24_r1); run2/run3 collapse has no tensor on disk"])
    evidence.append(["QPSK/8PSK", "4,5", "all", "现有证据无法确定", "0 C tensors on disk"])
    evidence.append(["all", "-", "snr_db", "现有证据无法确定",
                     "C snr_db=nan; comparison is per-A-SNR-stratum only, never a definite SNR for C"])
    evidence.append(["repeat3 classes", "-", "source independence", "现有证据无法确定",
                     "repeat3 rounds are repeated captures of the SAME source_index (same RF "
                     "source); they are NOT independent sources"])

    ac.write_tsv(os.path.join(ac.RESULTS, "evidence_table.tsv"),
                 ["modulation", "raw24_class", "metric", "tier", "note"], evidence)

    # ---- figures ----
    _make_figures(by_class, a_feats, classes)

    # ---- metric_definitions.md ----
    _make_metric_definitions()

    # ---- summary.json ----
    summary = {
        "task": "fix10class24-ac-input-detailed-audit1-fix1",
        "status": ac.STATUS,
        "identity": ident,
        "c_tensor_count": len(per_sample),
        "c_classes_covered": n_classes_covered,
        "a_reference": {
            "split": "test", "snrs": ac.SELECT_SNRS, "per_class_snr": ac.PER_CLASS_SNR,
            "seed": ac.SELECT_SEED, "total_frames": ac.N_CLASSES * len(ac.SELECT_SNRS) * ac.PER_CLASS_SNR,
        },
        "c_by_class": {str(k): [rec["round"] for rec in v]
                       for k, v in sorted(by_class.items())},
        "metric_count": len(METRICS),
        "phase_eps_rule": "drop |x|<%.2f*median(|x|) before phase-increment" % ac.PHASE_EPS_RATIO,
        "spectral": {"fft_n": ac.FFT_N, "window": ac.WINDOW,
                     "floor": "reserved numeric constant %.0e * total_power (NOT applied to flatness)" % ac.SPECTRAL_FLOOR_REL},
        "correct_wrong": {
            cls: {
                "n": len(v), "correct": sum(1 for r in v if r["correct"] == 1),
                "wrong": sum(1 for r in v if r["correct"] == 0),
            } for cls, v in sorted(by_class.items())
        },
        "correlation_tested": False,
        "causal_attribution": "none",
        "retracted_conclusions": [
            "0 of 50 metrics correlates with the 64QAM/128QAM->256QAM collapse",
            "class-specific domain difference excluded",
            "misclassification attributed to decision-boundary sensitivity",
            "all 24 classes show a universal / uniform A<->C shift",
            "C effective SNR ~= 25 dB (spectral peak-to-outer-band used as an SNR)",
            "all differences are small, unidirectional and within the A reference distribution",
        ],
        "verdict": "AUDIT_COMPLETE_DESCRIPTIVE_ONLY",
    }
    ac.write_json(os.path.join(ac.RESULTS, "summary.json"), summary)
    print("  done: evidence_table, summary, figures, metric_definitions")


def _make_figures(by_class, a_feats, classes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import h5py
    z = np.load(ac.SPLIT_NPZ, allow_pickle=False)
    tidx = z["test_indices"].astype(np.int64)
    tlab = z["test_labels"].astype(np.int64)
    tsnr = z["test_snrs"].astype(np.float64)
    rng = np.random.default_rng(ac.SELECT_SEED)
    N_SUB = 30  # deterministic A subset per (class, snr) for distribution plots
    f = h5py.File(ac.A_HDF5, "r")
    a_sub = {}     # (cls, snr) -> list[complex]
    a_rep = {}     # cls -> one complex sample @ snr20
    for cls in classes:
        for snr in ac.SELECT_SNRS:
            pos = np.flatnonzero((tlab == cls) & (np.isclose(tsnr, snr)))
            order = rng.permutation(len(pos))
            chosen = pos[order[:N_SUB]]
            a_sub[(cls, snr)] = [
                (f["X"][int(tidx[p])][:, 0] + 1j * f["X"][int(tidx[p])][:, 1]).astype(np.complex128)
                for p in chosen]
            if snr == 20:
                a_rep[cls] = a_sub[(cls, snr)][0]
    f.close()

    cls_list = sorted(classes)
    ncls = len(cls_list)
    ncol = 4
    nrow = int(np.ceil(ncls / ncol))

    def _grid(title):
        fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3 * nrow), squeeze=False)
        fig.suptitle(title, fontsize=13)
        return fig, axes

    def _hide(axes):
        for j in range(ncls, nrow * ncol):
            axes[j // ncol][j % ncol].axis("off")

    def _sub_axis(axes, i):
        return axes[i // ncol][i % ncol]

    # fig01 amplitude CDF: A per-SNR band (shaded) vs C samples (black)
    fig, axes = _grid("Amplitude CDF: A (per SNR, shaded) vs C (black)")
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        recs = by_class.get(cls, [])
        for snr in ac.SELECT_SNRS:
            amps = np.concatenate([np.abs(x) for x in a_sub[(cls, snr)]])
            q = np.linspace(0, 1, 200)
            ax.plot(q, np.quantile(amps, q), lw=1, alpha=0.55, label="A snr%d" % snr)
        for rec in recs:
            amp = np.sort(np.abs(rec["iq"]))
            ax.plot(np.linspace(0, 1, amp.size), amp, "k-", lw=1.4)
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xlabel("quantile"); ax.set_ylabel("|x|")
        if cls == cls_list[0]:
            ax.legend(fontsize=6)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig01_amplitude_cdf.png"), dpi=120)
    plt.close(fig)

    # fig02 IQ point cloud: A (snr20) vs C
    fig, axes = _grid("IQ point cloud: A (snr20) vs C")
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        ar = a_rep[cls]
        ax.scatter(ar.real[:400], ar.imag[:400], s=3, alpha=0.35, label="A")
        for rec in by_class.get(cls, []):
            c = rec["iq"]
            ax.scatter(c.real[:400], c.imag[:400], s=3, alpha=0.6, label=rec["round"][:12])
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xlabel("I"); ax.set_ylabel("Q"); ax.axis("equal")
        if cls == cls_list[0]:
            ax.legend(fontsize=5)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig02_iq_pointcloud.png"), dpi=120)
    plt.close(fig)

    # fig03 PSD overlay (normalized, dB): A (snr20 median band) vs C
    fig, axes = _grid("Normalized PSD (dB): A (snr20 shaded) vs C")
    fq = np.fft.fftshift(np.fft.fftfreq(ac.FFT_N))
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        Psa = []
        for x in a_sub[(cls, 20)]:
            X = np.fft.fftshift(np.fft.fft(x * np.hanning(x.size), n=ac.FFT_N))
            P = np.abs(X) ** 2
            Psa.append(10 * np.log10(P / P.max() + 1e-12))
        Psa = np.array(Psa)
        lo = np.percentile(Psa, 5, axis=0)
        hi = np.percentile(Psa, 95, axis=0)
        med = np.median(Psa, axis=0)
        ax.fill_between(fq, lo, hi, alpha=0.25, label="A (5-95%)")
        ax.plot(fq, med, "k-", lw=1.1)
        for rec in by_class.get(cls, []):
            c = rec["iq"]
            Xc = np.fft.fftshift(np.fft.fft(c * np.hanning(c.size), n=ac.FFT_N))
            Pc = np.abs(Xc) ** 2
            ax.plot(fq, 10 * np.log10(Pc / Pc.max() + 1e-12), lw=1, alpha=0.7)
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xlabel("cycles/sample"); ax.set_ylabel("dB"); ax.set_ylim(-60, 2)
        if cls == cls_list[0]:
            ax.legend(fontsize=5)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig03_psd_overlay.png"), dpi=120)
    plt.close(fig)

    # fig04 non-circularity: A per-SNR (bar+range) vs C (markers)
    fig, axes = _grid("Non-circularity |E[x^2]|/E[|x|^2]: A vs C")
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        a_med = [np.nanmedian(a_feats[(cls, snr)]["noncirc"]) for snr in ac.SELECT_SNRS]
        a_q05 = [np.nanquantile(a_feats[(cls, snr)]["noncirc"], 0.05) for snr in ac.SELECT_SNRS]
        a_q95 = [np.nanquantile(a_feats[(cls, snr)]["noncirc"], 0.95) for snr in ac.SELECT_SNRS]
        x = np.arange(4)
        ax.bar(x, a_med, 0.5, yerr=[np.array(a_med) - np.array(a_q05), np.array(a_q95) - np.array(a_med)],
               capsize=2, label="A")
        for rec in by_class.get(cls, []):
            ax.axhline(rec["metrics"]["noncirc"], color="k", lw=1, alpha=0.7)
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xticks(x); ax.set_xticklabels(["snr%d" % s for s in ac.SELECT_SNRS], fontsize=6)
        if cls == cls_list[0]:
            ax.legend(fontsize=6)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig04_noncircularity.png"), dpi=120)
    plt.close(fig)

    # fig05 autocorrelation: A (snr20 median band) vs C
    fig, axes = _grid("|Autocorr(lag)|: A (snr20) vs C")
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        Rs = np.array([[ac.full_metrics(x)["acorr_lag%d" % k] for k in ac.ACORR_LAGS]
                       for x in a_sub[(cls, 20)]])
        lo = np.percentile(Rs, 5, axis=0); hi = np.percentile(Rs, 95, axis=0)
        ax.fill_between(ac.ACORR_LAGS, lo, hi, alpha=0.25)
        ax.plot(ac.ACORR_LAGS, np.median(Rs, axis=0), "ko-", label="A")
        for rec in by_class.get(cls, []):
            rc = [rec["metrics"]["acorr_lag%d" % k] for k in ac.ACORR_LAGS]
            ax.plot(ac.ACORR_LAGS, rc, "s--", alpha=0.7)
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xlabel("lag"); ax.set_ylabel("|acorr|")
        if cls == cls_list[0]:
            ax.legend(fontsize=6)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig05_autocorrelation.png"), dpi=120)
    plt.close(fig)

    # fig06 phase increment histogram: A (snr20) vs C
    fig, axes = _grid("Adjacent phase increment: A (snr20) vs C")
    for i, cls in enumerate(cls_list):
        ax = _sub_axis(axes, i)
        dpa = []
        for x in a_sub[(cls, 20)]:
            eps = ac.PHASE_EPS_RATIO * np.median(np.abs(x))
            v = (np.abs(x[:-1]) >= eps) & (np.abs(x[1:]) >= eps)
            dpa.append(np.angle(x[1:] * np.conj(x[:-1]))[v])
        dpa = np.concatenate(dpa)
        ax.hist(dpa, bins=40, density=True, alpha=0.4, label="A")
        for rec in by_class.get(cls, []):
            c = rec["iq"]
            e2 = ac.PHASE_EPS_RATIO * np.median(np.abs(c))
            v2 = (np.abs(c[:-1]) >= e2) & (np.abs(c[1:]) >= e2)
            dpc = np.angle(c[1:] * np.conj(c[:-1]))[v2]
            ax.hist(dpc, bins=40, density=True, alpha=0.5)
        ax.set_title(classes[cls], fontsize=9)
        ax.set_xlabel("rad/sample")
        if cls == cls_list[0]:
            ax.legend(fontsize=6)
    _hide(axes)
    fig.tight_layout()
    fig.savefig(os.path.join(ac.FIGURES, "fig06_phase_increment.png"), dpi=120)
    plt.close(fig)


def _make_metric_definitions():
    by_class_counts = {}
    try:
        h, rows = ac.read_tsv(os.path.join(ac.RESULTS, "per_sample_features.tsv"))
        for r in rows:
            c = int(r[2])
            by_class_counts[c] = by_class_counts.get(c, 0) + 1
    except Exception:
        pass

    lines = []
    lines.append("# Metric definitions — fix10class24-ac-input-detailed-audit1\n")
    lines.append("All units in **cycles/sample** (no sampling-rate mapping assumed; the\n"
                 "1024-point recovered tensor is NOT interpreted as 2.56 Msps).\n")
    lines.append("A reference = TEST split, per class per SNR ∈ {0,10,20,30}, N=100/stratum,\n"
                 "seed=20261019 (never mixing SNR into one pooled mean).  C = real dual-SDR\n"
                 "wide-linear model-input tensors, snr_db=nan, diagnostic-gate-bypass.\n")
    lines.append("The model-input contract is `X[row].T` -> [2,1024] (row0=real,row1=imag);\n"
                 "for feature analysis the same complex signal is loaded as\n"
                 "`I + jQ = X[:,0] + 1j*X[:,1]` (a layout transpose only, no DC/normalize).\n")
    lines.append("\n## Amplitude / DC\n")
    for k, d in [
        ("rms", "sqrt(mean(|x|^2)) — total RMS (scaling)."),
        ("ac_rms", "sqrt(mean(|x - mean(x)|^2)) — demeaned RMS (AC only)."),
        ("dc", "|mean(x)| — complex-mean magnitude (DC level)."),
        ("dc_i / dc_q", "real / imag of mean(x)."),
        ("dc_power_frac", "|mean(x)|^2 / mean(|x|^2) — DC power fraction."),
        ("amp_q05/q25/q50/q75/q95", "quantiles of |x|."),
        ("papr_db", "10*log10(max(|x|^2)/mean(|x|^2))."),
        ("amp_skew / amp_kurt", "3rd standardized moment / excess kurtosis of |x|."),
    ]:
        lines.append("- `%s`: %s\n" % (k, d))

    lines.append("\n## I/Q joint structure\n")
    for k, d in [
        ("var_i / var_q / var_ratio", "var of real / imag; var_i/var_q (asymmetry)."),
        ("cov_iq / corr_iq", "covariance / Pearson corr of (real, imag)."),
        ("noncirc", "|E[x^2]| / E[|x|^2] — normalized pseudo-covariance."),
        ("pseudocov_mag / phase", "|E[x^2]| and arg(E[x^2])."),
    ]:
        lines.append("- `%s`: %s\n" % (k, d))
    lines.append("> I/Q asymmetry alone is NOT concluded as hardware IQ imbalance.\n")

    lines.append("\n## Spectral (unified window=Hann, FFT n=4096, fftshift)\n")
    for k, d in [
        ("centroid", "sum(f * Pn) — spectral centroid (cycles/sample)."),
        ("asym", "power(f>centroid) - power(f<centroid) — left/right asymmetry."),
        ("flatness", "exp(mean(log P))/mean P over P>0 bins; NO additive floor applied\n"
         "  (SPECTRAL_FLOOR_REL = 1e-12 is a reserved numeric constant, NOT used)."),
        ("bw99_cont", "**corrected 99% occupied bandwidth = full width of the smallest\n"
         "  symmetric interval [centroid-b, centroid+b] containing 99% of power\n"
         "  (CONTINUOUS interval, cycles/sample).**"),
        ("bw99", "OLD bin-count 99% bandwidth (fraction of FFT bins by descending power\n"
         "  cumsum) — kept SEPARATE, identical to threedomain audit_common."),
        ("bw20", "OLD bin-count 20 dB bandwidth (fraction of bins above peak/100)."),
        ("peak_freq / peak_to_floor_db", "argmax P freq; peak vs outer-band median."),
    ]:
        lines.append("- `%s`: %s\n" % (k, d))

    lines.append("\n## Time / phase\n")
    for k, d in [
        ("acorr_lag1..32", "normalized complex-autocorrelation MAGNITUDE "
         "|sum conj(x[n]) x[n-k]| / sum |x[n]|^2 (abs of the COMPLEX lagged inner "
         "product, NOT abs of its real part)."),
        ("acorr_half_lag", "first lag k where |acorr|<0.5."),
        ("phase_inc_mean/std", "adjacent-sample phase increment (linear mean/std)."),
        ("phase_inc_circ_mean/std", "circular mean/std of phase increment."),
        ("amp_roc_mean/std/q90", "|Δ|x|| amplitude rate of change."),
        ("seg_power_mean/std/cv/minmax", "8×128-sample segment RMS statistics."),
    ]:
        lines.append("- `%s`: %s\n" % (k, d))
    lines.append("\n**Phase low-amplitude rule (fixed before computing):** samples with\n"
                 "`|x| < 0.05*median(|x|)` are dropped from phase-increment statistics.\n")

    lines.append("\n## C sample counts per class\n")
    lines.append("| class | C tensors |\n|---|---|\n")
    for cls in range(ac.N_CLASSES):
        n = by_class_counts.get(cls, 0)
        lines.append("| %s | %s |\n" % (ac.LABEL_ORDER_24[cls],
                                         (str(n) if n else "INSUFFICIENT_DATA")))
    with open(os.path.join(ac.RESULTS, "metric_definitions.md"), "w", encoding="utf-8") as f:
        f.write("".join(lines))


# --------------------------------------------------------------------------
def main():
    c_samples, ident, inventory = phase1()
    a_feats, a_rows = phase2()
    per_sample = phase3(c_samples)
    phase4(per_sample, a_feats)
    phase5(per_sample, a_feats)
    phase6(per_sample, a_feats, ident)
    print("\nAUDIT_OK status=%s" % ac.STATUS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
