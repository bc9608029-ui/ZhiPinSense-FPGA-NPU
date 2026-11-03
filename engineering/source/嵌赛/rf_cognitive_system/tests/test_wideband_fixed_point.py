from __future__ import annotations

import numpy as np
import pytest
import yaml

from hardware.fpga.python.wideband_fixed_point import (
    DEFAULT_WIDTH_PLAN,
    apply_window_int16,
    ddc_error_metrics,
    ddc_int16_q15,
    hann_window_q15,
)


SAMPLE_RATE = 1_024_000.0
LENGTH = 16_384


def _quantized_tone(frequency_hz: float, amplitude: float = 0.7) -> np.ndarray:
    sample_index = np.arange(LENGTH, dtype=np.float64)
    values = amplitude * np.exp(1j * 2.0 * np.pi * frequency_hz * sample_index / SAMPLE_RATE)
    return np.stack(
        (np.rint(values.real * 32767.0), np.rint(values.imag * 32767.0)), axis=1
    ).astype(np.int16)


def test_wideband_width_plan_is_internally_consistent() -> None:
    assert DEFAULT_WIDTH_PLAN.fft_guard_bits == 10
    assert DEFAULT_WIDTH_PLAN.fft_output_bits == 26
    assert DEFAULT_WIDTH_PLAN.magnitude_square_bits == 51
    assert DEFAULT_WIDTH_PLAN.psd_accumulator_bits == 56


def test_machine_readable_contract_matches_python_width_plan() -> None:
    with open("configs/wideband_fixed_point.yaml", "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    assert config["input"]["format"] == "interleaved_signed_int16_iq"
    assert config["window"]["coefficient_format"] == "signed_q1_15_int16"
    assert config["fft_abstract_interface"]["fft_length"] == DEFAULT_WIDTH_PLAN.fft_length
    assert config["fft_abstract_interface"]["output_real_bits"] == DEFAULT_WIDTH_PLAN.fft_output_bits
    assert config["magnitude_square"]["output_bits"] == DEFAULT_WIDTH_PLAN.magnitude_square_bits
    assert config["psd"]["accumulator_bits"] == DEFAULT_WIDTH_PLAN.psd_accumulator_bits


def test_q15_hann_window_and_int16_application() -> None:
    rng = np.random.default_rng(20261010)
    iq = rng.integers(-30_000, 30_001, size=(1024, 2), dtype=np.int16)
    coefficients = hann_window_q15(1024)
    fixed = apply_window_int16(iq, coefficients)
    reference = iq.astype(np.float64) * np.hanning(1024)[:, None]
    error = fixed.astype(np.float64) - reference
    assert coefficients.dtype == np.int16
    assert coefficients[0] == coefficients[-1] == 0
    assert int(coefficients.max()) == 32767
    assert fixed.dtype == np.int16
    assert float(np.max(np.abs(error))) < 2.0


@pytest.mark.parametrize("frequency_hz", [-240_000.0, 90_000.0, 260_000.0])
def test_fixed_point_nco_ddc(frequency_hz: float) -> None:
    iq = _quantized_tone(frequency_hz)
    output, metadata = ddc_int16_q15(iq, frequency_hz, SAMPLE_RATE)
    metrics = ddc_error_metrics(iq, output, frequency_hz, SAMPLE_RATE)
    assert output.shape == iq.shape
    assert output.dtype == np.int16
    assert metadata["phase_bits"] == 32
    assert metadata["amplitude_format"] == "signed Q1.15 int16"
    assert metadata["saturation_count"] == 0
    assert abs(metadata["frequency_word_error_hz"]) < SAMPLE_RATE / 2**33
    assert abs(metrics["residual_frequency_hz"]) < 0.1
    assert metrics["rmse"] < 5e-5
    assert metrics["evm_db"] < -80.0
