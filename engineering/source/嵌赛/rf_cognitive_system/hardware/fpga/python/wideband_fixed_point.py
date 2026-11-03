"""Python reference for the pre-board wideband fixed-point interface contract.

This is arithmetic/interface evidence only.  It does not model a particular
FFT IP, LUT architecture, DSP primitive, or board clock.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np


@dataclass(frozen=True)
class WidebandWidthPlan:
    input_bits: int = 16
    window_bits: int = 16
    window_fraction_bits: int = 15
    fft_length: int = 1024
    fft_guard_bits: int = 10
    fft_output_bits: int = 26
    magnitude_square_bits: int = 51
    psd_average_frames: int = 32
    psd_accumulator_bits: int = 56

    def __post_init__(self) -> None:
        expected_guard = math.ceil(math.log2(self.fft_length))
        expected_fft = self.input_bits + expected_guard
        expected_magnitude = 2 * self.fft_output_bits - 1
        expected_accumulator = self.magnitude_square_bits + math.ceil(
            math.log2(self.psd_average_frames)
        )
        if self.fft_length < 2 or self.fft_length & (self.fft_length - 1):
            raise ValueError("The V1 width plan requires a power-of-two FFT length")
        if self.fft_guard_bits != expected_guard or self.fft_output_bits != expected_fft:
            raise ValueError("FFT guard/output width is inconsistent with unscaled worst-case growth")
        if self.magnitude_square_bits != expected_magnitude:
            raise ValueError("Magnitude-square width must cover Re^2 + Im^2")
        if self.psd_average_frames < 1 or self.psd_accumulator_bits != expected_accumulator:
            raise ValueError("PSD accumulator width is inconsistent with the averaging depth")

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


DEFAULT_WIDTH_PLAN = WidebandWidthPlan()


def round_shift_ties_away(values: np.ndarray, shift: int) -> np.ndarray:
    """Signed integer right shift with nearest, exact halves away from zero."""

    array = np.asarray(values, dtype=np.int64)
    if shift < 0:
        raise ValueError("shift must be non-negative")
    if shift == 0:
        return array.copy()
    magnitude = np.abs(array)
    rounded = (magnitude + (1 << (shift - 1))) >> shift
    return np.where(array < 0, -rounded, rounded).astype(np.int64)


def quantize_q15(values: np.ndarray) -> np.ndarray:
    """Quantize real values to signed Q1.15 with ties-away rounding."""

    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError("Q1.15 input must be finite")
    scaled = np.sign(array) * np.floor(np.abs(array) * (1 << 15) + 0.5)
    return np.clip(scaled, -32768, 32767).astype(np.int16)


def hann_window_q15(length: int) -> np.ndarray:
    """Return the symmetric NumPy-Hann window in signed Q1.15."""

    if length < 2:
        raise ValueError("window length must be at least 2")
    return quantize_q15(np.hanning(length))


def apply_window_int16(iq: np.ndarray, coefficients_q15: np.ndarray) -> np.ndarray:
    """Apply Q1.15 window coefficients to int16 ``[L,2]`` IQ."""

    values = np.asarray(iq)
    coefficients = np.asarray(coefficients_q15)
    if values.dtype != np.int16 or values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("IQ must be signed int16 [L,2]")
    if coefficients.dtype != np.int16 or coefficients.shape != (values.shape[0],):
        raise ValueError("Window must be signed int16 Q1.15 [L]")
    products = values.astype(np.int64) * coefficients.astype(np.int64)[:, None]
    rounded = round_shift_ties_away(products, 15)
    return np.clip(rounded, -32768, 32767).astype(np.int16)


def nco_tuning_word(frequency_hz: float, sample_rate_hz: float, phase_bits: int = 32) -> tuple[int, int, float]:
    """Return unsigned word, signed word, and represented frequency."""

    if not np.isfinite(frequency_hz) or not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("frequency and positive sample rate must be finite")
    if abs(frequency_hz) >= sample_rate_hz / 2:
        raise ValueError("frequency must lie strictly inside the Nyquist interval")
    if phase_bits < 2 or phase_bits > 62:
        raise ValueError("phase_bits must be in [2, 62]")
    modulus = 1 << phase_bits
    magnitude = abs(frequency_hz / sample_rate_hz * modulus)
    signed_word = int(math.floor(magnitude + 0.5))
    if frequency_hz < 0:
        signed_word = -signed_word
    unsigned_word = signed_word % modulus
    represented_hz = signed_word * sample_rate_hz / modulus
    return unsigned_word, signed_word, represented_hz


def nco_q15(
    frequency_hz: float,
    sample_rate_hz: float,
    length: int,
    *,
    phase_bits: int = 32,
) -> tuple[np.ndarray, np.ndarray, dict[str, float | int]]:
    """Generate Q1.15 cosine/sine from an ideal 32-bit phase accumulator.

    Phase-to-amplitude lookup/CORDIC approximation is intentionally outside
    this reference.  Only phase-word and Q1.15 amplitude quantization are
    evaluated here.
    """

    if length < 1:
        raise ValueError("length must be positive")
    unsigned_word, signed_word, represented_hz = nco_tuning_word(
        frequency_hz, sample_rate_hz, phase_bits
    )
    modulus = 1 << phase_bits
    indices = np.arange(length, dtype=np.uint64)
    phases = (indices * np.uint64(unsigned_word)) & np.uint64(modulus - 1)
    angles = phases.astype(np.float64) * (2.0 * np.pi / modulus)
    cosine = quantize_q15(np.cos(angles))
    sine = quantize_q15(np.sin(angles))
    return cosine, sine, {
        "phase_bits": phase_bits,
        "tuning_word_unsigned": unsigned_word,
        "tuning_word_signed": signed_word,
        "requested_frequency_hz": float(frequency_hz),
        "represented_frequency_hz": float(represented_hz),
        "frequency_word_error_hz": float(represented_hz - frequency_hz),
        "amplitude_format": "signed Q1.15 int16",
    }


def ddc_int16_q15(
    iq: np.ndarray,
    center_frequency_hz: float,
    sample_rate_hz: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Mix int16 IQ by a 32-bit-phase, Q1.15-amplitude negative-frequency NCO."""

    values = np.asarray(iq)
    if values.dtype != np.int16 or values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("IQ must be signed int16 [L,2]")
    cosine, sine, metadata = nco_q15(center_frequency_hz, sample_rate_hz, len(values))
    i_value = values[:, 0].astype(np.int64)
    q_value = values[:, 1].astype(np.int64)
    cosine_wide = cosine.astype(np.int64)
    sine_wide = sine.astype(np.int64)
    # (I+jQ)*(cos-j*sin): four s16xs16 products, two s33 add/sub results.
    mixed_i_raw = i_value * cosine_wide + q_value * sine_wide
    mixed_q_raw = q_value * cosine_wide - i_value * sine_wide
    mixed = np.stack(
        (round_shift_ties_away(mixed_i_raw, 15), round_shift_ties_away(mixed_q_raw, 15)),
        axis=1,
    )
    saturated = (mixed < -32768) | (mixed > 32767)
    output = np.clip(mixed, -32768, 32767).astype(np.int16)
    metadata.update(
        {
            "mixer_product_bits": 32,
            "mixer_sum_bits": 33,
            "output_shift": 15,
            "output_bits": 16,
            "saturation_count": int(np.count_nonzero(saturated)),
        }
    )
    return output, metadata


def ddc_error_metrics(
    iq: np.ndarray,
    fixed_output: np.ndarray,
    center_frequency_hz: float,
    sample_rate_hz: float,
) -> dict[str, float]:
    """Compare a fixed DDC result against the float mixer on the same int16 IQ."""

    values = np.asarray(iq)
    output = np.asarray(fixed_output)
    if values.dtype != np.int16 or output.dtype != np.int16 or values.shape != output.shape:
        raise ValueError("input and output must be matching int16 [L,2] arrays")
    complex_input = (values[:, 0].astype(np.float64) + 1j * values[:, 1].astype(np.float64)) / 32768.0
    sample_index = np.arange(len(values), dtype=np.float64)
    reference = complex_input * np.exp(
        -1j * 2.0 * np.pi * center_frequency_hz * sample_index / sample_rate_hz
    )
    candidate = (output[:, 0].astype(np.float64) + 1j * output[:, 1].astype(np.float64)) / 32768.0
    error = candidate - reference
    reference_rms = float(np.sqrt(np.mean(np.abs(reference) ** 2)))
    error_rms = float(np.sqrt(np.mean(np.abs(error) ** 2)))
    phase_step = np.angle(candidate[1:] * np.conj(candidate[:-1]))
    residual_hz = float(np.mean(phase_step) * sample_rate_hz / (2.0 * np.pi))
    return {
        "rmse": error_rms,
        "max_abs_error": float(np.max(np.abs(error))),
        "evm_db": float(20.0 * np.log10(max(error_rms, np.finfo(float).tiny) / reference_rms)),
        "residual_frequency_hz": residual_hz,
    }
