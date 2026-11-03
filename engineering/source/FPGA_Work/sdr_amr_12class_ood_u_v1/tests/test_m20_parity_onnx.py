"""M20 test category 15: PyTorch / ONNX fp32 logits parity + int8-NPU replay
tolerance + OOD decision agreement at the frozen threshold.

The fp32 columns (PyTorch vs ONNX, identical weights/opset) must agree tightly
and must produce *identical* UNKNOWN / known decisions.  The int8-NPU column is
board-captured, so offline we exercise the same comparison path used by
``scripts/m20_logits_parity.py`` with a simulated output-boundary quantization
and assert it falls inside the documented int8 tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ood.scores import compute_scores
from ood_u.model import load_model, predict_logits, predict_logits_onnx
from scripts.m20_parity_data import build_parity_iq
from tools.compare_logits import (
    FP32_MAX_ABS_DIFF,
    NPU_MAX_ABS_DIFF,
    compare_logits,
    read_logits_file,
)

_PROJECT = Path(__file__).resolve().parents[1]
_METHOD = "logit_margin"
_TEMPERATURE = 1.0
_THRESHOLD = -0.153


@pytest.fixture(scope="session")
def parity():
    model = load_model(_PROJECT / "model_12class/seed2026_best.pt")
    onnx = _PROJECT / "model_12class/ad_amr_v1_1_opset17.onnx"
    planar, labels = build_parity_iq()
    pt = predict_logits(model, planar)
    onnx_logits = predict_logits_onnx(onnx, planar)
    return planar, labels, pt, onnx_logits


def test_pytorch_onnx_fp32_parity(parity):
    _, _, pt, onnx_logits = parity
    report = compare_logits(pt, onnx_logits, FP32_MAX_ABS_DIFF)
    assert report["within_tolerance"], report
    assert report["max_abs_diff"] <= FP32_MAX_ABS_DIFF
    assert report["argmax_agreement"] == 1.0, report


def test_pytorch_onnx_ood_decision_agreement(parity):
    _, _, pt, onnx_logits = parity
    ref_score = compute_scores(pt, _METHOD, _TEMPERATURE)
    onnx_score = compute_scores(onnx_logits, _METHOD, _TEMPERATURE)
    assert np.array_equal(ref_score > _THRESHOLD, onnx_score > _THRESHOLD)


def test_npu_int8_replay_within_tolerance(parity, tmp_path):
    _, _, pt, _ = parity
    # Simulate the observed int8 output-boundary quantization (scale 0.23273507,
    # see tools/compare_logits.py) and route it through the *same* read + compare
    # path the one-click parity script uses for the board-captured NPU column.
    scale = 0.23273507
    quantized = np.round(pt / scale) * scale
    npu_path = tmp_path / "npu_logits.json"
    npu_path.write_text(
        json.dumps({"n": int(quantized.shape[0]),
                    "output_dim": 12, "logits": quantized.tolist()}),
        encoding="utf-8")
    npu = read_logits_file(npu_path, "NPU")
    report = compare_logits(pt, npu, NPU_MAX_ABS_DIFF)
    assert report["within_tolerance"], report
    assert report["max_abs_diff"] <= NPU_MAX_ABS_DIFF
