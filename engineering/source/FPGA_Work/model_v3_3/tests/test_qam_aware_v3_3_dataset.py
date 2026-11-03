"""Dataset integrity: no cross-split waveform leakage and a sealed blind set."""

from __future__ import annotations

from pathlib import Path

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.dataset_audit import _fingerprints
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SMOKE_CONFIG = "configs/qam_aware_v3_3_smoke.yaml"
BLIND_SPLIT = "v3_3_final_blind_test"


def test_fingerprint_overlap_is_zero_across_splits() -> None:
    config = load_qam_aware_v3_3_config(SMOKE_CONFIG)
    train = _fingerprints(config, "train")
    validation = _fingerprints(config, "validation")
    test = _fingerprints(config, "test")
    # Non-empty, 64 unique records each.
    assert len(train) == 64
    assert len(validation) == 64
    assert len(test) == 64
    assert not (train & validation), "train/validation share an exact waveform"
    assert not (train & test), "train/test share an exact waveform"
    assert not (validation & test), "validation/test share an exact waveform"


def test_blind_split_is_reserved_and_never_instantiated(monkeypatch) -> None:
    config = load_qam_aware_v3_3_config(SMOKE_CONFIG)
    assert config["final_blind_test"]["split"] == BLIND_SPLIT

    requested: list[str] = []
    real_init = SyntheticModulationDataset.__init__

    def spy(self, num_samples, signal_config, channel_config=None, seed=2026, split="train",
            return_metadata=False, fixed_snr_db=None, snr_values=None) -> None:
        requested.append(str(split))
        if str(split) == BLIND_SPLIT:
            raise AssertionError("development code instantiated the final blind namespace")
        return real_init(self, num_samples, signal_config, channel_config, seed, split,
                         return_metadata, fixed_snr_db, snr_values)

    monkeypatch.setattr(SyntheticModulationDataset, "__init__", spy)
    for split in ("train", "validation", "test"):
        _fingerprints(config, split)

    assert set(requested) == {"train", "validation", "test"}


def test_no_python_source_instantiates_the_blind_split() -> None:
    offending: list[str] = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if "tests" in path.relative_to(PROJECT_ROOT).parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if BLIND_SPLIT in line and "split=" in line:
                offending.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
    assert not offending, (
        "the final blind split must only appear in documentation/config, never as a split value: "
        + "; ".join(offending)
    )
