"""Export a trained ablation model to an ONNX graph and run the checker."""

from __future__ import annotations

import argparse
from pathlib import Path

import onnx
import torch

from models.dual_domain_rfnet import build_ablation_model
from training.ablation_utils import load_ablation_config
from training.utils import ensure_output_dirs


def export_checkpoint(config_path: str, variant: str) -> Path:
    config = load_ablation_config(config_path)
    output_dir = str(Path(config["output_root"]) / variant)
    paths = ensure_output_dirs(output_dir)
    checkpoint = torch.load(paths["checkpoints"] / "best.pt", map_location="cpu", weights_only=False)
    model = build_ablation_model(variant, len(checkpoint["class_names"]), **config["dual_domain"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    destination = Path(paths["tables"]).parent / "onnx" / f"{variant}.onnx"
    destination.parent.mkdir(parents=True, exist_ok=True)
    example = torch.zeros(1, 2, int(config["signal"]["sample_length"]), dtype=torch.float32)
    torch.onnx.export(
        model,
        example,
        destination,
        input_names=["iq"],
        output_names=["logits"],
        dynamic_axes={"iq": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    graph = onnx.load(destination)
    onnx.checker.check_model(graph)
    print(f"ONNX check passed: {destination} ({destination.stat().st_size / (1024**2):.3f} MiB)")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dual_domain_smoke.yaml")
    parser.add_argument("--variant", required=True, choices=("time_only", "frequency_only", "time_only_wide", "dual"))
    args = parser.parse_args()
    export_checkpoint(args.config, args.variant)


if __name__ == "__main__":
    main()
