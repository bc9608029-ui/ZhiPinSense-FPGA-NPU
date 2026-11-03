#!/usr/bin/env python3
"""Bit-exact PC reference for the frozen FPGA feature-migration boundary."""

from __future__ import annotations

import math
import numpy as np


def exact_features(iq: np.ndarray) -> dict[str, np.ndarray | int | float]:
    x = np.asarray(iq)
    if x.dtype != np.int16 or x.ndim != 2 or x.shape[1] != 2:
        raise ValueError("iq must be int16 with shape [N,2]")
    i = x[:, 0].astype(np.int64)
    q = x[:, 1].astype(np.int64)
    power = i * i + q * q
    lag_re = np.zeros(len(x), dtype=np.int64)
    lag_im = np.zeros(len(x), dtype=np.int64)
    if len(x) > 1:
        lag_re[1:] = i[1:] * i[:-1] + q[1:] * q[:-1]
        lag_im[1:] = q[1:] * i[:-1] - i[1:] * q[:-1]
    energy = int(power.sum(dtype=np.int64))
    peak = int(power.max(initial=0))
    rms = math.sqrt(energy / len(x)) if len(x) else 0.0
    return {"power": power, "lag_re": lag_re, "lag_im": lag_im,
            "energy": energy, "peak_power": peak, "rms": rms,
            "sample_count": len(x)}
