"""RadioML2018.01A strict 24-class trainer (reuses the shared V2Trainer).

The V2Trainer is already parameterized by ``num_classes`` and feeds batch keys
``noisy_iq/clean_iq/label/snr_db`` that ``RadioML2018Dataset`` provides exactly.
The only 12-class-specific parts are the checkpoint payload (V2 model name / V1
SHA) and the synthetic ``build_v2_train_dataset``, so this module overrides
``_payload`` and adds a RadioML-backed loader builder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from contracts.rml24_contract import RML24_MODEL_NAME, rml24_model_payload
from datasets.ad_amr_dataset import collate_ad_amr
from datasets.radioml2018_dataset import RadioML2018Dataset
from models.rml24_net import build_rml24_model
from v2.trainer import V2Trainer


class RML24Trainer(V2Trainer):
    def __init__(self, config: dict[str, Any], paths: dict[str, Path],
                 classes: list[str]) -> None:
        super().__init__(config, paths, classes, build_model=build_rml24_model)

    def _payload(self, epoch: int) -> dict[str, Any]:
        model_name = str(self.config.get("rml24", {}).get("model_name", RML24_MODEL_NAME))
        return rml24_model_payload(
            model_name=model_name, epoch=epoch, best_score=self.best_score,
            best_epoch=self.best_epoch, stale_epochs=self.stale_epochs,
            history=self.history, classes=self.classes, loss_name=self.loss_name,
            config=self.config, model_state=self.model.state_dict(),
            optimizer_state=self.optimizer.state_dict(),
            scheduler_state=self.scheduler.state_dict(),
            amp_state=self.scaler.state_dict(),
        )


def build_rml24_loader(config: dict[str, Any], split: str,
                       device: torch.device, shuffle: bool = False) -> DataLoader:
    """Build a RadioML2018Dataset DataLoader for ``train``/``validation``/``test``."""
    if split not in ("train", "validation", "test"):
        raise ValueError(f"split must be train/validation/test, got {split!r}")
    public = config["public_data"]
    max_per_stratum = None
    if split == "train":
        max_per_stratum = config.get("rml24", {}).get("smoke_max_per_stratum")
    dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], split, max_per_stratum=max_per_stratum,
    )
    batch_size = int(config["training"]["batch_size"])
    num_workers = int(config["dataset"].get("num_workers", 0))
    pin = device.type == "cuda"
    return DataLoader(
        dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers,
        collate_fn=collate_ad_amr, pin_memory=pin, drop_last=False,
    )


__all__ = ["RML24Trainer", "build_rml24_loader"]
