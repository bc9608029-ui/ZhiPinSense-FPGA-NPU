"""pytest for the M27 confusable-class expert framework (spec §十二)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "channel_proto"))

from m27_expert_framework import (  # noqa: E402
    EXPERT_FRAMEWORK_STATUS,
    EXPERT_MODEL_STATUS,
    LABEL_ORDER_24,
    PLACEHOLDER_EXPERT_GROUPS,
    find_confusable_pairs,
    build_expert_label_map,
    routing_gate,
)
from m27_channel_contract import SUPPORTED_OPS  # noqa: E402


def test_status_markers():
    assert EXPERT_FRAMEWORK_STATUS == "EXPERT_MODEL_FRAMEWORK_READY"
    assert EXPERT_MODEL_STATUS == "24CLASS_EXPERT_MODEL_NOT_TRAINED"
    assert len(LABEL_ORDER_24) == 24


def test_find_confusable_pairs():
    # 24x24; classes 0 and 1 are bidirectionally confused, 5 and 6 are not.
    cm = np.eye(24) * 100
    cm[0, 1] = cm[1, 0] = 40
    pairs = find_confusable_pairs(cm, min_ratio=0.05)
    assert (0, 1) in pairs
    assert (5, 6) not in pairs


def test_expert_label_map():
    m = build_expert_label_map(PLACEHOLDER_EXPERT_GROUPS, LABEL_ORDER_24)
    assert m[12] == ("qam", 0, "16QAM")
    assert m[4] == ("psk", 1, "QPSK")


def test_routing_gate_not_trained():
    status, msg = routing_gate()
    assert status == "24CLASS_EXPERT_MODEL_NOT_TRAINED"
    assert "not frozen" in msg


def test_stub_model_and_onnx(tmp_path):
    torch = pytest.importorskip("torch")
    from m27_expert_framework import ExpertStub, export_expert_onnx, npu_operator_audit
    model = ExpertStub(n_classes=4)
    model.eval()
    x = torch.zeros(2, 2, 1024)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (2, 4)
    onnx_path = str(tmp_path / "expert_stub.onnx")
    export_expert_onnx(model, onnx_path)
    assert os.path.exists(onnx_path)
    ok, unsupported = npu_operator_audit(onnx_path, SUPPORTED_OPS)
    assert ok, f"unsupported ops: {unsupported}"
