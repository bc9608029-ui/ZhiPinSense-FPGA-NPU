"""Frozen-contract invariants (contract sec. 3, 2026-10-29 revision)."""

import pytest

from src import contracts as C


def test_frozen_frequency_constants():
    assert C.SAMPLE_RATE_HZ == 2_560_000
    assert C.FFT_LENGTH == 1024
    assert C.BIN_HZ == 2500


def test_validate_scan_step_accepts_any_positive_integer_up_to_span():
    # Sec. 3 (revised): step is NOT inherently a multiple of 2500 Hz.
    C.validate_scan_step_hz(2_500)
    C.validate_scan_step_hz(1_000_000)
    C.validate_scan_step_hz(1_234_567)   # non-bin-aligned is legal
    C.validate_scan_step_hz(2_304_000)   # main-chain existing span/upper limit


def test_validate_scan_step_rejects_bad_values():
    for bad in (0, -2500, 2_305_000):
        with pytest.raises(ValueError):
            C.validate_scan_step_hz(bad)


def test_resolution_envelope_is_consistent():
    assert C.RESOLVABLE_SEPARATION_HZ == 12_500
    assert C.MERGE_RADIUS_HZ < C.RESOLVABLE_SEPARATION_HZ
    assert C.MERGE_RADIUS_HZ == 6_250
    assert C.MAX_TARGET_BW_HZ == int(0.45 * C.SAMPLE_RATE_HZ)


def test_power_contract_is_numeric_and_relative():
    # power_valid is a numeric power (dB above adaptive median noise floor),
    # a relative scale -- explicitly never dBm.
    assert "not dbm" in C.POWER_UNIT.lower()
    assert C.POWER_VALID_MIN_DB == C.PEAK_THRESHOLD_DB
    assert C.POWER_VALID_MAX_DB > C.POWER_VALID_MIN_DB
    import math
    assert math.isnan(C.POWER_INVALID_DB)


def test_backends_and_statuses_frozen():
    assert C.BACKENDS == ("software", "fpga", "auto")
    assert C.TARGET_STATUSES == ("new", "tracking", "missing", "expired")
