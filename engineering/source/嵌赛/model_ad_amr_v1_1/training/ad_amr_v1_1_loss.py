"""Composite supervised, denoising, and multi-teacher distillation loss."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as functional

from models.ad_amr_v1_1_teachers import TeacherEnsemble


# Teacher output order -> student output indices.
TEACHER_TO_STUDENT = (4, 5, 6, 7, 8, 2, 3, 9)
DISTILLABLE_STUDENT_CLASSES = frozenset(TEACHER_TO_STUDENT)


def snr_weights(snr_db: torch.Tensor, config: dict[str, Any]) -> torch.Tensor:
    low = float(config.get("very_low_snr_weight", 0.35))
    rated = float(config.get("rated_snr_weight", 1.25))
    zero = float(config.get("zero_db_extra_weight", 1.20))
    result = torch.ones_like(snr_db, dtype=torch.float32)
    result = torch.where(snr_db < -10.0, torch.full_like(result, low), result)
    result = torch.where(snr_db >= 0.0, torch.full_like(result, rated), result)
    result = torch.where(snr_db == 0.0, result * zero, result)
    return result


def _kd(student_logits: torch.Tensor, teacher_logits: torch.Tensor, labels: torch.Tensor,
        temperature: float) -> torch.Tensor:
    indices = torch.tensor(TEACHER_TO_STUDENT, device=student_logits.device, dtype=torch.long)
    mask = torch.zeros_like(labels, dtype=torch.bool)
    for class_index in DISTILLABLE_STUDENT_CLASSES:
        mask |= labels == class_index
    if not bool(mask.any()):
        return student_logits.sum() * 0.0
    selected = student_logits[mask].index_select(1, indices).float() / temperature
    targets = teacher_logits[mask].float() / temperature
    return functional.kl_div(
        functional.log_softmax(selected, dim=1),
        functional.softmax(targets, dim=1),
        reduction="batchmean",
    ) * (temperature * temperature)


def ad_amr_v1_1_loss(
    logits: torch.Tensor,
    denoised: torch.Tensor,
    clean: torch.Tensor,
    labels: torch.Tensor,
    snr_db: torch.Tensor,
    training_config: dict[str, Any],
    teachers: TeacherEnsemble | None = None,
    teacher_logits: tuple[torch.Tensor, torch.Tensor] | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    weights = snr_weights(snr_db, training_config.get("snr_weighting", {})).to(logits.device)
    ce_each = functional.cross_entropy(logits.float(), labels, reduction="none")
    ce = (ce_each * weights).sum() / weights.sum().clamp_min(1e-6)
    reconstruction = functional.mse_loss(denoised.float(), clean.float())
    reconstruction_weight = float(training_config.get("reconstruction_weight", 0.02))
    total = ce + reconstruction_weight * reconstruction
    components = {"ce": ce, "reconstruction": reconstruction}

    if teachers is not None and teachers.enabled:
        if teacher_logits is None:
            raise ValueError("enabled distillation requires teacher_logits")
        v2_logits, v1_logits = teacher_logits
        kd_v2 = _kd(logits, v2_logits, labels, teachers.temperature)
        kd_v1 = _kd(logits, v1_logits, labels, teachers.temperature)
        total = total + teachers.v2_weight * kd_v2 + teachers.v1_weight * kd_v1
        components.update({"kd_v2": kd_v2, "kd_v1": kd_v1})
    components["total"] = total
    return total, components
