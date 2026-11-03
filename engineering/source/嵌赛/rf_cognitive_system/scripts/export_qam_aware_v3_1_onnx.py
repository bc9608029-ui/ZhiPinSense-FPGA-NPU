"""Export V3.1 training and FPGA-partitioned graphs to ONNX opset 17.

This exporter is a hard gate, not a reporter:

* ``onnx.checker`` must pass for both graphs;
* the default-domain opset must be exactly 17;
* the NPU partition inputs must be ``iq`` FP32 ``[1, 2, 1024]`` and
  ``physical_features`` FP32 ``[1, 3, 1024]``;
* the output ``logits`` must be FP32 ``[1, 8]``;
* every operator in the NPU partition must be in the frozen deployment policy
  (Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm).  Any unexpected
  operator raises ``SystemExit`` — it is never downgraded to a warning.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import onnx
import torch
from onnx import TensorProto

from models.qam_aware_rfnet_v3_1 import build_qam_aware_v3_1, build_qam_aware_v3_1_partition
from training.qam_aware_v3_1_utils import load_qam_aware_v3_1_config
from training.utils import ensure_output_dirs

ALLOWED_OPS = {
    "Add",
    "BatchNormalization",
    "Concat",
    "Conv",
    "Gemm",
    "Mul",
    "ReduceMean",
    "Relu",
}
OPSET_VERSION = 17
FLOAT = TensorProto.DataType.Name(TensorProto.FLOAT)


def _fail(message: str) -> None:
    # A hard gate: non-zero exit, never a recorded warning that still passes.
    raise SystemExit(f"[ONNX export gate] {message}")


def _default_opset(model: onnx.ModelProto) -> int:
    for imp in model.opset_import:
        if imp.domain in ("", "ai.onnx"):
            return int(imp.version)
    _fail("no default-domain opset import found")


def _tensor_spec(value_info) -> dict[str, object]:
    tensor = value_info.type.tensor_type
    dims: list[object] = []
    for dim in tensor.shape.dim:
        if dim.HasField("dim_value"):
            dims.append(int(dim.dim_value))
        elif dim.HasField("dim_param"):
            dims.append(str(dim.dim_param))
        else:
            dims.append(None)
    return {
        "name": value_info.name,
        "elem_type": int(tensor.elem_type),
        "dtype": TensorProto.DataType.Name(tensor.elem_type),
        "shape": dims,
    }


def _io_spec(model: onnx.ModelProto) -> dict[str, object]:
    return {
        "inputs": [_tensor_spec(v) for v in model.graph.input],
        "outputs": [_tensor_spec(v) for v in model.graph.output],
    }


def _find_io(specs: list[dict], name: str) -> dict:
    for spec in specs:
        if spec["name"] == name:
            return spec
    _fail(f"missing graph I/O tensor {name!r}")


def _assert_spec(spec: dict, dtype: str, shape: list[int]) -> None:
    if spec["dtype"] != dtype:
        _fail(
            f"tensor {spec['name']!r} dtype {spec['dtype']} != expected {dtype}"
        )
    if spec["shape"] != shape:
        _fail(
            f"tensor {spec['name']!r} shape {spec['shape']} != expected {shape}"
        )


def _inspect(path: Path) -> dict[str, object]:
    model = onnx.load(str(path))
    onnx.checker.check_model(model)  # raises CheckerError -> non-zero exit
    opset = _default_opset(model)
    if opset != OPSET_VERSION:
        _fail(f"{path.name} default-domain opset {opset} != {OPSET_VERSION}")
    operators = Counter(node.op_type for node in model.graph.node)
    return {
        "checker_passed": True,
        "opset": opset,
        "op_types": dict(sorted(operators.items())),
        "io": _io_spec(model),
        "file_size_bytes": path.stat().st_size,
    }


def _gate_partition(inspection: dict[str, object]) -> None:
    io = inspection["io"]
    _assert_spec(_find_io(io["inputs"], "iq"), FLOAT, [1, 2, 1024])
    _assert_spec(_find_io(io["inputs"], "physical_features"), FLOAT, [1, 3, 1024])
    _assert_spec(_find_io(io["outputs"], "logits"), FLOAT, [1, 8])

    actual = set(inspection["op_types"])
    unexpected = sorted(actual - ALLOWED_OPS)
    if unexpected:
        _fail(
            "NPU partition contains unexpected operators "
            f"{unexpected}; allowed policy is {sorted(ALLOWED_OPS)}"
        )


def _gate_e2e(inspection: dict[str, object]) -> None:
    io = inspection["io"]
    _assert_spec(_find_io(io["inputs"], "iq"), FLOAT, [1, 2, 1024])
    _assert_spec(_find_io(io["outputs"], "logits"), FLOAT, [1, 8])


def export_v3_1(config_path: str, checkpoint_path: str | None = None) -> dict[str, object]:
    config = load_qam_aware_v3_1_config(config_path)
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=False)
    classes = list(config["signal"]["modulations"])
    length = int(config["signal"]["sample_length"])
    model = build_qam_aware_v3_1(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    destination = paths["checkpoints"].parent / "onnx"
    destination.mkdir(parents=True, exist_ok=True)
    e2e_path = destination / "qam_aware_v3_1_e2e_opset17.onnx"
    partition_path = destination / "qam_aware_v3_1_npu_partition_opset17.onnx"
    iq = torch.zeros(1, 2, length, dtype=torch.float32)
    physical = torch.zeros(1, 3, length, dtype=torch.float32)

    torch.onnx.export(
        model,
        iq,
        e2e_path,
        opset_version=OPSET_VERSION,
        input_names=["iq"],
        output_names=["logits"],
        dynamo=False,
    )
    torch.onnx.export(
        build_qam_aware_v3_1_partition(model).eval(),
        (iq, physical),
        partition_path,
        opset_version=OPSET_VERSION,
        input_names=["iq", "physical_features"],
        output_names=["logits"],
        dynamo=False,
    )

    e2e = _inspect(e2e_path)
    partition = _inspect(partition_path)
    _gate_e2e(e2e)
    _gate_partition(partition)

    report = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "e2e": e2e,
        "npu_partition": partition,
        "allowed_operator_policy": sorted(ALLOWED_OPS),
        "npu_partition_unexpected_operators": [],
    }
    (destination / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_1_smoke.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    try:
        print(json.dumps(export_v3_1(args.config, args.checkpoint), indent=2))
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
