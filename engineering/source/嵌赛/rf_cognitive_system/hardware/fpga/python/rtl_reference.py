"""Integer/cycle-independent golden functions for the mandatory FPGA path."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from deployment.fixed_point_frontend import power_lag1_int16


@dataclass(frozen=True)
class QuantizerConfig:
    """Multiplier/shift representation of the frozen symmetric quantizer."""

    multiplier: int
    shift: int
    quant_min: int = -127
    quant_max: int = 127

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


REFERENCE_IQ_QUANTIZER = QuantizerConfig(multiplier=127, shift=15)
REFERENCE_PHYSICAL_QUANTIZER = QuantizerConfig(multiplier=127, shift=31)


def quantize_multiplier_shift(
    values: np.ndarray,
    config: QuantizerConfig,
    *,
    signed_input: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Match ``feature_quantizer.sv`` exactly.

    Rounding is nearest with exact halves away from zero.  Integer arithmetic
    is used throughout; final Icraft calibration may replace multiplier/shift
    but not this rule.
    """

    array = np.asarray(values)
    if config.multiplier < 0 or config.shift < 0:
        raise ValueError("multiplier and shift must be non-negative")
    wide = array.astype(object)
    if not signed_input and any(int(value) < 0 for value in wide.flat):
        raise ValueError("Unsigned quantizer input cannot be negative")
    result = np.empty(array.shape, dtype=np.int8)
    saturated = np.zeros(array.shape, dtype=bool)
    half = 0 if config.shift == 0 else 1 << (config.shift - 1)
    divisor_shift = config.shift
    for index, raw in np.ndenumerate(wide):
        integer = int(raw)
        negative = signed_input and integer < 0
        magnitude = -integer if negative else integer
        product = magnitude * config.multiplier
        rounded = product if divisor_shift == 0 else (product + half) >> divisor_shift
        is_saturated = rounded > config.quant_max
        saturated[index] = is_saturated
        clipped = min(rounded, config.quant_max)
        quantized = -clipped if negative else clipped
        quantized = min(max(quantized, config.quant_min), config.quant_max)
        result[index] = np.int8(quantized)
    return result, saturated


def tensor_offsets(sample_index: np.ndarray | int, frame_length: int = 1024) -> dict[str, np.ndarray]:
    """Return byte offsets for contiguous NCL IQ and physical channel planes."""

    index = np.asarray(sample_index, dtype=np.int64)
    if np.any(index < 0) or np.any(index >= frame_length):
        raise ValueError("sample_index is outside the frame")
    return {
        "iq_i_addr": index,
        "iq_q_addr": frame_length + index,
        "power_addr": index,
        "lag_re_addr": frame_length + index,
        "lag_im_addr": 2 * frame_length + index,
    }


def mandatory_frame_reference(iq: np.ndarray, frame_id: int = 0) -> dict[str, np.ndarray]:
    """Produce exact features, INT8 tensors and sidebands for one IQ frame."""

    values = np.asarray(iq)
    if values.dtype != np.int16 or values.shape != (1024, 2):
        raise ValueError(f"Expected int16 [1024,2], received {values.dtype} {values.shape}")
    exact = power_lag1_int16(values)
    iq_i, iq_i_sat = quantize_multiplier_shift(values[:, 0], REFERENCE_IQ_QUANTIZER)
    iq_q, iq_q_sat = quantize_multiplier_shift(values[:, 1], REFERENCE_IQ_QUANTIZER)
    power, power_sat = quantize_multiplier_shift(
        exact["power_u32_exact"], REFERENCE_PHYSICAL_QUANTIZER, signed_input=False
    )
    lag_re, lag_re_sat = quantize_multiplier_shift(
        exact["lag1_real_s33_exact"], REFERENCE_PHYSICAL_QUANTIZER
    )
    lag_im, lag_im_sat = quantize_multiplier_shift(
        exact["lag1_imag_s33_exact"], REFERENCE_PHYSICAL_QUANTIZER
    )
    sample_index = np.arange(1024, dtype=np.int64)
    return {
        "frame_id": np.full(1024, int(frame_id), dtype=np.int64),
        "sample_index": sample_index,
        "frame_start": sample_index == 0,
        "frame_end": sample_index == 1023,
        "i": values[:, 0],
        "q": values[:, 1],
        **exact,
        "iq_i_int8": iq_i,
        "iq_q_int8": iq_q,
        "power_int8": power,
        "lag_re_int8": lag_re,
        "lag_im_int8": lag_im,
        "iq_i_saturated": iq_i_sat,
        "iq_q_saturated": iq_q_sat,
        "power_saturated": power_sat,
        "lag_re_saturated": lag_re_sat,
        "lag_im_saturated": lag_im_sat,
        **tensor_offsets(sample_index),
    }
