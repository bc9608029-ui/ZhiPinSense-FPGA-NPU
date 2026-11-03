"""Real-CUDA gate for the data-v4 robustness fine-tune wiring.

Verifies on a real GPU + BF16: strict init from the frozen twelve-class best
checkpoint -> one epoch -> strict resume one epoch -> frozen validation -> ONNX
export with the unchanged operator whitelist, then writes the robustness
preflight marker.  No RadioML public data and no final blind data is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1_data_v4_12class_robust import write_robust_marker
from training.train_ad_amr_v4_12class_robust import run_robust_training
from training.utils import load_yaml

PASS = "AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_CUDA_PREFLIGHT_PASS"


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("robustness preflight requires a real CUDA device")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("robustness preflight requires BF16 support")
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust_preflight.yaml")
    if config["training"].get("amp_dtype") != "bfloat16":
        raise RuntimeError("robustness preflight must use BF16")

    first = run_robust_training(config, resume=False, stop_after_epoch=1)
    if first["init"].get("mode") != "fine_tune_from_twelve_class_best":
        raise RuntimeError("robustness preflight did not init from the twelve-class best")
    if [int(row["epoch"]) for row in first["history"]] != [1]:
        raise RuntimeError("robustness initial history is not [1]")
    resumed = run_robust_training(config, resume=True, stop_after_epoch=1)
    if [int(row["epoch"]) for row in resumed["history"]] != [1, 2]:
        raise RuntimeError("robustness strict-resume history is not [1,2]")

    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    evaluation = evaluate_v1_1(config, checkpoint)
    export = export_v1_1(config, checkpoint)
    if evaluation["final_blind_test_accessed"]:
        raise RuntimeError("robustness preflight accessed final blind data")
    if export["inspection"]["unexpected_operators"]:
        raise RuntimeError("robustness preflight exported unexpected NPU operators")

    payload = {
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "amp_dtype": "bfloat16", "history": [1, 2],
        "class_contract": config["signal"]["modulations"],
        "init": first["init"],
        "train_channel_sha256": first["train_channel_sha256"],
        "architecture_changed_from_v1_1": first["architecture_changed_from_v1_1"],
        "validation_macro_f1": evaluation["metrics"]["macro_f1"],
        "onnx": export["inspection"], "ort": export["ort_parity"],
    }
    bound = write_robust_marker(config, payload)
    print(json.dumps(payload, indent=2))
    print(f"release_input_hash={bound}")
    print(PASS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
