#!/usr/bin/env python3
"""train_fix10class24_rf_adapt.py -- pilot RF domain-adaptation training (preregistered).

This is a PREP scaffolding script.  It encodes the frozen pilot training spec
(``contracts/rml24_dualsdr_rf_dataset_v1.py::PILOT_TRAINING_SPEC``) and runs ONE
preregistered run.  It requires torch (runs in the training environment, e.g.
radioconda), and fails closed if torch is absent or the checkpoint SHA mismatches.

Preregistered protocol (frozen — no deviation):

* init from FP32 checkpoint ``96cd25f8…`` (SHA verified before anything runs)
* candidates: exactly ``classification-head-only`` and ``full-network-low-LR``
* AdamW / lr in {1e-5, 3e-5, 1e-4} / weight_decay 0.01 / grad clip 1.0 /
  cosine schedule / warmup 5% / max_epochs 20 / early-stop patience 4
* seeds {17, 29, 43}
* data mix: ``real-rf-only`` or ``clean-plus-real-rf-balanced`` (the clean replay
  pool must be SHA-disjoint from every frozen evaluation set, else fail closed)
* per-batch class-balanced
* model selection on **val only**; the test split is loaded only at final
  evaluation and never influences any training decision

Usage::

    python scripts/train_fix10class24_rf_adapt.py \
        --checkpoint <best.pt> --model-def <module_with_build_model> \
        --dataset datasets/rml24_dualsdr_rf_v1 \
        --candidate classification-head-only --lr 1e-5 --seed 17 \
        --data-mix real-rf-only --output runs/pilot

    python scripts/train_fix10class24_rf_adapt.py --enumerate   # print the 36-run grid
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402

SPEC = C.PILOT_TRAINING_SPEC


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checkpoint(path) -> None:
    if not os.path.isfile(path):
        raise SystemExit(f"checkpoint not found: {path}")
    actual = sha256_file(path)
    expected = SPEC["init_from_checkpoint_sha256"]
    if actual != expected:
        raise SystemExit(
            f"checkpoint SHA mismatch: {actual} != frozen {expected} "
            f"(refusing to adapt from an unverified source)")


def enumerate_runs():
    """Yield the full preregistered grid (candidate x data_mix x seed x lr)."""
    for candidate in SPEC["candidates"]:
        for data_mix in SPEC["data_mix"]:
            for seed in SPEC["seeds"]:
                for lr in SPEC["learning_rates"]:
                    yield {
                        "candidate": candidate,
                        "data_mix": data_mix,
                        "seed": seed,
                        "lr": lr,
                    }


def validate_run(candidate, data_mix, seed, lr) -> None:
    if candidate not in SPEC["candidates"]:
        raise SystemExit(f"candidate {candidate!r} not in preregistered {SPEC['candidates']}")
    if data_mix not in SPEC["data_mix"]:
        raise SystemExit(f"data_mix {data_mix!r} not in preregistered {SPEC['data_mix']}")
    if seed not in SPEC["seeds"]:
        raise SystemExit(f"seed {seed} not in preregistered {SPEC['seeds']}")
    if lr not in SPEC["learning_rates"]:
        raise SystemExit(f"lr {lr} not in preregistered {SPEC['learning_rates']}")


def load_model_def(model_def_path):
    if not model_def_path or not os.path.isfile(model_def_path):
        raise SystemExit(
            "model architecture not found; pass --model-def <module> exposing "
            "build_model(num_classes=24) -> nn.Module (the ADAMRV11Net def lives in "
            "the training repo)")
    spec = importlib.util.spec_from_file_location("rf_adapt_model_def", model_def_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build_model"):
        raise SystemExit(f"{model_def_path}: missing build_model(num_classes) factory")
    return mod


def _last_linear(model):
    """Return the final nn.Linear module (the classification head)."""
    last = None
    for module in model.modules():
        if module.__class__.__name__ == "Linear":
            last = module
    if last is None:
        raise SystemExit("no nn.Linear found; cannot isolate the classification head")
    return last


def apply_candidate(model, candidate):
    """Freeze/unfreeze according to the preregistered candidate."""
    if candidate == "classification-head-only":
        for p in model.parameters():
            p.requires_grad = False
        for p in _last_linear(model).parameters():
            p.requires_grad = True
    elif candidate == "full-network-low-LR":
        for p in model.parameters():
            p.requires_grad = True
    else:
        raise SystemExit(f"unknown candidate {candidate!r}")
    trainable = sum(1 for p in model.parameters() if p.requires_grad)
    total = sum(1 for _ in model.parameters())
    return {"candidate": candidate, "trainable_params": trainable, "total_params": total}


def _assert_clean_replay_disjoint(clean_replay_dir, dataset_dir) -> None:
    """Fail closed if the clean replay pool overlaps any frozen eval set by SHA."""
    if not clean_replay_dir:
        return
    # The only in-tree frozen eval set is clean24_smoke; the external F2/F3 sets
    # are verified at eval time by the evaluator.  Here we refuse to reuse the
    # clean24_smoke tensors as replay.
    clean24 = Path(_HERE).resolve().parent.parent / "clean24_smoke"
    if clean24.is_dir():
        smoke_shas = {sha256_file(p) for p in clean24.glob("recovered_tensor_*.f32")}
        replay_shas = {sha256_file(p) for p in Path(clean_replay_dir).glob("*.f32")}
        overlap = smoke_shas & replay_shas
        if overlap:
            raise SystemExit(
                f"clean replay pool overlaps clean24_smoke by {len(overlap)} tensor(s); "
                f"refusing (leak between replay and F1 holdout)")
    _ = dataset_dir  # reserved: cross-check dataset train split vs replay pool


def require_torch():
    try:
        import torch  # noqa: F401
        return torch
    except ImportError:
        raise SystemExit(
            "torch not available in this environment; run in the training env "
            "(radioconda).  This is expected for the contract test.")


def run_training(args):
    torch = require_torch()
    import torch.nn as nn
    import torch.optim as optim

    verify_checkpoint(args.checkpoint)
    validate_run(args.candidate, args.data_mix, args.seed, args.lr)
    _assert_clean_replay_disjoint(args.clean_replay_dir, args.dataset)

    torch.manual_seed(args.seed)
    model_def = load_model_def(args.model_def)
    model = model_def.build_model(num_classes=SPEC["class_count"])
    ckpt = torch.load(args.checkpoint, map_location="cpu")
    state = ckpt.get("model_state_dict", ckpt.get("state_dict", ckpt))
    model.load_state_dict(state, strict=True)

    info = apply_candidate(model, args.candidate)
    head = _last_linear(model)

    # --- dataset loading is delegated to the training env loader; the frozen
    #     contract only requires: train/val/test disjoint by source_index, and
    #     model selection uses val only.  The loader must return dicts keyed by
    #     'train'/'val'/'test' of (tensor, class_index) iterables. -------------
    loader = load_dataset(args.dataset, data_mix=args.data_mix,
                          clean_replay_dir=args.clean_replay_dir,
                          class_balanced=SPEC["per_batch_class_balanced"])
    if "val" not in loader:
        raise SystemExit("dataset loader must provide a 'val' split")

    opt = optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr, weight_decay=SPEC["weight_decay"])

    steps_per_epoch = max(1, len(loader["train"]) // loader.get("batch_size", 1))
    total_steps = steps_per_epoch * SPEC["max_epochs"]
    warmup_steps = int(total_steps * SPEC["warmup_fraction"])

    def lr_at(step):
        if step < warmup_steps:
            return args.lr * (step + 1) / max(1, warmup_steps)
        t = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return args.lr * 0.5 * (1 + math.cos(math.pi * t))

    best_val = -float("inf")
    best_state = None
    patience_left = SPEC["early_stopping_patience"]
    step = 0

    for epoch in range(1, SPEC["max_epochs"] + 1):
        model.train()
        for x, y in loader["train"]:
            for g in opt.param_groups:
                g["lr"] = lr_at(step)
            opt.zero_grad(set_to_none=True)
            logits = model(x)
            loss = nn.functional.cross_entropy(logits, y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), SPEC["grad_clip_norm"])
            opt.step()
            step += 1

        val_acc = _evaluate(model, loader["val"])
        if val_acc > best_val:
            best_val = val_acc
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            patience_left = SPEC["early_stopping_patience"]
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    # --- test split is touched ONLY here, at final evaluation, after selection
    test_acc = _evaluate(model, loader.get("test")) if "test" in loader else None
    if best_state is not None:
        model.load_state_dict(best_state)

    out = {
        "candidate": args.candidate, "data_mix": args.data_mix, "seed": args.seed,
        "lr": args.lr, "best_val_accuracy": best_val, "test_accuracy": test_acc,
        "epochs_run": epoch, "trainable_params": info["trainable_params"],
        "total_params": info["total_params"], "head_out_features": head.out_features,
    }
    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, f"run_{args.candidate.replace('-', '_')}"
                            f"_lr{args.lr:g}_seed{args.seed}_{args.data_mix}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print(json.dumps(out, indent=2, sort_keys=True))
    print(f"run written -> {out_path}")


def _evaluate(model, split):
    torch = require_torch()
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for x, y in split:
            logits = model(x)
            correct += (logits.argmax(dim=1) == y).sum().item()
            total += y.numel()
    return correct / total if total else 0.0


def load_dataset(dataset_dir, data_mix, clean_replay_dir, class_balanced):
    """Load the dataset splits.  Implemented in the training environment; here we
    provide a fail-closed stub that documents the required split contract."""
    torch = require_torch()
    import numpy as np  # noqa: F401
    manifest = os.path.join(dataset_dir, "manifest.tsv")
    if not os.path.isfile(manifest):
        raise SystemExit(f"dataset manifest not found: {manifest} (run the builder first)")
    # NOTE: full loader lives in the training repo; this stub refuses to run
    # with real data so a half-wired loader can never silently train on test.
    raise SystemExit(
        "dataset loader is intentionally not implemented in this prep scaffold; "
        "the training repo wires it against the frozen split contract "
        "(train/val/test disjoint by source_index, val-only selection).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--enumerate", action="store_true",
                    help="print the preregistered 36-run grid and exit (no torch)")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--model-def", default=None)
    ap.add_argument("--dataset", default="datasets/rml24_dualsdr_rf_v1")
    ap.add_argument("--candidate", choices=SPEC["candidates"])
    ap.add_argument("--lr", type=float)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--data-mix", choices=SPEC["data_mix"])
    ap.add_argument("--clean-replay-dir", default=None)
    ap.add_argument("--output", default="runs/pilot")
    args = ap.parse_args()

    if args.enumerate:
        grid = list(enumerate_runs())
        print(json.dumps({"count": len(grid), "runs": grid}, indent=2))
        return 0

    if not args.checkpoint:
        ap.error("--checkpoint is required (use --enumerate for the grid)")
    if not all([args.candidate, args.lr, args.seed, args.data_mix]):
        ap.error("--candidate/--lr/--seed/--data-mix are all required")

    run_training(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
