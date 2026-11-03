#!/usr/bin/env python3
"""Generate stimulus + NumPy reference for the real-vendor-FFT testbench.

The testbench drives `smart_scan_top` (Hann framer -> Xilinx XFFT 9.1 sim netlist
-> u54 magnitude-square -> fftshift double buffer). This generator emits, for each
deterministic case:

  vectors/real_fft/<case>.stim.hex   -- raw int16 IQ stimulus, one {Q[15:0],I[15:0]}
                                         32-bit hex word per line (concatenated frames)
  vectors/real_fft/<case>.psd_ref.hex -- NumPy reference PSD in fftshift storage
                                         order, one 64-bit hex word per line
                                         (54-bit power, high 10 bits zero)

The reference PSD uses the *same* Hann window and the frozen rounding口径
(`window_iq`, round-away) as the RTL, but a float numpy FFT. The vendor FFT has
its own internal fixed-point rounding, so the cross-check is tolerance-based; the
peak bins, however, must match exactly (integer-bin tones are unambiguous).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "reference"))
from smart_scan_golden import window_iq  # noqa: E402

N = 1024
FS = 2_560_000


def round_away(x):
    x = np.asarray(x, dtype=np.float64)
    return (np.sign(x) * np.floor(np.abs(x) + 0.5)).astype(np.int64)


def r16(x):
    x = np.asarray(x, dtype=np.float64)
    return np.clip(round_away(x), -32768, 32767).astype(np.int16)


def tone(bin_, amp=10000.0, phase_deg=0.0, conj=False):
    th = 2.0 * np.pi * bin_ * np.arange(N) / N + np.deg2rad(phase_deg)
    re = amp * np.cos(th)
    im = amp * np.sin(th)
    if conj:
        im = -im
    return np.column_stack((r16(re), r16(im)))


def ref_psd(iq):
    """NumPy reference PSD in fftshift storage order (u54, int64)."""
    y = window_iq(iq).astype(np.int64)  # bit-exact windowed int16
    z = y[:, 0].astype(np.float64) + 1j * y[:, 1].astype(np.float64)
    X = np.fft.fft(z)
    re = round_away(X.real)
    im = round_away(X.imag)
    if np.any(np.abs(re) >= (1 << 26)) or np.any(np.abs(im) >= (1 << 26)):
        raise OverflowError("unscaled FFT exceeds signed-27 boundary")
    power = (re * re + im * im).astype(np.int64)
    if np.any(power < 0) or np.any(power > (1 << 54) - 1):
        raise OverflowError("PSD exceeds unsigned-54 boundary")
    idx = np.arange(N)
    stored = power[idx ^ (N // 2)]  # stored[j] = natural power[j ^ 512]
    return stored


def _hex32(i, q):
    return f"{(int(q) & 0xFFFF) << 16 | (int(i) & 0xFFFF):08X}"


def _hex64(v):
    return f"{int(v) & ((1 << 64) - 1):016X}"


def build_cases():
    cases = {}

    cases["tone_pos37"] = tone(37, 10000.0)
    cases["tone_neg37"] = tone(37, 10000.0, conj=True)
    cases["tone_dc"] = np.full((N, 2), (10000, 0), dtype=np.int16)
    cases["tone_bin511"] = tone(511, 10000.0)
    # dual tone: +37 and -37 with equal amplitude -> real cosine, two peaks
    c = tone(37, 8000.0)
    cc = tone(37, 8000.0, conj=True)
    cases["dual_tone"] = np.column_stack(
        (np.clip(c[:, 0].astype(np.int32) + cc[:, 0].astype(np.int32), -32768, 32767),
         np.clip(c[:, 1].astype(np.int32) + cc[:, 1].astype(np.int32), -32768, 32767))
    ).astype(np.int16)
    # impulse at the Hann peak (k=511) -> flat spectrum
    pulse = np.zeros((N, 2), dtype=np.int16)
    pulse[512, 0] = 10000
    cases["pulse"] = pulse
    rng = np.random.default_rng(20261028)
    cases["random"] = rng.integers(-32768, 32768, size=(N, 2)).astype(np.int16)

    # three back-to-back positive tones (multi-frame)
    t = tone(37, 10000.0)
    cases["multi_frame"] = np.vstack([t, t, t])

    # all-zero frame: the pipeline must emit an all-zero PSD with no fault
    cases["zero"] = np.zeros((N, 2), dtype=np.int16)

    return cases


def main():
    outdir = os.path.join(ROOT, "vectors", "real_fft")
    os.makedirs(outdir, exist_ok=True)

    cases = build_cases()
    # Per-case peak-check policy:
    #   peak_check=True   -> peak_dut must equal peak_ref (or peak_any_of)
    #   peak_check=False  -> flat/zero spectra with no meaningful unique peak;
    #                        only the tolerance check applies.
    peak_policy = {
        "tone_pos37":   {"peak_check": True},
        "tone_neg37":   {"peak_check": True},
        "tone_dc":      {"peak_check": True},
        "tone_bin511":  {"peak_check": True},
        "dual_tone":    {"peak_check": True, "peak_any_of": [549, 475]},
        "pulse":        {"peak_check": False},
        "random":       {"peak_check": True},
        "multi_frame":  {"peak_check": True},
        "zero":         {"peak_check": False},
    }
    manifest = {"fft_length": N, "sample_rate_hz": FS, "cases": {}}
    for name, iq in cases.items():
        frames = iq.shape[0] // N
        assert iq.shape[0] == frames * N and iq.shape[1] == 2
        # stimulus
        stim_path = os.path.join(outdir, f"{name}.stim.hex")
        with open(stim_path, "w", newline="\n") as f:
            f.write("\n".join(_hex32(i, q) for i, q in iq) + "\n")
        # reference PSD (concatenated frames)
        ref_path = os.path.join(outdir, f"{name}.psd_ref.hex")
        refs = []
        peaks = []
        for fr in range(frames):
            psd = ref_psd(iq[fr * N:(fr + 1) * N])
            refs.extend(int(v) for v in psd)
            peaks.append(int(np.argmax(psd)))
        with open(ref_path, "w", newline="\n") as f:
            f.write("\n".join(_hex64(v) for v in refs) + "\n")
        meta = {
            "frames": frames,
            "peak_bins_fftshift": peaks,
        }
        meta.update(peak_policy[name])
        manifest["cases"][name] = meta
        print(f"REAL_FFT_VECTOR name={name} frames={frames} "
              f"peak_bins={peaks} policy={peak_policy[name]}")

    manifest_path = os.path.join(outdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"GEN_REAL_FFT_VECTORS result=PASS cases={len(cases)}")


if __name__ == "__main__":
    main()
