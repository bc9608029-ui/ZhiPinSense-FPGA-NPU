"""Fake symmetric INT8 weight-quantization accuracy check for the V2 model.

Reuses V1's evaluation with ``fake_int8=True`` so the numeric mode is exactly
"fake symmetric int8 weights / fp32 activations", and compares it against the
fp32 baseline to produce the quantization accuracy-drop gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from v2.evaluate import evaluate_v1_1


def fake_int8_report(config: dict[str, Any], checkpoint_path: str | Path,
                     samples: int | None = None) -> dict[str, Any]:
    fp32 = evaluate_v1_1(config, checkpoint_path, samples=samples, fake_int8=False)
    int8 = evaluate_v1_1(config, checkpoint_path, samples=samples, fake_int8=True)
    fp32_acc = float(fp32["metrics"]["accuracy"])
    int8_acc = float(int8["metrics"]["accuracy"])
    return {
        "checkpoint": str(checkpoint_path),
        "fp32_accuracy": fp32_acc,
        "fake_int8_accuracy": int8_acc,
        "accuracy_drop": fp32_acc - int8_acc,
        "fp32": fp32,
        "fake_int8": int8,
    }


def main() -> None:
    import argparse
    from training.utils import load_yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/v2_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--samples", type=int, default=None)
    args = parser.parse_args()
    print(fake_int8_report(load_yaml(args.config), args.checkpoint, args.samples))


if __name__ == "__main__":
    main()
