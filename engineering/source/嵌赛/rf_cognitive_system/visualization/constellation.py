"""Constellation scatter plot."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_constellation(
    iq: np.ndarray,
    path: Path,
    title: str,
    max_points: int = 1500,
    symbol_stride: int | None = None,
    symbol_offset: int = 0,
) -> None:
    # For linearly modulated signals, inspect decisions at symbol centers rather
    # than mixing them with the valid RRC transition trajectory.
    source = iq[symbol_offset::symbol_stride] if symbol_stride else iq
    step = max(1, len(source) // max_points)
    values = source[::step][:max_points]
    fig, axis = plt.subplots(figsize=(5.5, 5.5))
    label = "Symbol-center samples" if symbol_stride else "IQ samples"
    axis.scatter(values.real, values.imag, s=10, alpha=0.55, label=label)
    axis.axhline(0.0, color="black", linewidth=0.6)
    axis.axvline(0.0, color="black", linewidth=0.6)
    axis.set(title=title, xlabel="In-phase I (normalized)", ylabel="Quadrature Q (normalized)")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
