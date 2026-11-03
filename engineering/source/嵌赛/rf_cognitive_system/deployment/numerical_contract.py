"""Reference conversion from SDR-like int16 IQ to planned NPU tensors."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from deployment.fixed_point_frontend import power_lag1_int16


@dataclass(frozen=True)
class NumericalContract:
    """Explicit reference scales used by consistency tests.

    These defaults interpret ADC samples as Q1.15 and span the mathematical
    int16 Power/Lag range with signed INT8. They are reference values, not final
    calibration scales for a real radio; target scales must be calibrated and
    then frozen with the NPU artifact.
    """

    adc_lsb: float = 2.0**-15
    iq_int8_scale: float = 1.0 / 127.0
    power_int8_scale: float = 2.0 / 127.0
    correlation_int8_scale: float = 2.0 / 127.0
    quant_min: int = -127
    quant_max: int = 127


def round_nearest_away_from_zero(values: np.ndarray) -> np.ndarray:
    """Deterministic rounding rule suitable for a matching RTL quantizer."""

    array = np.asarray(values, dtype=np.float64)
    return np.sign(array) * np.floor(np.abs(array) + 0.5)


def symmetric_quantize(values: np.ndarray, scale: float, contract: NumericalContract) -> np.ndarray:
    if scale <= 0.0:
        raise ValueError("Quantization scale must be positive")
    rounded = round_nearest_away_from_zero(np.asarray(values, dtype=np.float64) / scale)
    return np.clip(rounded, contract.quant_min, contract.quant_max).astype(np.int8)


def float_frontend(iq_float: np.ndarray) -> np.ndarray:
    """Float64 reference with channel order [Power, LagRe, LagIm]."""

    values = np.asarray(iq_float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError(f"Expected [L,2] IQ, received {values.shape}")
    i_component = values[:, 0].astype(np.float64)
    q_component = values[:, 1].astype(np.float64)
    power = i_component * i_component + q_component * q_component
    real = np.zeros(values.shape[0], dtype=np.float64)
    imaginary = np.zeros(values.shape[0], dtype=np.float64)
    if values.shape[0] > 1:
        real[1:] = i_component[1:] * i_component[:-1] + q_component[1:] * q_component[:-1]
        imaginary[1:] = q_component[1:] * i_component[:-1] - i_component[1:] * q_component[:-1]
    return np.stack((power, real, imaginary), axis=0)


def reference_tensors_from_int16(
    iq_int16: np.ndarray, contract: NumericalContract = NumericalContract()
) -> dict[str, np.ndarray]:
    """Float path followed by the frozen quantization definition."""

    values = np.asarray(iq_int16)
    if values.dtype != np.int16:
        raise TypeError(f"Expected int16 IQ, received {values.dtype}")
    iq_float_l2 = values.astype(np.float64) * contract.adc_lsb
    physical_float = float_frontend(iq_float_l2)
    iq_ncl = iq_float_l2.T
    iq_quantized = symmetric_quantize(iq_ncl, contract.iq_int8_scale, contract)
    physical_quantized = np.stack(
        (
            symmetric_quantize(physical_float[0], contract.power_int8_scale, contract),
            symmetric_quantize(physical_float[1], contract.correlation_int8_scale, contract),
            symmetric_quantize(physical_float[2], contract.correlation_int8_scale, contract),
        ),
        axis=0,
    )
    return {
        "iq_float": iq_ncl.astype(np.float32),
        "physical_float": physical_float.astype(np.float32),
        "iq_int8": iq_quantized,
        "physical_int8": physical_quantized,
    }


def planned_fpga_tensors_from_int16(
    iq_int16: np.ndarray, contract: NumericalContract = NumericalContract()
) -> dict[str, np.ndarray]:
    """Integer Power/Lag path scaled into the same float/INT8 contract."""

    values = np.asarray(iq_int16)
    exact = power_lag1_int16(values)
    square_lsb = contract.adc_lsb * contract.adc_lsb
    physical_float = np.stack(
        (
            exact["power_u32_exact"] * square_lsb,
            exact["lag1_real_s33_exact"] * square_lsb,
            exact["lag1_imag_s33_exact"] * square_lsb,
        ),
        axis=0,
    )
    iq_float = values.astype(np.float64).T * contract.adc_lsb
    return {
        "iq_float": iq_float.astype(np.float32),
        "physical_float": physical_float.astype(np.float32),
        "iq_int8": symmetric_quantize(iq_float, contract.iq_int8_scale, contract),
        "physical_int8": np.stack(
            (
                symmetric_quantize(physical_float[0], contract.power_int8_scale, contract),
                symmetric_quantize(physical_float[1], contract.correlation_int8_scale, contract),
                symmetric_quantize(physical_float[2], contract.correlation_int8_scale, contract),
            ),
            axis=0,
        ),
    }


def consistency_metrics(
    reference: dict[str, np.ndarray],
    candidate: dict[str, np.ndarray],
    contract: NumericalContract = NumericalContract(),
) -> dict[str, float | bool | int]:
    result: dict[str, float | bool] = {}
    for name in ("iq_float", "physical_float"):
        error = reference[name].astype(np.float64) - candidate[name].astype(np.float64)
        result[f"{name}_max_abs_error"] = float(np.max(np.abs(error)))
        result[f"{name}_rmse"] = float(np.sqrt(np.mean(error * error)))
    result["iq_int8_exact_match"] = bool(np.array_equal(reference["iq_int8"], candidate["iq_int8"]))
    result["physical_int8_exact_match"] = bool(
        np.array_equal(reference["physical_int8"], candidate["physical_int8"])
    )
    iq_dequantized = candidate["iq_int8"].astype(np.float64) * contract.iq_int8_scale
    physical_dequantized = candidate["physical_int8"].astype(np.float64).copy()
    physical_dequantized[0] *= contract.power_int8_scale
    physical_dequantized[1:] *= contract.correlation_int8_scale
    iq_quantization_error = reference["iq_float"].astype(np.float64) - iq_dequantized
    physical_quantization_error = reference["physical_float"].astype(np.float64) - physical_dequantized
    result["iq_int8_dequant_rmse"] = float(np.sqrt(np.mean(iq_quantization_error**2)))
    result["iq_int8_dequant_max_abs_error"] = float(np.max(np.abs(iq_quantization_error)))
    result["physical_int8_dequant_rmse"] = float(np.sqrt(np.mean(physical_quantization_error**2)))
    result["physical_int8_dequant_max_abs_error"] = float(np.max(np.abs(physical_quantization_error)))
    result["iq_saturation_count"] = int(np.count_nonzero(np.abs(candidate["iq_int8"].astype(np.int16)) == 127))
    result["physical_saturation_count"] = int(
        np.count_nonzero(np.abs(candidate["physical_int8"].astype(np.int16)) == 127)
    )
    return result
