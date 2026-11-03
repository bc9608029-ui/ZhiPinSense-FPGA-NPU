"""M20 NPU logits capture (host reference + capture contract, Section 十一).

Produces the fixed IQ parity bundle (raw fp32 planar [N,2,1024]) and the host
reference logits (PyTorch fp32 + ONNX fp32) plus a capture contract that names
the board-side tool (``tools/capture_npu_logits``) and the exact output JSON
schema it must emit.  The board capture itself is executed by the user on the
ZG330 — this script only prepares the offline reference.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ood_u import contract
from ood_u.model import load_model
from scripts.m20_common import (
    PROJECT_ROOT,
    add_common_args,
    emit_result,
    new_run_id,
    resolve_path,
    run,
    write_json,
)
from scripts.m20_parity_data import build_parity_iq, save_reference_bundle

_CAPTURE_TOOL = "tools/capture_npu_logits"


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_npu_logits_capture")
    model = load_model(resolve_path(args.checkpoint))
    onnx_path = resolve_path("model_12class/ad_amr_v1_1_opset17.onnx")

    planar, labels = build_parity_iq()
    meta = save_reference_bundle(out_dir, planar, labels, model, onnx_path)

    contract_payload: dict[str, Any] = {
        "run_id": run_id,
        "step": "npu_logits_capture",
        "capture_tool": _CAPTURE_TOOL,
        "input": {
            "path": "parity_iq.bin",
            "dtype": "float32",
            "layout": "planar_iq_c_order",
            "shape": meta["shape"],
            "sha256": meta["iq_sha256"],
        },
        "model_sha256": contract.MODEL_SHA256,
        "label_order": list(contract.LABEL_ORDER_12),
        "expected_output": {
            "schema": "capture_npu_logits",
            "fields": ["n", "output_dim", "logits"],
            "logits_numeric_type": "fp32",
            "logits_kind": "raw_logits_no_softmax",
            "note": "logits[i] is the 12-d raw logit vector for parity_iq.bin sample i",
        },
        "board_execution": {
            "who": "user (ZG330 FMQL30TAI)",
            "how": "run tools/capture_npu_logits on parity_iq.bin, then save its JSON output as npu_logits.json",
            "then": "scripts/run_m20_logits_parity.sh --npu-logits npu_logits.json --manifest runs/m20_threshold_calibration/ood_u_threshold_manifest.json",
        },
    }
    out_path = write_json(out_dir / "capture_contract.json", contract_payload)
    emit_result("PASS", run_id,
                n_samples=meta["n"],
                iq_sha256=meta["iq_sha256"][:16] + "...",
                capture_tool=_CAPTURE_TOOL,
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 NPU logits capture (host reference)")
    add_common_args(parser)
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
