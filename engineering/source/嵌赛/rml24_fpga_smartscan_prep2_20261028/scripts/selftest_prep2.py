#!/usr/bin/env python3
"""Offline, fail-closed checks for the smart-scan pre-board package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
from postfft_stream_reference import FFT_LENGTH, POWER_MAX, power_u54, write_frame_natural


def check_vectors() -> int:
    checked = 0
    for path in sorted((ROOT / "vectors").glob("*.golden.npz")):
        data = np.load(path)
        shifted_re = np.asarray(data["fft_re"], dtype=np.int64)
        shifted_im = np.asarray(data["fft_im"], dtype=np.int64)
        natural_re = np.fft.ifftshift(shifted_re)
        natural_im = np.fft.ifftshift(shifted_im)
        actual = write_frame_natural(natural_re, natural_im)
        expected = np.asarray(data["power_u54"], dtype=np.int64)
        if not np.array_equal(actual, expected):
            raise RuntimeError(f"post-FFT mismatch: {path.name}")
        checked += 1
    if checked != 4:
        raise RuntimeError(f"expected 4 vector sets, got {checked}")
    return checked


def check_boundaries() -> None:
    extreme = np.array([-(1 << 26)], dtype=np.int64)
    value = int(power_u54(extreme, extreme)[0])
    if value != (1 << 53) or value > POWER_MAX:
        raise RuntimeError("u54 extreme-value contract failed")
    try:
        write_frame_natural(np.zeros(FFT_LENGTH - 1), np.zeros(FFT_LENGTH - 1))
    except ValueError:
        pass
    else:
        raise RuntimeError("short FFT frame was not rejected")


def check_contract() -> None:
    contract = json.loads((ROOT / "contract" / "smart_scan_contract.json").read_text(encoding="utf-8"))
    if contract["fft_length"] != FFT_LENGTH:
        raise RuntimeError("FFT length drift")
    if contract["fft_boundary"]["output_bits"] != 27:
        raise RuntimeError("FFT width drift")
    if contract["power_boundary"]["magnitude_square_bits"] != 54:
        raise RuntimeError("power width drift")
    if contract["cpu_v1"][:3] != ["noise_floor", "adaptive_threshold", "bin_merge"]:
        raise RuntimeError("CPU/FPGA partition drift")


def check_no_fake_fft() -> None:
    boundary = (ROOT / "rtl" / "procise_fft_axis_boundary.sv").read_text(encoding="utf-8")
    if "module procise_fft_axis_boundary" not in boundary:
        raise RuntimeError("missing explicit FFT boundary")
    if "sin(" in boundary or "cos(" in boundary or "real " in boundary:
        raise RuntimeError("non-synthesizable fake FFT found")
    if not (ROOT / "integration" / "FFT_IP_ADAPTER.md").is_file():
        raise RuntimeError("missing vendor FFT integration contract")


def main() -> int:
    checks = 0
    checked_vectors = check_vectors(); checks += checked_vectors
    check_boundaries(); checks += 2
    check_contract(); checks += 1
    check_no_fake_fft(); checks += 1
    print(f"SMART_SCAN_PREP2_SELFTEST result=PASS checks={checks} vectors={checked_vectors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
