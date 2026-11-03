"""Standard compact PyTorch training loop with bounded logging/checkpoints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import psutil
import torch
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from torch import nn
from torch.optim import Adam, AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau
from torch.utils.data import DataLoader
from tqdm import tqdm

from training.metrics import classification_metrics


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        config: dict[str, Any],
        output_paths: dict[str, Path],
        class_names: list[str],
    ) -> None:
        self.model = model.to(device)
        self.device = device
        self.config = config
        self.output_paths = output_paths
        self.class_names = class_names
        training = config["training"]
        optimizer_class = {"Adam": Adam, "AdamW": AdamW}.get(training["optimizer"])
        if optimizer_class is None:
            raise ValueError("optimizer must be Adam or AdamW")
        self.optimizer = optimizer_class(
            self.model.parameters(),
            lr=float(training["learning_rate"]),
            weight_decay=float(training.get("weight_decay", 0.0)),
        )
        scheduler_name = str(training.get("scheduler", "none")).lower()
        if scheduler_name == "cosine":
            self.scheduler = CosineAnnealingLR(self.optimizer, T_max=int(training["epochs"]))
        elif scheduler_name == "plateau":
            self.scheduler = ReduceLROnPlateau(self.optimizer, mode="min", patience=2, factor=0.5)
        else:
            self.scheduler = None
        self.criterion = nn.CrossEntropyLoss()
        self.process = psutil.Process()
        self.peak_rss_mb = self.process.memory_info().rss / (1024**2)
        self.best_epoch: int | None = None
        self.total_training_time_sec = 0.0

    def _update_peak_memory(self) -> None:
        self.peak_rss_mb = max(self.peak_rss_mb, self.process.memory_info().rss / (1024**2))

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, float]:
        self.model.train(training)
        total_loss = 0.0
        targets: list[int] = []
        predictions: list[int] = []
        description = "train" if training else "valid"
        for batch in tqdm(loader, desc=description, leave=False):
            inputs, labels = batch[:2]
            inputs = inputs.to(self.device, non_blocking=True)
            labels = labels.to(self.device, non_blocking=True)
            if training:
                self.optimizer.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                logits = self.model(inputs)
                loss = self.criterion(logits, labels)
                if training:
                    loss.backward()
                    self.optimizer.step()
            self._update_peak_memory()
            total_loss += float(loss.item()) * inputs.shape[0]
            targets.extend(labels.detach().cpu().tolist())
            predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
        result = classification_metrics(targets, predictions, len(self.class_names))
        return {
            "loss": total_loss / len(loader.dataset),
            "accuracy": float(result["accuracy"]),
            "macro_f1": float(result["macro_f1"]),
        }

    def _checkpoint(self, epoch: int, metrics: dict[str, float]) -> dict[str, Any]:
        return {
            "epoch": epoch,
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "metrics": metrics,
            "class_names": self.class_names,
            "config": self.config,
        }

    def fit(self, train_loader: DataLoader, val_loader: DataLoader) -> list[dict[str, float]]:
        training = self.config["training"]
        patience = int(training.get("early_stopping_patience", 7))
        min_delta = float(training.get("min_delta", 0.0))
        best_loss = float("inf")
        stale_epochs = 0
        history: list[dict[str, float]] = []
        start = time.perf_counter()
        log_path = self.output_paths["logs"] / "training_console.log"
        log_path.write_text("", encoding="utf-8")

        for epoch in range(1, int(training["epochs"]) + 1):
            if hasattr(train_loader.dataset, "set_epoch"):
                train_loader.dataset.set_epoch(epoch)
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
            history.append(row)
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

            checkpoint = self._checkpoint(epoch, row)
            torch.save(checkpoint, self.output_paths["checkpoints"] / "last.pt")
            if val_metrics["loss"] < best_loss - min_delta:
                best_loss = val_metrics["loss"]
                self.best_epoch = epoch
                stale_epochs = 0
                torch.save(checkpoint, self.output_paths["checkpoints"] / "best.pt")
            else:
                stale_epochs += 1
                if stale_epochs >= patience:
                    message = f"Early stopping at epoch {epoch}."
                    print(message)
                    with log_path.open("a", encoding="utf-8") as handle:
                        handle.write(message + "\n")
                    break

            pd.DataFrame(history).to_csv(self.output_paths["logs"] / "training_history.csv", index=False)

        pd.DataFrame(history).to_csv(self.output_paths["logs"] / "training_history.csv", index=False)
        self.total_training_time_sec = time.perf_counter() - start
        self._save_training_curves(history)
        message = f"Total training time: {self.total_training_time_sec:.1f}s"
        print(message)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
        return history

    def _save_training_curves(self, history: list[dict[str, float]]) -> None:
        """Save compact train/validation curves for convergence diagnostics."""
        frame = pd.DataFrame(history)
        for train_key, val_key, ylabel, filename in (
            ("train_loss", "val_loss", "Cross-entropy loss", "training_loss.png"),
            ("train_accuracy", "val_accuracy", "Accuracy", "training_accuracy.png"),
        ):
            fig, axis = plt.subplots(figsize=(8, 5))
            axis.plot(frame["epoch"], frame[train_key], marker="o", label="Train")
            axis.plot(frame["epoch"], frame[val_key], marker="o", label="Validation")
            axis.set(title=f"Train/validation {ylabel}", xlabel="Epoch", ylabel=ylabel)
            axis.grid(True, alpha=0.3)
            axis.legend()
            fig.tight_layout()
            fig.savefig(self.output_paths["figures"] / filename, dpi=180)
            plt.close(fig)
