"""The ONNX export gate fails hard on any unexpected operator or wrong I/O."""

from __future__ import annotations

import pytest

from scripts.export_qam_aware_v3_1_onnx import _gate_partition


def _inspection(op_types, iq_shape, physical_shape, logits_shape, logits_dtype="FLOAT"):
    return {
        "op_types": op_types,
        "io": {
            "inputs": [
                {"name": "iq", "dtype": "FLOAT", "shape": iq_shape},
                {"name": "physical_features", "dtype": "FLOAT", "shape": physical_shape},
            ],
            "outputs": [{"name": "logits", "dtype": logits_dtype, "shape": logits_shape}],
        },
    }


def test_gate_passes_clean_partition() -> None:
    _gate_partition(
        _inspection({"Conv": 24, "Relu": 22, "Add": 6}, [1, 2, 1024], [1, 3, 1024], [1, 8])
    )


def test_gate_rejects_unexpected_operator() -> None:
    with pytest.raises(SystemExit):
        _gate_partition(
            _inspection({"Conv": 1, "Constant": 4}, [1, 2, 1024], [1, 3, 1024], [1, 8])
        )


def test_gate_rejects_wrong_iq_shape() -> None:
    with pytest.raises(SystemExit):
        _gate_partition(
            _inspection({"Conv": 1}, [1, 2, 512], [1, 3, 1024], [1, 8])
        )


def test_gate_rejects_wrong_output_dtype() -> None:
    with pytest.raises(SystemExit):
        _gate_partition(
            _inspection({"Conv": 1}, [1, 2, 1024], [1, 3, 1024], [1, 8], logits_dtype="DOUBLE")
        )
