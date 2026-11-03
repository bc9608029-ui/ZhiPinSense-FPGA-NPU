"""Single-batch overfit probe for AD-AMR V1 (P0 and P1).

This is the pre-release overfit verification.  It builds one fixed, balanced batch
(8 classes x 4 samples, generated once via the deterministic dataset so the channel
augmentation is frozen — no augmentation is applied during the training loop), then
repeatedly trains ONLY that batch and reports the initial/final loss and accuracy,
the iteration count, a coarse loss/accuracy curve, and per-group gradient health
(ADM / ECA / FEM / classification head).  It runs for BOTH the P0 and P1 loss
variants so their behaviour can be compared side by side.

Exit code 0 does NOT itself declare readiness; the caller judges whether the loss
fell clearly and accuracy approached 100%.
"""

from __future__ import annotations

import json

import torch

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from models.ad_amr_net import ECA, build_ad_amr_model
from training.ad_amr_loss import ad_amr_loss
from training.utils import load_yaml, set_seed

NUM_SAMPLES = 32          # 8 classes x 4 samples
ITERATIONS = 500
ALPHA = 0.1
CURVE_EVERY = 50


def _gradient_groups(model: torch.nn.Module) -> dict[str, list[dict]]:
    eca_ids = {id(p) for m in model.modules() if isinstance(m, ECA) for p in m.parameters()}
    groups: dict[str, list[dict]] = {"adm": [], "eca": [], "fem": [], "head": []}
    for name, p in model.named_parameters():
        if p.grad is None:
            continue
        finite = bool(torch.isfinite(p.grad).all())
        nonzero = bool((p.grad.abs().max() > 0).item())
        row = {"name": name, "finite": finite, "nonzero": nonzero,
               "grad_norm": float(p.grad.norm().item()) if finite else float("nan")}
        if name.startswith("adm."):
            groups["adm"].append(row)
        if name.startswith("fem."):
            groups["fem"].append(row)
        if name.startswith("fc."):
            groups["head"].append(row)
        if id(p) in eca_ids:
            groups["eca"].append(row)
    return groups


def _summarize(rows: list[dict]) -> dict:
    total = len(rows)
    finite = sum(1 for r in rows if r["finite"])
    nonzero = sum(1 for r in rows if r["nonzero"])
    return {
        "n_params": total,
        "n_finite": finite,
        "n_nonzero": nonzero,
        "all_finite_nonzero": total > 0 and finite == total and nonzero == total,
        "max_grad_norm": max((r["grad_norm"] for r in rows), default=float("nan")),
        "mean_grad_norm": sum(r["grad_norm"] for r in rows) / total if total else float("nan"),
    }


def run_variant(cfg: dict, variant: str) -> dict:
    set_seed(2026)
    signal, channel = cfg["signal"], cfg["channel"]
    snr = [float(v) for v in cfg["dataset"]["snr_values"]]
    ds = ADAMRPairDataset(NUM_SAMPLES, signal, channel, 2026, "ad_amr_train", snr_values=snr)
    # Generate the batch exactly once -> fixed tensors, augmentation frozen for the loop.
    batch = collate_ad_amr([ds[i] for i in range(NUM_SAMPLES)])
    clean = batch["clean_iq"]
    noisy = batch["noisy_iq"]
    labels = batch["label"]

    model = build_ad_amr_model(8, **cfg["model"])
    optimizer = torch.optim.Adam(model.parameters(), lr=float(cfg["training"]["learning_rate"]))

    def evaluate() -> tuple[float, float, float, float]:
        model.eval()
        with torch.inference_mode():
            logits, denoised = model(noisy)
            loss, comps = ad_amr_loss(logits, denoised, labels, clean, noisy, variant, ALPHA)
        acc = float((logits.argmax(dim=1) == labels).float().mean())
        return float(loss.item()), acc, float(comps["ce"].item()), float(comps["mse"].item())

    init_loss, init_acc, init_ce, init_mse = evaluate()

    curve = [{"iter": 0, "loss": init_loss, "ce": init_ce, "mse": init_mse, "accuracy": init_acc}]
    model.train()
    for step in range(1, ITERATIONS + 1):
        optimizer.zero_grad(set_to_none=True)
        logits, denoised = model(noisy)
        loss, _ = ad_amr_loss(logits, denoised, labels, clean, noisy, variant, ALPHA)
        loss.backward()
        optimizer.step()
        if step % CURVE_EVERY == 0:
            l, a, c, m = evaluate()
            curve.append({"iter": step, "loss": l, "ce": c, "mse": m, "accuracy": a})
            model.train()

    final_loss, final_acc, final_ce, final_mse = evaluate()
    grads = _gradient_groups(model)

    return {
        "variant": variant,
        "num_samples": NUM_SAMPLES,
        "num_classes": 8,
        "iterations": ITERATIONS,
        "learning_rate": cfg["training"]["learning_rate"],
        "alpha": ALPHA,
        "augmentation_during_loop": "off (batch generated once, held fixed)",
        "initial": {"loss": init_loss, "ce": init_ce, "mse": init_mse, "accuracy": init_acc},
        "final": {"loss": final_loss, "ce": final_ce, "mse": final_mse, "accuracy": final_acc},
        "loss_delta": init_loss - final_loss,
        "curve": curve,
        "gradient_health": {k: _summarize(v) for k, v in grads.items()},
    }


def main() -> None:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    results = [run_variant(cfg, "P0"), run_variant(cfg, "P1")]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
