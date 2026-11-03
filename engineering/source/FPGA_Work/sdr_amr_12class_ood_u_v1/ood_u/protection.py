"""Known-class protection (OOD-R) tests.

Known 12-class signals under channel impairment are OOD-R: the model must still
recognise them as their original class and must NOT reject them as UNKNOWN.  This
module generates impaired known-class samples (clean / SNR sweep / CFO / phase
noise / IQ imbalance / multipath / clipping / multi-impairment / strong-nearby)
and reports, per condition, the classification accuracy, ID accept rate, ID
false-reject rate, per-class reject rate, per-SNR reject rate and the most
rejected class at the frozen threshold.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from channel.awgn import add_awgn
from channel.fading import multipath_fading
from channel.impairments import (
    carrier_frequency_offset,
    clip_iq,
    iq_imbalance,
    narrowband_interference,
    phase_noise,
)
from datasets.modulation_generator import generate_iq
from ood.scores import compute_scores
from ood_u import contract
from ood_u.benchmark import logits_for
from ood_u.data import SplitRecords, signal_config
from ood_u.model import ADAMRV11Net

PROTECTION_SNR_DB = 10.0

IMPAIRMENT_CONDITIONS = (
    "clean", "snr_sweep", "cfo", "phase_noise", "iq_imbalance",
    "multipath", "clipping", "multi", "strong_nearby",
)

# Full SNR sweep for the low-SNR known-class (OOD-R) acceptance check.
SNR_SWEEP: tuple[float, ...] = (-20.0, -10.0, 0.0, 10.0, 20.0)


def _apply_impairment(iq: np.ndarray, condition: str, rng: np.random.Generator,
                      sample_rate: float) -> np.ndarray:
    if condition in ("clean", "snr_sweep"):
        return iq
    if condition == "cfo":
        return carrier_frequency_offset(iq, 2000.0, sample_rate)
    if condition == "phase_noise":
        return phase_noise(iq, 0.05, rng)
    if condition == "iq_imbalance":
        return iq_imbalance(iq, 2.0, 10.0)
    if condition == "multipath":
        out, _ = multipath_fading(iq, 3, 8, rng)
        return out
    if condition == "clipping":
        return clip_iq(iq, 1.5)
    if condition == "strong_nearby":
        ref = float(np.mean(np.abs(iq) ** 2))
        return narrowband_interference(iq, sample_rate, -10.0, 5000.0, float(rng.uniform(-np.pi, np.pi)),
                                       reference_power=ref)
    if condition == "multi":
        out = carrier_frequency_offset(iq, 1500.0, sample_rate)
        out = iq_imbalance(out, 1.5, 8.0)
        out, _ = multipath_fading(out, 3, 8, rng)
        out = clip_iq(out, 1.8)
        return phase_noise(out, 0.03, rng)
    raise ValueError(f"unknown impairment condition {condition!r}")


def generate_protection_records(
    condition: str,
    split: str,
    *,
    seed: int,
    count_per_class: int,
    snr_values: tuple[float, ...] | None = None,
) -> SplitRecords:
    """Generate known 12-class samples under ``condition`` (family="id")."""
    if condition not in IMPAIRMENT_CONDITIONS:
        raise ValueError(f"unknown impairment condition {condition!r}")
    cfg = signal_config()
    if condition == "snr_sweep":
        snr_values = SNR_SWEEP
    else:
        snr_values = (PROTECTION_SNR_DB,) if snr_values is None else tuple(snr_values)

    split_code = {"oe_aux_train": 1, "ood_validation": 2, "ood_final_test": 3}[split]
    cond_code = IMPAIRMENT_CONDITIONS.index(condition) + 1

    planar_list: list[np.ndarray] = []
    mod_list: list[str] = []
    snr_list: list[float] = []
    for mod_index, mod in enumerate(contract.LABEL_ORDER_12):
        for snr_index, snr in enumerate(snr_values):
            for i in range(int(count_per_class)):
                rng = np.random.default_rng(
                    np.random.SeedSequence([seed, split_code, cond_code, mod_index, snr_index, i])
                )
                iq, _ = generate_iq(mod, cfg, rng)
                iq = _apply_impairment(iq, condition, rng, cfg["sample_rate"])
                iq, _ = add_awgn(iq, float(snr), rng)
                planar_list.append(np.stack((iq.real, iq.imag), axis=0).astype(np.float32))
                mod_list.append(mod)
                snr_list.append(float(snr))

    planar = np.stack(planar_list).astype(np.float32)
    import hashlib
    return SplitRecords(
        planar=planar,
        modulation=np.asarray(mod_list, dtype=object),
        snr_db=np.asarray(snr_list, dtype=np.float64),
        family="id",
        split=split,
        seed=seed,
        signal_config=cfg,
        sample_hashes=[
            hashlib.sha256(np.ascontiguousarray(p, dtype=np.float32).tobytes()).hexdigest()
            for p in planar
        ],
    )


def _per_class_reject(reject: np.ndarray, modulation: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {}
    for mod in sorted(set(str(m) for m in modulation)):
        mask = modulation == mod
        result[mod] = float(np.mean(reject[mask]))
    return result


def _per_snr_reject(reject: np.ndarray, snr: np.ndarray) -> dict[str, float]:
    result: dict[str, float] = {}
    for value in sorted(set(float(s) for s in snr)):
        mask = snr == value
        result[f"{value:g}"] = float(np.mean(reject[mask]))
    return result


def evaluate_protection(
    model: ADAMRV11Net,
    records: SplitRecords,
    *,
    score_method: str,
    temperature: float,
    threshold: float,
) -> dict[str, Any]:
    """Score impaired known classes and report accept/reject statistics."""
    logits = logits_for(model, records)
    scores = compute_scores(logits, score_method, temperature)
    predicted = np.argmax(logits, axis=1)
    labels = np.asarray([contract.LABEL_ORDER_12.index(str(m)) for m in records.modulation],
                        dtype=np.int64)
    reject = scores > threshold

    per_class = _per_class_reject(reject, records.modulation)
    most_rejected = max(per_class, key=per_class.get) if per_class else None
    return {
        "classification_accuracy": float(np.mean(predicted == labels)),
        "id_accept_rate": float(np.mean(scores <= threshold)),
        "id_false_reject_rate": float(np.mean(reject)),
        "per_class_reject_rate": per_class,
        "per_snr_reject_rate": _per_snr_reject(reject, records.snr_db),
        "most_rejected_class": most_rejected,
        "most_rejected_class_rate": per_class[most_rejected] if most_rejected else float("nan"),
    }


def run_protection_suite(
    model: ADAMRV11Net,
    *,
    score_method: str,
    temperature: float,
    threshold: float,
    split: str = "ood_final_test",
    seed: int,
    count_per_class: int = 20,
) -> dict[str, Any]:
    """Evaluate every impairment condition and return a per-condition report."""
    report: dict[str, Any] = {}
    for condition in IMPAIRMENT_CONDITIONS:
        records = generate_protection_records(condition, split, seed=seed, count_per_class=count_per_class)
        report[condition] = evaluate_protection(
            model, records, score_method=score_method, temperature=temperature, threshold=threshold
        )
        report[condition]["samples"] = len(records)
    return report


__all__ = [
    "IMPAIRMENT_CONDITIONS", "SNR_SWEEP", "PROTECTION_SNR_DB",
    "generate_protection_records", "evaluate_protection", "run_protection_suite",
]
