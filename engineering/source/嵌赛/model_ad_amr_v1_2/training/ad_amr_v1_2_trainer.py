"""V1.2 trainer guard layered on the frozen V1.1 training implementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from training.ad_amr_v1_1_trainer import ADAMRV11Trainer


def training_signature(config: dict[str, Any]) -> str:
    tracked = {
        name: config[name]
        for name in ("seed", "signal", "channel", "data_robustness", "dataset", "model", "training")
        if name in config
    }
    payload = json.dumps(tracked, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ADAMRV12Trainer(ADAMRV11Trainer):
    """Adds a data/config signature so variants cannot cross-resume silently."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.v1_2_signature = training_signature(self.config)

    def _payload(self, epoch: int, train_loader: DataLoader) -> dict[str, Any]:
        payload = super()._payload(epoch, train_loader)
        payload.update({"track": "ad_amr_v1_2", "training_signature": self.v1_2_signature})
        return payload

    def load_resume(self, path: Path, train_loader: DataLoader) -> int:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("track") != "ad_amr_v1_2":
            raise RuntimeError("resume checkpoint is not an AD-AMR V1.2 checkpoint")
        if checkpoint.get("training_signature") != self.v1_2_signature:
            raise RuntimeError("V1.2 resume configuration/data curriculum changed")
        return super().load_resume(path, train_loader)


__all__ = ["ADAMRV12Trainer", "training_signature"]
