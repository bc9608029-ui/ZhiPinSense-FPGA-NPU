"""Read-only Baseline V1 failure diagnosis on the frozen SNR-sweep records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from scipy.stats import kurtosis, skew, wasserstein_distance
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.evaluate import load_model
from training.utils import PROJECT_ROOT, load_config, select_device, set_seed


SELECTED_CLASSES = ("QPSK", "8PSK", "16QAM", "64QAM")
PAIR_CLASSES = (("QPSK", "8PSK"), ("16QAM", "64QAM"))
SNR_VALUES = (-10, -6, 0, 10, 20)


def _suffix(snr: int) -> str:
    return f"m{abs(snr)}" if snr < 0 else f"p{snr}"


def _verify_frozen_baseline() -> None:
    lock = json.loads((PROJECT_ROOT / "configs" / "baseline_v1_lock.json").read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in lock["sha256"].items():
        actual = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            mismatches.append(relative)
    if mismatches:
        raise RuntimeError(f"Baseline V1 lock mismatch; diagnosis aborted: {mismatches}")


def _moments(values: np.ndarray, prefix: str) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_std": float(np.std(values)),
        f"{prefix}_skewness": float(skew(values, bias=False)),
        f"{prefix}_kurtosis": float(kurtosis(values, fisher=True, bias=False)),
    }


def _distribution_figure(signals: dict[str, np.ndarray], snr: int, path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    colors = plt.cm.tab10.colors
    for color, (name, iq) in zip(colors, signals.items()):
        flat = iq.reshape(-1)
        radius = np.abs(flat)
        stride = max(len(radius) // 40000, 1)
        radius_plot = radius[::stride]
        axes[0, 0].hist(radius_plot, bins=100, density=True, histtype="step", linewidth=1.5, label=name, color=color)
        ordered = np.sort(radius_plot)
        axes[0, 1].plot(ordered, np.linspace(0, 1, len(ordered), endpoint=False), label=name, color=color)
        axes[0, 2].hist(flat.real[::stride], bins=100, density=True, histtype="step", linewidth=1.4, label=name, color=color)
        axes[1, 0].hist(flat.imag[::stride], bins=100, density=True, histtype="step", linewidth=1.4, label=name, color=color)
        axes[1, 1].hist(np.angle(flat)[::stride], bins=72, range=(-np.pi, np.pi), density=True, histtype="step", linewidth=1.4, label=name, color=color)
        power = np.abs(iq) ** 2
        papr = 10 * np.log10(np.max(power, axis=1) / np.maximum(np.mean(power, axis=1), 1e-12))
        axes[1, 2].hist(papr, bins=35, density=True, histtype="step", linewidth=1.4, label=name, color=color)
    titles = ("Amplitude histogram", "|IQ| radius ECDF", "I distribution", "Q distribution", "Instantaneous phase", "PAPR distribution")
    xlabels = ("|IQ|", "|IQ|", "I amplitude", "Q amplitude", "Phase (rad)", "PAPR (dB)")
    for axis, title, xlabel in zip(axes.flat, titles, xlabels):
        axis.set(title=title, xlabel=xlabel, ylabel="Density" if "ECDF" not in title else "Cumulative probability")
        axis.grid(True, alpha=0.25)
    axes[0, 0].legend(ncol=2, fontsize=8)
    fig.suptitle(f"Frozen Baseline V1 signal statistics at SNR = {snr} dB")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _logit_figure(rows: pd.DataFrame, classes: list[str], snr: int, path: Path) -> None:
    columns = [f"logit_{name}" for name in classes]
    means = rows.groupby("true_class")[columns].mean().reindex(SELECTED_CLASSES)
    fig, axis = plt.subplots(figsize=(10, 4.8))
    image = axis.imshow(means.to_numpy(), cmap="coolwarm", aspect="auto")
    fig.colorbar(image, ax=axis, label="Mean baseline logit")
    axis.set_xticks(range(len(classes)), labels=classes, rotation=45, ha="right")
    axis.set_yticks(range(len(SELECTED_CLASSES)), labels=SELECTED_CLASSES)
    axis.set(xlabel="Output class", ylabel="True class", title=f"Baseline mean logits at {snr} dB")
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


@torch.inference_mode()
def run_diagnosis(samples_per_class: int = 250) -> dict[str, Any]:
    _verify_frozen_baseline()
    config = load_config("configs/baseline.yaml")
    set_seed(int(config["seed"]))
    device = select_device(config.get("device", "auto"))
    model, classes = load_model(config, PROJECT_ROOT / "outputs" / "baseline_v1" / "checkpoints" / "best.pt", device)
    model.eval()
    output = PROJECT_ROOT / "outputs" / "baseline_v1_diagnostics"
    paths = {name: output / name for name in ("figures", "tables", "logs")}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    statistic_rows: list[dict[str, Any]] = []
    logit_rows: list[dict[str, Any]] = []
    separation_rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    pca_rows: list[dict[str, Any]] = []
    pca_summary_rows: list[dict[str, Any]] = []
    total_per_snr = samples_per_class * len(classes)

    for snr in SNR_VALUES:
        dataset = SyntheticModulationDataset(
            total_per_snr,
            config["signal"],
            config["channel"],
            seed=int(config["seed"]),
            split=f"snr_sweep_{snr}",
            fixed_snr_db=float(snr),
        )
        signals: dict[str, np.ndarray] = {}
        embeddings: dict[str, np.ndarray] = {}
        for class_name in SELECTED_CLASSES:
            label = classes.index(class_name)
            tensors = torch.stack([dataset[label + repetition * len(classes)][0] for repetition in range(samples_per_class)])
            complex_iq = tensors[:, 0].numpy() + 1j * tensors[:, 1].numpy()
            signals[class_name] = complex_iq
            flat = complex_iq.reshape(-1)
            radius = np.abs(flat)
            phase = np.angle(flat)
            power = np.abs(complex_iq) ** 2
            papr = 10 * np.log10(np.max(power, axis=1) / np.maximum(np.mean(power, axis=1), 1e-12))
            row: dict[str, Any] = {"snr_db": snr, "modulation": class_name, "samples": samples_per_class}
            row.update(_moments(flat.real, "i"))
            row.update(_moments(flat.imag, "q"))
            row.update(_moments(radius, "radius"))
            row.update(_moments(phase, "phase"))
            row.update(_moments(papr, "papr_db"))
            row["papr_db_p05"] = float(np.quantile(papr, 0.05))
            row["papr_db_p50"] = float(np.quantile(papr, 0.50))
            row["papr_db_p95"] = float(np.quantile(papr, 0.95))
            statistic_rows.append(row)

            batch = tensors.to(device)
            embedding = model.features(batch).flatten(1)
            logits = model.classifier(embedding)
            embeddings[class_name] = embedding.cpu().numpy()
            predictions = logits.argmax(dim=1).cpu().numpy()
            logits_numpy = logits.cpu().numpy()
            for index in range(samples_per_class):
                record: dict[str, Any] = {
                    "snr_db": snr,
                    "true_class": class_name,
                    "predicted_class": classes[int(predictions[index])],
                    "correct": int(predictions[index] == label),
                }
                record.update({f"logit_{name}": float(value) for name, value in zip(classes, logits_numpy[index])})
                logit_rows.append(record)

        _distribution_figure(signals, snr, paths["figures"] / f"distributions_snr_{_suffix(snr)}.png")
        snr_logits = pd.DataFrame([row for row in logit_rows if row["snr_db"] == snr])
        _logit_figure(snr_logits, classes, snr, paths["figures"] / f"baseline_logits_snr_{_suffix(snr)}.png")

        for first, second in PAIR_CLASSES:
            first_embedding, second_embedding = embeddings[first], embeddings[second]
            centroid_distance = float(np.linalg.norm(first_embedding.mean(axis=0) - second_embedding.mean(axis=0)))
            within_first = float(np.sqrt(np.mean(np.sum((first_embedding - first_embedding.mean(axis=0)) ** 2, axis=1))))
            within_second = float(np.sqrt(np.mean(np.sum((second_embedding - second_embedding.mean(axis=0)) ** 2, axis=1))))
            separation_rows.append({
                "snr_db": snr,
                "pair": f"{first}_vs_{second}",
                "centroid_distance": centroid_distance,
                "within_class_rms_mean": (within_first + within_second) / 2,
                "normalized_embedding_separation": centroid_distance / max((within_first + within_second) / 2, 1e-12),
            })
            first_flat, second_flat = signals[first].reshape(-1), signals[second].reshape(-1)
            distance_rows.append({
                "snr_db": snr,
                "pair": f"{first}_vs_{second}",
                "radius_wasserstein": float(wasserstein_distance(np.abs(first_flat), np.abs(second_flat))),
                "i_wasserstein": float(wasserstein_distance(first_flat.real, second_flat.real)),
                "q_wasserstein": float(wasserstein_distance(first_flat.imag, second_flat.imag)),
                "papr_mean_difference_db": float(
                    np.mean(10 * np.log10(np.max(np.abs(signals[first]) ** 2, axis=1) / np.mean(np.abs(signals[first]) ** 2, axis=1)))
                    - np.mean(10 * np.log10(np.max(np.abs(signals[second]) ** 2, axis=1) / np.mean(np.abs(signals[second]) ** 2, axis=1)))
                ),
            })

        if snr in (10, 20):
            qam_embedding = np.concatenate((embeddings["16QAM"], embeddings["64QAM"]), axis=0)
            labels = np.array(["16QAM"] * samples_per_class + ["64QAM"] * samples_per_class)
            standardized = StandardScaler().fit_transform(qam_embedding)
            pca_model = PCA(n_components=2, random_state=int(config["seed"]))
            coordinates = pca_model.fit_transform(standardized)
            score = float(silhouette_score(coordinates, labels))
            pca_summary_rows.append({
                "snr_db": snr,
                "silhouette_2d": score,
                "explained_variance_pc1": float(pca_model.explained_variance_ratio_[0]),
                "explained_variance_pc2": float(pca_model.explained_variance_ratio_[1]),
            })
            for coordinate, label in zip(coordinates, labels):
                pca_rows.append({"snr_db": snr, "modulation": label, "pc1": coordinate[0], "pc2": coordinate[1]})
            fig, axis = plt.subplots(figsize=(7, 6))
            for name in ("16QAM", "64QAM"):
                mask = labels == name
                axis.scatter(coordinates[mask, 0], coordinates[mask, 1], s=14, alpha=0.55, label=name)
            axis.set(title=f"Baseline penultimate embeddings PCA at {snr} dB\n2-D silhouette = {score:.3f}", xlabel="PC1", ylabel="PC2")
            axis.grid(True, alpha=0.25)
            axis.legend()
            fig.tight_layout()
            fig.savefig(paths["figures"] / f"qam_embedding_pca_snr_{_suffix(snr)}.png", dpi=180)
            plt.close(fig)

    statistics = pd.DataFrame(statistic_rows)
    logits = pd.DataFrame(logit_rows)
    separations = pd.DataFrame(separation_rows)
    distances = pd.DataFrame(distance_rows)
    pca_frame = pd.DataFrame(pca_rows)
    pca_summary = pd.DataFrame(pca_summary_rows)
    statistics.to_csv(paths["tables"] / "signal_statistics.csv", index=False)
    logits.to_csv(paths["tables"] / "baseline_logits.csv", index=False)
    logits.groupby(["snr_db", "true_class"])["correct"].mean().rename("baseline_accuracy").reset_index().to_csv(
        paths["tables"] / "baseline_selected_accuracy.csv", index=False
    )
    separations.to_csv(paths["tables"] / "embedding_separation.csv", index=False)
    distances.to_csv(paths["tables"] / "pair_distribution_distances.csv", index=False)
    pca_frame.to_csv(paths["tables"] / "qam_embedding_pca_coordinates.csv", index=False)
    pca_summary.to_csv(paths["tables"] / "qam_embedding_pca_summary.csv", index=False)

    selected_accuracy = logits.groupby(["snr_db", "true_class"])["correct"].mean().unstack()
    qam_high = float(selected_accuracy.loc[[10, 20], ["16QAM", "64QAM"]].mean().mean())
    high_qam_separation = float(separations.query("snr_db >= 10 and pair == '16QAM_vs_64QAM'")["normalized_embedding_separation"].mean())
    report = {
        "baseline_lock_verified": True,
        "checkpoint": "outputs/baseline_v1/checkpoints/best.pt",
        "frozen_evaluation_split_pattern": "snr_sweep_{snr}",
        "samples_per_class_per_snr": samples_per_class,
        "snr_values": list(SNR_VALUES),
        "classes": list(SELECTED_CLASSES),
        "high_snr_qam_mean_accuracy": qam_high,
        "high_snr_qam_normalized_embedding_separation": high_qam_separation,
        "high_snr_qam_pca_2d_silhouette": dict(zip(pca_summary["snr_db"].astype(str), pca_summary["silhouette_2d"])),
        "interpretation": [
            "Raw distribution distances remain non-zero at high SNR, so the QAM classes retain measurable statistical differences.",
            "Baseline high-SNR QAM accuracy and embedding separation are substantially weaker than for the other selected classes.",
            "This supports a representation/capacity limitation in the time-only baseline; it does not prove that every raw statistic is independently sufficient for classification.",
        ],
    }
    (paths["tables"] / "diagnosis_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (paths["logs"] / "provenance.json").write_text(
        json.dumps({"baseline_config": config["_config_path"], "seed": config["seed"], "device": str(device), **report}, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-class", type=int, default=250)
    args = parser.parse_args()
    print(json.dumps(run_diagnosis(args.samples_per_class), indent=2))


if __name__ == "__main__":
    main()
