"""Optional RadioML 2018.01A HDF5 loader with a safe synthetic fallback."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from datasets.synthetic_dataset import SyntheticModulationDataset


class RadioML2018Dataset(Dataset):
    """Lazy HDF5 reader. h5py is optional and only needed when data is present."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        try:
            import h5py  # type: ignore
        except ImportError as exc:
            raise ImportError("RadioML loading requires optional dependency: pip install h5py") from exc
        self._h5py = h5py
        with h5py.File(self.path, "r") as handle:
            self.length = int(handle["X"].shape[0])

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int):
        with self._h5py.File(self.path, "r") as handle:
            iq = np.asarray(handle["X"][index], dtype=np.float32)
            one_hot = np.asarray(handle["Y"][index])
            snr = float(np.asarray(handle["Z"][index]).squeeze())
        if iq.shape[-1] == 2:
            iq = iq.T
        return torch.from_numpy(iq), int(np.argmax(one_hot)), {"snr_db": snr, "source": "RadioML2018.01A"}


def radioml_or_synthetic(
    path: str | Path,
    fallback_samples: int,
    signal_config: dict[str, Any],
    channel_config: dict[str, Any],
    seed: int,
) -> Dataset:
    candidate = Path(path)
    if candidate.exists():
        return RadioML2018Dataset(candidate)
    warnings.warn(
        f"RadioML dataset not found at {candidate}. Falling back to on-the-fly synthetic IQ.",
        RuntimeWarning,
        stacklevel=2,
    )
    return SyntheticModulationDataset(fallback_samples, signal_config, channel_config, seed=seed)

