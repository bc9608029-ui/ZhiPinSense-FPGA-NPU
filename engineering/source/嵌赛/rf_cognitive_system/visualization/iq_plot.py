"""I/Q time-domain plotting."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_iq_time(iq: np.ndarray, sample_rate: float, path: Path, title: str) -> None:
    time_ms = np.arange(len(iq)) / sample_rate * 1e3
    fig, axis = plt.subplots(figsize=(9, 4.5))
    axis.plot(time_ms, iq.real, label="I", linewidth=1.0)
    axis.plot(time_ms, iq.imag, label="Q", linewidth=1.0, alpha=0.8)
    axis.set(title=title, xlabel="Time (ms)", ylabel="Normalized amplitude")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_before_after(
    before: np.ndarray,
    after: np.ndarray,
    sample_rate: float,
    path: Path,
    title: str,
    labels: tuple[str, str],
) -> None:
    count = min(len(before), 300)
    time_ms = np.arange(count) / sample_rate * 1e3
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    for axis, values, label in zip(axes, (before, after), labels):
        axis.plot(time_ms, values[:count].real, label="I", linewidth=0.9)
        axis.plot(time_ms, values[:count].imag, label="Q", linewidth=0.9, alpha=0.8)
        axis.set_ylabel("Amplitude")
        axis.set_title(label)
        axis.grid(True, alpha=0.25)
        axis.legend(loc="upper right")
    axes[-1].set_xlabel("Time (ms)")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)

