"""M27 channel/interference synthetic generator (spec §十一).

Deterministic, 3-way seed-isolated synthetic I/Q for the 11 environment labels.
For every sample a known modulation is drawn uniformly from MODULATION_POOL (so the
modulation is balanced across environments), a clean baseband signal is synthesised,
the chosen environment impairment is applied, AWGN at a matched SNR is added, and the
result is RMS-normalised to ~1.  Output is float32 [N,2,1024] planar I/Q with no
metadata channel, so the label cannot be recovered from array shape/format/power.

Reproducibility: the random stream for a (split, family, index) sample is derived from
``SeedSequence([seed, split_code, family_code, index])`` so different splits and
families never share a stream, and a re-run with the same seed reproduces byte-identical
arrays.
"""

from __future__ import annotations

import numpy as np

from m27_channel_contract import (
    CHANNEL_LABELS,
    MODULATION_POOL,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    SPLIT_FINAL_TEST,
)

N_SAMPLES = 1024
N_CHANNELS = 2


def _rng_for(seed, split_code, family_code, index):
    return np.random.default_rng(
        np.random.SeedSequence([seed, split_code, family_code, index])
    )


def _gen_baseband(rng, mod, n):
    """Synthesise a clean baseband signal of length n for a known modulation."""
    sps = 8  # samples per symbol
    nsym = n // sps
    if mod in ("BPSK", "QPSK", "8PSK"):
        m = {"BPSK": 2, "QPSK": 4, "8PSK": 8}[mod]
        phases = rng.integers(0, m, size=nsym)
        syms = np.exp(1j * 2 * np.pi * phases / m)
    elif mod in ("16QAM", "64QAM"):
        m = {"16QAM": 4, "64QAM": 8}[mod]  # m points per axis
        a = rng.integers(-m + 1, m, size=(nsym, 2))
        syms = (a[:, 0] + 1j * a[:, 1]) / float(m)
    elif mod == "GFSK":
        # approximate GFSK: integrate a smoothed binary frequency sequence
        bits = rng.integers(0, 2, size=nsym) * 2 - 1
        fdev = 0.15
        phase = np.cumsum(bits) * fdev * 2 * np.pi / sps
        syms = np.exp(1j * phase)
    else:
        raise ValueError(f"unknown modulation {mod}")
    # rectangular pulse (upsample and repeat) -> simple, NPU-independent
    base = np.repeat(syms, sps)
    return base[:n].astype(np.complex64)


def _apply_impairment(rng, label, x):
    n = len(x)
    if label == "CLEAN":
        return x
    if label == "CFO":
        df = rng.uniform(0.01, 0.08) * (1 if rng.random() < 0.5 else -1)
        return x * np.exp(2j * np.pi * df * np.arange(n)).astype(np.complex64)
    if label == "PHASE_NOISE":
        sigma = rng.uniform(0.02, 0.15)
        phase = np.cumsum(rng.normal(0.0, sigma, size=n))
        return x * np.exp(1j * phase).astype(np.complex64)
    if label == "IQ_IMBALANCE":
        g = rng.uniform(0.5, 0.9)          # gain imbalance
        phi = rng.uniform(0.1, 0.6)        # phase imbalance (rad)
        alpha = np.cos(phi) + 1j * g * np.sin(phi)
        beta = g * np.cos(phi) - 1j * np.sin(phi)
        return (alpha * x + beta * np.conj(x)).astype(np.complex64)
    if label == "MULTIPATH":
        d = int(rng.integers(1, 12))
        a = rng.uniform(0.3, 0.85) * np.exp(1j * rng.uniform(0, 2 * np.pi))
        y = np.copy(x)
        y[d:] = y[d:] + a * x[:-d]
        return y.astype(np.complex64)
    if label == "CLIPPING":
        level = rng.uniform(0.4, 0.9) * np.sqrt(np.mean(np.abs(x) ** 2))
        mag = np.abs(x)
        scale = np.minimum(1.0, level / np.maximum(mag, 1e-12))
        return (x * scale).astype(np.complex64)
    if label == "CW_INTERFERENCE":
        f0 = rng.uniform(-0.4, 0.4)
        a = rng.uniform(0.3, 1.0)
        tone = a * np.exp(2j * np.pi * f0 * np.arange(n))
        return (x + tone).astype(np.complex64)
    if label == "MULTITONE":
        y = np.copy(x)
        for _ in range(int(rng.integers(3, 6))):
            f0 = rng.uniform(-0.45, 0.45)
            a = rng.uniform(0.15, 0.5)
            y = y + a * np.exp(2j * np.pi * f0 * np.arange(n))
        return y.astype(np.complex64)
    if label == "PULSE":
        y = np.copy(x)
        for _ in range(int(rng.integers(1, 3))):
            t0 = int(rng.integers(0, n))
            width = int(rng.integers(16, 128))
            a = rng.uniform(0.5, 1.5)
            lo = min(t0, n); hi = min(t0 + width, n)
            y[lo:hi] = y[lo:hi] + a * np.exp(1j * rng.uniform(0, 2 * np.pi))
        return y.astype(np.complex64)
    if label == "SWEEP":
        f0 = rng.uniform(-0.4, 0.1)
        k = rng.uniform(0.2e-3, 0.8e-3)
        a = rng.uniform(0.3, 0.8)
        t = np.arange(n)
        chirp = a * np.exp(2j * np.pi * (f0 * t + 0.5 * k * t * t))
        return (x + chirp).astype(np.complex64)
    if label == "MULTI_IMPAIRMENT":
        pool = ["CFO", "PHASE_NOISE", "IQ_IMBALANCE", "MULTIPATH", "CLIPPING"]
        for lab in rng.choice(pool, size=int(rng.integers(2, 4)), replace=False):
            x = _apply_impairment(rng, lab, x)
        return x
    raise ValueError(f"unknown label {label}")


def generate_split(seed, split_code, samples_per_label=64, snr_range=(0.0, 20.0)):
    """Generate one split.  Returns (x, y, snr) with x float32 [N,2,1024],
    y int [N], snr float32 [N] (per-sample SNR, for per-SNR evaluation)."""
    labels_per = samples_per_label
    n_total = labels_per * len(CHANNEL_LABELS)
    x = np.zeros((n_total, N_CHANNELS, N_SAMPLES), dtype=np.float32)
    y = np.zeros(n_total, dtype=np.int64)
    snr = np.zeros(n_total, dtype=np.float32)

    idx = 0
    for lab_i, label in enumerate(CHANNEL_LABELS):
        for k in range(labels_per):
            family_code = lab_i  # family = environment label
            rng = _rng_for(seed, split_code, family_code, k)
            mod = MODULATION_POOL[int(rng.integers(0, len(MODULATION_POOL)))]
            base = _gen_baseband(rng, mod, N_SAMPLES)
            imp = _apply_impairment(rng, label, base)
            snr_val = rng.uniform(*snr_range)
            noise = (rng.normal(0, 1, N_SAMPLES) + 1j * rng.normal(0, 1, N_SAMPLES))
            noise = noise.astype(np.complex128) / np.sqrt(2.0)
            sig_power = np.mean(np.abs(imp) ** 2)
            scale = 10 ** (-snr_val / 20.0)
            noisy = imp + scale * np.sqrt(sig_power) * noise
            # RMS-normalise the final sample to ~1 (matched power across labels)
            rms = np.sqrt(np.mean(np.abs(noisy) ** 2))
            if rms > 1e-9:
                noisy = noisy / rms
            x[idx, 0] = np.real(noisy).astype(np.float32)
            x[idx, 1] = np.imag(noisy).astype(np.float32)
            y[idx] = lab_i
            snr[idx] = snr_val
            idx += 1
    return x, y, snr


def generate_all(seed, samples_per_label=64):
    """Generate train/validation/final-test with three distinct split codes."""
    return {
        "train": generate_split(seed, SPLIT_TRAIN, samples_per_label),
        "validation": generate_split(seed, SPLIT_VALIDATION, samples_per_label),
        "final_test": generate_split(seed, SPLIT_FINAL_TEST, samples_per_label),
    }
