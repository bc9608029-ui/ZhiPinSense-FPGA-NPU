"""Deterministic synthetic OOD dataset (near / far / ambiguous families).

Samples are generated on the fly from a fixed SeedSequence so a frozen TSV
manifest plus the recorded (seed, split, family) triple reproduces the exact
records without storing tensors to disk.  Every record is RMS-normalized to
``amplitude`` and returned as planar float32 I/Q ``[2, sample_length]`` to match
``RadioML2018Dataset`` and the board input contract.

The three OOD sets are kept strictly isolated by ``split``:

* ``oe_aux_train``  — auxiliary outliers seen by OE+Energy training only;
* ``ood_validation`` — used only to lock thresholds;
* ``ood_final_test`` — final evaluation, never used for thresholds or training.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from datasets.ood_generator import (
    OOD_AMBIGUOUS,
    OOD_FAR,
    OOD_NEAR_12,
    OOD_NEAR_24,
    generate_ood_iq,
)

OOD_FAMILIES: dict[str, tuple[str, ...]] = {
    "near_12": OOD_NEAR_12,
    "near_24": OOD_NEAR_24,
    "far": OOD_FAR,
    "ambiguous": OOD_AMBIGUOUS,
}

# split -> stable integer code (kept separate from model training seeds).
SPLIT_CODES: dict[str, int] = {
    "oe_aux_train": 1,
    "ood_validation": 2,
    "ood_final_test": 3,
}


def default_ood_signal_config() -> dict[str, Any]:
    """Signal config matching the deployment generator's native representation."""
    return {
        "sample_rate": 128_000.0,
        "symbol_rate": 16_000.0,
        "samples_per_symbol": 8,
        "sample_length": 1024,
        "amplitude": 1.0,
        "frequency_offset": 0.0,
        "phase_offset": 0.0,
        "pulse_shape": {"rolloff": 0.35, "span_symbols": 8},
    }


def to_planar(iq_complex: np.ndarray) -> np.ndarray:
    """Convert complex64 [N, L] -> planar float32 [N, 2, L]."""
    iq_complex = np.asarray(iq_complex)
    planar = np.stack((iq_complex.real, iq_complex.imag), axis=1).astype(np.float32)
    return planar


@dataclass
class OODRecords:
    """Container for a generated OOD family split."""
    iq: np.ndarray          # complex64 [N, L]
    modulation: np.ndarray  # object/str [N]
    family: str
    split: str
    seed: int
    signal_config: dict[str, Any]

    @property
    def planar(self) -> np.ndarray:
        return to_planar(self.iq)

    def __len__(self) -> int:
        return int(self.iq.shape[0])


def generate_ood_records(
    family: str,
    split: str,
    *,
    seed: int,
    count_per_modulation: int,
    signal_config: dict[str, Any] | None = None,
) -> OODRecords:
    """Generate every modulation in ``family``, ``count_per_modulation`` each."""
    if family not in OOD_FAMILIES:
        raise ValueError(f"unknown OOD family {family!r}; expected {sorted(OOD_FAMILIES)}")
    if split not in SPLIT_CODES:
        raise ValueError(f"unknown OOD split {split!r}; expected {sorted(SPLIT_CODES)}")
    if count_per_modulation <= 0:
        raise ValueError("count_per_modulation must be positive")

    config = signal_config or default_ood_signal_config()
    modulations = OOD_FAMILIES[family]
    rng = np.random.default_rng(np.random.SeedSequence([seed, SPLIT_CODES[split], _FAMILY_CODES[family]]))

    iq_list: list[np.ndarray] = []
    mod_list: list[str] = []
    for modulation in modulations:
        for _ in range(int(count_per_modulation)):
            iq, _meta = generate_ood_iq(modulation, config, rng)
            iq_list.append(iq)
            mod_list.append(modulation)

    return OODRecords(
        iq=np.stack(iq_list).astype(np.complex64),
        modulation=np.asarray(mod_list, dtype=object),
        family=family,
        split=split,
        seed=seed,
        signal_config=config,
    )


_FAMILY_CODES: dict[str, int] = {name: i for i, name in enumerate(OOD_FAMILIES)}


def write_ood_manifest(records: OODRecords, path: str) -> None:
    """Write a frozen TSV manifest (sample_index, family, split, modulation)."""
    header = "sample_index\tfamily\tsplit\tmodulation\n"
    rows = [
        f"{i}\t{records.family}\t{records.split}\t{records.modulation[i]}\n"
        for i in range(len(records))
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(header)
        handle.writelines(rows)


__all__ = [
    "OOD_FAMILIES", "SPLIT_CODES", "default_ood_signal_config", "to_planar",
    "OODRecords", "generate_ood_records", "write_ood_manifest",
]
