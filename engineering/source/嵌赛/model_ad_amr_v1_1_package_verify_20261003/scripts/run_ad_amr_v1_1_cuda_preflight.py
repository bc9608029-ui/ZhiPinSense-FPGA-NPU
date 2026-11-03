"""Release-blocking real-CUDA production-path preflight."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1 import write_marker
from training.train_ad_amr_v1_1 import run_v1_1_training
from training.utils import load_yaml

PASS = "AD_AMR_V1_1_CUDA_PREFLIGHT_PASS"


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("V1.1 CUDA preflight requires a real CUDA device")
    config = load_yaml("configs/ad_amr_v1_1_preflight.yaml")
    first = run_v1_1_training(config, resume=False, stop_after_epoch=1)
    if [int(row["epoch"]) for row in first["history"]] != [1]:
        raise RuntimeError("preflight initial history is not [1]")
    resumed = run_v1_1_training(config, resume=True, stop_after_epoch=1)
    if [int(row["epoch"]) for row in resumed["history"]] != [1, 2]:
        raise RuntimeError("preflight strict-resume history is not [1,2]")
    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    evaluation = evaluate_v1_1(config, checkpoint)
    export = export_v1_1(config, checkpoint)
    if evaluation["final_blind_test_accessed"]:
        raise RuntimeError("preflight accessed final blind data")
    if export["inspection"]["unexpected_operators"]:
        raise RuntimeError("preflight exported unexpected NPU operators")
    payload = {
        "device": torch.cuda.get_device_name(0), "torch": torch.__version__,
        "cuda": torch.version.cuda, "history": [1, 2],
        "macro_f1": evaluation["metrics"]["macro_f1"],
        "onnx": export["inspection"], "ort": export["ort_parity"],
    }
    bound = write_marker(payload)
    print(json.dumps(payload, indent=2))
    print(f"release_input_hash={bound}")
    print(PASS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
