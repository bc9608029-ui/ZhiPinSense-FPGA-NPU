#!/usr/bin/env python3
"""analyze_live_rx_capture.py -- errata 39e5 Stage D analysis tool.

Reads the atomic tensor captures written by the live-rx producer's capture hook
(`--capture-dir`, see board_package/capture_hook.hpp) and computes the
THEORETICAL occupied bandwidth at 90/95/99% of total FFT power, per Evidence 5.

Evidence 5 root cause: `sdr::DspMeasure.occupied_bins` counts the contiguous
[min_bin, max_bin] span of bins whose power exceeds `noise_floor *
10^(occupied_threshold_db/10)`.  Under a strong signal the estimated noise floor
collapses, the threshold collapses with it, and the span saturates at 1024
(== the full FFT length).  That counter is a *threshold* detector, not a
bandwidth estimator.

This tool does NOT trust that saturated counter.  It recomputes the occupied
bandwidth from first principles on the exact captured tensor: the minimum-width
contiguous FFT band that contains X% of the frame's total power (X in 90/95/99).
This is the standard "X% power / occupied bandwidth" (OBW) definition, and it is
immune to the threshold-saturation failure: a pure tone stays ~1 bin, a spread
signal widens, and only genuinely full-spectrum noise approaches 1024.

Inputs:
  --capture-dir DIR   directory of live_rx_tensor_<frame_id>.f32 files
                      (8192 B each: [2,1024] fp32 little-endian, plane0=I, plane1=Q)
  --log LOG           (optional) the producer's stdout.  Used two ways:
                        * "LIVE_RX_CAPTURE frame=N sha256=... presence=..." lines
                          verify each captured file's SHA-256 and attach presence;
                        * "type":"result" JSON-lines attach argmax_idx/class and
                          confidence per frame_id for the classification trajectory.
  --energy-pcts       comma list (default 90,95,99)
  --json PATH         (optional) write full machine-readable JSON here

Pure stdlib + numpy.  Run isolated:  python -I analyze_live_rx_capture.py ...

This is a DIAGNOSTIC tool: it reports theoretical occupied bandwidth, never a
PASS/FAIL verdict, and never modifies the model/golden/labels.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys

import numpy as np

FS_HZ = 128000.0        # model-domain sample rate (FROZEN contract)
N_FFT = 1024            # samples per frame / FFT length
BIN_HZ = FS_HZ / N_FFT  # 125.0 Hz per bin

_CAP_RE = re.compile(
    r"LIVE_RX_CAPTURE frame=(?P<frame>\d+) bytes=\d+ "
    r"sha256=(?P<sha>[0-9a-f]+) presence=(?P<presence>\S+)")


def read_tensor(path):
    """Read an 8192-byte [2,1024] fp32 tensor -> complex64 array of length 1024."""
    data = np.fromfile(path, dtype="<f4")
    if data.size != 2 * N_FFT:
        raise ValueError(
            "tensor %s has %d floats, want %d" % (path, data.size, 2 * N_FFT))
    return (data[:N_FFT] + 1j * data[N_FFT:]).astype(np.complex128)


def power_spectrum(x):
    """Complex FFT power spectrum (full 1024 bins, not folded)."""
    return np.abs(np.fft.fft(x)) ** 2


def occupied_bins_min_contig(power, pct):
    """Minimum-width contiguous band (bin count) containing pct% of total power.

    Non-circular over the 0..N_FFT-1 FFT bins (the live-rx NCO centres the signal,
    so the band does not wrap).  Deterministic: prefix sums + searchsorted.
    """
    total = float(power.sum())
    if total <= 0.0:
        return 0
    thr = total * (float(pct) / 100.0)
    prefix = np.concatenate(([0.0], np.cumsum(power)))
    best = N_FFT
    for lo in range(N_FFT):
        j = int(np.searchsorted(prefix, prefix[lo] + thr, side="left"))
        if j <= N_FFT and j > lo:
            w = j - lo
            if w < best:
                best = w
    return best


def _synthesize_cw(bin_idx, amp=1000.0, n=N_FFT):
    """Return a complex tone at FFT bin `bin_idx` (integer bins only)."""
    t = np.arange(n, dtype=np.float64)
    return amp * np.exp(1j * 2.0 * np.pi * bin_idx * t / n)


def self_test():
    """Deterministic self-check of occupied_bins_min_contig on synthetic signals.

    Only proves the *theoretical* estimator is correct; it never touches a real
    capture and never emits a PASS/FAIL verdict about the board.
    """
    cases = []
    # Each case is (name, power_spectrum, pred) where pred(widths)->bool with
    # widths = [90%, 95%, 99%] occupied bin counts.  A pure tone must collapse
    # to ~1 bin (NOT saturate to 1024); spread / noise must widen monotonically.
    cw = power_spectrum(_synthesize_cw(100))
    cases.append(("pure tone bin=100 -> ~1 bin", cw, lambda w: w[2] <= 2))

    two = power_spectrum(_synthesize_cw(100) + _synthesize_cw(160))
    cases.append(("two tones 60 bins apart -> spans gap", two,
                  lambda w: w[0] >= 59 and w[2] >= w[0]))

    uni = power_spectrum(np.random.RandomState(0).standard_normal(N_FFT)
                         + 1j * np.random.RandomState(1).standard_normal(N_FFT))
    cases.append(("white noise -> wideband (NOT saturated)", uni,
                  lambda w: w[0] > N_FFT // 4 and w[2] >= w[0]))

    dc = power_spectrum(np.full(N_FFT, 1000.0 + 0j))
    cases.append(("DC -> 1 bin", dc, lambda w: w[2] <= 2))

    zero = power_spectrum(np.zeros(N_FFT, dtype=np.complex128))
    cases.append(("all-zero -> 0 (no power)", zero, lambda w: w[2] == 0))

    n_pass = 0
    for name, power, pred in cases:
        widths = [occupied_bins_min_contig(power, p) for p in (90, 95, 99)]
        if pred(widths):
            n_pass += 1
            print("  OK  %-38s 90%%=%d 95%%=%d 99%%=%d"
                  % (name, widths[0], widths[1], widths[2]))
        else:
            print("  BAD %-38s widths=%s" % (name, widths))
    print("self-test: %d/%d correct" % (n_pass, len(cases)))
    return 0 if n_pass == len(cases) else 1


def parse_log(path):
    """Return (caps, results) from the producer stdout log.

    caps:    {frame_id: {"sha256": hex, "presence": str}}
    results: {frame_id: {"argmax_idx": int, "argmax_class": str,
                         "confidence": float, "raw_24_top1": int}}
    """
    caps = {}
    results = {}
    if not path:
        return caps, results
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            m = _CAP_RE.search(line)
            if m:
                caps[int(m.group("frame"))] = {
                    "sha256": m.group("sha"), "presence": m.group("presence")}
                continue
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "result":
                continue
            fid = rec.get("frame_id")
            if fid is None:
                continue
            results[int(fid)] = {
                "argmax_idx": rec.get("argmax_idx"),
                "argmax_class": rec.get("argmax_class"),
                "confidence": rec.get("confidence"),
                "raw_24_top1": rec.get("raw_24_top1"),
            }
    return caps, results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--energy-pcts", default="90,95,99")
    ap.add_argument("--json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.capture_dir:
        ap.error("--capture-dir is required unless --self-test is given")

    pcts = [int(x) for x in args.energy_pcts.split(",") if x.strip()]
    for p in pcts:
        if not (0 < p < 100):
            ap.error("--energy-pcts must be integers in (0,100): %r" % (p,))

    paths = sorted(glob.glob(os.path.join(args.capture_dir, "live_rx_tensor_*.f32")))
    if not paths:
        print("no live_rx_tensor_*.f32 files under %s" % args.capture_dir,
              file=sys.stderr)
        return 1

    caps, results = parse_log(args.log)

    frames = []
    for path in paths:
        name = os.path.basename(path)
        fid = int(name[len("live_rx_tensor_"):-len(".f32")])
        raw = open(path, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()
        x = read_tensor(path)
        power = power_spectrum(x)
        total = float(power.sum())
        rec = {
            "frame_id": fid,
            "file": name,
            "sha256": sha,
            "power_dbfs": float(
                10.0 * np.log10(total / N_FFT + 1e-300)) if total > 0 else -200.0,
            "occupied": {str(p): occupied_bins_min_contig(power, p) for p in pcts},
            "occupied_bw_hz": {
                str(p): occupied_bins_min_contig(power, p) * BIN_HZ for p in pcts},
        }
        if fid in caps:
            if caps[fid]["sha256"] == sha:
                rec["sha_verified"] = True
            else:
                rec["sha_verified"] = False
                rec["sha_mismatch"] = caps[fid]["sha256"]
            rec["presence"] = caps[fid]["presence"]
        if fid in results:
            rec["result"] = results[fid]
        frames.append(rec)

    # Summary: median occupied bins per energy target, and the min/max spread.
    summary = {"num_frames": len(frames), "energy_pcts": pcts, "occupied_bins": {}}
    for p in pcts:
        bins = [f["occupied"][str(p)] for f in frames]
        summary["occupied_bins"][str(p)] = {
            "min": int(min(bins)), "max": int(max(bins)),
            "median": float(np.median(bins)),
        }

    # Human-readable report.
    print("analyze_live_rx_capture: %d frames, theoretical occupied bandwidth"
          % len(frames))
    print("  (fs=%.0f Hz, FFT=%d, %.3f Hz/bin; THEORETICAL, not the saturated "
          "DspMeasure counter)" % (FS_HZ, N_FFT, BIN_HZ))
    for p in pcts:
        s = summary["occupied_bins"][str(p)]
        print("  occupied_bins_%d%%  min=%d median=%.1f max=%d  (%.3f Hz/bin)"
              % (p, s["min"], s["median"], s["max"], BIN_HZ))
    mism = [f["frame_id"] for f in frames if f.get("sha_verified") is False]
    if mism:
        print("  SHA MISMATCH on frames: %s" % mism, file=sys.stderr)
    for f in frames:
        occ = " ".join("%d%%=%d" % (p, f["occupied"][str(p)]) for p in pcts)
        line = "  frame=%d power_dbfs=%.2f %s" % (f["frame_id"], f["power_dbfs"], occ)
        if f.get("presence"):
            line += " presence=%s" % f["presence"]
        if f.get("result"):
            r = f["result"]
            line += " argmax=%d(%s) conf=%.3f raw24=%s" % (
                r["argmax_idx"], r["argmax_class"], r["confidence"], r["raw_24_top1"])
        print(line)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "frames": frames}, f, indent=2)
        print("wrote %s" % args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
