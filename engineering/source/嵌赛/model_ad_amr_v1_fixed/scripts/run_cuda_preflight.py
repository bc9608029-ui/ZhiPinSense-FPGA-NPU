"""Release-blocking CUDA preflight through the production entrypoints."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import torch
import yaml

from evaluation.evaluate_ad_amr import evaluate
from scripts.export_ad_amr_onnx import export_ad_amr
from scripts.release_guard import write_preflight_marker
from training.train_ad_amr import run_training
from training.utils import load_yaml, save_json

MARKER = "AD_AMR_V1_CUDA_PREFLIGHT_PASS"


def _config(variant: str) -> dict[str, Any]:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["device"] = "cuda:0"
    cfg["training"]["amp"] = True
    cfg["training"]["loss"]["variant"] = variant
    cfg["output_root"] = f"outputs/ad_amr_v1/preflight/{variant}"
    cfg["v2_checkpoint"] = "init/v2_time_power_phase_best.pt"
    return cfg


def _run_variant(variant: str) -> dict[str, Any]:
    cfg = _config(variant)
    first = run_training(cfg, resume=False, stop_after_epoch=2)
    if [int(row["epoch"]) for row in first["history"]] != [1, 2]:
        raise RuntimeError(f"{variant}: initial production history is not [1, 2]")
    for row in first["history"]:
        for key in ("train_loss", "val_loss", "val_accuracy", "val_macro_f1"):
            if not torch.isfinite(torch.tensor(float(row[key]))):
                raise RuntimeError(f"{variant}: non-finite {key} at epoch {row['epoch']}")

    last_path = Path(cfg["output_root"]) / "checkpoints/last.pt"
    disk = torch.load(last_path, map_location="cpu", weights_only=False)
    loader_state = disk.get("train_loader_generator_state")
    if not isinstance(loader_state, torch.Tensor) or loader_state.dtype != torch.uint8:
        raise RuntimeError(f"{variant}: last.pt lacks a CPU ByteTensor loader RNG state")
    if loader_state.device.type != "cpu":
        raise RuntimeError(f"{variant}: loader RNG state was serialized off CPU")

    resumed = run_training(cfg, resume=True, stop_after_epoch=1)
    epochs = [int(row["epoch"]) for row in resumed["history"]]
    if epochs != [1, 2, 3]:
        raise RuntimeError(f"{variant}: cumulative resume history {epochs} != [1, 2, 3]")

    checkpoint = Path(cfg["output_root"]) / "checkpoints/best.pt"
    evaluation = evaluate(cfg, str(checkpoint), split="ad_amr_validation")
    if evaluation["final_blind_test_accessed"]:
        raise RuntimeError(f"{variant}: evaluation accessed final blind data")
    for key in ("accuracy", "macro_f1", "qam_mean", "accuracy_0_10db"):
        if not torch.isfinite(torch.tensor(float(evaluation["metrics"][key]))):
            raise RuntimeError(f"{variant}: evaluation metric {key} is non-finite")

    exported = export_ad_amr(cfg, str(checkpoint))
    if exported["inspection"]["opset"] != 17 or not exported["inspection"]["checker_passed"]:
        raise RuntimeError(f"{variant}: ONNX checker/opset gate failed")
    if exported["ort_parity"]["status"] != "ok":
        raise RuntimeError(f"{variant}: ONNX Runtime parity did not run cleanly: {exported['ort_parity']}")

    return {
        "variant": variant,
        "history_before_resume": [1, 2],
        "history_after_resume": epochs,
        "evaluation": {
            "accuracy": evaluation["metrics"]["accuracy"],
            "macro_f1": evaluation["metrics"]["macro_f1"],
        },
        "onnx_runtime": exported["ort_parity"],
    }


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA preflight requires a real CUDA GPU")
    print(
        f"[preflight] device={torch.cuda.get_device_name(0)} "
        f"torch={torch.__version__} cuda={torch.version.cuda}", flush=True,
    )
    results = {variant: _run_variant(variant) for variant in ("P0", "P1")}
    payload = {"results": results, "marker": MARKER, "timestamp": time.time()}
    save_json(payload, "outputs/ad_amr_v1/preflight/preflight_result.json")
    bound_hash = write_preflight_marker(payload)
    print(f"release_input_hash={bound_hash}", flush=True)
    print(MARKER, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
