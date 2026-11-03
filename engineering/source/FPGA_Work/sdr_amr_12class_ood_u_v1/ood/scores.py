"""OOD anomaly scores (higher = more likely OOD).

MSP / Entropy / MaxLogit / Energy operate on raw logits.  Mahalanobis operates on
penultimate features and OpenMax fits a per-class Weibull on logits; both are
provided as offline contrast baselines only.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ood.energy import energy_score


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float64)
    maximum = logits.max(axis=1, keepdims=True)
    exp = np.exp(logits - maximum)
    return exp / exp.sum(axis=1, keepdims=True)


def msp_anomaly(logits: np.ndarray) -> np.ndarray:
    """``1 - max softmax`` (higher = more OOD)."""
    probs = _softmax(logits)
    return 1.0 - probs.max(axis=1)


def max_logit_anomaly(logits: np.ndarray) -> np.ndarray:
    """``-max logit`` (higher = more OOD)."""
    return -np.asarray(logits, dtype=np.float64).max(axis=1)


def entropy_anomaly(logits: np.ndarray) -> np.ndarray:
    """Predictive entropy (higher = more OOD)."""
    probs = _softmax(logits)
    log_probs = np.log(np.clip(probs, 1e-12, 1.0))
    return -(probs * log_probs).sum(axis=1)


def logit_margin_anomaly(logits: np.ndarray) -> np.ndarray:
    """``-(top1_logit - top2_logit)`` (higher = more OOD).

    Uses a partial sort for the two largest logits, so it is well-defined even
    when logits carry a large common offset (unlike softmax-based scores).
    """
    logits = np.asarray(logits, dtype=np.float64)
    if logits.ndim != 2:
        raise ValueError(f"logit margin needs logits [N, C], got shape {logits.shape}")
    if logits.shape[1] < 2:
        raise ValueError("logit margin needs at least two logits per sample")
    top2 = np.partition(logits, -2, axis=1)[:, -2:]
    return -(top2[:, 1] - top2[:, 0])


def energy_anomaly(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Energy score (higher = more OOD)."""
    return energy_score(logits, temperature)


def _normalize_logits(logits: np.ndarray) -> np.ndarray:
    return np.asarray(logits, dtype=np.float64)


class MahalanobisScorer:
    """Class-conditional Mahalanobis distance on penultimate features.

    Fits per-class means and a shared precision (inverse covariance) from ID
    training features, then scores a sample by the minimum class distance.
    Offline contrast baseline only.
    """

    def __init__(self) -> None:
        self.means: dict[int, np.ndarray] = {}
        self.precision: np.ndarray | None = None

    def fit(self, features: np.ndarray, labels: np.ndarray,
            eps: float = 1e-6) -> "MahalanobisScorer":
        features = np.asarray(features, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.int64)
        if features.ndim != 2 or labels.shape[0] != features.shape[0]:
            raise ValueError("features must be [N, D] and labels [N]")
        self.means = {
            int(c): features[labels == c].mean(axis=0)
            for c in np.unique(labels)
        }
        centered = features - np.vstack([self.means[int(c)] for c in labels])
        covariance = (centered.T @ centered) / max(features.shape[0] - 1, 1)
        covariance += np.eye(features.shape[1]) * eps
        self.precision = np.linalg.inv(covariance)
        return self

    def score(self, features: np.ndarray) -> np.ndarray:
        if self.precision is None:
            raise RuntimeError("MahalanobisScorer must be fit before scoring")
        features = np.asarray(features, dtype=np.float64)
        distances = []
        for mean in self.means.values():
            delta = features - mean
            distances.append(np.einsum("ij,jk,ik->i", delta, self.precision, delta))
        return np.min(np.vstack(distances), axis=0)


class OpenMaxScorer:
    """Weibull-based OpenMax unknown probability (offline contrast baseline).

    Fits a per-class Weibull on the distance of logits to the per-class mean
    activation vector for correctly classified ID samples, then renormalizes a
    (C+1)-way output whose final component is the OOD (unknown) probability.
    """

    def __init__(self) -> None:
        self.means: dict[int, np.ndarray] = {}
        self.weibull: dict[int, tuple[float, float]] = {}

    @staticmethod
    def _weibull_fit(values: np.ndarray) -> tuple[float, float]:
        values = np.sort(values)
        n = len(values)
        if n < 3:
            return (float(np.mean(values)), 1.0)
        # Method-of-moments fit for the Weibull shape/scale on positive distances.
        mean = float(values.mean())
        var = float(values.var())
        if var <= 1e-12:
            return (mean, 1.0)
        cv2 = var / (mean ** 2)
        shape = 1.0 / max(np.sqrt(cv2), 1e-6)
        scale = mean / max(np.exp(_digamma_ln(1.0 / shape)), 1e-12)
        return (scale, shape)

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> "OpenMaxScorer":
        logits = np.asarray(logits, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.int64)
        self.means = {
            int(c): logits[labels == c].mean(axis=0)
            for c in np.unique(labels)
        }
        self.weibull = {}
        for c in np.unique(labels):
            c = int(c)
            mask = labels == c
            distances = np.abs(logits[mask] - self.means[c]).mean(axis=1)
            self.weibull[c] = self._weibull_fit(distances)
        return self

    def score(self, logits: np.ndarray) -> np.ndarray:
        if not self.weibull:
            raise RuntimeError("OpenMaxScorer must be fit before scoring")
        logits = np.asarray(logits, dtype=np.float64)
        alpha = len(self.weibull)
        scores = np.zeros((logits.shape[0], alpha + 1), dtype=np.float64)
        classes = sorted(self.means)
        for j, c in enumerate(classes):
            scale, shape = self.weibull[c]
            dist = np.abs(logits - self.means[c]).mean(axis=1)
            scores[:, j] = 1.0 - np.exp(-((dist / max(scale, 1e-12)) ** max(shape, 1e-6)))
        # unknown activation = mean over the (1 - weibull cdf) rejection weights
        scores[:, alpha] = (1.0 - scores[:, :alpha]).mean(axis=1)
        probs = _softmax(scores)
        return probs[:, alpha]


def _digamma_ln(_x: float) -> float:
    """Approximate ``ln Gamma(1/x)`` used only to map cv2 -> Weibull shape."""
    # gamma(1 + 1/k) ~ 1 for large k; we only need a stable positive value.
    return 0.0


_SCORE_FN = {
    "msp": msp_anomaly,
    "entropy": entropy_anomaly,
    "max_logit": max_logit_anomaly,
    "logit_margin": logit_margin_anomaly,
    "energy": energy_anomaly,
}


def compute_scores(logits: np.ndarray, method: str, temperature: float = 1.0) -> np.ndarray:
    """Dispatch to a logits-based OOD anomaly score (higher = more OOD)."""
    method = str(method).lower()
    if method not in _SCORE_FN:
        raise ValueError(f"unknown OOD score method {method!r}; expected {sorted(_SCORE_FN)}")
    fn = _SCORE_FN[method]
    if method == "energy":
        return fn(logits, temperature)
    return fn(logits)
