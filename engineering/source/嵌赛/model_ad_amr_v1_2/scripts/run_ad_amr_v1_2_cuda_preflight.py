"""Release-blocking real-CUDA production-path preflight for V1.2."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import torch

from datasets.ad_amr_v1_2_dataset import ADAMRV12Dataset
from evaluation.evaluate_ad_amr_v1_2 import evaluate_v1_2, ood_channels
from scripts.export_ad_amr_v1_2_onnx import export_v1_2
from scripts.release_guard_v1_2 import write_marker
from training.train_ad_amr_v1_2 import run_v1_2_training
from training.utils import load_yaml

PASS = "AD_AMR_V1_2_CUDA_PREFLIGHT_PASS"


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("V1.2 CUDA preflight requires a real CUDA device")
    config = load_yaml("configs/ad_amr_v1_2_preflight.yaml")
    if config["training"].get("amp_dtype") != "bfloat16":
        raise RuntimeError("release preflight requires the BF16 stability policy")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("release preflight GPU does not support BF16")

    probe = ADAMRV12Dataset(
        256, config["signal"], config["channel"], config["data_robustness"],
        int(config["seed"]), "ad_amr_v1_2_train", snr_values=config["dataset"]["snr_values"],
    )
    probe.set_epoch(20)
    profile_counts = Counter(probe[index]["channel_profile"] for index in range(len(probe)))
    if set(profile_counts) != set(probe.profile_names):
        raise RuntimeError(f"preflight did not exercise every robustness profile: {profile_counts}")

    first = run_v1_2_training(config, resume=False, stop_after_epoch=1)
    if [int(row["epoch"]) for row in first["history"]] != [1]:
        raise RuntimeError("preflight initial history is not [1]")
    resumed = run_v1_2_training(config, resume=True, stop_after_epoch=1)
    if [int(row["epoch"]) for row in resumed["history"]] != [1, 2]:
        raise RuntimeError("preflight strict-resume history is not [1,2]")
    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    evaluation = evaluate_v1_2(config, checkpoint)
    focus = {}
    channels = ood_channels(config["channel"])
    for domain in config["pilot"]["focus_ood_domains"]:
        focus[str(domain)] = evaluate_v1_2(
            config, checkpoint, split=f"ad_amr_v1_2_validation_ood_{domain}",
            channel=channels[str(domain)], samples=210,
        )["metrics"]["macro_f1"]
    export = export_v1_2(config, checkpoint)
    if evaluation["final_blind_test_accessed"] or export["inspection"]["unexpected_operators"]:
        raise RuntimeError("preflight release gate failed")
    payload = {
        "device": torch.cuda.get_device_name(0), "torch": torch.__version__,
        "cuda": torch.version.cuda, "history": [1, 2],
        "amp_dtype": config["training"]["amp_dtype"],
        "profile_counts": dict(profile_counts), "macro_f1": evaluation["metrics"]["macro_f1"],
        "focus_ood_macro_f1": focus, "onnx": export["inspection"], "ort": export["ort_parity"],
    }
    bound = write_marker(payload)
    print(json.dumps(payload, indent=2))
    print(f"release_input_hash={bound}")
    print(PASS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
