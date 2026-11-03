"""Validation/OOD evaluation facade for the V1.2 data-only candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels


def evaluate_v1_2(
    config_or_path: dict[str, Any] | str,
    checkpoint_path: str | Path,
    split: str = "ad_amr_v1_2_validation",
    channel: dict[str, Any] | None = None,
    samples: int | None = None,
    fake_int8: bool = False,
) -> dict[str, Any]:
    report = evaluate_v1_1(config_or_path, checkpoint_path, split, channel, samples, fake_int8)
    report["track"] = "ad_amr_v1_2"
    return report


__all__ = ["evaluate_v1_2", "ood_channels"]
