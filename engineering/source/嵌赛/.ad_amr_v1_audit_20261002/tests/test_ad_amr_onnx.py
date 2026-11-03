"""AD-AMR ONNX export + ORT parity + NPU-whitelist-gap audit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from models.ad_amr_net import ADAMRClassifier, build_ad_amr_model
from scripts.export_ad_amr_onnx import ALLOWED_OPS, OPSET_VERSION, _inspect, _ort_parity
from training.utils import load_yaml, set_seed

pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")


def _export(tmp_path: Path):
    cfg = load_yaml("configs/ad_amr_v1.yaml")
    set_seed(2026)
    model = build_ad_amr_model(8, **cfg["model"]).eval()
    sample = torch.randn(1, 2, 1024)
    onnx_path = tmp_path / "ad_amr_classifier.onnx"
    torch.onnx.export(
        ADAMRClassifier(model).eval(), sample, str(onnx_path), opset_version=OPSET_VERSION,
        input_names=["iq"], output_names=["logits"], dynamo=False,
    )
    return model, sample, onnx_path


def test_onnx_checker_and_opset(tmp_path) -> None:
    _, _, onnx_path = _export(tmp_path)
    inspection = _inspect(onnx_path)
    assert inspection["checker_passed"] is True
    assert inspection["opset"] == OPSET_VERSION


def test_ort_parity(tmp_path) -> None:
    model, sample, onnx_path = _export(tmp_path)
    parity = _ort_parity(onnx_path, model, sample)
    assert parity["status"] == "ok", parity
    assert parity["max_abs_diff"] < 1e-3


def test_npu_whitelist_gap_is_documented(tmp_path) -> None:
    _, _, onnx_path = _export(tmp_path)
    inspection = _inspect(onnx_path)
    actual = set(inspection["op_types"])
    gap = sorted(actual - ALLOWED_OPS)
    # The denoising front-end necessarily introduces ops outside the 8-op policy
    # (ECA sigmoid and soft-thresholding sign/abs at minimum).
    assert "Sigmoid" in actual, "ECA channel attention must introduce Sigmoid"
    assert gap, "expected a non-empty gap vs the frozen 8-op NPU whitelist"
