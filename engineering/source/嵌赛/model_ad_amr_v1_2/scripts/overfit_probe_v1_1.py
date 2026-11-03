"""Fixed-batch trainability probe for the V1.1 student."""

from __future__ import annotations

import json

import torch

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, collate_ad_amr
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from training.utils import load_yaml, save_json, set_seed


def run_probe(
    steps: int = 250,
    config_path: str = "configs/ad_amr_v1_1_smoke.yaml",
    output_path: str = "outputs/ad_amr_v1_1/smoke/overfit_probe.json",
) -> dict[str, float | int | bool]:
    config = load_yaml(config_path)
    set_seed(2026)
    class_count = len(config["signal"]["modulations"])
    sample_count = max(2 * class_count, 20)
    dataset = ADAMRV11Dataset(sample_count, config["signal"], config["channel"], 2026,
                              "ad_amr_v1_1_train_overfit", fixed_snr_db=10.0)
    batch = collate_ad_amr([dataset[index] for index in range(sample_count)])
    inputs, labels = batch["noisy_iq"], batch["label"]
    model = build_ad_amr_v1_1_model(class_count, **config["model"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.0)
    initial_loss = 0.0
    final_loss = 0.0
    for step in range(steps):
        logits, _ = model(inputs)
        loss = torch.nn.functional.cross_entropy(logits, labels)
        if step == 0:
            initial_loss = float(loss.detach())
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach())
    model.eval()
    with torch.inference_mode():
        logits, _ = model(inputs)
        accuracy = float((logits.argmax(1) == labels).float().mean())
    finite_gradients = all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
    result = {
        "steps": steps, "initial_loss": initial_loss, "final_loss": final_loss,
        "final_accuracy": accuracy, "finite_gradients": finite_gradients,
    }
    result["class_count"] = class_count
    save_json(result, output_path)
    if not (final_loss < initial_loss * 0.25 and accuracy >= 0.95 and finite_gradients):
        raise RuntimeError(f"V1.1 fixed-batch overfit probe failed: {result}")
    return result


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2))
