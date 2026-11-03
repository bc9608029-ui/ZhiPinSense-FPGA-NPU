#!/usr/bin/env python3
# offline_frame_simulator.py -- deterministic synthetic IQ-frame generator for
# the M29 RML23 constellation UI (desktop1 work tree).
#
# Purpose (honest, render-verification ONLY):
#   The UI's data contract (docs/data_format.md, contracts/ui_runtime_frame_v1.md)
#   defines FOUR stage views. Real board fixtures exist only for RECOVERED_PAYLOAD
#   and MODEL_INPUT. RAW_RX and SYMBOL_SAMPLED have NO real board data, and the
#   prototype red line forbids fabricating RAW_RX / faking symbol sampling from
#   real oversampled data. So this simulator produces CLEARLY-LABELLED SYNTHETIC
#   frames (metric_provenance = "synthetic-offline-desktop1", source_index = -1)
#   purely so the UI can be exercised end-to-end for all four views WITHOUT the
#   board. These are NOT real RF and must never be labelled as such.
#
# Determinism: fixed seed by default; the payload_sha256 is the SHA-256 of the
# exact bytes written, so the sidecar always matches its binary (fail-closed).
#
#   python3 offline_frame_simulator.py --out fixtures/synthetic [--seed 20261018]
#
# Emits, per stage, a flat-JSON sidecar + a planar little-endian f32 binary:
#   raw_rx.f32/json               RAW_RX            (QPSK, smeared: CFO+noise+DC)
#   recovered_payload.f32/json    RECOVERED_PAYLOAD (QPSK, recovered)
#   model_input.f32/json          MODEL_INPUT       (BPSK, [2,1024])
#   symbol_sampled.f32/json       SYMBOL_SAMPLED    (4ASK, 1 sample/symbol)
import argparse
import hashlib
import json
import os

import numpy as np

FS = 2560000  # frozen sample rate the UI displays
PROVENANCE = "synthetic-offline-desktop1"


def planar_f32_bytes(iq):
    """Planar little-endian float32: real[0:N] then imag[0:N]."""
    a = np.empty(2 * iq.size, dtype="<f4")
    a[: iq.size] = np.real(iq).astype("<f4")
    a[iq.size:] = np.imag(iq).astype("<f4")
    return a.tobytes()


def write_frame(out_dir, name, stage, iq, modulation, frame_id, symbol_timing_valid):
    data = planar_f32_bytes(iq)
    sha = hashlib.sha256(data).hexdigest()
    iq_file = f"{name}.f32"
    with open(os.path.join(out_dir, iq_file), "wb") as f:
        f.write(data)

    sidecar = {
        "schema_version": 1,
        "frame_id": frame_id,
        "stage": stage,
        "dtype": "<f4",
        "layout": "planar",
        "complex_count": int(iq.size),
        "sample_rate_hz": FS,
        "source_index": -1,  # sentinel: synthetic, no real dataset source
        "modulation": modulation,
        "predicted_class": modulation,
        "baseline_class": modulation,
        "confidence": 0.0,
        "confidence_valid": False,
        "cfo_hz": 0.0,
        "cfo_valid": False,
        "sro_ppm": 0.0,
        "sro_valid": False,
        "gain_mag": 0.0,
        "gain_valid": False,
        "recovery_metrics_valid": False,
        "metric_provenance": PROVENANCE,
        "symbol_timing_valid": bool(symbol_timing_valid),
        "payload_sha256": sha,
        "iq_file": iq_file,
    }
    with open(os.path.join(out_dir, f"{name}.json"), "w") as f:
        json.dump(sidecar, f, indent=2)
        f.write("\n")
    return sha, iq.size


def qpsk_symbols(rng, n):
    c = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j], dtype=complex) / np.sqrt(2.0)
    return c[rng.integers(0, 4, n)]


def add_awgn(rng, sig, snr_db):
    if snr_db is None:
        return sig
    std = 10.0 ** (-snr_db / 20.0)
    n = (rng.normal(0.0, std, sig.size) + 1j * rng.normal(0.0, std, sig.size)) / np.sqrt(2.0)
    return sig + n


def raw_rx(rng):
    # RAW_RX: QPSK held at 8 samples/symbol, CFO rotation, DC offset, 12 dB noise.
    n_sym, sps = 512, 8
    sig = np.repeat(qpsk_symbols(rng, n_sym), sps)
    t = np.arange(sig.size) / FS
    sig = sig * np.exp(2j * np.pi * 3000.0 * t)  # uncompensated CFO
    sig = add_awgn(rng, sig, 12.0)
    sig = sig + (0.15 - 0.10j)  # uncompensated DC offset
    return sig


def recovered_payload(rng):
    # RECOVERED_PAYLOAD: QPSK held at 4 samples/symbol, near-unit, ~26 dB residual.
    n_sym, sps = 512, 4
    sig = np.repeat(qpsk_symbols(rng, n_sym), sps)
    t = np.arange(sig.size) / FS
    sig = sig * np.exp(2j * np.pi * 8.0 * t)  # tiny residual CFO
    return add_awgn(rng, sig, 26.0)


def model_input(rng):
    # MODEL_INPUT: BPSK [2,1024] tensor (real +/-1, imag 0), no noise.
    n = 1024
    return np.where(rng.integers(0, 2, n) == 0, -1.0, 1.0).astype(complex)


def symbol_sampled(rng):
    # SYMBOL_SAMPLED: 16QAM at 1 sample/symbol + small residual noise -> 16 crisp
    # clusters (the classic per-symbol constellation look). symbol_timing_valid.
    n = 1024
    levels = np.array([-3.0, -1.0, 1.0, 3.0]) / 3.0
    i = levels[rng.integers(0, 4, n)]
    q = levels[rng.integers(0, 4, n)]
    sig = (i + 1j * q)
    return add_awgn(rng, sig, 30.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fixtures/synthetic")
    ap.add_argument("--seed", type=int, default=20261018)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    stages = [
        ("raw_rx", "RAW_RX", raw_rx(rng), "QPSK", 1, False),
        ("recovered_payload", "RECOVERED_PAYLOAD", recovered_payload(rng), "QPSK", 2, False),
        ("model_input", "MODEL_INPUT", model_input(rng), "BPSK", 3, False),
        ("symbol_sampled", "SYMBOL_SAMPLED", symbol_sampled(rng), "16QAM", 4, True),
    ]
    print(f"offline_frame_simulator: seed={args.seed} out={args.out}")
    for name, stage, iq, mod, fid, stv in stages:
        sha, n = write_frame(args.out, name, stage, iq, mod, fid, stv)
        print(f"  {stage:18s} {name:20s} complex={n:5d} sha256={sha}")


if __name__ == "__main__":
    main()
