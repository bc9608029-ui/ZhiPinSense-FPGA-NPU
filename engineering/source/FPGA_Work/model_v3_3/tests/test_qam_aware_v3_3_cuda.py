"""Real-model CUDA integration test for V3.3 (release-blocking device paths).

The CPU host can never catch the device/dtype bug class that this test exercises
on a real GPU.  It covers, against the *real* frozen V2 champion and the *real*
V3.3 model (not ``TinyV33Net``):

   1. load the real frozen V2 champion checkpoint;
   2. build the real V3.3 student + V2 teacher and move both to CUDA;
   3. init logits equal V2 (``verify_init_matches_v2`` on CUDA);
   4. a real ``QAMAwareV33Trainer`` completes round 1 (one micro train/val epoch);
   5. ``last.pt``/``best.pt`` are written;
   6. a new model/trainer resumes from ``last.pt`` on CUDA (every RNG source is
      deliberately perturbed first so the restoration below is proven, not assumed);
   7. round 2 actually executes and the history/epochs are continuous (cumulative
      ``[1, 2]``);
   8. model parameters are on CUDA;
   9. optimizer tensor state is on the exact CUDA device;
  10. the DataLoader generator state and the torch CPU RNG state are restored as
      CPU ByteTensors (not GPU-mapped);
  11. CUDA RNG (per-device), Python random, NumPy RNG, the scheduler and the AMP
      scaler are restored to round 1's exact state;
  12. loss/logits contain no NaN/Inf;
  13. ``_finite_probe`` and the real evaluator pass on CUDA.

The whole test is skipped on a CPU-only host.  ``ready=true`` must therefore never
rely on this skip: the CUDA preflight on AutoDL re-runs this test on a real GPU.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.evaluate_qam_aware_v3_3 import evaluate_v3_3_validation
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.qam_aware_v3_3_trainer import QAMAwareV33Trainer
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config
from training.train_qam_aware_v3_3 import (
    _build_v2_teacher,
    _finite_probe,
    verify_init_matches_v2,
)
from training.utils import ensure_output_dirs, set_seed, select_device

REAL_V2_MODEL_STATE_KEYS = 91


def _train_loader(dataset, config: dict, device: torch.device) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(int(config["seed"])),
        num_workers=0,
        pin_memory=device.type == "cuda",
    )


def _val_loader(dataset, config: dict, device: torch.device) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=int(config["training"]["batch_size"]),
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )


def _build_datasets(config: dict) -> tuple[SyntheticModulationDataset, SyntheticModulationDataset]:
    signal = config["signal"]
    channel = config["channel"]
    seed = int(config["seed"])
    snr_values = [float(value) for value in config["dataset"]["snr_values"]]
    train_set = SyntheticModulationDataset(
        int(config["dataset"]["train_samples"]), signal, channel, seed, "v3_3_train", snr_values=snr_values
    )
    val_set = SyntheticModulationDataset(
        int(config["dataset"]["val_samples"]), signal, channel, seed, "v3_3_validation", snr_values=snr_values
    )
    return train_set, val_set


def _write_eval_config(root: Path, device: str) -> str:
    """A smoke-shaped experiment config pointing output at a temp dir (no outputs/ pollution)."""
    text = (
        "experiment_config: configs/qam_aware_v3_3.yaml\n"
        f"output_root: {root / 'outputs_eval'}\n"
        f"device: {device}\n"
        "seed: 2026\n"
        "dataset:\n"
        "  train_samples: 480\n"
        "  val_samples: 192\n"
        "  test_samples: 240\n"
        "  snr_values: [0, 10, 20]\n"
        "training:\n"
        "  epochs: 2\n"
        "  batch_size: 32\n"
        "  minimum_epochs_before_stopping: 1\n"
        "evaluation:\n"
        "  batch_size: 64\n"
        "  samples_per_modulation_per_snr: 40\n"
        "  snr_values: [0, 10, 20]\n"
    )
    path = root / "cuda_eval_config.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _assert_cpu_byte_tensor(name: str, tensor: object) -> None:
    assert isinstance(tensor, torch.Tensor), f"{name} is not a tensor"
    assert not tensor.is_cuda, f"{name} must stay on CPU (got {tensor.device})"
    assert tensor.dtype == torch.uint8, f"{name} must be a ByteTensor (got {tensor.dtype})"


def _numpy_state_equal(a: tuple, b: tuple) -> bool:
    """Compare two ``np.random.get_state()`` tuples (no ambiguous array ``==``)."""
    return a[0] == b[0] and a[2:] == b[2:] and np.array_equal(a[1], b[1])


def _perturb_all_rng(device: torch.device) -> None:
    """Shift every framework RNG away from its current state.

    Called immediately before ``load_resume`` so the restoration assertions that
    follow prove the checkpoint state was actually re-applied (a no-op restore
    would leave these perturbed values behind and fail).
    """
    random.seed(123456789)
    _ = random.random()
    np.random.seed(987654321)
    _ = np.random.rand(8)
    torch.manual_seed(555555555)
    _ = torch.rand(16)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(444444444)
        _ = torch.rand(16, device=device)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_real_v33_cuda_integration(tmp_path: Path) -> None:
    device = select_device("cuda:0")
    assert device.type == "cuda"

    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3_smoke.yaml")
    config["output_root"] = str(tmp_path / "outputs")
    config["device"] = "cuda:0"
    seed = int(config["seed"])
    set_seed(seed)

    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    num_classes = len(classes)
    sample_length = int(config["signal"]["sample_length"])
    assert (num_classes, sample_length) == (8, 1024)

    # (1) real frozen V2 champion.
    v2_path = Path(config["v2_checkpoint"])
    v2_ckpt = torch.load(v2_path, map_location="cpu", weights_only=False)
    assert len(v2_ckpt["model_state"]) == REAL_V2_MODEL_STATE_KEYS

    # (2) real V3.3 student + real V2 teacher, both moved to CUDA.
    student = build_qam_aware_v3_3(num_classes, **config["model"])
    load_v2_into_v3_3(student, v2_ckpt)
    teacher = _build_v2_teacher(v2_ckpt, num_classes)
    student = student.to(device)
    teacher = teacher.to(device)
    assert all(parameter.is_cuda for parameter in student.parameters())
    assert all(parameter.is_cuda for parameter in teacher.parameters())

    # (3) init-equivalence on CUDA (exercises the device-robust shared input).
    init_diff = verify_init_matches_v2(student, teacher, sample_length)
    assert init_diff < 1e-6

    # (4) a real QAMAwareV33Trainer completes round 1 on CUDA.
    paths = ensure_output_dirs(config["output_root"])
    train_set, val_set = _build_datasets(config)
    train_loader = _train_loader(train_set, config, device)
    val_loader = _val_loader(val_set, config, device)

    trainer = QAMAwareV33Trainer(student, device, config, paths, classes)
    history = trainer.fit(train_loader, val_loader, stop_after_epoch=1)
    assert [row["epoch"] for row in history] == [1]
    assert all(np.isfinite(row["train_loss"]) and np.isfinite(row["val_loss"]) for row in history)

    # (5) last.pt / best.pt are written; their RNG/generator/AMP state is CPU-safe.
    best_path = paths["checkpoints"] / "best.pt"
    last_path = paths["checkpoints"] / "last.pt"
    assert best_path.exists() and last_path.exists()

    #   (5a) model weights round-trip through a CPU load into the CUDA student.
    best_cpu = torch.load(best_path, map_location="cpu", weights_only=False)
    assert all(not tensor.is_cuda for tensor in best_cpu["model_state"].values())
    student.load_state_dict(best_cpu["model_state"])
    assert all(parameter.is_cuda for parameter in student.parameters())
    assert _finite_probe(student, val_loader)["finite_logits"] is True

    #   (5b) the on-disk resume state is CPU-safe (the exact invariant the GPU
    #        resume bug violated when the loader mapped it onto the GPU).
    last_cpu = torch.load(last_path, map_location="cpu", weights_only=False)
    _assert_cpu_byte_tensor("train_loader_generator_state", last_cpu["train_loader_generator_state"])
    rng_state = last_cpu["rng_state"]
    for key in ("python", "numpy", "torch_cpu", "torch_cuda_all"):
        assert key in rng_state, f"rng_state missing {key!r}"
    _assert_cpu_byte_tensor("rng_state.torch_cpu", rng_state["torch_cpu"])
    cuda_rng_on_disk = rng_state["torch_cuda_all"]
    assert isinstance(cuda_rng_on_disk, (list, tuple)), "torch_cuda_all must be a list/tuple"
    assert len(cuda_rng_on_disk) == torch.cuda.device_count(), (
        f"torch_cuda_all has {len(cuda_rng_on_disk)} states, want {torch.cuda.device_count()}"
    )
    for index, rng_tensor in enumerate(cuda_rng_on_disk):
        _assert_cpu_byte_tensor(f"rng_state.torch_cuda_all[{index}]", rng_tensor)
    scaler_state = last_cpu.get("amp_scaler_state")
    assert scaler_state, "checkpoint is missing amp_scaler_state"
    assert all(not isinstance(value, torch.Tensor) for value in scaler_state.values()), (
        "amp_scaler_state must be scalar-only"
    )
    assert last_cpu["scheduler_state"]["last_epoch"] == 1

    # (6) a fresh model/trainer resumes from last.pt on CUDA.  Every RNG source is
    #     deliberately perturbed *before* load_resume so the checks below prove the
    #     checkpoint state was actually re-applied (not merely "no type error").
    scaler_scale_after_round1 = trainer.scaler.get_scale()
    student2 = build_qam_aware_v3_3(num_classes, **config["model"])
    load_v2_into_v3_3(student2, v2_ckpt)
    student2 = student2.to(device)
    trainer2 = QAMAwareV33Trainer(student2, device, config, paths, classes)
    train_loader2 = _train_loader(train_set, config, device)
    val_loader2 = _val_loader(val_set, config, device)

    _perturb_all_rng(device)
    train_loader2.generator.manual_seed(987654)
    torch.empty((), dtype=torch.int64).random_(generator=train_loader2.generator)

    #   Restore directly (this is what fit(resume_path=...) calls internally).
    trainer2.load_resume(last_path, train_loader2)

    # (7) every continuation source is restored to round 1's exact state.
    assert torch.equal(
        train_loader2.generator.get_state(), last_cpu["train_loader_generator_state"]
    )
    assert torch.equal(torch.get_rng_state(), last_cpu["rng_state"]["torch_cpu"])
    cuda_now = torch.cuda.get_rng_state_all()
    cuda_saved = last_cpu["rng_state"]["torch_cuda_all"]
    assert isinstance(cuda_saved, (list, tuple))
    assert len(cuda_now) == len(cuda_saved) == torch.cuda.device_count()
    for index, (now, saved) in enumerate(zip(cuda_now, cuda_saved)):
        assert torch.equal(now, saved), f"CUDA RNG state {index} not restored"
    assert random.getstate() == last_cpu["rng_state"]["python"]
    assert _numpy_state_equal(np.random.get_state(), last_cpu["rng_state"]["numpy"])
    assert trainer2.scheduler is not None
    assert trainer2.scheduler.state_dict()["last_epoch"] == 1
    restored_scaler = trainer2.scaler.state_dict()
    saved_scaler = last_cpu["amp_scaler_state"]
    assert set(restored_scaler) == set(saved_scaler)
    for key in saved_scaler:
        assert float(restored_scaler[key]) == float(saved_scaler[key]), f"scaler {key} not restored"
    assert trainer2.resume_metadata["source_checkpoint_version"] == 2
    assert trainer2.resume_metadata["completed_epoch"] == 1
    assert trainer2.resume_metadata["next_epoch"] == 2
    assert trainer2.start_epoch == 2
    assert [row["epoch"] for row in trainer2.history] == [1]

    # (8) the optimizer tensor state sits on the exact CUDA device after resume.
    optimizer_states = list(trainer2.optimizer.state.values())
    assert optimizer_states, "optimizer has no state after resume"
    for param_state in optimizer_states:
        for key, value in param_state.items():
            if isinstance(value, torch.Tensor):
                assert value.device == device, f"optimizer state {key} on {value.device}, want {device}"
                assert torch.isfinite(value).all(), f"optimizer state {key} is non-finite"

    # (9) round 2 actually executes; history is cumulative [1, 2], not [2].
    history2 = trainer2.fit(train_loader2, val_loader2, stop_after_epoch=2)
    assert [row["epoch"] for row in history2] == [1, 2]
    assert len(history2) == 2
    assert history2[-1]["epoch"] == 2
    assert all(np.isfinite(row["train_loss"]) and np.isfinite(row["val_loss"]) for row in history2)

    # (10) model parameters are on CUDA and finite.
    for name, parameter in student2.named_parameters():
        assert parameter.is_cuda, f"{name} is not on CUDA"
        assert torch.isfinite(parameter).all(), f"{name} is non-finite"

    # (11) scheduler + AMP scaler advanced to round 2 and stayed consistent.
    assert trainer2.scheduler.state_dict()["last_epoch"] == 2
    assert trainer2.amp_enabled is True
    assert trainer2.scaler.is_enabled() is True
    assert trainer2.scaler.get_scale() == scaler_scale_after_round1

    # (12) loss/logits contain no NaN/Inf (rounds 1 and 2 already asserted finite).
    # (13) _finite_probe and the real evaluator pass on CUDA.
    probe = _finite_probe(student2, val_loader)
    assert probe["finite_logits"] is True
    assert probe["logit_shape"] == [int(config["training"]["batch_size"]), num_classes]

    eval_config = _write_eval_config(tmp_path, "cuda:0")
    report = evaluate_v3_3_validation(
        eval_config, checkpoint_path=str(best_path), seed=seed
    )
    assert report["final_blind_test_accessed"] is False
    assert np.isfinite(float(report["validation"]["accuracy"]))
    assert np.isfinite(float(report["validation"]["macro_f1"]))
    assert np.isfinite(float(report["fpga_sim_gap"]["accuracy_gap"]))
