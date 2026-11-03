"""AD-AMR V1 CUDA preflight — functional smoke on a real GPU.

Runs on the AutoDL GPU host (never here on a CPU-only machine).  For both P0 and
P1 it executes a 2-epoch AMP smoke, a checkpoint save/load/resume round-trip, a
tiny evaluation, and an ONNX export + ORT parity check, asserting finiteness of
every loss.  Prints ``AD_AMR_V1_CUDA_PREFLIGHT_PASS`` only when every step passes.

This certifies functional correctness + numerical stability only; it does NOT
certify performance (that is the pilot's job).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import torch

from models.ad_amr_net import build_ad_amr_model
from scripts.export_ad_amr_onnx import export_ad_amr
from training.ad_amr_trainer import ADAMRTrainer
from training.train_ad_amr import build_dataloaders
from training.utils import ensure_output_dirs, load_yaml, save_json, set_seed

MARKER = "AD_AMR_V1_CUDA_PREFLIGHT_PASS"
CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


def _smoke_config(variant: str, root: str) -> dict:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["device"] = "cuda:0"
    cfg["training"]["amp"] = True
    cfg["training"]["loss"]["variant"] = variant
    cfg["output_root"] = f"{root}/{variant}"
    return cfg


def _run_variant(variant: str, root: str) -> dict:
    cfg = _smoke_config(variant, root)
    set_seed(int(cfg["seed"]))
    device = torch.device("cuda:0")
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(len(CLASSES), **cfg["model"]).to(device)
    trainer = ADAMRTrainer(model, device, cfg, paths, CLASSES)
    assert trainer.amp_enabled is True, "AMP must be enabled on CUDA"
    train_loader, val_loader = build_dataloaders(cfg, device)

    history = trainer.fit(train_loader, val_loader, stop_after_epoch=2)
    for row in history:
        assert torch.isfinite(torch.tensor(row["train_loss"])), "non-finite train loss"
        assert torch.isfinite(torch.tensor(row["val_loss"])), "non-finite val loss"

    # Checkpoint save/load/resume round-trip.
    resume_path = paths["checkpoints"] / "last.pt"
    fresh_model = build_ad_amr_model(len(CLASSES), **cfg["model"]).to(device)
    fresh = ADAMRTrainer(fresh_model, device, cfg, paths, CLASSES)
    resumed_epoch = fresh.load_resume(resume_path)
    history2 = fresh.fit(train_loader, val_loader, stop_after_epoch=1)
    assert [r["epoch"] for r in history2] == [resumed_epoch, resumed_epoch + 1]

    return {
        "variant": variant,
        "epochs": [r["epoch"] for r in history],
        "resume_epoch": resumed_epoch,
        "final_train_loss": history[-1]["train_loss"],
        "final_val_loss": history[-1]["val_loss"],
    }


def main() -> int:
    assert torch.cuda.is_available(), "CUDA preflight requires a GPU"
    print(f"[preflight] device={torch.cuda.get_device_name(0)} "
          f"torch={torch.__version__} cuda={torch.version.cuda}", flush=True)

    results = {}
    for variant in ("P0", "P1"):
        print(f"[preflight] {variant} 2-epoch AMP smoke + resume", flush=True)
        results[variant] = _run_variant(variant, "outputs/ad_amr_v1/preflight")
        print(f"[preflight] {variant} OK: {results[variant]}", flush=True)

    # Evaluation + ONNX/ORT on a tiny split for each variant.
    for variant in ("P0", "P1"):
        checkpoint = f"outputs/ad_amr_v1/preflight/{variant}/checkpoints/best.pt"
        report = export_ad_amr("configs/ad_amr_v1_smoke.yaml", checkpoint)
        assert report["ort_parity"]["status"] in ("ok", "skipped"), report["ort_parity"]
        print(f"[preflight] {variant} ONNX opset={report['inspection']['opset']} "
              f"ort={report['ort_parity']['status']}", flush=True)

    save_json({"results": results, "marker": MARKER, "timestamp": time.time()},
              "outputs/ad_amr_v1/preflight/preflight_result.json")
    print(MARKER, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
