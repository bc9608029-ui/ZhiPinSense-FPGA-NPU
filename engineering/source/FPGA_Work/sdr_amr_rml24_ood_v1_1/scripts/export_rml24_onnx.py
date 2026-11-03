"""Export and strictly gate the deployable 24-class ONNX graph.

Mirrors ``scripts.export_ad_amr_v1_1_onnx`` but pins the frozen 24-class contract
(``RML24Classifier``, ``num_classes=24``, raw logits) and a 24-class-specific
output filename.  The operator whitelist, opset, and ONNX Runtime parity gates
are identical to the 12-class exporter.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from contracts.rml24_contract import LABEL_ORDER_24, RML24_MODEL_NAME
from models.ad_amr_v1_1_net import profile_ad_amr_v1_1
from models.rml24_net import RML24Classifier, build_rml24_model
from ood.scores import compute_scores
from scripts.export_ad_amr_v1_1_onnx import OPSET_VERSION, _ort_parity, inspect_onnx
from training.utils import ensure_output_dirs, load_yaml, save_json
from v2.candidate_signature import label_contract_sha256

_PARITY_TOLERANCE = 1e-3


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ort_logits(path: Path, sample: torch.Tensor) -> np.ndarray:
    import onnxruntime as ort

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return np.asarray(session.run(None, {"iq": sample.numpy()})[0], dtype=np.float32)


def _assert_no_softmax(model: torch.nn.Module) -> None:
    for module in model.modules():
        if isinstance(module, (torch.nn.Softmax, torch.nn.LogSoftmax)):
            raise RuntimeError("24-class model must emit raw logits (no Softmax/LogSoftmax)")


def _argmax_parity(torch_logits: np.ndarray, ort_logits: np.ndarray) -> dict[str, Any]:
    torch_argmax = torch_logits.argmax(1)
    ort_argmax = ort_logits.argmax(1)
    return {"match": bool((torch_argmax == ort_argmax).all()),
            "mismatch_count": int((torch_argmax != ort_argmax).sum())}


def _ood_score_parity(torch_logits: np.ndarray, ort_logits: np.ndarray) -> dict[str, Any]:
    parity: dict[str, Any] = {}
    for method in ("energy", "msp"):
        torch_scores = compute_scores(torch_logits, method)
        ort_scores = compute_scores(ort_logits, method)
        diff = float(np.abs(torch_scores - ort_scores).max())
        parity[method] = {"max_abs_diff": diff, "tolerance": _PARITY_TOLERANCE,
                          "status": "ok" if diff < _PARITY_TOLERANCE else "mismatch"}
    return parity


def export_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                 *, manifest_path: str | Path | None = None) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    classes = list(LABEL_ORDER_24)

    manifest: dict[str, Any] | None = None
    if manifest_path is not None:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if int(manifest.get("class_count", -1)) != len(classes):
            raise RuntimeError(f"manifest class_count {manifest.get('class_count')} != {len(classes)}")
        if not str(manifest.get("model_name", "")).strip():
            raise RuntimeError("manifest missing model_name")
        checkpoint_path = manifest["checkpoint_path"]
        expected_sha = str(manifest["checkpoint_sha256"])
        actual_sha = _sha256_file(Path(checkpoint_path))
        if actual_sha != expected_sha:
            raise RuntimeError(f"checkpoint SHA {actual_sha} != manifest {expected_sha}")

    checkpoint_path = Path(checkpoint_path)
    checkpoint_sha = _sha256_file(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("24-class checkpoint class order differs from the frozen contract")
    model = build_rml24_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    _assert_no_softmax(model)
    wrapper = RML24Classifier(model).eval()

    sample_length = int(config.get("signal", {}).get("sample_length", 1024))
    sample = torch.zeros(1, 2, sample_length, dtype=torch.float32)
    with torch.inference_mode():
        probe = wrapper(sample)
    if tuple(probe.shape) != (1, len(classes)):
        raise RuntimeError(f"unexpected logits shape {tuple(probe.shape)} (expected [1, {len(classes)}])")

    root = ensure_output_dirs(config["output_root"])["checkpoints"].parent
    output = root / "onnx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "rml24_opset17.onnx"
    torch.onnx.export(wrapper, sample, str(path), opset_version=OPSET_VERSION,
                      input_names=["iq"], output_names=["logits"], dynamo=False)
    inspection = inspect_onnx(path)
    if inspection["opset"] != OPSET_VERSION:
        raise RuntimeError(f"ONNX opset {inspection['opset']} != {OPSET_VERSION}")
    if inspection["unexpected_operators"]:
        raise RuntimeError(f"NPU operator gate failed: {inspection['unexpected_operators']}")
    parity = _ort_parity(path, wrapper, sample)
    if parity["status"] != "ok":
        raise RuntimeError(f"ONNX Runtime parity failed: {parity}")

    rng = torch.Generator().manual_seed(int(config["seed"]))
    batch = torch.randn(64, 2, sample_length, generator=rng)
    with torch.inference_mode():
        torch_logits = wrapper(batch).float().cpu().numpy()
    ort_logits = _ort_logits(path, batch)
    logits_diff = np.abs(torch_logits - ort_logits)
    argmax = _argmax_parity(torch_logits, ort_logits)
    if not argmax["match"]:
        raise RuntimeError(f"argmax parity failed: {argmax}")
    ood_parity = _ood_score_parity(torch_logits, ort_logits)

    label_sha = str(manifest.get("label_contract_sha256") or label_contract_sha256()) if manifest else label_contract_sha256()
    export_manifest = {
        "source_checkpoint_path": str(checkpoint_path),
        "source_checkpoint_sha256": checkpoint_sha,
        "onnx_path": str(path),
        "onnx_sha256": _sha256_file(path),
        "label_contract_sha256": label_sha,
        "model_name": str(manifest["model_name"]) if manifest else RML24_MODEL_NAME,
        "class_count": len(classes),
        "class_names": classes,
        "input_contract": {"name": "iq", "shape": [1, 2, sample_length], "dtype": "float32"},
        "output_contract": {"name": "logits", "shape": [1, len(classes)],
                            "kind": "raw_logits_no_softmax"},
        "opset": OPSET_VERSION,
        "checker_passed": bool(inspection["checker_passed"]),
        "operator_whitelist": {"allowed": sorted(inspection["op_types"]),
                               "unexpected": inspection["unexpected_operators"]},
        "parity": {
            "logits_max_abs_diff": float(logits_diff.max()),
            "logits_mean_abs_diff": float(logits_diff.mean()),
            "logits_tolerance": _PARITY_TOLERANCE,
            "single_sample_ort_parity": parity,
            "argmax_parity": argmax,
            "ood_score_parity": ood_parity,
        },
    }
    save_json(export_manifest, output / "export_manifest.json")

    report = {
        "onnx_path": str(path), "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_sha256": checkpoint_sha, "inspection": inspection,
        "ort_parity": parity, "argmax_parity": argmax, "ood_score_parity": ood_parity,
        "profile": profile_ad_amr_v1_1(model, sample_length),
        "export_manifest": str(output / "export_manifest.json"),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    save_json(report, output / "export_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--manifest", default=None,
                        help="final_checkpoint_manifest.json to verify checkpoint SHA against")
    args = parser.parse_args()
    print(json.dumps(export_rml24(args.config, args.checkpoint,
                                  manifest_path=args.manifest), indent=2))


if __name__ == "__main__":
    main()
