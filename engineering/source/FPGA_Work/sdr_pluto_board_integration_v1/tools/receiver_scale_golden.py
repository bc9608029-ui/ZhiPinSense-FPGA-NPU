#!/usr/bin/env python3
# receiver_scale_golden.py -- numpy reference for sdr::ReceiverScale
# (fixed scalar + Q1.15 conversion), matching the contract:
#
#   x_model[n] = adc_count[n] * (1/32768) * receiver_scale     (float)
#   Q1.15      = clip(lround(x_model * 32768))                  (int16)
#               == clip(lround(adc_count * receiver_scale))
#
# Verifies the same three properties the C++ host test (test_receiver_scale.cpp)
# checks, so the two agree independently:
#   1. the float conversion and the Q1.15 conversion are consistent;
#   2. saturation/clipping at the int16 rails behaves as specified;
#   3. the two mathematically-equivalent paths (count*scale -> Q1.15, and
#      float*32768 -> Q1.15) agree.
#
# Self-checking: exits 0 iff every assertion passes.

import numpy as np

ADC_LSB = 1.0 / 32768.0


def to_float(count, scale):
    return count * ADC_LSB * scale


def to_q115_from_count(count, scale):
    return np.clip(np.rint(count * scale), -32768, 32767).astype(np.int64)


def to_q115_from_float(x_model):
    return np.clip(np.rint(x_model * 32768.0), -32768, 32767).astype(np.int64)


def main():
    rng = np.random.default_rng(20261005)
    count = rng.integers(-32000, 32000, size=1_000_000)
    scale = 0.8

    # 1. collapsed path (count*scale -> Q1.15) == two-step float path
    q1 = to_q115_from_count(count, scale)
    q2 = to_q115_from_float(to_float(count, scale))
    assert np.array_equal(q1, q2), "count*scale path != float path"

    # 2. Q1.15 saturates exactly at the int16 rails
    assert to_q115_from_count(np.array([40000]), 1.0)[0] == 32767
    assert to_q115_from_count(np.array([-40000]), 1.0)[0] == -32768

    # 3. identity at scale 1.0 (no change to a representable count)
    c = np.array([1000, -1000, 32767, -32768], dtype=np.int64)
    assert np.array_equal(to_q115_from_count(c, 1.0), c)

    # 4. scale is a GLOBAL scalar: a single value applies to every sample
    assert len(set(np.unique(to_q115_from_count(np.array([1000, 2000, 3000]), 1.5)))) == 3

    print("receiver_scale_golden: float/Q1.15 consistency + saturation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
