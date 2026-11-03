"""Confusion-matrix plot and CSV writer."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_confusion_matrix(matrix: np.ndarray, class_names: list[str], figure_path: Path, csv_path: Path) -> None:
    normalized = matrix / np.maximum(matrix.sum(axis=1, keepdims=True), 1)
    fig, axis = plt.subplots(figsize=(8, 7))
    image = axis.imshow(normalized, cmap="Blues", vmin=0.0, vmax=1.0)
    fig.colorbar(image, ax=axis, label="Row-normalized fraction")
    axis.set(xticks=np.arange(len(class_names)), yticks=np.arange(len(class_names)))
    axis.set_xticklabels(class_names, rotation=45, ha="right")
    axis.set_yticklabels(class_names)
    axis.set_xlabel("Predicted modulation")
    axis.set_ylabel("True modulation")
    axis.set_title("Modulation Classification Confusion Matrix")
    for row in range(len(class_names)):
        for column in range(len(class_names)):
            value = normalized[row, column]
            axis.text(column, row, f"{value:.2f}", ha="center", va="center", color="white" if value > 0.5 else "black", fontsize=8)
    fig.tight_layout()
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)
    pd.DataFrame(matrix, index=class_names, columns=class_names).to_csv(csv_path)

