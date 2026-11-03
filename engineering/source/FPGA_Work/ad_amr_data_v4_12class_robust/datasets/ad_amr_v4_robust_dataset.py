"""Data-v4 robustness dataset: augmented train channel, frozen eval channel.

PROVISIONAL — experiment scaffold.

The single purpose of this class is to route the TRAIN split through the config-
driven ``RobustChannelPipeline`` (core + tail + composite) while leaving every
other split — validation, OOD, fake-int8 — on the FROZEN baseline
``ChannelPipeline`` (``config["channel"]``).  This guarantees the augmented train
channel can never pollute the frozen validation / OOD records: those are produced
byte-for-byte by the same code path as the twelve-class baseline.

The sample/split/sample-id contract is inherited unchanged from
``ADAMRPairDataset`` (SeedSequence([seed, split_code, epoch, index]),
sample_id_base = split_code * 1e6), and the twelve-class signal contract is
asserted by ``ADAMRV11Dataset``.
"""

from __future__ import annotations

from typing import Any

from channel.robust_augment import RobustChannelPipeline
from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, collate_ad_amr


class ADAMRV4RobustDataset(ADAMRV11Dataset):
    """Twelve-class dataset whose TRAIN split uses the augmented channel."""

    def __init__(
        self,
        num_samples: int,
        signal_config: dict[str, Any],
        channel_config: dict[str, Any] | None = None,
        seed: int = 2026,
        split: str = "ad_amr_v1_4_robust_train",
        fixed_snr_db: float | None = None,
        snr_values: list[float] | None = None,
        train_channel_config: dict[str, Any] | None = None,
    ) -> None:
        # ADAMRV11Dataset asserts the twelve-class signal contract and rejects any
        # blind/test split, then ADAMRPairDataset builds the FROZEN ChannelPipeline.
        super().__init__(num_samples, signal_config, channel_config, seed, split,
                         fixed_snr_db=fixed_snr_db, snr_values=snr_values)
        if self.is_train_split:
            robust_cfg = train_channel_config if train_channel_config is not None else channel_config
            self.channel = RobustChannelPipeline(robust_cfg, signal_config["sample_rate"])


__all__ = ["ADAMRV4RobustDataset", "collate_ad_amr"]
