"""12-class OOD-U data generation with a shared ID/OOD domain and 3-split isolation.

Both known (ID) and unknown (OOD) samples are produced by the *same* signal
generator + the *same* AWGN stage, so the model cannot distinguish ID from OOD
via a generator shortcut (power / bandwidth / sample-rate / file-format
signature).  The three OOD-U splits (``oe_aux_train`` / ``ood_validation`` /
``ood_final_test``) are isolated by a distinct ``split_code`` baked into every
SeedSequence, and every split carries a deterministic sample-hash manifest whose
zero-overlap and split SHA are asserted fail-closed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from channel.awgn import add_awgn
from datasets.modulation_generator import generate_iq
from datasets.ood_dataset import OOD_FAMILIES
from datasets.ood_generator import generate_ood_iq
from ood_u import contract

# split -> stable integer code (kept separate from the model's training seeds).
SPLIT_CODES: dict[str, int] = {
    "oe_aux_train": 1,
    "ood_validation": 2,
    "ood_final_test": 3,
}

_ID_CODE = 0
_FAMILY_CODES: dict[str, int] = {name: i + 1 for i, name in enumerate(OOD_FAMILIES)}


def signal_config() -> dict[str, Any]:
    """Frozen signal config (matches the deployment generator's native domain)."""
    return {
        "sample_rate": contract.SAMPLE_RATE_HZ,
        "symbol_rate": contract.SYMBOL_RATE_HZ,
        "samples_per_symbol": contract.SAMPLES_PER_SYMBOL,
        "sample_length": contract.SAMPLE_LENGTH,
        "amplitude": contract.AMPLITUDE,
        "frequency_offset": 0.0,
        "phase_offset": 0.0,
        "pulse_shape": {"rolloff": contract.ROLLOFF, "span_symbols": contract.SPAN_SYMBOLS},
    }


def _to_planar(iq_complex: np.ndarray) -> np.ndarray:
    return np.stack((iq_complex.real, iq_complex.imag), axis=0).astype(np.float32)


def _sample_hash(planar: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(planar, dtype=np.float32).tobytes()).hexdigest()


@dataclass
class SplitRecords:
    planar: np.ndarray        # [N, 2, 1024] fp32
    modulation: np.ndarray    # [N] object str
    snr_db: np.ndarray        # [N] float
    family: str               # "id" | "near_12" | "far" | "ambiguous"
    split: str
    seed: int
    signal_config: dict[str, Any]
    sample_hashes: list[str]

    def __len__(self) -> int:
        return int(self.planar.shape[0])

    def manifest_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "sample_index": i,
                "family": self.family,
                "split": self.split,
                "modulation": str(self.modulation[i]),
                "snr_db": float(self.snr_db[i]),
                "sample_sha256": self.sample_hashes[i],
            }
            for i in range(len(self))
        ]


def split_sha(records: SplitRecords) -> str:
    """Deterministic SHA-256 over the split's sorted sample hashes."""
    joined = "\n".join(sorted(records.sample_hashes)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def assert_no_overlap(*records: SplitRecords) -> None:
    """Fail-closed: no sample bytes may appear in more than one split/family."""
    seen: dict[str, str] = {}
    for rec in records:
        for hash_value in rec.sample_hashes:
            owner = seen.setdefault(hash_value, f"{rec.split}:{rec.family}")
            current = f"{rec.split}:{rec.family}"
            if owner != current:
                raise RuntimeError(
                    f"OOD-U data overlap: sample {hash_value} appears in both {owner} and {current}"
                )


def generate_id_split(
    split: str,
    *,
    seed: int,
    count_per_class: int,
    snr_values: tuple[float, ...] | None = None,
) -> SplitRecords:
    """Generate known 12-class samples (every class x every SNR x count)."""
    if split not in SPLIT_CODES:
        raise ValueError(f"unknown OOD-U split {split!r}; expected {sorted(SPLIT_CODES)}")
    snr_values = tuple(snr_values) if snr_values is not None else contract.BENCHMARK_SNR_VALUES
    cfg = signal_config()
    split_code = SPLIT_CODES[split]

    planar_list: list[np.ndarray] = []
    mod_list: list[str] = []
    snr_list: list[float] = []
    for mod_index, mod in enumerate(contract.LABEL_ORDER_12):
        for snr_index, snr in enumerate(snr_values):
            for i in range(int(count_per_class)):
                rng = np.random.default_rng(
                    np.random.SeedSequence([seed, split_code, _ID_CODE, mod_index, snr_index, i])
                )
                iq, _ = generate_iq(mod, cfg, rng)
                iq, _ = add_awgn(iq, float(snr), rng)
                planar_list.append(_to_planar(iq))
                mod_list.append(mod)
                snr_list.append(float(snr))

    planar = np.stack(planar_list).astype(np.float32)
    records = SplitRecords(
        planar=planar,
        modulation=np.asarray(mod_list, dtype=object),
        snr_db=np.asarray(snr_list, dtype=np.float64),
        family="id",
        split=split,
        seed=seed,
        signal_config=cfg,
        sample_hashes=[_sample_hash(p) for p in planar],
    )
    return records


def generate_ood_split(
    family: str,
    split: str,
    *,
    seed: int,
    count_per_modulation: int,
    snr_values: tuple[float, ...] | None = None,
) -> SplitRecords:
    """Generate unknown samples for one OOD family (every mod x every SNR x count)."""
    if split not in SPLIT_CODES:
        raise ValueError(f"unknown OOD-U split {split!r}; expected {sorted(SPLIT_CODES)}")
    if family not in OOD_FAMILIES:
        raise ValueError(f"unknown OOD family {family!r}; expected {sorted(OOD_FAMILIES)}")
    snr_values = tuple(snr_values) if snr_values is not None else contract.BENCHMARK_SNR_VALUES
    cfg = signal_config()
    split_code = SPLIT_CODES[split]
    family_code = _FAMILY_CODES[family]
    modulations = OOD_FAMILIES[family]

    planar_list: list[np.ndarray] = []
    mod_list: list[str] = []
    snr_list: list[float] = []
    for mod_index, mod in enumerate(modulations):
        for snr_index, snr in enumerate(snr_values):
            for i in range(int(count_per_modulation)):
                rng = np.random.default_rng(
                    np.random.SeedSequence([seed, split_code, family_code, mod_index, snr_index, i])
                )
                iq, _ = generate_ood_iq(mod, cfg, rng)
                iq, _ = add_awgn(iq, float(snr), rng)
                planar_list.append(_to_planar(iq))
                mod_list.append(mod)
                snr_list.append(float(snr))

    planar = np.stack(planar_list).astype(np.float32)
    records = SplitRecords(
        planar=planar,
        modulation=np.asarray(mod_list, dtype=object),
        snr_db=np.asarray(snr_list, dtype=np.float64),
        family=family,
        split=split,
        seed=seed,
        signal_config=cfg,
        sample_hashes=[_sample_hash(p) for p in planar],
    )
    return records


__all__ = [
    "SPLIT_CODES", "SplitRecords", "signal_config", "split_sha", "assert_no_overlap",
    "generate_id_split", "generate_ood_split",
]
