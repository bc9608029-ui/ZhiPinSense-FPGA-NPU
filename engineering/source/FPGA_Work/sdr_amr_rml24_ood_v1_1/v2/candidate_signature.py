"""Canonical candidate signature for pilot dedup and formal budget control.

A *candidate* is identified by the training-affecting part of its config plus the
frozen environment provenance (dataset / split / label contract).  Two pilot trials
that sample identical hyperparameters therefore produce the identical signature,
regardless of key order or any per-run fields.  The signature is a SHA-256 over a
key-sorted JSON serialization of a *curated* field surface, so trial number, output /
log / checkpoint paths, timestamps and ``run_id`` can never leak into the identity.

Two identities are exposed, both derived from the same curated surface:

* ``config_sha256``       — the training-knob identity (model + frozen I/O/label
  contract + hyperparameters + normalization), *without* data provenance.  Recorded
  in every checkpoint so a re-run can detect config drift.
* ``canonical_candidate_signature`` — ``config_sha256`` plus ``dataset_sha256`` /
  ``split_sha256`` / ``label_contract_sha256``.  This is the dedup identity used to
  group pilot trials and to forbid duplicate ``(signature, seed)`` formal runs.

Both fail closed if the data provenance SHAs are absent, because a signature that
does not bind to the data split is unsafe to dedup against.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contracts.rml24_contract import INPUT_SHAPE, LABEL_ORDER_24, OUTPUT_DIM, OUTPUT_KIND

# Reserved config keys carrying environment provenance.  The pipeline injects these
# from the data-audit contract before any dedup / formal decision.
KEY_DATASET_SHA = "_dataset_sha256"
KEY_SPLIT_SHA = "_split_sha256"
KEY_LABEL_SHA = "_label_contract_sha256"

_SCHEDULER_TYPE = "reduce_on_plateau"


def _canonical(value: Any) -> Any:
    """Recursively normalize a value for deterministic, key-order-insensitive JSON."""
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float, str)) or value is None:
        return value
    raise TypeError(f"non-serializable value in candidate config: {type(value).__name__} {value!r}")


def _sha(value: Any) -> str:
    blob = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def label_contract_sha256() -> str:
    """SHA-256 of the frozen 24-class label order (the label-contract identity)."""
    return hashlib.sha256(
        json.dumps(list(LABEL_ORDER_24), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _require_sha(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(
            f"candidate signature requires a 64-hex {key!r} in the config; run the data "
            f"audit and inject artifact SHAs before selecting candidates"
        )
    return value


def _training_surface(config: dict[str, Any]) -> dict[str, Any]:
    """The curated training-affecting surface shared by both identities.

    Covers model structure, frozen I/O and label contract, normalization, loss /
    focal / label-smoothing, class weighting, optimizer / LR / weight-decay,
    scheduler, augmentation, curriculum, batch size, AMP, gradient clipping,
    reconstruction and SNR weighting.  Excludes the per-run seed, trial number,
    output/log/checkpoint paths, timestamps and ``run_id``.

    Early-stopping knobs (``minimum_epochs_before_stopping`` /
    ``early_stopping_patience`` / ``min_delta``) are deliberately omitted: they are
    not search-space axes, and ``minimum_epochs_before_stopping`` is capped to the
    pilot epoch budget by ``run_rml24_trial``, so including it would make the
    pilot-computed signature differ from the formal-computed signature for the same
    candidate.
    """
    training = config.get("training") or {}
    v2 = config.get("v2") or {}
    rml24 = config.get("rml24") or {}
    return {
        "model": config.get("model", {}),
        "model_name": rml24.get("model_name", ""),
        "apply_channel_augmentation": rml24.get("apply_channel_augmentation", False),
        "input_shape": list(INPUT_SHAPE),
        "output_dim": OUTPUT_DIM,
        "output_kind": OUTPUT_KIND,
        "label_order": list(LABEL_ORDER_24),
        "normalization": "rms1.0_no_rescale",
        "loss": v2.get("loss", "cross_entropy"),
        "focal_gamma": v2.get("focal_gamma"),
        "label_smoothing": v2.get("label_smoothing"),
        "class_sampling": v2.get("class_sampling", "balanced"),
        "optimizer": v2.get("optimizer", "adamw"),
        "sgd_momentum": v2.get("sgd_momentum", 0.9),
        "learning_rate": training.get("learning_rate"),
        "weight_decay": training.get("weight_decay"),
        "scheduler": {
            "type": _SCHEDULER_TYPE,
            "factor": training.get("scheduler_factor"),
            "patience": training.get("scheduler_patience"),
            "min_lr": training.get("minimum_lr"),
        },
        "augmentation_groups": v2.get("augmentation_groups", []),
        "snr_curriculum": v2.get("snr_curriculum", "none"),
        "batch_size": training.get("batch_size"),
        "amp": training.get("amp"),
        "amp_dtype": training.get("amp_dtype"),
        "gradient_clip_norm": training.get("gradient_clip_norm"),
        "reconstruction_weight": training.get("reconstruction_weight"),
        "snr_weighting": training.get("snr_weighting", {}),
    }


def config_sha256(config: dict[str, Any]) -> str:
    """SHA-256 of the training-knob surface (no data provenance)."""
    return _sha(_training_surface(config))


def canonical_candidate_signature(
    config: dict[str, Any],
    *,
    dataset_sha256: str | None = None,
    split_sha256: str | None = None,
    label_contract_sha256: str | None = None,
) -> str:
    """Return the dedup identity of a training candidate config.

    ``dataset_sha256`` / ``split_sha256`` / ``label_contract_sha256`` may be passed
    explicitly or read from the reserved config keys injected by the data audit; a
    missing value fails closed.
    """
    surface = _training_surface(config)
    surface["dataset_sha256"] = dataset_sha256 or _require_sha(config, KEY_DATASET_SHA)
    surface["split_sha256"] = split_sha256 or _require_sha(config, KEY_SPLIT_SHA)
    surface["label_contract_sha256"] = label_contract_sha256 or _require_sha(config, KEY_LABEL_SHA)
    return _sha(surface)


def load_artifact_shas(contract_path: str | Path = "contracts/rml2018_data_contract.json") -> dict[str, str]:
    """Read dataset / split / label SHAs from the portable data-audit contract.

    Returns a dict ready to inject into a candidate config under the reserved
    ``_*`` keys.  ``dataset_sha256`` is the HDF5 SHA, ``split_sha256`` the split-index
    SHA, and ``label_contract_sha256`` the frozen label-order SHA.
    """
    path = Path(contract_path)
    if not path.is_file():
        raise FileNotFoundError(f"artifact contract {path} missing; run scripts/run_data_audit.sh first")
    contract = json.loads(path.read_text(encoding="utf-8"))
    dataset = contract.get("sha256")
    split = contract.get("index_sha256")
    if not dataset or not split:
        raise ValueError(f"artifact contract {path} lacks sha256/index_sha256")
    return {
        KEY_DATASET_SHA: str(dataset),
        KEY_SPLIT_SHA: str(split),
        KEY_LABEL_SHA: label_contract_sha256(),
    }


def build_checkpoint_provenance(config: dict[str, Any], code_version: str) -> dict[str, Any]:
    """Build the provenance block recorded in every checkpoint.

    Always records ``seed`` / ``code_version`` / ``config_sha256`` / ``model_name`` /
    ``class_count``; the data provenance (dataset/split/label SHAs and the full
    candidate signature) is recorded only when the reserved ``_*`` SHA keys are
    present (they are injected by the select/formal steps, and optionally by the
    pilot).  This block is what the formal resume/dedup step verifies.
    """
    from contracts.rml24_contract import OUTPUT_DIM  # local import to avoid a cycle

    rml24 = config.get("rml24") or {}
    provenance: dict[str, Any] = {
        "seed": config.get("seed"),
        "code_version": code_version,
        "config_sha256": config_sha256(config),
        "model_name": rml24.get("model_name", ""),
        "class_count": OUTPUT_DIM,
    }
    if config.get(KEY_DATASET_SHA):
        provenance["dataset_sha256"] = config[KEY_DATASET_SHA]
        provenance["split_sha256"] = config[KEY_SPLIT_SHA]
        provenance["label_contract_sha256"] = config[KEY_LABEL_SHA]
        provenance["candidate_signature"] = canonical_candidate_signature(config)
    return provenance


__all__ = [
    "canonical_candidate_signature",
    "config_sha256",
    "label_contract_sha256",
    "load_artifact_shas",
    "build_checkpoint_provenance",
    "KEY_DATASET_SHA",
    "KEY_SPLIT_SHA",
    "KEY_LABEL_SHA",
]
