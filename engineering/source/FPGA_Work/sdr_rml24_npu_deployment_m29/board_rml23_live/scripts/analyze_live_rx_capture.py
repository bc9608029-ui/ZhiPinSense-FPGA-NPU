#!/usr/bin/env python3
"""analyze_live_rx_capture.py -- errata 39e5 Stage D analysis tool (OBW fix).

Reads the atomic tensor captures written by the live-rx producer's capture hook
(`--capture-dir`, see board_package/capture_hook.hpp) and computes the
THEORETICAL occupied bandwidth at 90/95/99% of total FFT power.

OBW algorithm (corrected, errata 39e5 #8):
    The previous `occupied_bins_min_contig` searched for a minimum-width
    CONTIGUOUS band in the RAW 0..N_FFT-1 FFT index space.  The live-rx NCO
    centres the carrier near DC, and ``np.fft.fft`` places DC at BIN 0 with the
    negative-frequency half at the TOP of the array -- so a centred narrowband
    carrier straddles the array's wrap point (bins ~958..1023 AND ~0..86).  A
    non-circular contiguous band must then span nearly the whole array to cover
    both halves, which is exactly why a clean 16 kBaud QPSK was mis-reported as
    ~128 kHz full bandwidth.

    The fix FFT-SHIFTS the spectrum (DC to the centre) before the minimum-width
    contiguous search, so a centred carrier is contiguous and the search returns
    its true width.  This reproduces the independent DSP re-check (90/95/99% OBW
    ~15.1/16.5/18.6 kHz for the 16 kBaud RRC QPSK capture) instead of saturating.

power metric (corrected, errata 39e5 #8):
    The previous `power_dbfs` applied ``10*log10`` to the SCALED model-domain
    tensor.  That tensor is already past the receiver scale, so it has no
    ADC-full-scale reference and "dBFS" is meaningless.  This tool now reports
    the linear complex RMS and ``10*log10(mean power)`` labelled as
    ``power_db_re_unit`` (relative to a unit-RMS reference), never "dBFS".

Inputs:
  --capture-dir DIR   directory of live_rx_tensor_<frame_id>.f32 files
                      (8192 B each: [2,1024] fp32 little-endian, plane0=I, plane1=Q)
  --log LOG           (optional) producer stdout (capture + result lines)
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

    Operates on the FFT-SHIFTED spectrum (DC at the centre), so a carrier that the
    NCO centres near DC is contiguous and its true width is returned.  This is the
    errata-39e5 #8 correction: the raw 0..1023 index order made a centred carrier
    wrap and saturate to ~1024 bins (full 128 kHz).
    """
    ps = np.fft.fftshift(np.asarray(power, dtype=np.float64))
    total = float(ps.sum())
    if total <= 0.0:
        return 0
    thr = total * (float(pct) / 100.0)
    prefix = np.concatenate(([0.0], np.cumsum(ps)))
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


def _synthesize_qpsk_rrc(n_sym=160, sps=8, beta=0.35, nsym_taps=12, seed=0):
    """Synthesize a 16 kBaud RRC-shaped QPSK burst (sps samples/symbol, fs=128 kHz).

    sps=8 => symbol rate = 128e3/8 = 16 kBaud, matching the external QPSK signal
    under test.  Returns a complex array of length n_sym*sps (>= N_FFT).
    """
    rng = np.random.RandomState(seed)
    syms = (2 * rng.randint(0, 2, n_sym) - 1) + 1j * (2 * rng.randint(0, 2, n_sym) - 1)
    syms = syms / np.sqrt(2.0)          # unit mean power per symbol
    x = np.zeros(n_sym * sps, dtype=np.complex128)
    x[::sps] = syms
    # RRC pulse, h(t) = (sin(pi t(1-b)) + 4 b t cos(pi t(1+b))) / (pi t (1-(4bt)^2))
    t = np.arange(-nsym_taps * sps, nsym_taps * sps + 1, dtype=np.float64) / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        num = np.sin(np.pi * t * (1 - beta)) + 4 * beta * t * np.cos(np.pi * t * (1 + beta))
        den = np.pi * t * (1 - (4 * beta * t) ** 2)
        h = np.where(np.abs(t) < 1e-12, (1 - beta) + 4 * beta / np.pi, num / den)
    h = h / np.sqrt(np.sum(h ** 2))     # unit-energy pulse
    return np.convolve(x, h, mode="same")


def self_test():
    """Deterministic self-check of occupied_bins_min_contig.

    Includes a synthetic 16 kBaud RRC beta=0.35 QPSK (errata 39e5 #8): the 90%
    OBW must land near the symbol rate and the 99% OBW near Rs*(1+beta), and BOTH
    must be far below the 128 kHz full bandwidth.  A centred narrowband carrier
    must never saturate to 1024 bins.
    """
    cases = []
    # (name, power_spectrum, pred(widths_90_95_99) -> bool)
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

    # errata 39e5 #8: a centred narrowband carrier straddles the wrap point.  The
    # corrected estimator must return its true width, NOT the full 1024 bins.
    centred_cw = power_spectrum(_synthesize_cw(0))
    cases.append(("centred CW at DC (wrap) -> ~1 bin, NOT full", centred_cw,
                  lambda w: w[2] <= 2))

    # errata 39e5 #8: synthetic 16 kBaud RRC beta=0.35 QPSK.
    qpsk = _synthesize_qpsk_rrc()
    q = qpsk[:N_FFT]                      # one 1024-sample frame
    pq = power_spectrum(q)
    rs = FS_HZ / 8.0                      # 16 kBaud
    def qpsk_pred(w):
        bw90 = w[0] * BIN_HZ
        bw99 = w[2] * BIN_HZ
        # 90% OBW ~ Rs, 99% OBW ~ Rs*(1+beta); both far below 128 kHz.
        ok90 = rs * 0.6 <= bw90 <= rs * 1.4
        ok99 = rs * (1 + 0.35) * 0.85 <= bw99 <= rs * (1 + 0.35) * 1.25
        return ok90 and ok99 and bw99 < FS_HZ / 2
    cases.append(("16kBaud RRC b=0.35 QPSK -> ~Rs..Rs(1+b) BW", pq, qpsk_pred))

    n_pass = 0
    for name, power, pred in cases:
        widths = [occupied_bins_min_contig(power, p) for p in (90, 95, 99)]
        if pred(widths):
            n_pass += 1
            print("  OK  %-44s 90%%=%d 95%%=%d 99%%=%d"
                  % (name, widths[0], widths[1], widths[2]))
        else:
            print("  BAD %-44s widths=%s (%.2f/%.2f/%.2f kHz)"
                  % (name, widths,
                     widths[0] * BIN_HZ / 1e3, widths[1] * BIN_HZ / 1e3,
                     widths[2] * BIN_HZ / 1e3))
    print("self-test: %d/%d correct" % (n_pass, len(cases)))
    return 0 if n_pass == len(cases) else 1


def parse_log(path):
    """Return (caps, results) from the producer stdout log."""
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
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        rec = {
            "frame_id": fid,
            "file": name,
            "sha256": sha,
            # errata 39e5 #8: linear RMS + power re-unit-1.0 (NOT dBFS -- the
            # captured tensor is already past the receiver scale).
            "rms": rms,
            "power_db_re_unit": float(10.0 * np.log10(total / N_FFT + 1e-300))
                if total > 0 else -200.0,
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
    print("  (fs=%.0f Hz, FFT=%d, %.3f Hz/bin; DC-centred, wrap-corrected)"
          % (FS_HZ, N_FFT, BIN_HZ))
    for p in pcts:
        s = summary["occupied_bins"][str(p)]
        print("  occupied_bins_%d%%  min=%d median=%.1f max=%d  (%.3f Hz/bin)"
              % (p, s["min"], s["median"], s["max"], BIN_HZ))
    mism = [f["frame_id"] for f in frames if f.get("sha_verified") is False]
    if mism:
        print("  SHA MISMATCH on frames: %s" % mism, file=sys.stderr)
    for f in frames:
        occ = " ".join("%d%%=%d" % (p, f["occupied"][str(p)]) for p in pcts)
        line = "  frame=%d rms=%.4f power_db=%.2f %s" % (
            f["frame_id"], f["rms"], f["power_db_re_unit"], occ)
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
