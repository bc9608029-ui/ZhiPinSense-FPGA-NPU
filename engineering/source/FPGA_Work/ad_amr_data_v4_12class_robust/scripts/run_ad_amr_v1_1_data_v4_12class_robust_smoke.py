"""Offline CPU smoke for the data-v4 robustness wiring (no CUDA, no real data).

Writes a synthetic twelve-class init checkpoint (so the fine-tune has a valid
``model_state`` / ``class_names`` to load strictly), then runs a two-epoch CPU
fine-tune with the augmented train channel, evaluates the frozen validation, and
confirms the ONNX export keeps the unchanged operator whitelist.  This only
verifies wiring — it is not a training run and no result is promoted.
"""

from __future__ import annotations

import torch

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from training.train_ad_amr_v4_12class_robust import run_robust_training
from training.utils import load_yaml, resolve_project_path

SMOKE_CONFIG = "configs/ad_amr_v1_1_data_v4_12class_robust_smoke.yaml"


def main() -> int:
    config = load_yaml(SMOKE_CONFIG)
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    init_path = resolve_project_path(config["robust"]["init_checkpoint"])
    init_path.parent.mkdir(parents=True, exist_ok=True)
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    torch.save({"model_state": model.state_dict(), "class_names": classes, "epoch": 0}, init_path)

    result = run_robust_training(SMOKE_CONFIG, resume=False)
    assert result["init"]["mode"] == "fine_tune_from_twelve_class_best"
    assert result["best_epoch"] > 0

    checkpoint = f"{config['output_root']}/checkpoints/best.pt"
    evaluation = evaluate_v1_1(config, checkpoint)
    export = export_v1_1(config, checkpoint)
    assert not evaluation["final_blind_test_accessed"]
    assert not export["inspection"]["unexpected_operators"], export["inspection"]
    assert export["ort_parity"]["status"] == "ok"

    print({
        "best_epoch": result["best_epoch"],
        "train_channel_sha256": result["train_channel_sha256"],
        "architecture_changed": result["architecture_changed_from_v1_1"],
        "validation_macro_f1": evaluation["metrics"]["macro_f1"],
        "onnx_operators": export["inspection"]["op_types"],
    })
    print("AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
