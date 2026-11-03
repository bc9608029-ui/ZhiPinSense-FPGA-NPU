"""Classification metrics used by training and evaluation."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


def classification_metrics(targets: list[int] | np.ndarray, predictions: list[int] | np.ndarray, num_classes: int) -> dict[str, object]:
    targets_array = np.asarray(targets)
    predictions_array = np.asarray(predictions)
    matrix = confusion_matrix(targets_array, predictions_array, labels=np.arange(num_classes))
    denominators = matrix.sum(axis=1)
    per_class = np.divide(np.diag(matrix), denominators, out=np.zeros(num_classes, dtype=float), where=denominators > 0)
    return {
        "accuracy": float(accuracy_score(targets_array, predictions_array)),
        "macro_f1": float(f1_score(targets_array, predictions_array, labels=np.arange(num_classes), average="macro", zero_division=0)),
        "per_class_accuracy": per_class.tolist(),
        "confusion_matrix": matrix,
    }

