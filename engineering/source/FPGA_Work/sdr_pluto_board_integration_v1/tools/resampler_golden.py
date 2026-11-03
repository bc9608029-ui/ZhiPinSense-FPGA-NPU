#!/usr/bin/env python3
# resampler_golden.py -- numpy float64 reference for the streaming resampler.
#
# Generates deterministic canonical inputs (in-band tones + an out-of-band alias
# probe) and their reference resampled outputs using the SAME FIR coefficients as
# the C++ build (tools/fir_coeffs.json == sdr_adapter/fir_coeffs.h).  The C++
# host test test_resampler loads these inputs, runs the streaming resampler, and
# compares its output to the reference within a tolerance.
#
# Reference implements the polyphase identity exactly:
#     y[m] = sum_k h[r + k*up] * x[i - k],   i = floor(m*down/up), r = (m*down) % up
# with zero-fill outside the input, then discards the first (N-1) outputs
# (N = total taps) as startup transient -- matching resampler.cpp.

import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.abspath(os.path.join(HERE, "..", "host_tests", "golden"))
OS = os  # keep import for clarity


def load_coeffs(name):
    with open(os.path.join(HERE, "fir_coeffs.json")) as f:
        d = json.load(f)
    for s in d["specs"]:
        if s["name"] == name:
            return np.array(s["coeffs"], dtype=np.float64), s
    raise KeyError(name)


def reference(x, up, down, coeffs):
    n = len(coeffs)          # N = up * p
    p = n // up
    n_in = len(x)
    m = (n_in * up - 1) // down + 1  # number of outputs before transient discard
    idx = np.arange(m, dtype=np.int64)
    r = (idx * down) % up
    i = (idx * down) // up
    y = np.zeros(m, dtype=np.complex128)
    for k in range(p):
        pos = i - k                         # input index for tap k (i = floor(m*down/up))
        valid = (pos >= 0) & (pos < n_in)
        xv = np.zeros(m, dtype=np.complex128)
        xv[valid] = x[pos[valid]]
        y += coeffs[r + k * up] * xv
    return y[n - 1:]                        # discard N-1 transient samples


def make_input(fs_in, n_in):
    n = np.arange(n_in, dtype=np.float64)
    # in-band tones (preserved) + out-of-band probe (must be suppressed)
    return (0.6 * np.exp(2j * np.pi * 10000.0 / fs_in * n)
            + 0.35 * np.exp(2j * np.pi * 30000.0 / fs_in * n)
            + 0.9 * np.exp(2j * np.pi * 200000.0 / fs_in * n))


def main():
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    cases = [
        dict(name="2p56M", fs_in_hz=2_560_000, n_in=51_200),
        dict(name="3p84M", fs_in_hz=3_840_000, n_in=76_800),
    ]
    manifest = dict(fs_out_hz=128_000, cases=[])
    for c in cases:
        coeffs, spec = load_coeffs(c["name"])
        up, down = spec["up"], spec["down"]
        x = make_input(c["fs_in_hz"], c["n_in"])
        y = reference(x, up, down, coeffs)
        inp = os.path.join(GOLDEN_DIR, f"resampler_{c['name']}_input.bin")
        out = os.path.join(GOLDEN_DIR, f"resampler_{c['name']}_output.bin")
        x.astype(np.complex128).tofile(inp)
        y.astype(np.complex128).tofile(out)
        entry = dict(name=c["name"], fs_in_hz=c["fs_in_hz"], up=up, down=down,
                     n_in=int(x.size), n_out=int(y.size), transient=int(len(coeffs) - 1),
                     input_file=os.path.relpath(inp, GOLDEN_DIR),
                     output_file=os.path.relpath(out, GOLDEN_DIR))
        manifest["cases"].append(entry)
        print(f"[{c['name']}] n_in={x.size} n_out={y.size} transient={len(coeffs)-1}")

    with open(os.path.join(GOLDEN_DIR, "resampler_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("wrote", os.path.join(GOLDEN_DIR, "resampler_manifest.json"))


if __name__ == "__main__":
    main()
