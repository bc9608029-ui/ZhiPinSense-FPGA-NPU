"""Ten-class V1.1 dataset with hard split isolation."""

from __future__ import annotations

from typing import Any

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from datasets.modulation_generator import V1_1_MODULATIONS

FORBIDDEN_SELECTION_TOKENS = ("test", "blind")


def assert_v1_1_signal_contract(signal_config: dict[str, Any]) -> None:
    classes = tuple(str(v).upper() for v in signal_config["modulations"])
    if classes != V1_1_MODULATIONS:
        raise ValueError(f"V1.1 requires fixed class order {V1_1_MODULATIONS}, received {classes}")
    if int(signal_config["sample_length"]) != 1024:
        raise ValueError("V1.1 deployment contract requires sample_length=1024")


def assert_selection_split(split: str) -> None:
    lowered = str(split).lower()
    if "validation" not in lowered or any(token in lowered for token in FORBIDDEN_SELECTION_TOKENS):
        raise RuntimeError(f"selection may only access validation namespaces, received {split!r}")


class ADAMRV11Dataset(ADAMRPairDataset):
    def __init__(self, num_samples: int, signal_config: dict[str, Any],
                 channel_config: dict[str, Any] | None = None, seed: int = 2026,
                 split: str = "ad_amr_v1_1_train", fixed_snr_db: float | None = None,
                 snr_values: list[float] | None = None) -> None:
        assert_v1_1_signal_contract(signal_config)
        lowered = str(split).lower()
        if "blind" in lowered:
            raise RuntimeError("final blind data may not be instantiated by V1.1 preparation/training")
        super().__init__(num_samples, signal_config, channel_config, seed, split,
                         fixed_snr_db=fixed_snr_db, snr_values=snr_values)


__all__ = ["ADAMRV11Dataset", "collate_ad_amr", "assert_selection_split",
           "assert_v1_1_signal_contract"]
