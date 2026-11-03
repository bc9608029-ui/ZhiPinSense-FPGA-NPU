"""Real-CUDA gate for public pretrain -> 12-class trunk transfer -> export."""

from __future__ import annotations

import json
from pathlib import Path

import torch

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.overfit_probe_v1_1 import run_probe
from scripts.release_guard_v1_1_data_v3_12class import write_marker
from training.pretrain_ad_amr_v1_1_radioml import run_public_pretraining
from training.train_ad_amr_v1_1_data_v3_12class import run_data_v3_training
from training.utils import load_yaml

PASS = "AD_AMR_V1_1_DATA_V3_12CLASS_CUDA_PREFLIGHT_PASS"


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("twelve-class preflight requires a real CUDA device")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("twelve-class preflight requires BF16 support")
    config = load_yaml("configs/ad_amr_v1_1_data_v3_12class_preflight.yaml")
    if config["training"].get("amp_dtype") != "bfloat16":
        raise RuntimeError("target preflight must use BF16")
    if config["public_pretraining"].get("amp_dtype") != "bfloat16":
        raise RuntimeError("public preflight must use BF16")

    overfit = run_probe(
        steps=250,
        config_path="configs/ad_amr_v1_1_data_v3_12class_preflight.yaml",
        output_path="outputs/ad_amr_v1_1_data_v3_12class/preflight/overfit_probe.json",
    )
    public_first = run_public_pretraining(config, resume=False, stop_after_epoch=1)
    public_resumed = run_public_pretraining(config, resume=True, stop_after_epoch=1)
    if [int(row["epoch"]) for row in public_first["history"]] != [1]:
        raise RuntimeError("public initial history is not [1]")
    if [int(row["epoch"]) for row in public_resumed["history"]] != [1, 2]:
        raise RuntimeError("public strict-resume history is not [1,2]")

    target_first = run_data_v3_training(config, resume=False, stop_after_epoch=1)
    target_resumed = run_data_v3_training(config, resume=True, stop_after_epoch=1)
    if [int(row["epoch"]) for row in target_first["history"]] != [1]:
        raise RuntimeError("target initial history is not [1]")
    if [int(row["epoch"]) for row in target_resumed["history"]] != [1, 2]:
        raise RuntimeError("target strict-resume history is not [1,2]")

    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    evaluation = evaluate_v1_1(config, checkpoint)
    export = export_v1_1(config, checkpoint)
    if evaluation["final_blind_test_accessed"]:
        raise RuntimeError("preflight accessed final blind data")
    if export["inspection"]["unexpected_operators"]:
        raise RuntimeError("preflight exported unexpected NPU operators")
    if int(target_resumed["target_class_count"]) != 12:
        raise RuntimeError("model profile is not twelve-class")
    payload = {
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "amp_dtype": "bfloat16", "public_history": [1, 2], "target_history": [1, 2],
        "class_contract": config["signal"]["modulations"],
        "fixed_batch_overfit": overfit,
        "public_dataset_sha256": public_resumed["dataset_sha256"],
        "public_test_accessed": public_resumed["public_test_accessed"],
        "target_macro_f1": evaluation["metrics"]["macro_f1"],
        "onnx": export["inspection"], "ort": export["ort_parity"],
    }
    bound = write_marker(config, payload)
    print(json.dumps(payload, indent=2))
    print(f"release_input_hash={bound}")
    print(PASS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
