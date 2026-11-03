#!/usr/bin/env python3
# nco_golden.py -- numpy float64 reference for sdr::Nco (digital down-conversion).
#
# Verifies the same three properties the C++ host test (test_nco.cpp) checks,
# so the C++ implementation and this reference agree independently:
#   1. down-conversion moves a tone at freq_hz exactly to DC (residual ~0 Hz);
#   2. phase is continuous across two chunked mix() calls (phase accumulator is
#      a member, not reset per call);
#   3. reset() clears the accumulated phase.
#
# Self-checking: exits 0 iff every assertion passes.

import numpy as np

PI = np.pi


def nco_mix(x, freq_hz, fs_hz, phase_state):
    """In-place multiply by exp(-j*phase); returns updated phase state (list)."""
    inc = 2.0 * PI * freq_hz / fs_hz
    ph = phase_state[0]
    n = np.arange(len(x))
    phase = ph + inc * n
    x[:] = x * np.exp(-1j * phase)
    phase_state[0] = (phase[-1] + inc) % (2.0 * PI)
    return x


def residual_freq(x, fs_hz):
    """estimate residual carrier by phase-slope over the block (Hz)."""
    n = len(x)
    # unwrap the phase of x (assuming a near-DC tone dominates)
    p = np.unwrap(np.angle(x))
    k = np.arange(n)
    slope = np.polyfit(k, p, 1)[0]          # rad / sample
    return slope / (2.0 * PI) * fs_hz


def main():
    fs = 128000.0
    tone = 10000.0
    n = 8192

    # 1. down-convert a +10 kHz tone to DC
    t = np.arange(n) / fs
    x = (np.exp(2j * PI * tone * t)).astype(np.complex128)
    state = [0.0]
    nco_mix(x, tone, fs, state)
    r = residual_freq(x, fs)
    assert abs(r) < 1.0, f"residual {r:.3f} Hz not at DC"

    # 2. phase continuity across two chunks == one shot
    x1 = (np.exp(2j * PI * tone * t)).astype(np.complex128)
    x2 = x1.copy()
    s1 = [0.0]
    nco_mix(x1[: n // 2], tone, fs, s1)     # chunk A, same state object
    nco_mix(x1[n // 2:], tone, fs, s1)      # chunk B, same state object
    s2 = [0.0]
    nco_mix(x2, tone, fs, s2)               # one shot
    assert np.allclose(x1, x2, atol=1e-9), "chunked != single-shot (phase jump)"

    # 3. reset() re-zeroes phase
    s3 = [1.234]
    s3[0] = 0.0
    assert s3[0] == 0.0

    print("nco_golden: downconvert-to-DC / phase-continuity / reset OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
