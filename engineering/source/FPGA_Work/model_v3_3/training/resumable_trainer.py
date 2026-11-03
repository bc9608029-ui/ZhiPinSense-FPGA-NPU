"""Strictly resumable trainer used by post-Baseline ablation experiments.

The frozen Baseline V1 trainer remains untouched.  This implementation stores
all state that can affect the next epoch, including RNG and DataLoader shuffle
generator state.  It can also migrate the already-produced legacy ablation
checkpoint by deterministically replaying its known RNG consumption pattern.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as functional
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader

from training.trainer import Trainer


CHECKPOINT_VERSION = 2


def capture_rng_state() -> dict[str, Any]:
    """Capture every framework RNG used by this project."""
    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["torch_cuda_all"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict[str, Any]) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    # The structured checkpoint is loaded on CPU, but keep the restore
    # device-explicit.  The CPU RNG state is a single CPU ByteTensor; the CUDA RNG
    # state is a *list* of per-device CPU ByteTensors (``get_rng_state_all`` returns
    # a list, not a single tensor), so it is restored element-wise with strict
    # type + device-count checks before ``set_rng_state_all``.
    torch.set_rng_state(state["torch_cpu"].detach().cpu())
    cuda_states = state.get("torch_cuda_all")
    if cuda_states is not None and torch.cuda.is_available():
        if not isinstance(cuda_states, (list, tuple)):
            raise TypeError("torch_cuda_all must be a list/tuple of per-device ByteTensors")
        if len(cuda_states) != torch.cuda.device_count():
            raise RuntimeError(
                f"CUDA RNG device count mismatch: checkpoint={len(cuda_states)}, "
                f"runtime={torch.cuda.device_count()}"
            )
        restored_states = []
        for index, rng_tensor in enumerate(cuda_states):
            if not isinstance(rng_tensor, torch.Tensor):
                raise TypeError(f"CUDA RNG state {index} is not a Tensor")
            if rng_tensor.dtype != torch.uint8:
                raise TypeError(f"CUDA RNG state {index} must be uint8, got {rng_tensor.dtype}")
            restored_states.append(rng_tensor.detach().cpu())
        torch.cuda.set_rng_state_all(restored_states)


def reconstruct_loader_generator_state(seed: int, num_samples: int, completed_epochs: int) -> torch.Tensor:
    """Reproduce RandomSampler plus DataLoader base-seed consumption exactly."""
    generator = torch.Generator().manual_seed(int(seed))
    for _ in range(int(completed_epochs)):
        # DataLoader draws its worker/base seed before RandomSampler is consumed.
        torch.empty((), dtype=torch.int64).random_(generator=generator)
        torch.randperm(int(num_samples), generator=generator)
    return generator.get_state()


def replay_legacy_global_rng(
    *, completed_epochs: int, train_samples: int, batch_size: int, fusion_features: int, dropout: float
) -> None:
    """Replay RNG calls made by the legacy ablation loop after model creation.

    The ablation models contain exactly one classifier dropout.  Train samples
    are deterministic NumPy records and the validation loader makes one global
    Torch base-seed draw per epoch.  This restores the counterfactual continuous
    Torch RNG state without rerunning optimization.
    """
    full_batches, remainder = divmod(int(train_samples), int(batch_size))
    batch_sizes = [int(batch_size)] * full_batches + ([remainder] if remainder else [])
    for _ in range(int(completed_epochs)):
        for current_batch in batch_sizes:
            functional.dropout(
                torch.empty(current_batch, int(fusion_features)),
                p=float(dropout),
                training=True,
            )
        # Validation DataLoader has no dedicated generator in the frozen setup.
        torch.empty((), dtype=torch.int64).random_()


class ResumableTrainer(Trainer):
    """Trainer with complete, versioned continuation state."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        training = self.config["training"]
        self.checkpoint_metric = str(training.get("checkpoint_metric", "val_loss"))
        default_mode = "min" if self.checkpoint_metric.endswith("loss") else "max"
        self.checkpoint_mode = str(training.get("checkpoint_mode", default_mode)).lower()
        if self.checkpoint_mode not in {"min", "max"}:
            raise ValueError("checkpoint_mode must be 'min' or 'max'")
        self.best_loss = float("inf") if self.checkpoint_mode == "min" else float("-inf")
        self.stale_epochs = 0
        self.start_epoch = 1
        self.current_epoch = 0
        self.history: list[dict[str, float]] = []
        self.resume_metadata: dict[str, Any] | None = None

    def _complete_checkpoint(
        self,
        epoch: int,
        metrics: dict[str, float],
        train_loader: DataLoader,
    ) -> dict[str, Any]:
        generator = train_loader.generator
        if generator is None:
            raise RuntimeError("Strict resume requires a dedicated train DataLoader generator.")
        return {
            "checkpoint_version": CHECKPOINT_VERSION,
            "epoch": int(epoch),
            "next_epoch": int(epoch) + 1,
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "scheduler_state": self.scheduler.state_dict() if self.scheduler is not None else None,
            "metrics": metrics,
            "best_validation_loss": float(self.best_loss),
            "best_monitor_value": float(self.best_loss),
            "checkpoint_metric": self.checkpoint_metric,
            "checkpoint_mode": self.checkpoint_mode,
            "best_epoch": self.best_epoch,
            "early_stopping_state": {
                "stale_epochs": int(self.stale_epochs),
                "patience": int(self.config["training"].get("early_stopping_patience", 7)),
                "min_delta": float(self.config["training"].get("min_delta", 0.0)),
            },
            "rng_state": capture_rng_state(),
            "train_loader_generator_state": generator.get_state(),
            "dataset_state": {
                "train_epoch": int(getattr(train_loader.dataset, "epoch", epoch)),
                "next_epoch": int(epoch) + 1,
                "split": str(getattr(train_loader.dataset, "split", "train")),
            },
            "history": self.history,
            "total_training_time_sec": float(self.total_training_time_sec),
            "peak_process_rss_mb": float(self.peak_rss_mb),
            "class_names": self.class_names,
            "config": self.config,
        }

    def _reconstruct_scheduler(self, completed_epoch: int) -> None:
        if self.scheduler is None:
            return
        # The optimizer checkpoint already carries the post-step LR.  Rebuild
        # scheduler counters without modifying that optimizer LR.
        state = self.scheduler.state_dict()
        state["last_epoch"] = int(completed_epoch)
        if "_step_count" in state:
            state["_step_count"] = int(completed_epoch) + 1
        state["_last_lr"] = [float(group["lr"]) for group in self.optimizer.param_groups]
        self.scheduler.load_state_dict(state)

    def _migrate_optimizer_state_to_device(self) -> None:
        """Move every optimizer state tensor onto the training device.

        ``Optimizer.load_state_dict`` normally casts state tensors (moments,
        per-param ``step``) to each parameter's device, but the resume contract
        requires device-exact placement.  Any tensor that still lives elsewhere
        is migrated explicitly; this is a no-op when the device already matches.
        """
        for param_state in self.optimizer.state.values():
            for key, value in list(param_state.items()):
                if isinstance(value, torch.Tensor) and value.device != self.device:
                    param_state[key] = value.to(self.device)

    def _load_legacy_checkpoint(self, checkpoint: dict[str, Any], train_loader: DataLoader) -> None:
        completed_epoch = int(checkpoint["epoch"])
        self.model.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self._migrate_optimizer_state_to_device()
        self._reconstruct_scheduler(completed_epoch)

        best_path = self.output_paths["checkpoints"] / "best.pt"
        # best.pt is a structured checkpoint too; load it on CPU so none of its
        # tensors are mapped onto the GPU (only scalars are read here, but the
        # load stays device-safe).
        best_checkpoint = torch.load(best_path, map_location="cpu", weights_only=False)
        self.best_epoch = int(best_checkpoint["epoch"])
        metric = self.checkpoint_metric
        if metric not in best_checkpoint["metrics"]:
            raise RuntimeError(f"Legacy checkpoint does not contain selection metric {metric!r}")
        self.best_loss = float(best_checkpoint["metrics"][metric])
        self.stale_epochs = completed_epoch - self.best_epoch
        self.start_epoch = completed_epoch + 1

        history_path = self.output_paths["logs"] / "training_history.csv"
        if history_path.exists():
            self.history = pd.read_csv(history_path).to_dict(orient="records")
        else:
            self.history = []
        self.total_training_time_sec = float(sum(float(row.get("training_time_sec", 0.0)) for row in self.history))

        generator = train_loader.generator
        if generator is None:
            raise RuntimeError("Legacy migration requires a dedicated train DataLoader generator.")
        generator.set_state(
            reconstruct_loader_generator_state(
                int(self.config["seed"]), len(train_loader.dataset), completed_epoch
            )
        )
        replay_legacy_global_rng(
            completed_epochs=completed_epoch,
            train_samples=len(train_loader.dataset),
            batch_size=int(self.config["training"]["batch_size"]),
            fusion_features=int(self.config["dual_domain"]["fusion_features"]),
            dropout=float(self.config["dual_domain"]["dropout"]),
        )
        self.resume_metadata = {
            "source_checkpoint_version": 1,
            "legacy_state_reconstructed": True,
            "completed_epoch": completed_epoch,
            "next_epoch": self.start_epoch,
        }

    def load_resume(self, checkpoint_path: str | Path, train_loader: DataLoader) -> None:
        # Load the structured checkpoint on CPU.  On a GPU host ``map_location=self.device``
        # moves *every* tensor in the checkpoint onto the GPU, including the DataLoader
        # generator state and the CPU/CUDA RNG states.  Those must stay CPU-side:
        # ``Generator.set_state``/``torch.set_rng_state`` require a CPU ``ByteTensor`` and
        # reject a CUDA-mapped one ("RNG state must be a torch.ByteTensor").  Only the
        # model/optimizer state is placed on the training device below.
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        version = int(checkpoint.get("checkpoint_version", 1))
        if version < CHECKPOINT_VERSION:
            self._load_legacy_checkpoint(checkpoint, train_loader)
            return

        self.model.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self._migrate_optimizer_state_to_device()
        if self.scheduler is not None:
            if checkpoint["scheduler_state"] is None:
                raise RuntimeError("Checkpoint is missing scheduler state.")
            self.scheduler.load_state_dict(checkpoint["scheduler_state"])
        checkpoint_metric = str(checkpoint.get("checkpoint_metric", "val_loss"))
        checkpoint_mode = str(checkpoint.get("checkpoint_mode", "min"))
        if checkpoint_metric != self.checkpoint_metric or checkpoint_mode != self.checkpoint_mode:
            raise RuntimeError(
                "Resume selection policy changed: "
                f"checkpoint={checkpoint_metric}/{checkpoint_mode}, "
                f"config={self.checkpoint_metric}/{self.checkpoint_mode}"
            )
        self.best_loss = float(
            checkpoint.get("best_monitor_value", checkpoint["best_validation_loss"])
        )
        self.best_epoch = int(checkpoint["best_epoch"])
        early = checkpoint["early_stopping_state"]
        self.stale_epochs = int(early["stale_epochs"])
        self.start_epoch = int(checkpoint["next_epoch"])
        self.history = list(checkpoint.get("history", []))
        self.total_training_time_sec = float(checkpoint.get("total_training_time_sec", 0.0))
        self.peak_rss_mb = max(self.peak_rss_mb, float(checkpoint.get("peak_process_rss_mb", 0.0)))
        generator = train_loader.generator
        if generator is None:
            raise RuntimeError("Strict resume requires a dedicated train DataLoader generator.")
        generator.set_state(checkpoint["train_loader_generator_state"].detach().cpu())
        restore_rng_state(checkpoint["rng_state"])
        self.resume_metadata = {
            "source_checkpoint_version": version,
            "legacy_state_reconstructed": False,
            "completed_epoch": int(checkpoint["epoch"]),
            "next_epoch": self.start_epoch,
        }

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        *,
        resume_path: str | Path | None = None,
        stop_after_epoch: int | None = None,
    ) -> list[dict[str, float]]:
        training = self.config["training"]
        patience = int(training.get("early_stopping_patience", 7))
        minimum_epochs = int(training.get("minimum_epochs_before_stopping", 1))
        min_delta = float(training.get("min_delta", 0.0))
        log_path = self.output_paths["logs"] / "training_console.log"
        if resume_path is None:
            log_path.write_text("", encoding="utf-8")
        else:
            self.load_resume(resume_path, train_loader)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"Resume checkpoint={Path(resume_path)} next_epoch={self.start_epoch} "
                    f"version={self.resume_metadata['source_checkpoint_version']}\n"
                )

        run_start = time.perf_counter()
        end_epoch = int(training["epochs"])
        if stop_after_epoch is not None:
            end_epoch = min(end_epoch, int(stop_after_epoch))

        for epoch in range(self.start_epoch, end_epoch + 1):
            if hasattr(train_loader.dataset, "set_epoch"):
                train_loader.dataset.set_epoch(epoch)
            self.current_epoch = epoch
            epoch_start = time.perf_counter()
            train_metrics = self._run_epoch(train_loader, training=True)
            val_metrics = self._run_epoch(val_loader, training=False)
            elapsed = time.perf_counter() - epoch_start
            row = {
                "epoch": epoch,
                "learning_rate": float(self.optimizer.param_groups[0]["lr"]),
                "training_time_sec": elapsed,
                **{f"train_{key}": value for key, value in train_metrics.items()},
                **{f"val_{key}": value for key, value in val_metrics.items()},
            }
            self.history.append(row)
            message = (
                f"epoch={epoch:02d} train_loss={train_metrics['loss']:.4f} "
                f"val_loss={val_metrics['loss']:.4f} val_acc={val_metrics['accuracy']:.4f} "
                f"val_f1={val_metrics['macro_f1']:.4f} time={elapsed:.1f}s"
            )
            print(message)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(message + "\n")

            if isinstance(self.scheduler, ReduceLROnPlateau):
                self.scheduler.step(val_metrics["loss"])
            elif self.scheduler is not None:
                self.scheduler.step()

            monitor_key = self.checkpoint_metric.removeprefix("val_")
            if monitor_key not in val_metrics:
                raise RuntimeError(
                    f"Unknown checkpoint metric {self.checkpoint_metric!r}; "
                    f"available validation metrics are {sorted(val_metrics)}"
                )
            monitor_value = float(val_metrics[monitor_key])
            if self.checkpoint_mode == "min":
                improved = monitor_value < self.best_loss - min_delta
            else:
                improved = monitor_value > self.best_loss + min_delta
            if improved:
                self.best_loss = monitor_value
                self.best_epoch = epoch
                self.stale_epochs = 0
            else:
                self.stale_epochs += 1

            self.total_training_time_sec += time.perf_counter() - epoch_start
            checkpoint = self._complete_checkpoint(epoch, row, train_loader)
            torch.save(checkpoint, self.output_paths["checkpoints"] / "last.pt")
            if improved:
                torch.save(checkpoint, self.output_paths["checkpoints"] / "best.pt")
            pd.DataFrame(self.history).to_csv(log_path.parent / "training_history.csv", index=False)

            if epoch >= minimum_epochs and self.stale_epochs >= patience:
                message = f"Early stopping at epoch {epoch}."
                print(message)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(message + "\n")
                break

        self._save_training_curves(self.history)
        run_elapsed = time.perf_counter() - run_start
        message = f"This run time: {run_elapsed:.1f}s; cumulative epoch time: {self.total_training_time_sec:.1f}s"
        print(message)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
        return self.history
