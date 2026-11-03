"""Float/fixed DSP golden reference for future RTL point-by-point comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from dsp.fft import compute_fft, energy_detect, power_spectrum
from dsp.fir import apply_fir, design_lowpass
from dsp.normalization import complex_to_int16, dc_remove, int16_to_complex, rms_normalize


@dataclass(frozen=True)
class FPGAInterfaceSpec:
    iq_input_format: str = "interleaved signed int16: [I0,Q0,I1,Q1,...]"
    sample_length: int = 1024
    fft_length: int = 1024
    window: str = "Hann, coefficients Q1.15"
    normalization: str = "DC removal then block-RMS gain; gain supplied/configured by CPU"
    output_format: str = "FFT complex signed values plus uint32/uint64 power bins"


@dataclass(frozen=True)
class FixedPointRecommendation:
    adc_bits: int = 16
    coefficient_fractional_bits: int = 15
    fir_accumulator_bits: int = 40
    fft_internal_bits: int = 24
    fft_scaling: str = "block floating point or 1-bit/stage; retain exponent metadata"
    rationale: str = (
        "For signed Q1.15 input and coefficients, each product is ~Q2.30. "
        "A 65-tap FIR needs ceil(log2(65))=7 guard bits plus sign, so 40 bits "
        "prevents worst-case accumulation overflow. FFT growth is log2(N) bits; "
        "do not freeze the final width until RTL scaling and crest-factor tests exist."
    )


def float_pipeline(
    iq: np.ndarray,
    sample_rate: float,
    fft_length: int = 1024,
    fir_taps: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    taps = fir_taps if fir_taps is not None else design_lowpass(65, 0.2 * sample_rate, sample_rate)
    centered = dc_remove(iq)
    normalized = rms_normalize(centered, target_rms=0.5)
    filtered = apply_fir(normalized, taps)
    spectrum = compute_fft(filtered, fft_length=fft_length, window="hann")
    power = np.abs(spectrum) ** 2 / fft_length
    detections, energies = energy_detect(filtered, frame_length=128, hop_length=64, threshold=0.01)
    return {
        "dc_removed": centered,
        "normalized": normalized,
        "filtered": filtered,
        "fft": spectrum,
        "power": power,
        "frame_energy": energies,
        "detections": detections,
    }


def fixed_fir_int16(iq_int16: np.ndarray, taps: np.ndarray, coefficient_fractional_bits: int = 15) -> np.ndarray:
    """Integer FIR model with Q1.15 coefficients and a wide accumulator."""
    coefficients = np.round(np.asarray(taps) * (1 << coefficient_fractional_bits)).astype(np.int64)
    output = np.zeros_like(iq_int16, dtype=np.int64)
    for component in range(2):
        values = iq_int16[:, component].astype(np.int64)
        accumulated = np.convolve(values, coefficients, mode="full")[: len(values)]
        rounded = accumulated + (1 << (coefficient_fractional_bits - 1))
        output[:, component] = rounded >> coefficient_fractional_bits
    return np.clip(output, -32768, 32767).astype(np.int16)


def fixed_point_pipeline(
    iq: np.ndarray,
    sample_rate: float,
    fft_length: int = 1024,
    fir_taps: np.ndarray | None = None,
) -> dict[str, np.ndarray | float]:
    taps = fir_taps if fir_taps is not None else design_lowpass(65, 0.2 * sample_rate, sample_rate)
    prepared = rms_normalize(dc_remove(iq), target_rms=0.5)
    iq_int16, scale = complex_to_int16(prepared, full_scale=0.9)
    filtered_int16 = fixed_fir_int16(iq_int16, taps)
    filtered = int16_to_complex(filtered_int16, scale)
    spectrum = compute_fft(filtered, fft_length=fft_length, window="hann")
    power = np.abs(spectrum) ** 2 / fft_length
    return {"input_int16": iq_int16, "filtered_int16": filtered_int16, "filtered": filtered, "fft": spectrum, "power": power, "scale": scale}


def comparison_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    error = np.asarray(reference) - np.asarray(candidate)
    mse = float(np.mean(np.abs(error) ** 2))
    reference_power = float(np.mean(np.abs(reference) ** 2))
    relative_error = float(np.sqrt(mse / max(reference_power, 1e-20)))
    degradation = float(10.0 * np.log10(reference_power / max(mse, 1e-20)))
    return {"mse": mse, "relative_error": relative_error, "quantization_snr_db": degradation}


def run_golden_comparison(iq: np.ndarray, sample_rate: float, fft_length: int = 1024) -> dict[str, Any]:
    taps = design_lowpass(65, 0.2 * sample_rate, sample_rate)
    floating = float_pipeline(iq, sample_rate, fft_length, taps)
    fixed = fixed_point_pipeline(iq, sample_rate, fft_length, taps)
    return {
        "interface": asdict(FPGAInterfaceSpec(sample_length=len(iq), fft_length=fft_length)),
        "fixed_point_recommendation": asdict(FixedPointRecommendation()),
        "filtered_comparison": comparison_metrics(floating["filtered"], fixed["filtered"]),
        "fft_comparison": comparison_metrics(floating["fft"], fixed["fft"]),
        "note": "TODO-HARDWARE: compare these arrays with Procise RTL simulation and FMQL30TAI captures.",
    }

