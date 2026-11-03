#!/usr/bin/env python
"""M29 Phase D.2 — empirical FP32<->INT8(SFB) activation alignment check (single sample).

Reads the throwaway probe dir's iq_0.bin + ftmpSFB dump, runs the fp32 checkpoint
on the same input with forward hooks, and matches each SFB tensor to the fp32
activation of the same shape by cosine similarity. Confirms the SFB unpack layout
(NCHWc32 -> [C, L] channel-major) and the conv1(relu-fused)/conv2(pre-relu)
fusion map before the full 1536-sample analysis is built.

READ-ONLY: no test access, no board, no model changes.
"""
from __future__ import annotations

import glob
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
PROBE = r"F:\FPGA_Work\_tmp_m29_d2_ftmp_probe_20261010"


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.reshape(-1).astype(np.float64)
    b = b.reshape(-1).astype(np.float64)
    na = float(np.linalg.norm(a)); nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def main() -> int:
    sys.path.insert(0, V11)
    from models.rml24_net import build_rml24_model

    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    cfg = {"denoiser_channels": 24, "denoiser_blocks": 3, "feature_channels": [32, 48, 64, 96],
           "classifier_hidden": 128, "dropout": 0.15}
    model = build_rml24_model(24, **cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    # capture outputs of named modules (leaf + key containers)
    caps: dict[str, np.ndarray] = {}
    handles = []

    def make_hook(name):
        def hook(mod, inp, out):
            if isinstance(out, torch.Tensor):
                caps[name] = out.detach().cpu().numpy().copy()
            elif isinstance(out, (tuple, list)) and isinstance(out[0], torch.Tensor):
                caps[name] = out[0].detach().cpu().numpy().copy()
        return hook

    def make_prehook(name):
        def hook(mod, inp):
            t = inp[0]
            if isinstance(t, torch.Tensor):
                caps[name] = t.detach().cpu().numpy().copy()
        return hook

    import torch.nn as nn
    for name, mod in model.named_modules():
        if isinstance(mod, (nn.Conv1d, nn.BatchNorm1d, nn.ReLU, nn.Linear)):
            handles.append(mod.register_forward_hook(make_hook(name)))
    # container-level hooks (residual add post-relu, denoiser add, logits)
    for name, mod in model.named_modules():
        if mod.__class__.__name__ == "ResidualUnit":
            handles.append(mod.register_forward_hook(make_hook(name)))
        if mod.__class__.__name__ == "DeployableResidualDenoiser":
            handles.append(mod.register_forward_hook(make_hook(name)))
    # classifier input = mean(features) [B,96]
    handles.append(model.classifier[0].register_forward_pre_hook(make_prehook("classifier.input")))

    iq = np.fromfile(os.path.join(PROBE, "iq_0.bin"), dtype=np.float32).reshape(1, 2, 1024)
    x = torch.from_numpy(np.ascontiguousarray(iq))
    with torch.inference_mode():
        logits, denoised = model(x)
    for h in handles:
        h.remove()
    caps["logits"] = logits.detach().cpu().numpy().copy()
    caps["denoised"] = denoised.detach().cpu().numpy().copy()

    print("== fp32 captured activations (shape) ==")
    for k, v in caps.items():
        print(f"  {k:55s} {str(v.shape):18s}")

    # load SFB tensors
    sfbs: dict[int, np.ndarray] = {}
    for p in glob.glob(os.path.join(PROBE, ".icraft", "logs", "model_24class", "ftmpSFB", "*.ftmp")):
        vid = int(os.path.basename(p).split(".")[0])
        sfbs[vid] = np.fromfile(p, dtype=np.float32)

    print("\n== SFB tensors (shape inferred: N flat) ==")
    for vid in sorted(sfbs):
        print(f"  v{vid:5d}  size={sfbs[vid].size:8d}")

    # match each SFB tensor to fp32 tensor of same size by cosine
    print("\n== best fp32 match per SFB tensor (by size, then cosine) ==")
    fp_by_size = {}
    for k, v in caps.items():
        fp_by_size.setdefault(int(v.size), []).append((k, v))

    for vid in sorted(sfbs):
        t = sfbs[vid]
        candidates = fp_by_size.get(int(t.size), [])
        if not candidates:
            print(f"  v{vid:5d} size={t.size:8d}  -> NO fp32 tensor of this size")
            continue
        best = max(candidates, key=lambda kv: cosine(t, kv[1]))
        c = cosine(t, best[1])
        # also print the runner-up if close
        rest = sorted(candidates, key=lambda kv: -cosine(t, kv[1]))
        others = [f"{k}({cosine(t,v):.4f})" for k, v in rest[1:4]]
        print(f"  v{vid:5d} size={t.size:8d}  -> {best[0]:50s} cos={c:.6f}   alt={others}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
