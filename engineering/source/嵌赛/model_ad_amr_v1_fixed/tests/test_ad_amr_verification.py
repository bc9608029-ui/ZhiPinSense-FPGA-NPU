"""Pre-release verification tests: config identity, same-signal pairs, split guard,
and full checkpoint/resume state restoration.

These back the release checklist with executable assertions so each "verified" item
is a real test that passed, not a claim.
"""

from __future__ import annotations

import copy
import random

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from evaluation.evaluate_ad_amr import FORBIDDEN_SPLITS, evaluate
from models.ad_amr_net import build_ad_amr_model
from training.ad_amr_trainer import ADAMRTrainer
from training.utils import ensure_output_dirs, load_yaml, set_seed

CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


def _awgn_channel() -> dict:
    # AWGN-only channel (domain randomization off): noisy is clean + Gaussian noise,
    # so the pair provably comes from one underlying signal.
    return {"domain_randomization": False,
            "awgn": {"enabled": True, "probability": 1.0, "snr_db": [30.0, 30.0]}}


def _deep_equal(a, b) -> bool:
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and torch.equal(a.cpu(), b.cpu())
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and np.array_equal(a, b)
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a.keys()) == set(b.keys()) and all(
            _deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(
            _deep_equal(x, y) for x, y in zip(a, b))
    try:
        return bool(a == b)
    except Exception:
        return False


# 1. P0/P1 configs differ ONLY in the MSE target (and output root).
def test_p0_p1_configs_identical_except_variant_and_root() -> None:
    p0 = load_yaml("configs/ad_amr_v1_p0.yaml")
    p1 = load_yaml("configs/ad_amr_v1_p1.yaml")

    def normalize(cfg: dict) -> dict:
        c = copy.deepcopy(cfg)
        c.pop("_config_path", None)
        c["training"]["loss"]["variant"] = None
        c["output_root"] = None
        return c

    assert p0["training"]["loss"]["variant"] != p1["training"]["loss"]["variant"]
    assert p0["training"]["loss"]["alpha"] == p1["training"]["loss"]["alpha"]
    assert normalize(p0) == normalize(p1)


# 2. clean_iq / noisy_iq come from the same underlying signal.
def test_clean_noisy_same_underlying_signal() -> None:
    cfg = load_yaml("configs/ad_amr_v1.yaml")
    ds = ADAMRPairDataset(16, cfg["signal"], _awgn_channel(), 2026, "ad_amr_train",
                          fixed_snr_db=30.0)
    for index in range(8):
        rec = ds[index]
        clean = rec["clean_iq"].numpy().ravel()
        noisy = rec["noisy_iq"].numpy().ravel()
        corr = float(np.corrcoef(clean, noisy)[0, 1])
        assert corr > 0.98, f"clean/noisy not the same underlying signal (corr={corr:.4f})"
        assert not np.array_equal(clean, noisy), "noisy should differ from clean (AWGN)"


# 3. train/validation/test sample-id fingerprints are disjoint (zero overlap).
def test_split_sample_id_zero_overlap() -> None:
    cfg = load_yaml("configs/ad_amr_v1.yaml")
    ids: dict[str, set[int]] = {}
    for split, n in (("ad_amr_train", 64), ("ad_amr_validation", 32), ("ad_amr_test", 32)):
        ds = ADAMRPairDataset(n, cfg["signal"], cfg["channel"], 2026, split,
                              snr_values=[-20.0, -10.0, 0.0, 10.0, 20.0])
        ids[split] = {ds[i]["sample_id"] for i in range(n)}
    assert not (ids["ad_amr_train"] & ids["ad_amr_validation"])
    assert not (ids["ad_amr_train"] & ids["ad_amr_test"])
    assert not (ids["ad_amr_validation"] & ids["ad_amr_test"])


# 4. final blind split is never instantiated / evaluated.
def test_final_blind_split_refused(tmp_path) -> None:
    assert FORBIDDEN_SPLITS == ("final_blind_test", "ad_amr_final_blind_test")
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["output_root"] = str(tmp_path / "out")
    for forbidden in FORBIDDEN_SPLITS:
        with pytest.raises(RuntimeError, match="forbidden split"):
            evaluate(cfg, checkpoint_path=None, split=forbidden)


# 5 + 6. Checkpoint resume restores model / optimizer / scheduler / AMP / all RNG.
def test_resume_restores_full_state(tmp_path) -> None:
    cfg = load_yaml("configs/ad_amr_v1_smoke.yaml")
    cfg["output_root"] = str(tmp_path / "out")
    set_seed(2026)
    paths = ensure_output_dirs(cfg["output_root"])
    model = build_ad_amr_model(8, **cfg["model"])
    trainer = ADAMRTrainer(model, torch.device("cpu"), cfg, paths, CLASSES)

    snr = [float(v) for v in cfg["dataset"]["snr_values"]]
    signal, channel = cfg["signal"], cfg["channel"]
    train_set = ADAMRPairDataset(32, signal, channel, 2026, "ad_amr_train", snr_values=snr)
    val_set = ADAMRPairDataset(16, signal, channel, 2026, "ad_amr_validation", snr_values=snr)
    bs = int(cfg["training"]["batch_size"])
    train_loader = DataLoader(train_set, batch_size=bs, shuffle=True, collate_fn=collate_ad_amr,
                              generator=torch.Generator().manual_seed(2026))
    val_loader = DataLoader(val_set, batch_size=bs, shuffle=False, collate_fn=collate_ad_amr)
    trainer.fit(train_loader, val_loader, stop_after_epoch=2)
    ckpt = paths["checkpoints"] / "last.pt"

    # Capture the exact state to restore.
    saved_model = {k: v.clone() for k, v in model.state_dict().items()}
    saved_lr = trainer.optimizer.param_groups[0]["lr"]
    saved_opt_state = trainer.optimizer.state_dict()["state"]
    saved_sched = trainer.scheduler.state_dict()
    saved_amp = trainer.scaler.state_dict()
    saved_py = random.getstate()
    saved_np = np.random.get_state()
    saved_torch = torch.get_rng_state().clone()
    saved_loader = train_loader.generator.get_state().clone()

    # Perturb global RNG and rebuild a fresh trainer.
    random.seed(999)
    np.random.seed(999)
    torch.manual_seed(999)
    fresh_model = build_ad_amr_model(8, **cfg["model"])
    fresh = ADAMRTrainer(fresh_model, torch.device("cpu"), cfg, paths, CLASSES)
    fresh_train_loader = DataLoader(
        train_set, batch_size=bs, shuffle=True, collate_fn=collate_ad_amr,
        generator=torch.Generator().manual_seed(999),
    )
    resumed_epoch = fresh.load_resume(ckpt, fresh_train_loader)
    assert resumed_epoch == 2

    # model weights
    for k, v in saved_model.items():
        assert torch.equal(fresh.model.state_dict()[k], v), f"model param {k} not restored"

    # optimizer: hyperparameters + per-param (step, exp_avg, exp_avg_sq) values
    assert fresh.optimizer.param_groups[0]["lr"] == saved_lr
    def state_triples(state):
        return sorted(
            (float(v["step"]), float(v["exp_avg"].sum()), float(v["exp_avg_sq"].sum()))
            for v in state.values()
        )
    assert state_triples(fresh.optimizer.state) == state_triples(saved_opt_state)

    # scheduler + AMP scaler state (recursive, tensor-aware equality)
    assert _deep_equal(fresh.scheduler.state_dict(), saved_sched)
    assert _deep_equal(fresh.scaler.state_dict(), saved_amp)

    # all RNG states
    assert random.getstate() == saved_py
    assert np.random.get_state()[0] == saved_np[0]
    assert np.array_equal(np.random.get_state()[1], saved_np[1])
    assert np.random.get_state()[2] == saved_np[2]
    assert torch.equal(torch.get_rng_state(), saved_torch)
    assert torch.equal(fresh_train_loader.generator.get_state(), saved_loader)


# 7. ONNX Runtime parity is covered by test_ad_amr_onnx.py::test_ort_parity;
#    re-assert it here so the checklist is self-contained.
def test_ort_parity_self_contained(tmp_path) -> None:
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from models.ad_amr_net import ADAMRClassifier
    from scripts.export_ad_amr_onnx import OPSET_VERSION, _ort_parity

    cfg = load_yaml("configs/ad_amr_v1.yaml")
    set_seed(2026)
    model = build_ad_amr_model(8, **cfg["model"]).eval()
    sample = torch.randn(1, 2, 1024)
    onnx_path = tmp_path / "classifier.onnx"
    torch.onnx.export(ADAMRClassifier(model).eval(), sample, str(onnx_path),
                      opset_version=OPSET_VERSION, input_names=["iq"], output_names=["logits"],
                      dynamo=False)
    parity = _ort_parity(onnx_path, model, sample)
    assert parity["status"] == "ok", parity
    assert parity["max_abs_diff"] < 1e-3
