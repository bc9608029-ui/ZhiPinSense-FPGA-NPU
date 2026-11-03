"""pytest for the M27 channel/interference synthetic prototype (spec §十一)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from m27_channel_contract import (  # noqa: E402
    CHANNEL_LABELS,
    NUM_CHANNEL_LABELS,
    MODULATION_POOL,
    ALLOWED_STATUS,
    FORBIDDEN_STATUS_MARKERS,
    SUPPORTED_OPS,
)
from m27_channel_generator import generate_all, generate_split  # noqa: E402
from m27_channel_manifest import build_manifest, verify_zero_overlap  # noqa: E402
from m27_channel_shortcut_audit import audit_shortcuts  # noqa: E402
from m27_channel_contract import SPLIT_TRAIN  # noqa: E402


def test_contract_labels():
    assert CHANNEL_LABELS == [
        "CLEAN", "CFO", "PHASE_NOISE", "IQ_IMBALANCE", "MULTIPATH", "CLIPPING",
        "CW_INTERFERENCE", "MULTITONE", "PULSE", "SWEEP", "MULTI_IMPAIRMENT",
    ]
    assert NUM_CHANNEL_LABELS == 11
    assert ALLOWED_STATUS == "CHANNEL_IMPAIRMENT_MODEL_SYNTHETIC_PROTOTYPE"
    assert "HARDWARE_PASS" in FORBIDDEN_STATUS_MARKERS


def test_generator_shape_dtype_rms():
    x, y, snr = generate_split(2026, SPLIT_TRAIN, samples_per_label=8)
    assert x.dtype == np.float32
    assert x.shape == (11 * 8, 2, 1024)
    assert y.shape == (11 * 8,)
    assert snr.shape == (11 * 8,)
    # complex IQ signal is RMS-normalised to ~1: mean(real^2 + imag^2) ~= 1
    rms = np.sqrt(np.mean(x[:, 0] ** 2 + x[:, 1] ** 2, axis=1))
    assert np.allclose(rms, 1.0, atol=1e-3)
    # balanced across environments
    for i in range(11):
        assert (y == i).sum() == 8


def test_generator_reproducible_and_isolated():
    x1, y1, _ = generate_split(2026, SPLIT_TRAIN, samples_per_label=8)
    x2, y2, _ = generate_split(2026, SPLIT_TRAIN, samples_per_label=8)
    assert np.array_equal(x1, x2) and np.array_equal(y1, y2)
    # different split code -> different stream
    xv, yv, _ = generate_split(2026, 1, samples_per_label=8)
    assert not np.array_equal(x1, xv)


def test_manifest_zero_overlap():
    splits = generate_all(seed=2026, samples_per_label=16)
    manifest = build_manifest(splits, 2026)
    assert verify_zero_overlap(manifest)
    per = manifest["splits"]["train"]["per_label"]
    assert per == manifest["splits"]["final_test"]["per_label"]
    assert all(c == 16 for c in per)


def test_shortcut_audit_ok():
    splits = generate_all(seed=2026, samples_per_label=16)
    ok, reasons = audit_shortcuts(splits)
    assert ok, reasons


def test_shortcut_audit_detects_power_encoding():
    # A label recoverable from mean power must be flagged.
    splits = generate_all(seed=2026, samples_per_label=16)
    x, y, _ = splits["train"]
    x = x.copy()
    x[y == 0] *= 5.0  # make CLEAN have fixed high power -> shortcut
    bad_splits = {k: (v[0].copy(), v[1], v[2]) for k, v in splits.items()}
    bad_splits["train"] = (x, y, splits["train"][2])
    ok, reasons = audit_shortcuts(bad_splits)
    assert not ok


def test_model_and_onnx_and_int8(tmp_path):
    torch = pytest.importorskip("torch")
    from m27_channel_model import ChannelImpairmentNet, export_onnx, int8_feasibility
    model = ChannelImpairmentNet()
    model.eval()
    x = torch.zeros(4, 2, 1024)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (4, 11)
    onnx_path = str(tmp_path / "m27_channel.onnx")
    export_onnx(model, onnx_path)
    assert os.path.exists(onnx_path)
    ok, unsupported = int8_feasibility(onnx_path, SUPPORTED_OPS)
    assert ok, f"unsupported ops: {unsupported}"
