from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from deployment.numerical_contract import NumericalContract, reference_tensors_from_int16
from hardware.fpga.python.rtl_reference import (
    QuantizerConfig,
    REFERENCE_IQ_QUANTIZER,
    REFERENCE_PHYSICAL_QUANTIZER,
    mandatory_frame_reference,
    quantize_multiplier_shift,
    tensor_offsets,
)
from hardware.fpga.python.wideband_reference import ExtractionRequest, extract_candidate
from hardware.fpga.vectors.generate_vectors import FRAME_LENGTH, SEED, build_cases, generate


def test_exact_power_and_lag_width_extremes() -> None:
    iq = np.zeros((1024, 2), dtype=np.int16)
    iq[:4] = [(32767, 32767), (-32768, -32768), (32767, -32768), (-32768, 32767)]
    result = mandatory_frame_reference(iq)
    wide = iq.astype(np.int64)
    expected_power = wide[:, 0] ** 2 + wide[:, 1] ** 2
    expected_re = np.zeros(1024, dtype=np.int64)
    expected_im = np.zeros(1024, dtype=np.int64)
    expected_re[1:] = wide[1:, 0] * wide[:-1, 0] + wide[1:, 1] * wide[:-1, 1]
    expected_im[1:] = wide[1:, 1] * wide[:-1, 0] - wide[1:, 0] * wide[:-1, 1]
    np.testing.assert_array_equal(result["power_u32_exact"], expected_power)
    np.testing.assert_array_equal(result["lag1_real_s33_exact"], expected_re)
    np.testing.assert_array_equal(result["lag1_imag_s33_exact"], expected_im)
    assert int(expected_power.max()) <= 2**32 - 1
    assert int(np.abs(expected_re).max()) <= 2**32
    assert int(np.abs(expected_im).max()) <= 2**32
    assert result["lag1_real_s33_exact"][0] == 0
    assert result["lag1_imag_s33_exact"][0] == 0


@pytest.mark.parametrize(
    ("raw", "expected", "saturated"),
    [(0, 0, False), (1, 1, False), (-1, -1, False), (2, 1, False), (-2, -1, False),
     (253, 127, False), (-253, -127, False), (300, 127, True), (-300, -127, True)],
)
def test_quantizer_round_ties_away_and_saturation(raw: int, expected: int, saturated: bool) -> None:
    output, flags = quantize_multiplier_shift(np.array([raw]), QuantizerConfig(1, 1))
    assert int(output[0]) == expected
    assert bool(flags[0]) is saturated


def test_reference_multiplier_shift_matches_frozen_float_contract() -> None:
    rng = np.random.default_rng(20261002)
    iq = rng.integers(-32768, 32768, size=(1024, 2), dtype=np.int16)
    integer = mandatory_frame_reference(iq)
    floating = reference_tensors_from_int16(iq, NumericalContract())
    np.testing.assert_array_equal(
        np.stack((integer["iq_i_int8"], integer["iq_q_int8"])), floating["iq_int8"]
    )
    np.testing.assert_array_equal(
        np.stack((integer["power_int8"], integer["lag_re_int8"], integer["lag_im_int8"])),
        floating["physical_int8"],
    )
    assert REFERENCE_IQ_QUANTIZER == QuantizerConfig(127, 15)
    assert REFERENCE_PHYSICAL_QUANTIZER == QuantizerConfig(127, 31)


def test_tensor_packer_channel_major_offsets() -> None:
    offsets = tensor_offsets(np.array([0, 1, 1023]))
    np.testing.assert_array_equal(offsets["iq_i_addr"], [0, 1, 1023])
    np.testing.assert_array_equal(offsets["iq_q_addr"], [1024, 1025, 2047])
    np.testing.assert_array_equal(offsets["power_addr"], [0, 1, 1023])
    np.testing.assert_array_equal(offsets["lag_re_addr"], [1024, 1025, 2047])
    np.testing.assert_array_equal(offsets["lag_im_addr"], [2048, 2049, 3071])


def test_vector_case_coverage_and_determinism(tmp_path: Path) -> None:
    cases_a = build_cases()
    cases_b = build_cases()
    expected_names = {
        "all_zero", "single_impulse", "positive_negative_alternating", "maximum_positive",
        "maximum_negative", "near_full_scale", "random_iq",
    }
    assert len(cases_a) == 19
    assert expected_names.issubset({case[0] for case in cases_a})
    assert {case[2].get("modulation") for case in cases_a} >= {"BPSK", "QPSK", "16QAM", "64QAM"}
    assert {case[2].get("snr_db") for case in cases_a if "snr_db" in case[2]} == {-10.0, 0.0, 20.0}
    for first, second in zip(cases_a, cases_b, strict=True):
        assert first[0] == second[0]
        np.testing.assert_array_equal(first[1], second[1])
    manifest = generate(tmp_path)
    persisted = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == persisted["seed"] == SEED
    assert persisted["total_samples"] == 19 * FRAME_LENGTH
    assert persisted["blind_test_accessed"] is False


def test_wideband_extraction_contract_marks_symbol_rate_todo() -> None:
    sample_rate = 1_024_000.0
    n = np.arange(16384)
    iq = np.exp(1j * 2 * np.pi * 160_000.0 * n / sample_rate)
    request = ExtractionRequest(0, 160_000.0, 32_000.0)
    frame, metadata = extract_candidate(iq, sample_rate, request)
    assert frame.shape == (1024,)
    assert frame.dtype == np.complex64
    assert np.isfinite(frame).all()
    assert metadata["target_sample_rate_hz"] == 128_000.0
    assert metadata["symbol_rate_status"] == "TODO-SYMBOL-RATE"


def test_rtl_sources_are_board_independent() -> None:
    root = Path(__file__).resolve().parents[1] / "hardware" / "fpga" / "rtl"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.sv")).lower()
    # Comments may name future integration boundaries. These tokens identify
    # actual vendor-specific module/primitive declarations or constraint syntax.
    forbidden = ("module fmql", "module axi_dma", "fmql30tai_primitive", "set_property package_pin")
    for token in forbidden:
        assert token not in text
