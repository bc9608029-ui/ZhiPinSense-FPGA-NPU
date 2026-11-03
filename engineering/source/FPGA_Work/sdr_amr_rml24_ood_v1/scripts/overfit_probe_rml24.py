"""Fixed-batch trainability probe for the strict 24-class model (M5).

Loads a tiny balanced RadioML2018.01A slice (``smoke_max_per_stratum``), fixes a
single batch of ``samples_per_class`` samples per class, and proves the
24-class head can overfit it (final accuracy >= 0.95, loss collapses, gradients
finite).  Failing this probe forbids any full training run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from contracts.rml24_contract import LABEL_ORDER_24
from datasets.ad_amr_dataset import collate_ad_amr
from datasets.radioml2018_dataset import RadioML2018Dataset
from models.rml24_net import build_rml24_model
from training.utils import load_yaml, save_json, set_seed


def run_probe(config_or_path: dict[str, Any] | str, *, steps: int = 400,
              samples_per_class: int = 4, hdf5_path: str | None = None,
              output_path: str | None = None) -> dict[str, Any]:
    config = config_or_path if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    if hdf5_path:
        config["public_data"] = dict(config["public_data"])
        config["public_data"]["hdf5_path"] = hdf5_path
    set_seed(2026)
    public = config["public_data"]
    dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], "train",
        max_per_stratum=config.get("rml24", {}).get("smoke_max_per_stratum"),
    )
    classes = list(LABEL_ORDER_24)
    labels = np.asarray(dataset.labels)
    chosen: list[int] = []
    for c in range(len(classes)):
        chosen.extend(np.flatnonzero(labels == c)[:samples_per_class].tolist())
    batch = collate_ad_amr([dataset[item] for item in chosen])
    inputs, targets = batch["noisy_iq"], batch["label"]
    model = build_rml24_model(len(classes), **config["model"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.0)
    initial_loss = 0.0
    final_loss = 0.0
    for step in range(int(steps)):
        logits, _ = model(inputs)
        loss = torch.nn.functional.cross_entropy(logits, targets)
        if step == 0:
            initial_loss = float(loss.detach())
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach())
    model.eval()
    with torch.inference_mode():
        logits, _ = model(inputs)
        accuracy = float((logits.argmax(1) == targets).float().mean())
    finite_gradients = all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
    result: dict[str, Any] = {
        "steps": int(steps), "batch_samples": len(chosen),
        "samples_per_class": samples_per_class, "class_count": len(classes),
        "initial_loss": initial_loss, "final_loss": final_loss,
        "final_accuracy": accuracy, "finite_gradients": finite_gradients,
    }
    destination = output_path or str(Path(config["output_root"]) / "overfit_probe.json")
    save_json(result, destination)
    if not (final_loss < initial_loss * 0.25 and accuracy >= 0.95 and finite_gradients):
        raise RuntimeError(f"24-class fixed-batch overfit probe failed: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_smoke.yaml")
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--samples-per-class", type=int, default=4)
    parser.add_argument("--hdf5-path", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.config, steps=args.steps,
                               samples_per_class=args.samples_per_class,
                               hdf5_path=args.hdf5_path, output_path=args.output), indent=2))


if __name__ == "__main__":
    main()
