"""Bit-exact integer reference for the planned FPGA Power/Lag-1 frontend."""

from __future__ import annotations

import numpy as np


def power_lag1_int16(iq: np.ndarray) -> dict[str, np.ndarray]:
    """Calculate exact integer features from ``[L,2]`` signed int16 IQ.

    NumPy int64 intermediates deliberately avoid host int32 overflow.  RTL may
    retain Power as unsigned 32-bit and each correlation component as signed
    33-bit before its explicit quantization stage.
    """

    values = np.asarray(iq)
    if values.dtype != np.int16:
        raise TypeError(f"Expected int16 IQ, received {values.dtype}")
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError(f"Expected [L,2] IQ, received {values.shape}")
    wide = values.astype(np.int64)
    i_component = wide[:, 0]
    q_component = wide[:, 1]
    power = i_component * i_component + q_component * q_component
    correlation_real = np.zeros(values.shape[0], dtype=np.int64)
    correlation_imag = np.zeros(values.shape[0], dtype=np.int64)
    if values.shape[0] > 1:
        correlation_real[1:] = (
            i_component[1:] * i_component[:-1] + q_component[1:] * q_component[:-1]
        )
        correlation_imag[1:] = (
            q_component[1:] * i_component[:-1] - i_component[1:] * q_component[:-1]
        )
    return {
        "power_u32_exact": power,
        "lag1_real_s33_exact": correlation_real,
        "lag1_imag_s33_exact": correlation_imag,
    }
