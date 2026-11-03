#!/usr/bin/env python3
"""Cross-check the real-vendor-FFT PSD dump against the NumPy reference.

The RTL applies the frozen Hann window bit-exactly (verified separately by
tb_smart_scan_framer) and the vendor XFFT 9.1 does its own fixed-point
arithmetic, so the FFT magnitudes are NOT expected to be bit-identical to a
float numpy FFT. What MUST hold exactly:

  * the peak bin (fftshift storage order) matches the NumPy reference -- a
    mirrored result (549<->475) means the transform ran inverse;
  * the spectra agree within a small relative tolerance everywhere.

Reads vectors/real_fft/<case>.psd_ref.hex and
evidence/real_fft_review_fix/psd_<case>.hex.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECDIR = os.path.join(ROOT, "vectors", "real_fft")
EVEDIR = os.path.join(ROOT, "evidence", "real_fft_review_fix")

# Tolerance on the magnitude-square. The vendor FFT truncates each butterfly,
# so a 1024-pt unscaled fixed-point transform carries a small absolute noise
# floor that is invisible near the peak but large next to the reference's tiny
# sidelobes. The honest metric is therefore per-frame: every bin must agree
# with the NumPy reference within ABS_TOL absolute plus REL_TOL *relative to the
# frame peak power*. (A per-bin relative error would falsely fail the near-zero
# sidelobe bins of a pure tone, where the fixed-point floor dominates.)
REL_TOL = 0.05          # 5% of the frame peak power
ABS_TOL = 1 << 12       # 4096 counts of u54 absolute floor for zero frames


def load_hex(path, width_bits):
    vals = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            vals.append(int(line, 16) & ((1 << width_bits) - 1))
    return np.asarray(vals, dtype=np.int64)


def main():
    manifest = json.load(open(os.path.join(VECDIR, "manifest.json"), encoding="utf-8"))
    n = manifest["fft_length"]
    fails = 0
    rows = []
    for name, meta in manifest["cases"].items():
        frames = meta["frames"]
        ref = load_hex(os.path.join(VECDIR, f"{name}.psd_ref.hex"), 64)
        dut = load_hex(os.path.join(EVEDIR, f"psd_{name}.hex"), 64)
        expect_len = frames * n
        if len(ref) != expect_len or len(dut) != expect_len:
            print(f"CHECK_REAL_FFT FAIL case={name} ref_len={len(ref)} "
                  f"dut_len={len(dut)} expect={expect_len}")
            fails += 1
            continue
        dut = dut.reshape(frames, n)
        ref = ref.reshape(frames, n)
        peak_check = meta.get("peak_check", True)
        peak_any_of = meta.get("peak_any_of", None)
        case_ok = True
        for fr in range(frames):
            peak_dut = int(np.argmax(dut[fr]))
            peak_ref = int(np.argmax(ref[fr]))
            diff = np.abs(dut[fr] - ref[fr]).astype(np.int64)
            max_abs = int(diff.max())
            # tolerance: absolute floor + REL_TOL relative to the frame peak
            ref_peak = float(ref[fr].max())
            tol = ABS_TOL + REL_TOL * ref_peak
            max_rel_peak = float(diff.max()) / ref_peak if ref_peak > 0 else 0.0
            if peak_check:
                if peak_any_of is not None:
                    peak_ok = peak_dut in peak_any_of
                else:
                    peak_ok = peak_dut == peak_ref
            else:
                # flat/zero spectra: no unique peak to compare, tolerance only
                peak_ok = True
            tol_ok = bool(np.all(diff <= tol))
            if not peak_ok or not tol_ok:
                case_ok = False
                fails += 1
                print(f"CHECK_REAL_FFT FAIL case={name} frame={fr} "
                      f"peak_dut={peak_dut} peak_ref={peak_ref} "
                      f"peak_any_of={peak_any_of} peak_check={peak_check} "
                      f"max_abs={max_abs} max_rel_peak={max_rel_peak:.4f} "
                      f"tol={tol:.1f}")
        rows.append((name, frames, meta["peak_bins_fftshift"],
                     [int(np.argmax(dut[f])) for f in range(frames)],
                     float(np.abs(dut - ref).max()),
                     float((np.abs(dut - ref).max()
                            / max(float(ref.max()), 1.0)))))
        if case_ok:
            print(f"CHECK_REAL_FFT PASS case={name} frames={frames} "
                  f"peaks_dut={[int(np.argmax(dut[f])) for f in range(frames)]} "
                  f"peaks_ref={meta['peak_bins_fftshift']} "
                  f"peak_check={peak_check} "
                  f"max_abs={rows[-1][4]:.1f} max_rel_peak={rows[-1][5]:.5f}")

    if fails:
        print(f"CHECK_REAL_FFT_NUMPY result=FAIL fails={fails}")
        sys.exit(1)
    print(f"CHECK_REAL_FFT_NUMPY result=PASS cases={len(manifest['cases'])} "
          f"rel_tol={REL_TOL}")


if __name__ == "__main__":
    main()
