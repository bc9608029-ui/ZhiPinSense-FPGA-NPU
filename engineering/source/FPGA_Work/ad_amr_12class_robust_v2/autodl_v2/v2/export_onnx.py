"""V2 ONNX export reusing V1's strict operator/parity gates.

The V2 baseline is the same ADAMRV11Net as V1, so the V1 export machinery
(operator allow-list, opset 17, ONNX Runtime parity) applies unchanged.  Only
the output filename is V2-named so the V1 artifact is never overwritten.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import onnx
import torch

from models.ad_amr_v1_1_net import ADAMRV11Classifier, build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from scripts.export_ad_amr_v1_1_onnx import ALLOWED_OPS, OPSET_VERSION, inspect_onnx, _ort_parity
from training.utils import ensure_output_dirs, load_yaml, save_json
from v2.contract import V1_MODEL_SHA, V2_MODEL_NAME


def _remove_identity_nodes(path: str | Path) -> int:
    """Splice out no-op ``Identity`` nodes the exporter may emit.

    Some ``torch.onnx.export`` (legacy, ``dynamo=False``) versions insert
    ``Identity`` nodes, e.g. when constant-folding BatchNormalization into Conv.
    ``Identity`` is a pure no-op, so it is safe to rewire every reference to an
    ``Identity`` output straight to its input and delete the node.  The frozen
    NPU operator gate otherwise rejects ``Identity`` as an unexpected operator.

    Returns the number of removed nodes (0 if the graph was already clean).
    """
    model = onnx.load(str(path))
    graph = model.graph
    identity_map: dict[str, str] = {}
    identity_nodes: list[Any] = []
    for node in graph.node:
        if node.op_type == "Identity" and len(node.input) == 1 and len(node.output) == 1:
            identity_map[node.output[0]] = node.input[0]
            identity_nodes.append(node)
    if not identity_nodes:
        return 0

    def resolve(name: str) -> str:
        seen: set[str] = set()
        while name in identity_map and name not in seen:
            seen.add(name)
            name = identity_map[name]
        return name

    resolved = {key: resolve(key) for key in identity_map}
    for node in graph.node:
        for index, input_name in enumerate(node.input):
            node.input[index] = resolved.get(input_name, input_name)
    for output in graph.output:
        output.name = resolved.get(output.name, output.name)
    kept = [node for node in graph.node if node not in identity_nodes]
    del graph.node[:]
    graph.node.extend(kept)
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    return len(identity_nodes)


def export_v2(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("checkpoint and export class orders differ")
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    wrapper = ADAMRV11Classifier(model).eval()
    root = ensure_output_dirs(config["output_root"])["checkpoints"].parent
    output = root / "onnx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "12class_robust_candidate_v2_opset17.onnx"
    sample = torch.zeros(1, 2, int(config["signal"]["sample_length"]), dtype=torch.float32)
    torch.onnx.export(wrapper, sample, str(path), opset_version=OPSET_VERSION,
                      input_names=["iq"], output_names=["logits"], dynamo=False)
    removed_identity = _remove_identity_nodes(path)
    inspection = inspect_onnx(path)
    if inspection["opset"] != OPSET_VERSION:
        raise RuntimeError(f"ONNX opset {inspection['opset']} != {OPSET_VERSION}")
    if inspection["unexpected_operators"]:
        raise RuntimeError(f"NPU operator gate failed: {inspection['unexpected_operators']}")
    parity = _ort_parity(path, wrapper, sample)
    if parity["status"] != "ok":
        raise RuntimeError(f"ONNX Runtime parity failed: {parity}")
    report = {
        "onnx_path": str(path), "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]), "model_name": V2_MODEL_NAME,
        "v1_model_sha": V1_MODEL_SHA, "inspection": inspection, "ort_parity": parity,
        "graph_cleanup": {"removed_identity_nodes": removed_identity},
        "profile": profile_ad_amr_v1_1(model, sample.shape[-1]),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    save_json(report, output / "export_report_v2.json")
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/v2_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    print(export_v2(args.config, args.checkpoint))


if __name__ == "__main__":
    main()
