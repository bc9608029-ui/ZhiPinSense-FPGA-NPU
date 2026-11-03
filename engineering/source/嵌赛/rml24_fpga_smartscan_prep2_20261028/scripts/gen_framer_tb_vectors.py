#!/usr/bin/env python3
"""Generate stimulus/expect hex vectors for the framer bit-exact testbench.

Drives the production Hann framer with full-range int16 I/Q and compares against
the frozen Golden `window_iq` (window multiply, round-away, sat16), which is the
only integer arithmetic the framer adds around `window_mul_q15` + `hann_coeff_rom`.

Outputs (concatenated frames, 1024 samples each):
  vectors/framer_stim.hex   -- one 32-bit {Q,I} word per line (I in low 16 bits)
  vectors/framer_expect.hex -- one 32-bit {Qw,Iw} word per line (windowed)
  vectors/framer_manifest.txt -- frame count + samples-per-frame (for the TB)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "reference"))
from smart_scan_golden import window_iq  # noqa: E402

import numpy as np  # noqa: E402

FRAMES = 4
N = 1024


def _s16(x: int) -> int:
    x = int(x)
    return x & 0xFFFF


def main() -> None:
    rng = np.random.default_rng(20261028)
    stim_i, stim_q = [], []
    exp_i, exp_q = [], []
    for _ in range(FRAMES):
        iq = rng.integers(-32768, 32768, size=(N, 2)).astype(np.int16)
        win = window_iq(iq)  # int16 [N,2], bit-exact vs RTL round15+sat16
        stim_i.extend(int(v) for v in iq[:, 0])
        stim_q.extend(int(v) for v in iq[:, 1])
        exp_i.extend(int(v) for v in win[:, 0])
        exp_q.extend(int(v) for v in win[:, 1])

    def _w(i: int, q: int) -> str:
        # {Q, I}: I in low 16 bits (framer s_axis_iq_tdata layout).
        return f"{(_s16(q) << 16) | _s16(i):08X}"

    stim_path = os.path.join(ROOT, "vectors", "framer_stim.hex")
    exp_path = os.path.join(ROOT, "vectors", "framer_expect.hex")
    with open(stim_path, "w", newline="\n") as f:
        f.write("\n".join(_w(i, q) for i, q in zip(stim_i, stim_q)) + "\n")
    with open(exp_path, "w", newline="\n") as f:
        f.write("\n".join(_w(i, q) for i, q in zip(exp_i, exp_q)) + "\n")

    manifest = os.path.join(ROOT, "vectors", "framer_manifest.txt")
    with open(manifest, "w", newline="\n") as f:
        f.write(f"frames={FRAMES}\n")
        f.write(f"samples_per_frame={N}\n")
        f.write("word_layout={Q[15:0],I[15:0]}\n")

    # Self-check: the golden is symmetric-Hann so bin 511 (peak) saturates; and
    # the expected output must already be within int16 by construction.
    assert len(stim_i) == FRAMES * N and len(exp_i) == FRAMES * N
    assert all(-32768 <= v <= 32767 for v in exp_i) and all(-32768 <= v <= 32767 for v in exp_q)
    print(f"FRAMER_TB_VECTORS result=PASS frames={FRAMES} samples={FRAMES*N} "
          f"peak_win={window_iq(np.full((N,2), 32767, dtype=np.int16))[511,0]}")
    print(f"wrote {stim_path}")
    print(f"wrote {exp_path}")
    print(f"wrote {manifest}")


if __name__ == "__main__":
    main()
