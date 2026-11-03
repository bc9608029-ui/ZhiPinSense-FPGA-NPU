#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_blind_clean_contract.py -- fix10class24-dualsdr-blind-clean1 TX-side
frozen payload producer (PC host, pure offline, never touches the board/SDR/RF).

Builds the BLIND (no-sample-prior) pure-modulation TX package: 24 clean
RadioML2018.01A waveforms (one per class) quantized to CI16 with a SINGLE frozen
scale S, then order-shuffled so source_index (1..24) is a blind waveform ordinal
that never reveals the class on the control channel.  source_index 0 is reserved
for the negative control (TX off, no payload file).

Frozen contract (authority: contract/blind_rx_sampling_contract.json):
  * waveform[k]  = generate_class(LABEL_ORDER_24[class_index], seed)  (complex, 1024)
  * seed         = seed_base + class_index          (seed_base = 3000000)
  * ci16         = lround(waveform * S)  interleaved int16 LE  (S = 1600 / max_peak)
  * S            = 117.84922023433009    (SINGLE scale for ALL classes, NOT per-class RMS)
  * rx_scale     = adc_full_scale / S    = 17.37813789457223    (frozen RX reconstruction)
  * max_peak over the 24 production seeds = 13.576670230134553  ->  max |ci16| = 1599 (< 2048)
  * order        = default_rng(shuffle_seed=20261020).permutation(24)
  * source_index 1..24 -> class_index = order[source_index-1]   (blind ordinal)

lround is C++ std::llround semantics (round-half-AWAY-from-zero), NOT numpy.rint
(round-half-to-even).  This is a byte-exact red line: the board reconstructs
z = int16/2048 * rx_scale, so the TX CI16 and the frozen S must agree exactly.

Outputs (--out-dir must not exist; refused otherwise):
    blind_tx_manifest.tsv   source_index -> class/seed/SHA/peak (24 rows)
    <source_index>.i16      1024-complex CI16 payload (2048 int16 = 4096 bytes)
    SHA256SUMS.txt          per-file SHA sidecar
    blind_tx_summary.json   frozen constants + generation verification

Usage (Windows, radioconda python -I):
    python -I scripts/radioml_blind_clean_contract.py --out-dir <fresh dir>
    python -I scripts/radioml_blind_clean_contract.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as GEN  # noqa: E402  (frozen clean2a generator)

LABEL_ORDER_24 = GEN.LABEL_ORDER_24    # frozen 24-class label order (index 22=GMSK, 23=OQPSK)

# ---- frozen constants (authority: contract/blind_rx_sampling_contract.json) ----
TX_SCALE = 117.84922023433009           # S = 1600 / max_peak (SINGLE frozen scale)
RX_SCALE = 17.37813789457223            # = adc_full_scale / S
ADC_FULL_SCALE = 2048.0
MAX_PEAK = 13.576670230134553           # max |waveform| over the 24 production seeds
MAX_LROUND_CI16_ABS = 1599              # max |lround(waveform*S)| over the 24 seeds
                                         #   (S = 1600/max_peak => continuous peak = 1600;
                                         #    lround rounds real/imag separately => 1599)
SEED_BASE = 3000000
SHUFFLE_SEED = 20261020
N_CLASSES = 24

MANIFEST_HEADER = [
    "source_index", "class_index", "class_name", "seed", "tx_payload_file",
    "tx_payload_sha256", "original_sha256", "peak_abs", "max_lround_abs", "clip",
]

TOKEN = "M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-TX-PACKAGE"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _round_half_away(x: np.ndarray) -> np.ndarray:
    """C++ std::llround semantics: round-half-AWAY-from-zero (NOT numpy.rint)."""
    x = np.asarray(x, dtype=np.float64)
    return np.where(x >= 0.0, np.floor(x + 0.5), np.ceil(x - 0.5))


def lround(v) -> np.ndarray:
    v = np.asarray(v)
    if np.iscomplexobj(v):
        return _round_half_away(v.real) + 1j * _round_half_away(v.imag)
    return _round_half_away(v)


def quantize_ci16(iq: np.ndarray, scale: float) -> np.ndarray:
    """complex -> interleaved int16 LE [I0,Q0,...], lround + clamp (byte-exact)."""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    vals = np.clip(lround(iq * scale), -32768, 32767)
    out = np.empty(iq.size * 2, dtype="<i2")
    out[0::2] = vals.real.astype("<i2")
    out[1::2] = vals.imag.astype("<i2")
    return out


def deinterleave_int16(interleaved: np.ndarray) -> np.ndarray:
    """interleaved int16 [I0,Q0,...] -> complex128 counts."""
    iq = np.asarray(interleaved, dtype=np.int16).ravel()
    assert iq.size % 2 == 0
    n = iq.size // 2
    return iq[0::2].astype(np.float64) + 1j * iq[1::2].astype(np.float64)


def tensor_to_bytes(iq: np.ndarray) -> bytes:
    """complex[1024] -> [2,1024] f32le bytes (model-input contract, row0=real)."""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    assert iq.size == GEN.SAMPLE_LENGTH
    x = np.empty((2, GEN.SAMPLE_LENGTH), dtype="<f4")
    x[0] = iq.real.astype("<f4")
    x[1] = iq.imag.astype("<f4")
    return x.tobytes()


def blind_order() -> np.ndarray:
    """source_index 1..24 -> class_index permutation (frozen shuffle)."""
    return np.random.default_rng(SHUFFLE_SEED).permutation(N_CLASSES)


def build_all_waveforms():
    """Generate the 24 clean waveforms (class order) + CI16 + evidence.

    Returns (rows, ci16_by_class) where rows[i] is the class-index evidence dict and
    ci16_by_class[i] is the interleaved int16 payload for class_index i.
    """
    order = blind_order()
    rows = []
    ci16_by_class = {}
    for ci in range(N_CLASSES):
        name = GEN.LABEL_ORDER_24[ci]
        seed = SEED_BASE + ci
        wf = GEN.generate_class(name, seed)
        assert wf.size == GEN.SAMPLE_LENGTH
        ci16 = quantize_ci16(wf, TX_SCALE)
        counts = deinterleave_int16(ci16)
        peak_abs = float(np.abs(wf).max())
        max_lround_abs = int(np.abs(counts).max())
        assert max_lround_abs <= MAX_LROUND_CI16_ABS, \
            "max_lround_abs %d > %d for %s (constant drift)" % (
                max_lround_abs, MAX_LROUND_CI16_ABS, name)
        rows.append({
            "class_index": ci,
            "class_name": name,
            "seed": seed,
            "tx_payload_file": None,       # assigned after shuffle below
            "tx_payload_sha256": sha256_bytes(ci16.tobytes()),
            "original_sha256": sha256_bytes(tensor_to_bytes(wf)),
            "peak_abs": peak_abs,
            "max_lround_abs": max_lround_abs,
            "clip": 0,
        })
        ci16_by_class[ci] = ci16

    # Assign source_index 1..24 via the frozen permutation (blind ordinal).
    for s, ci in enumerate(order, start=1):
        rows[ci]["tx_payload_file"] = "%d.i16" % s

    # Verify the max_peak claim over the production seed set (self-consistency).
    overall_peak = max(r["peak_abs"] for r in rows)
    assert abs(overall_peak - MAX_PEAK) < 1e-9, \
        "max_peak recomputed %.17g != frozen %.17g" % (overall_peak, MAX_PEAK)
    return rows, ci16_by_class, order


def write_tx_package(out_dir: Path) -> dict:
    if out_dir.exists():
        raise SystemExit("ERROR: --out-dir already exists (refuse overwrite): %s" % out_dir)
    out_dir.mkdir(parents=True)

    rows, ci16_by_class, order = build_all_waveforms()

    manifest_rows = []
    sha_lines = []
    for ci in range(N_CLASSES):
        r = rows[ci]
        fname = r["tx_payload_file"]
        sid = int(fname.split(".")[0])
        (out_dir / fname).write_bytes(ci16_by_class[ci].tobytes())
        sha_lines.append("%s  %s" % (r["tx_payload_sha256"], fname))
        manifest_rows.append([
            sid, ci, r["class_name"], r["seed"], fname, r["tx_payload_sha256"],
            r["original_sha256"], "%.12g" % r["peak_abs"], r["max_lround_abs"],
            r["clip"],
        ])

    # Manifest ordered by source_index (1..24), not class.
    manifest_rows.sort(key=lambda row: row[0])
    with open(out_dir / "blind_tx_manifest.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(MANIFEST_HEADER) + "\n")
        for row in manifest_rows:
            f.write("\t".join(str(v) for v in row) + "\n")

    with open(out_dir / "SHA256SUMS.txt", "w", encoding="utf-8", newline="\n") as f:
        for line in sorted(sha_lines):
            f.write(line + "\n")

    summary = {
        "token": TOKEN,
        "frozen_constants": {
            "tx_scale": TX_SCALE,
            "rx_scale": RX_SCALE,
            "adc_full_scale": ADC_FULL_SCALE,
            "max_peak": MAX_PEAK,
            "max_lround_ci16_abs": MAX_LROUND_CI16_ABS,
            "seed_base": SEED_BASE,
            "shuffle_seed": SHUFFLE_SEED,
        },
        "negative_control": {
            "source_index": 0,
            "meaning": "TX off (no transmission, no payload file)",
        },
        "order_permutation": [int(o) for o in order],
        "per_class": {
            GEN.LABEL_ORDER_24[ci]: {
                "class_index": ci,
                "source_index": int(rows[ci]["tx_payload_file"].split(".")[0]),
                "seed": rows[ci]["seed"],
                "peak_abs": rows[ci]["peak_abs"],
                "max_lround_abs": rows[ci]["max_lround_abs"],
                "original_sha256": rows[ci]["original_sha256"],
                "tx_payload_sha256": rows[ci]["tx_payload_sha256"],
            } for ci in range(N_CLASSES)
        },
        "verification": {
            "no_clip": all(r["clip"] == 0 for r in rows),
            "max_lround_abs_matches_frozen":
                max(r["max_lround_abs"] for r in rows) == MAX_LROUND_CI16_ABS,
            "n_payload_files": N_CLASSES,
        },
    }
    with open(out_dir / "blind_tx_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_BLIND_CLEAN1_TX_PACKAGE classes=%d max_lround_abs=%d out_dir=%s" %
          (N_CLASSES, max(r["max_lround_abs"] for r in rows), out_dir))
    print("RADIOML_BLIND_CLEAN1_TX_PACKAGE_DONE")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.out_dir:
        ap.error("--out-dir=<fresh dir> is required (or --self-test)")
    write_tx_package(Path(args.out_dir))
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-48s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    rows, ci16_by_class, order = build_all_waveforms()
    check("24 waveforms generated", len(rows) == N_CLASSES)
    check("order is a permutation of 0..23", sorted(order.tolist()) == list(range(N_CLASSES)))
    check("max_lround_abs == 1599 (frozen)",
          max(r["max_lround_abs"] for r in rows) == MAX_LROUND_CI16_ABS)
    check("no clip (all <= 1600 < 2048)", all(r["clip"] == 0 for r in rows))

    # lround semantics: half-away-from-zero, NOT rint.
    check("lround(+0.5)==1 (half-away)", int(lround(np.array(0.5)).item()) == 1)
    check("lround(-0.5)==-1 (half-away)", int(lround(np.array(-0.5)).item()) == -1)
    check("lround(+2.5)==3 (half-away)", int(lround(np.array(2.5)).item()) == 3)

    # Byte-exact reconstruction roundtrip: z = counts/2048 * rx_scale ~= waveform.
    wf = GEN.generate_class("QPSK", SEED_BASE + 4)
    ci16 = quantize_ci16(wf, TX_SCALE)
    counts = deinterleave_int16(ci16)
    z = counts / ADC_FULL_SCALE * RX_SCALE
    err = float(np.sqrt(np.mean(np.abs(wf - z) ** 2)) / np.sqrt(np.mean(np.abs(wf) ** 2)))
    # Complex CI16 (real+imag each rounded) => RMS quantisation error ~ sqrt(1/6)/S
    # ~ 3.5e-3 for S=117.85; a sub-1% perturbation is the lossless-classification bar.
    check("quantization relative RMS error < 1e-2", err < 1e-2, "rel_rms=%.3e" % err)

    # source_index mapping is a strict 1..24 -> class bijection.
    sids = sorted(int(r["tx_payload_file"].split(".")[0]) for r in rows)
    check("source_index covers 1..24 exactly", sids == list(range(1, N_CLASSES + 1)))

    all_ok = all(checks)
    print("RADIOML_BLIND_CLEAN1_TX_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
