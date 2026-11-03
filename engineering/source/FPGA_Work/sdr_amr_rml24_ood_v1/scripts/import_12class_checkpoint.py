"""Import the 12-class V2 checkpoint into the shared OOD framework (M0).

Fail-closed: the 12-class V2 model is trained by a *separate* project, so this
project ships the contract with a PENDING placeholder.  Once the real checkpoint
exists, fill ``contracts/12class_import_contract.json`` (checkpoint_path +
model_sha256) and this importer verifies SHA-256 + label order + output dim
before writing an import manifest.  Until then it refuses with
``BLOCKED_12CLASS_CONTRACT``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from training.utils import load_yaml, resolve_project_path, save_json

_CONTRACT = "contracts/12class_import_contract.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_12class(contract_path: str | Path = _CONTRACT,
                   output_path: str | Path | None = None) -> dict[str, Any]:
    contract_file = resolve_project_path(contract_path)
    contract = json.loads(contract_file.read_text(encoding="utf-8"))

    checkpoint = str(contract.get("checkpoint_path", ""))
    expected_sha = str(contract.get("model_sha256", ""))
    if checkpoint.startswith("PENDING") or expected_sha.startswith("PENDING") or \
            str(contract.get("status", "")).startswith("PENDING"):
        raise RuntimeError(
            "BLOCKED_12CLASS_CONTRACT: checkpoint_path / model_sha256 are still PENDING; "
            "the 12-class V2 checkpoint has not been imported yet."
        )

    ckpt_path = resolve_project_path(checkpoint)
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"12-class checkpoint missing: {ckpt_path}")
    actual_sha = _sha256(ckpt_path)
    if actual_sha != expected_sha:
        raise RuntimeError(
            f"12-class checkpoint SHA-256 mismatch: expected {expected_sha}, got {actual_sha}"
        )

    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    label_order = [str(v).upper() for v in contract["label_order_12"]]
    if [str(v).upper() for v in state.get("class_names", [])] != label_order:
        raise RuntimeError("12-class checkpoint class order differs from the import contract")

    model_state = state["model_state"]
    classifier_weight = None
    for name, tensor in model_state.items():
        if name.endswith("classifier.1.weight") or name.endswith("fc.1.weight"):
            classifier_weight = tensor
            break
    output_dim = int(classifier_weight.shape[0]) if classifier_weight is not None else None
    if output_dim is not None and output_dim != int(contract["output_dim"]):
        raise RuntimeError(f"12-class checkpoint output dim {output_dim} != {contract['output_dim']}")

    manifest: dict[str, Any] = {
        "model_name": contract["model_name"],
        "checkpoint_path": str(ckpt_path),
        "model_sha256": actual_sha,
        "label_order_12": label_order,
        "output_dim": output_dim,
        "input_shape": contract["input_shape"],
        "status": "IMPORTED_12CLASS_V2",
    }
    destination = output_path or "runs/12class_import/import_manifest.json"
    save_json(manifest, destination)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default=_CONTRACT)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    print(json.dumps(import_12class(args.contract, args.output), indent=2))


if __name__ == "__main__":
    main()
