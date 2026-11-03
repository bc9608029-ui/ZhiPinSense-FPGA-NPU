"""Verify that a zero-gated V3.2 model reproduces the frozen V2 logits element-wise.

This is the single source of truth for ``run_complete.sh`` step 6.  A previous
inlined version called ``torch.randn`` twice — once for the student and once for
the teacher — so the two inputs differed and the check always failed.  This
module generates **one** input tensor, feeds the *same* tensor to both models,
and requires the maximum absolute logit difference to be below 1e-5 with the
gate exactly zero.
"""

from __future__ import annotations

import argparse
import json

import torch

from models.qam_aware_rfnet import build_qam_aware_model
from models.qam_aware_rfnet_v3_2 import build_qam_aware_v3_2, load_v2_into_v3_2
from training.qam_aware_v3_2_utils import load_qam_aware_v3_2_config


@torch.inference_mode()
def verify_init_matches_v2(config_path: str = "configs/qam_aware_v3_2.yaml") -> dict[str, object]:
    config = load_qam_aware_v3_2_config(config_path)
    checkpoint = torch.load(config["v2_checkpoint"], map_location="cpu", weights_only=False)
    qam_aware = checkpoint["config"]["qam_aware"]

    teacher = build_qam_aware_model(variant="time_power_phase", num_classes=8, **qam_aware)
    teacher.load_state_dict(checkpoint["model_state"], strict=True)
    teacher.eval()

    student = build_qam_aware_v3_2(8, **config["model"])
    load_v2_into_v3_2(student, checkpoint)
    student.eval()

    gate = float(student.core.gate.item())
    if gate != 0.0:
        raise RuntimeError(f"V3.2 gate must be exactly zero at initialization, got {gate}")

    # One input tensor, shared by both models.  (This is the fix: the two must
    # never be fed different random draws.)
    torch.manual_seed(0)
    inputs = torch.randn(8, 2, 1024)
    diff = (student(inputs) - teacher(inputs)).abs().max().item()
    if diff >= 1e-5:
        raise RuntimeError(f"Initial V3.2 logits differ from V2 by {diff}; expected < 1e-5")

    return {
        "init_logits_match_v2": True,
        "max_abs_diff": diff,
        "gate": gate,
        "input": [8, 2, 1024],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_2.yaml")
    args = parser.parse_args()
    result = verify_init_matches_v2(args.config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
