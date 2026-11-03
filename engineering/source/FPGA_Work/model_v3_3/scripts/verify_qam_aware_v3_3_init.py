"""Verify a zero-gated V3.3 model reproduces the frozen V2 logits element-wise.

This is the single source of truth for ``run_complete.sh`` init-equivalence step.
It generates **one** input tensor, feeds the *same* tensor to both the V3.3
student and the frozen V2 teacher, and requires the maximum absolute logit
difference to be below 1e-6 with the residual gate exactly zero.
"""

from __future__ import annotations

import argparse
import json

import torch

from models.qam_aware_rfnet import build_qam_aware_model
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config


@torch.inference_mode()
def verify_init_matches_v2(config_path: str = "configs/qam_aware_v3_3.yaml") -> dict[str, object]:
    config = load_qam_aware_v3_3_config(config_path)
    checkpoint = torch.load(config["v2_checkpoint"], map_location="cpu", weights_only=False)
    qam_aware = checkpoint["config"]["qam_aware"]

    teacher = build_qam_aware_model(variant="time_power_phase", num_classes=8, **qam_aware)
    teacher.load_state_dict(checkpoint["model_state"], strict=True)
    teacher.eval()

    student = build_qam_aware_v3_3(8, **config["model"])
    load_v2_into_v3_3(student, checkpoint)
    student.eval()

    expert = student.core.expert
    gate = float(expert.gate.item()) if expert is not None else None
    if gate is not None and gate != 0.0:
        raise RuntimeError(f"V3.3 residual gate must be exactly zero at initialization, got {gate}")

    # One input tensor, shared by both models, on the student's device (CPU here,
    # but device-robust if this source of truth is ever run on CUDA).
    torch.manual_seed(0)
    device = next(student.parameters()).device
    inputs = torch.randn(8, 2, 1024, device=device)
    diff = (student(inputs) - teacher(inputs)).abs().max().item()
    if diff >= 1e-6:
        raise RuntimeError(f"Initial V3.3 logits differ from V2 by {diff}; expected < 1e-6")

    return {
        "init_logits_match_v2": True,
        "max_abs_diff": diff,
        "gate": gate,
        "input": [8, 2, 1024],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3.yaml")
    args = parser.parse_args()
    result = verify_init_matches_v2(args.config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
