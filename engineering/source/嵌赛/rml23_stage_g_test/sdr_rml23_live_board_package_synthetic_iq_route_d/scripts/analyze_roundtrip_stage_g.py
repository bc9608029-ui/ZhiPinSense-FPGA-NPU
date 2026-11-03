#!/usr/bin/env python3
"""analyze_roundtrip_stage_g.py -- Stage G route D (RadioML round-trip) analyzer.

Reads the artifacts written by the board's route D runner
(board_gate9_full_chain_rml23.cpp, --phase=synthetic-iq --source=radioml
--inject-point=raw-rx-reconstructed) and independently re-derives the A-vs-D
round-trip verdicts, so the board's in-board metrics get an independent host-side
cross-check (requirement 6) and a per-frame one-to-one A/D table is assembled
(requirement 8).  It NEVER chooses an I/Q transform and NEVER issues a PASS/FAIL
accuracy verdict -- attribution is measurement-only (requirement 5/attribution).

For every frame it computes, from the SAVED artifacts (not from board stdout):
  * time-delay cross-check (residual delay after the board's alignment),
  * optimal single complex gain/phase (least-squares over the valid centre),
  * NMSE full + centre, EVM, |correlation|, RMS / DC / PAPR,
  * PSD and 90/95/99% occupied bandwidth (wrap-corrected) for A and D,
  * I/Q-swap and conjugation correlation (diagnostic only),
  * A raw24 top-1 vs D raw24 top-1, 24-dim logits max_abs/mean_abs/cosine,
  * merged-23 (AM-SSB logaddexp) top-1 consistency and label preservation,
  * the same 7-way per-frame attribution the board applies,
  * D confusion matrix and per-SNR statistics,
  * SHA256 of every artifact file (cross-checked against the manifest).

Inputs:
  --out-dir DIR   the board's --roundtrip-out-dir (holds roundtrip_manifest.tsv
                  and the per-frame artifact files)
  --log LOG       (optional) producer stdout, to cross-check the board's reported
                  ROUNDTRIP_* metric lines against this independent re-derivation
  --energy-pcts   comma list (default 90,95,99)
  --json PATH     write full machine-readable JSON here

Pure stdlib + numpy.  Run isolated:  python -I analyze_roundtrip_stage_g.py ...
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys

import numpy as np

N_SAMPLES = 1024
FS_HZ = 128000.0
BIN_HZ = FS_HZ / N_SAMPLES  # 125.0 Hz/bin
EDGE_MARGIN = 32           # valid centre == [32, 1024-32), matches the board

# Frozen 24-class source order (== cat::target_24 / rml23::kSourceToDeployed).
SOURCE_TO_DEPLOYED = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
]
SOURCE_CLASS_INDEX = {
    "OOK": 0, "4ASK": 1, "8ASK": 2, "BPSK": 3, "QPSK": 4, "8PSK": 5,
    "16PSK": 6, "32PSK": 7, "16APSK": 8, "32APSK": 9, "64APSK": 10,
    "128APSK": 11, "16QAM": 12, "32QAM": 13, "64QAM": 14, "128QAM": 15,
    "256QAM": 16, "AM-SSB-WC": 17, "AM-SSB-SC": 18, "AM-DSB-WC": 19,
    "AM-DSB-SC": 20, "FM": 21, "GMSK": 22, "OQPSK": 23,
}
INDEX_TO_CLASS = {v: k for k, v in SOURCE_CLASS_INDEX.items()}
DEPLOYED_LABELS = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK",
    "OQPSK",
]

# Attribution thresholds -- identical to the board runner.
COSINE_CLOSE = 0.999
NMSE_SIGNIFICANT = 0.01
NMSE_INCONCLUSIVE = 0.1

_BOARD_ROUNDTRIP_RE = re.compile(
    r"ROUNDTRIP frame=(?P<frame>\d+).*?nmse_center=(?P<nmse>[0-9.eE+-]+)")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tensor(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype="<f4")
    if data.size != 2 * N_SAMPLES:
        raise ValueError("%s: %d floats, want %d" % (path, data.size, 2 * N_SAMPLES))
    return (data[:N_SAMPLES] + 1j * data[N_SAMPLES:]).astype(np.complex128)


def read_logits(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype="<f4")
    if data.size != 24:
        raise ValueError("%s: %d floats, want 24" % (path, data.size))
    return data.astype(np.float64)


def merge_24_to_23(raw24: np.ndarray) -> np.ndarray:
    """Replicate the board's rml23::merge_logits_23 (AM-SSB logaddexp)."""
    out = np.full(23, -np.inf, dtype=np.float64)
    out[:17] = raw24[:17]
    out[17] = np.logaddexp(raw24[18], raw24[17])   # fold SC into the WC slot
    out[18:23] = raw24[19:24]                       # dims 19..23 shift down
    return out


def occupied_bins_min_contig(power: np.ndarray, pct: int) -> int:
    """Minimum-width contiguous band (bins) holding pct% of total power, on the
    FFT-shifted spectrum (DC centred) -- wrap-corrected."""
    ps = np.fft.fftshift(np.asarray(power, dtype=np.float64))
    total = float(ps.sum())
    if total <= 0.0:
        return 0
    thr = total * (float(pct) / 100.0)
    prefix = np.concatenate(([0.0], np.cumsum(ps)))
    best = N_SAMPLES
    for lo in range(N_SAMPLES):
        j = int(np.searchsorted(prefix, prefix[lo] + thr, side="left"))
        if lo < j <= N_SAMPLES:
            w = j - lo
            if w < best:
                best = w
    return best


def align_and_measure(orig: np.ndarray, recov: np.ndarray):
    """Independent A-vs-D metrics (requirement 6).  orig and recov are the SAME
    length (1024); the board already aligned them, so a small residual-delay
    search ([-4, 4]) cross-checks that alignment and refines it.  g satisfies
    orig ~ g * recov."""
    lo, hi = EDGE_MARGIN, N_SAMPLES - EDGE_MARGIN

    best = {"d": 0, "g": 1.0 + 0j, "err": float("inf")}
    for d in range(-4, 5):
        o = orig[max(0, lo - d):min(N_SAMPLES, hi - d)]
        r = recov[max(0, lo - d) + d:min(N_SAMPLES, hi - d) + d]
        if o.size < 2 or r.size < 2:
            continue
        den = float(np.vdot(r, r).real)
        if den <= 1e-30:
            continue
        g = float(np.vdot(o, r).conjugate()) / den
        err = float(np.sum(np.abs(o - g * r) ** 2))
        if err < best["err"]:
            best = {"d": d, "g": g, "err": err}

    d = best["d"]
    g = best["g"]
    o = orig[max(0, lo - d):min(N_SAMPLES, hi - d)]
    r = recov[max(0, lo - d) + d:min(N_SAMPLES, hi - d) + d]
    den = float(np.vdot(r, r).real)
    g = (float(np.vdot(o, r).conjugate()) / den) if den > 1e-30 else 1.0 + 0j

    full_o = orig
    full_r = recov if d == 0 else np.roll(recov, d)
    err_f = np.sum(np.abs(full_o - g * full_r) ** 2)
    ref_f = np.sum(np.abs(full_o) ** 2)
    err_c = np.sum(np.abs(orig[lo:hi] - g * recov[lo + d:hi + d]) ** 2)
    ref_c = np.sum(np.abs(orig[lo:hi]) ** 2)

    nmse_c = (err_c / ref_c) if ref_c > 0 else 0.0
    nmse_f = (err_f / ref_f) if ref_f > 0 else 0.0
    cc = np.vdot(orig[lo:hi], recov[lo + d:hi + d])
    az = float(np.vdot(orig[lo:hi], orig[lo:hi]).real)
    ar = float(np.vdot(recov[lo + d:hi + d], recov[lo + d:hi + d]).real)
    corr = abs(cc) / np.sqrt(az * ar) if az * ar > 0 else 0.0

    def stats(x):
        e = float(np.mean(np.abs(x) ** 2))
        rms = float(np.sqrt(e))
        dc = float(abs(np.mean(x)))
        peak = float(np.max(np.abs(x) ** 2))
        papr = (10.0 * np.log10(peak / e)) if e > 0 else 0.0
        return rms, dc, papr

    rms_o, dc_o, papr_o = stats(orig)
    rms_r, dc_r, papr_r = stats(recov)
    swapped = recov[lo + d:hi + d].imag + 1j * recov[lo + d:hi + d].real
    cswap = abs(np.vdot(orig[lo:hi], swapped)) / np.sqrt(az * ar) if az * ar > 0 else 0.0
    cconj = abs(np.vdot(orig[lo:hi], np.conj(recov[lo + d:hi + d]))) / np.sqrt(az * ar) if az * ar > 0 else 0.0

    return {
        "delay_offset": d,
        "gain_db": 20.0 * np.log10(abs(g) + 1e-300),
        "phase_deg": float(np.angle(g) * 180.0 / np.pi),
        "nmse_full": nmse_f,
        "nmse_center": nmse_c,
        "evm_center_pct": 100.0 * np.sqrt(nmse_c),
        "corr_center": float(corr),
        "rms_orig": rms_o, "rms_recov": rms_r,
        "dc_orig": dc_o, "dc_recov": dc_r,
        "papr_orig_db": papr_o, "papr_recov_db": papr_r,
        "corr_swap": float(cswap), "corr_conj": float(cconj),
    }


def attribute(ac: bool, dc: bool, close: bool, nmse_c: float) -> str:
    if nmse_c > NMSE_INCONCLUSIVE:
        return "RADIOML_ROUNDTRIP_EDGE_INCONCLUSIVE"
    if ac and dc:
        return ("PREPROCESS_PRESERVES_RADIOML_DOMAIN" if close
                else "PRESERVED_LABEL_BUT_LOGITS_SHIFTED")
    if ac and not dc:
        return ("PREPROCESS_ROUNDTRIP_MISMATCH" if nmse_c > NMSE_SIGNIFICANT
                else "MODEL_INPUT_SENSITIVITY")
    if not ac and not dc:
        return "MODEL_FAILS_ON_RADIOML_HELDOUT"
    return "D_IMPROVED_OVER_A"


def self_test() -> int:
    n_pass = 0
    # OBW wrap-correction on a centred carrier.
    cw = np.exp(1j * 2.0 * np.pi * 0 * np.arange(N_SAMPLES) / N_SAMPLES)  # DC
    power = np.abs(np.fft.fft(cw)) ** 2
    w99 = occupied_bins_min_contig(power, 99)
    if w99 <= 2:
        n_pass += 1
        print("  OK  centred carrier OBW99 = %d bin (not saturated)" % w99)
    else:
        print("  BAD centred carrier OBW99 = %d (saturated)" % w99)

    # merge semantics: SC+WC fold, dims shift down.
    raw = np.arange(24, dtype=np.float64)
    m = merge_24_to_23(raw)
    ok = (m.size == 23 and m[17] == np.logaddexp(18.0, 17.0)
          and np.allclose(m[18:23], raw[19:24]) and np.allclose(m[:17], raw[:17]))
    if ok:
        n_pass += 1
        print("  OK  merge_24_to_23 (AM-SSB logaddexp + shift)")
    else:
        print("  BAD merge_24_to_23 -> %r" % m)
    print("self-test: %d/2 correct" % n_pass)
    return 0 if n_pass == 2 else 1


def parse_manifest(out_dir: str):
    rows = []
    mpath = os.path.join(out_dir, "roundtrip_manifest.tsv")
    with open(mpath, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            p = line.split("\t")
            if len(p) < 13:
                raise ValueError("bad manifest row: %r" % line)
            rows.append({
                "index": int(p[0]),
                "source_index": int(p[1]),
                "hdf5_label": int(p[2]),
                "snr_db": float(p[3]),
                "class_index": int(p[4]),
                "class_name": p[5],
                "original_file": p[6],
                "interp_file": p[7],
                "quant_file": p[8],
                "recovered_file": p[9],
                "raw24_a_file": p[10],
                "raw24_d_file": p[11],
                "original_sha256": p[12],
            })
    return header, rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--energy-pcts", default="90,95,99")
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.out_dir:
        ap.error("--out-dir is required unless --self-test is given")

    pcts = [int(x) for x in args.energy_pcts.split(",") if x.strip()]
    for p in pcts:
        if not (0 < p < 100):
            ap.error("--energy-pcts must be integers in (0,100): %r" % (p,))

    _, rows = parse_manifest(args.out_dir)
    if not rows:
        print("no frames in %s/roundtrip_manifest.tsv" % args.out_dir, file=sys.stderr)
        return 1

    board_metrics = {}
    if args.log and os.path.exists(args.log):
        with open(args.log, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _BOARD_ROUNDTRIP_RE.search(line)
                if m:
                    board_metrics[int(m.group("frame"))] = float(m.group("nmse"))

    frames = []
    attrib_all = {}
    confusion = {}
    src_total, src_correct = {}, {}
    snr_stat = {}
    raw24_agree = merged23_agree = a_correct = d_correct = 0

    print("analyze_roundtrip_stage_g: %d frames (independent host re-derivation)"
          % len(rows))
    print("  fs=%.0f Hz FFT=%d %.3f Hz/bin centre=[%d,%d)"
          % (FS_HZ, N_SAMPLES, BIN_HZ, EDGE_MARGIN, N_SAMPLES - EDGE_MARGIN))
    print("  attribution thresholds: cosine_close=%.3f nmse_significant=%.3f "
          "nmse_inconclusive=%.3f" % (COSINE_CLOSE, NMSE_SIGNIFICANT, NMSE_INCONCLUSIVE))

    for r in rows:
        idx = r["index"]
        orig = read_tensor(os.path.join(args.out_dir, r["original_file"]))
        recov = read_tensor(os.path.join(args.out_dir, r["recovered_file"]))
        raw_a = read_logits(os.path.join(args.out_dir, r["raw24_a_file"]))
        raw_d = read_logits(os.path.join(args.out_dir, r["raw24_d_file"]))

        m = align_and_measure(orig, recov)
        pow_o = np.abs(np.fft.fft(orig)) ** 2
        pow_r = np.abs(np.fft.fft(recov)) ** 2

        merged_a = merge_24_to_23(raw_a)
        merged_d = merge_24_to_23(raw_d)
        raw_a_top = int(np.argmax(raw_a))
        raw_d_top = int(np.argmax(raw_d))
        merged_a_top = int(np.argmax(merged_a))
        merged_d_top = int(np.argmax(merged_d))
        truth = SOURCE_TO_DEPLOYED[r["class_index"]]
        ac = merged_a_top == truth
        dc = merged_d_top == truth
        diff = raw_a - raw_d
        max_abs = float(np.max(np.abs(diff)))
        mean_abs = float(np.mean(np.abs(diff)))
        den = np.linalg.norm(raw_a) * np.linalg.norm(raw_d)
        cosine = float(np.dot(raw_a, raw_d) / den) if den > 0 else 0.0
        close = cosine >= COSINE_CLOSE
        rule = attribute(ac, dc, close, m["nmse_center"])

        # SHA256 of every artifact + cross-check against the manifest.
        shas = {}
        for key, fname in (("original", r["original_file"]),
                           ("interpolated", r["interp_file"]),
                           ("quantized", r["quant_file"]),
                           ("recovered", r["recovered_file"]),
                           ("raw24_a", r["raw24_a_file"]),
                           ("raw24_d", r["raw24_d_file"])):
            shas[key] = sha256_file(os.path.join(args.out_dir, fname))
        sha_ok = shas["original"] == r["original_sha256"]

        rec = {
            "index": idx, "source_index": r["source_index"],
            "class_index": r["class_index"], "class_name": r["class_name"],
            "snr_db": r["snr_db"], "label": DEPLOYED_LABELS[truth],
            "metrics": m,
            "occupied_a": {str(p): occupied_bins_min_contig(pow_o, p) for p in pcts},
            "occupied_d": {str(p): occupied_bins_min_contig(pow_r, p) for p in pcts},
            "raw24_a_top1": raw_a_top, "raw24_d_top1": raw_d_top,
            "merged_a_top1": merged_a_top, "merged_d_top1": merged_d_top,
            "a_correct": ac, "d_correct": dc,
            "logits_max_abs": max_abs, "logits_mean_abs": mean_abs,
            "logits_cosine": cosine,
            "merged_consistent": merged_a_top == merged_d_top,
            "sha256": shas, "original_sha_ok": sha_ok,
            "attribution": rule,
            "board_nmse_center": board_metrics.get(idx),
        }
        frames.append(rec)

        raw24_agree += (raw_a_top == raw_d_top)
        merged23_agree += (merged_a_top == merged_d_top)
        a_correct += ac
        d_correct += dc
        attrib_all[rule] = attrib_all.get(rule, 0) + 1
        confusion.setdefault(r["class_index"], {})[merged_d_top] = \
            confusion[r["class_index"]].get(merged_d_top, 0) + 1
        src_total[r["class_index"]] = src_total.get(r["class_index"], 0) + 1
        src_correct[r["class_index"]] = src_correct.get(r["class_index"], 0) + int(dc)
        ss = snr_stat.setdefault(r["snr_db"], {"total": 0, "a_ok": 0, "d_ok": 0})
        ss["total"] += 1
        ss["a_ok"] += int(ac)
        ss["d_ok"] += int(dc)

    # Per-frame one-to-one table (requirement 8).
    for f in frames:
        m = f["metrics"]
        occ = " ".join("%d%%=%d" % (p, f["occupied_a"][str(p)]) for p in pcts)
        occd = " ".join("%d%%=%d" % (p, f["occupied_d"][str(p)]) for p in pcts)
        b = ""
        if f["board_nmse_center"] is not None:
            b = " board_nmse=%.3e" % f["board_nmse_center"]
        print("  frame=%d %s snr=%.1f delay=%d gain=%.4fdB ph=%.3fdeg "
              "nmse_f=%.3e nmse_c=%.3e evm=%.4f%% corr=%.6f "
              "corr_swap=%.4f corr_conj=%.4f "
              "rms=%.4f/%.4f dc=%.4f/%.4f papr=%.2f/%.2f "
              "OBW_A{%s} OBW_D{%s} "
              "raw24_A=%d raw24_D=%d merged_A=%d merged_D=%d label=%s "
              "A_ok=%d D_ok=%d mxd=%.4f mnd=%.4f cos=%.6f "
              "consistent=%d sha_ok=%d%s -> %s"
              % (f["index"], f["class_name"], f["snr_db"], m["delay_offset"],
                 m["gain_db"], m["phase_deg"], m["nmse_full"], m["nmse_center"],
                 m["evm_center_pct"], m["corr_center"],
                 m["corr_swap"], m["corr_conj"],
                 m["rms_orig"], m["rms_recov"], m["dc_orig"], m["dc_recov"],
                 m["papr_orig_db"], m["papr_recov_db"], occ, occd,
                 f["raw24_a_top1"], f["raw24_d_top1"],
                 f["merged_a_top1"], f["merged_d_top1"], f["label"],
                 f["a_correct"], f["d_correct"],
                 f["logits_max_abs"], f["logits_mean_abs"], f["logits_cosine"],
                 f["merged_consistent"], f["original_sha_ok"], b,
                 f["attribution"]))

    # D confusion matrix + per-SNR + attribution summary (requirement 9).
    print("== D confusion (src_class -> pred23) ==")
    for ci in sorted(confusion):
        print("  src_class=%d(%s) total=%d correct23=%d" %
              (ci, INDEX_TO_CLASS[ci], src_total[ci], src_correct[ci]))
        for pred, cnt in sorted(confusion[ci].items()):
            print("    pred23=%d(%s)=%d" % (pred, DEPLOYED_LABELS[pred], cnt))
    print("== per-SNR (A correct / D correct) ==")
    for snr in sorted(snr_stat):
        s = snr_stat[snr]
        print("  snr=%.1f total=%d a_correct=%d d_correct=%d" %
              (snr, s["total"], s["a_ok"], s["d_ok"]))
    print("== attribution summary ==")
    for rule in sorted(attrib_all):
        print("  %s count=%d" % (rule, attrib_all[rule]))
    print("== aggregate ==")
    print("  frames=%d raw24_agree=%d merged23_agree=%d a_correct=%d d_correct=%d"
          % (len(frames), raw24_agree, merged23_agree, a_correct, d_correct))
    bad_sha = [f["index"] for f in frames if not f["original_sha_ok"]]
    if bad_sha:
        print("  ORIGINAL_SHA_MISMATCH frames=%s" % bad_sha, file=sys.stderr)

    if args.json:
        out = {
            "num_frames": len(frames), "energy_pcts": pcts,
            "aggregate": {"raw24_agree": raw24_agree, "merged23_agree": merged23_agree,
                          "a_correct": a_correct, "d_correct": d_correct},
            "attribution": attrib_all,
            "per_snr": snr_stat,
            "frames": frames,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print("wrote %s" % args.json)

    return 0 if not bad_sha else 1


if __name__ == "__main__":
    sys.exit(main())
