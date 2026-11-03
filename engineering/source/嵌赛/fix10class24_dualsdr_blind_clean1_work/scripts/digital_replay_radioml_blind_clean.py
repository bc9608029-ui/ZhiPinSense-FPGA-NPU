#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digital_replay_radioml_blind_clean.py -- Phase B: digital no-RF blind replay
(THREE-LAYER reference: original -> digital-preprocessed -> (board, real RF)).

Verifies the blind sampling contract BEFORE any board run, in the digital domain,
running the SAME frozen BF16 model (icraft Host) over the SAME 24 waveforms at
three progressively-degraded layers:

  A  orig     = generate_class(name, seed)  -> [2,1024] f32   (original model input;
                OFFLINE reference ONLY -- it never enters the RX inference path)
  B  exact    = CI16 quantize -> reconstruct z = counts/2048*rx_scale -> [2,1024] f32
                (the "final unified-preprocessed DIGITAL input"; quantization roundtrip)
  B' rotated  = cyclic rotation of z by kBlindWindowOffset (512) -- the frozen window
                rule the board applies to a 2048-sample capture of a cyclic TX, at
                capture phase 0.  Isolates quantization loss vs fixed-window rotation,
                with NO RF impairment.

Per-layer statistics (coordinator point 2): accuracy, prediction flips, input RMS/DC,
aligned correlation + normalized residual (A<->B quantization loss).  The original
reference IQ is regenerated here for OFFLINE analysis only -- it is forbidden from the
RX inference path (blind red line, already covered by the board runner).

Full retention (coordinator point 3): per-source_index the three model inputs
(layers/<sid>.{orig,exact,rotated}.tensor.bin) and the three logits rows
(layers/<sid>.logits.tsv) are written; failed/non-finite samples are NOT dropped.

Honest boundary (no forgery):
  * This is the DIGITAL domain only.  The real-RF chain adds analog IQ imbalance,
    CFO, channel gain and an arbitrary capture phase; those are NOT reproduced here.
    The board's actual model input is a rotated + RF-impaired version of B.
  * The model is run with the SAME icraft Host BF16 backend as the npu-ab1 host
    reference; the board NPU is a separate engine (not claimed equivalent here).

Outputs (--out-dir must not exist):
    digital_replay.tsv         per-source_index three-layer predictions + stats
    digital_replay_summary.json
    layers/<sid>.<layer>.tensor.bin   ([2,1024] f32 model inputs)
    layers/<sid>.logits.tsv           (orig/exact/rotated 24-logit rows)

Usage:
    python -I scripts/digital_replay_radioml_blind_clean.py \
        --tx-dir <blind tx package> --out-dir <fresh dir> \
        [--icraft-run D:/icraft/bin/icraft-run.exe] \
        [--model-dir <model_rml24_bf16 dir>]
    python -I scripts/digital_replay_radioml_blind_clean.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_blind_clean_contract as BC  # noqa: E402
import radioml_clean_contract as GEN       # noqa: E402  (frozen clean2a generator)

NETWORK_NAME = "model_24class"
TOKEN = "M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-DIGITAL-REPLAY"

DEFAULT_ICRAFT_RUN = r"D:\icraft\bin\icraft-run.exe"
DEFAULT_MODEL_DIR = (
    r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
    r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16")

REPLAY_HEADER = [
    "source_index", "class_index", "class_name",
    "orig_pred", "orig_correct",
    "exact_pred", "exact_correct",
    "rotated_pred", "rotated_correct",
    "finite",
    "orig_rms", "orig_dc_real", "orig_dc_imag",
    "exact_rms", "exact_dc_real", "exact_dc_imag",
    "rotated_rms", "rotated_dc_real", "rotated_dc_imag",
    "corr_orig_exact", "resid_orig_exact",
    "model_input_sha256",
]


def load_tx_package(tx_dir: Path):
    """Read blind_tx_manifest.tsv -> list of rows ordered by source_index (1..24)."""
    manifest = tx_dir / "blind_tx_manifest.tsv"
    if not manifest.is_file():
        raise SystemExit("blind_tx_manifest.tsv not found in %s" % tx_dir)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    if header != BC.MANIFEST_HEADER:
        raise SystemExit("manifest header mismatch")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        rows.append({
            "source_index": int(f[0]),
            "class_index": int(f[1]),
            "class_name": f[2],
            "seed": int(f[3]),
            "tx_payload_file": f[4],
            "tx_payload_sha256": f[5],
            "original_sha256": f[6],
        })
    rows.sort(key=lambda r: r["source_index"])
    assert [r["source_index"] for r in rows] == list(range(1, 25))
    return rows


def reconstruct_from_i16(payload_bytes: bytes) -> np.ndarray:
    """deinterleave int16 -> counts -> z = counts/2048 * rx_scale  (complex, 1024)."""
    inter = np.frombuffer(payload_bytes, dtype="<i2")
    assert inter.size == 2 * 1024, "expected 1024-complex (2048 int16) payload"
    counts = inter[0::2].astype(np.float64) + 1j * inter[1::2].astype(np.float64)
    return counts / BC.ADC_FULL_SCALE * BC.RX_SCALE


def rotated_blind_window(z: np.ndarray, offset: int = 512) -> np.ndarray:
    """The frozen blind window: cyclic rotation by `offset` (capture phase 0)."""
    return np.roll(z, offset)


def tensor_stats(z: np.ndarray):
    """RMS and DC (real/imag) of a complex waveform (per-layer input statistics)."""
    z = np.asarray(z, dtype=np.complex128).ravel()
    rms = float(np.sqrt(np.mean(np.abs(z) ** 2)))
    dc_re = float(np.mean(z.real))
    dc_im = float(np.mean(z.imag))
    return rms, dc_re, dc_im


def aligned_corr_residual(a: np.ndarray, b: np.ndarray):
    """Normalized correlation magnitude + normalized residual (same-index, aligned).

    corr  = |a^H b| / (||a|| ||b||)  in [0,1]  (1.0 = identical up to a complex gain)
    resid = ||b - a|| / ||a||          (0.0 = identical; quantization loss here)
    """
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    na = float(np.sqrt(np.sum(np.abs(a) ** 2)))
    nb = float(np.sqrt(np.sum(np.abs(b) ** 2)))
    corr = float(np.abs(np.vdot(a, b))) / (na * nb) if (na > 0 and nb > 0) else 0.0
    resid = float(np.sqrt(np.sum(np.abs(b - a) ** 2))) / na if na > 0 else 0.0
    return corr, resid


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   tensor_bytes: bytes, workdir: Path) -> np.ndarray:
    inp = workdir / "input.bin"
    inp.write_bytes(tensor_bytes)
    log_path = workdir / "logs"
    cmd = [str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
           "--network", NETWORK_NAME, "--input", str(inp),
           "--backends", "Host", "--dump_output", "--log_path", str(log_path)]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("icraft-run exit %d: %s"
                         % (proc.returncode,
                            proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        raise SystemExit("expected exactly 1 ftmp, got %d" % len(ftmps))
    raw = ftmps[0].read_bytes()
    if len(raw) != 24 * 4:
        raise SystemExit("ftmp %s is %d bytes (want 96)" % (ftmps[0].name, len(raw)))
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tx-dir", default="")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--icraft-run", default=DEFAULT_ICRAFT_RUN)
    ap.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.tx_dir or not args.out_dir:
        ap.error("--tx-dir and --out-dir are required (or --self-test)")

    tx_dir = Path(args.tx_dir)
    out_dir = Path(args.out_dir)
    if out_dir.exists():
        raise SystemExit("ERROR: --out-dir already exists: %s" % out_dir)
    out_dir.mkdir(parents=True)
    layers_dir = out_dir / "layers"
    layers_dir.mkdir()

    icraft_run = Path(args.icraft_run)
    model_dir = Path(args.model_dir)
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not icraft_run.is_file():
        raise SystemExit("icraft-run not found: %s" % icraft_run)
    if not model_json.is_file() or not model_raw.is_file():
        raise SystemExit("model json/raw not found under %s" % model_dir)

    rows = load_tx_package(tx_dir)
    out_rows = []
    for r in rows:
        p = tx_dir / r["tx_payload_file"]
        payload = p.read_bytes()
        assert BC.sha256_bytes(payload) == r["tx_payload_sha256"], \
            "payload SHA mismatch for %s" % r["tx_payload_file"]

        # ---- three layers ----
        wf = GEN.generate_class(r["class_name"], r["seed"])           # A: original
        assert wf.size == GEN.SAMPLE_LENGTH
        # Verify the regenerated original is byte-exact vs the frozen manifest SHA
        # (proves the OFFLINE reference matches what the PC TX was built from).
        assert BC.sha256_bytes(BC.tensor_to_bytes(wf)) == r["original_sha256"], \
            "original_sha256 mismatch for %s" % r["tx_payload_file"]

        z = reconstruct_from_i16(payload)                              # B: exact
        z_rot = rotated_blind_window(z)                                # B': rotated

        layer_inputs = {"orig": wf, "exact": z, "rotated": z_rot}
        results = {}
        logit_rows = {}
        for label, zi in layer_inputs.items():
            tb = BC.tensor_to_bytes(zi)
            (layers_dir / ("%d.%s.tensor.bin" % (r["source_index"], label))) \
                .write_bytes(tb)
            with tempfile.TemporaryDirectory(prefix="blindreplay_") as td:
                logits = run_host_infer(icraft_run, model_json, model_raw, tb, Path(td))
            finite = bool(np.all(np.isfinite(logits)))
            pred = int(np.argmax(logits)) if finite else -1
            results[label] = {"pred": pred, "finite": finite, "logits": logits}
            logit_rows[label] = logits

        # per-layer input statistics
        o_rms, o_dc_re, o_dc_im = tensor_stats(wf)
        e_rms, e_dc_re, e_dc_im = tensor_stats(z)
        rt_rms, rt_dc_re, rt_dc_im = tensor_stats(z_rot)

        # aligned correlation + normalized residual (A <-> B quantization loss)
        corr_oe, resid_oe = aligned_corr_residual(wf, z)

        # retain the three logits rows
        with open(layers_dir / ("%d.logits.tsv" % r["source_index"]), "w",
                  encoding="utf-8", newline="\n") as lf:
            lf.write("layer\t" + "\t".join("logit_%02d" % c for c in range(24)) +
                     "\tpred\n")
            for label in ("orig", "exact", "rotated"):
                lg = logit_rows[label]
                lf.write(label + "\t" + "\t".join("%.9g" % v for v in lg) +
                         "\t%d\n" % results[label]["pred"])

        finite = (results["orig"]["finite"] and results["exact"]["finite"] and
                  results["rotated"]["finite"])
        out_rows.append({
            "source_index": r["source_index"],
            "class_index": r["class_index"],
            "class_name": r["class_name"],
            "orig_pred": results["orig"]["pred"],
            "orig_correct": 1 if results["orig"]["pred"] == r["class_index"] else 0,
            "exact_pred": results["exact"]["pred"],
            "exact_correct": 1 if results["exact"]["pred"] == r["class_index"] else 0,
            "rotated_pred": results["rotated"]["pred"],
            "rotated_correct": 1 if results["rotated"]["pred"] == r["class_index"] else 0,
            "finite": 1 if finite else 0,
            "orig_rms": o_rms, "orig_dc_real": o_dc_re, "orig_dc_imag": o_dc_im,
            "exact_rms": e_rms, "exact_dc_real": e_dc_re, "exact_dc_imag": e_dc_im,
            "rotated_rms": rt_rms, "rotated_dc_real": rt_dc_re, "rotated_dc_imag": rt_dc_im,
            "corr_orig_exact": corr_oe, "resid_orig_exact": resid_oe,
            "model_input_sha256": BC.sha256_bytes(BC.tensor_to_bytes(z)),
        })

    with open(out_dir / "digital_replay.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(REPLAY_HEADER) + "\n")
        for r in out_rows:
            f.write("\t".join([
                str(r["source_index"]), str(r["class_index"]), r["class_name"],
                str(r["orig_pred"]), str(r["orig_correct"]),
                str(r["exact_pred"]), str(r["exact_correct"]),
                str(r["rotated_pred"]), str(r["rotated_correct"]),
                str(r["finite"]),
                "%.9g" % r["orig_rms"], "%.9g" % r["orig_dc_real"],
                "%.9g" % r["orig_dc_imag"],
                "%.9g" % r["exact_rms"], "%.9g" % r["exact_dc_real"],
                "%.9g" % r["exact_dc_imag"],
                "%.9g" % r["rotated_rms"], "%.9g" % r["rotated_dc_real"],
                "%.9g" % r["rotated_dc_imag"],
                "%.9g" % r["corr_orig_exact"], "%.9g" % r["resid_orig_exact"],
                r["model_input_sha256"],
            ]) + "\n")

    orig_correct = sum(r["orig_correct"] for r in out_rows)
    exact_correct = sum(r["exact_correct"] for r in out_rows)
    rot_correct = sum(r["rotated_correct"] for r in out_rows)
    summary = {
        "token": TOKEN,
        "backend": "icraft-host-bf16",
        "three_layer": {
            "orig_correct": "%d/%d" % (orig_correct, len(out_rows)),
            "exact_correct": "%d/%d" % (exact_correct, len(out_rows)),
            "rotated_blind_window_correct": "%d/%d" % (rot_correct, len(out_rows)),
        },
        "flips": {
            "orig_to_exact": sum(1 for r in out_rows
                                 if r["orig_pred"] != r["exact_pred"]),
            "exact_to_rotated": sum(1 for r in out_rows
                                    if r["exact_pred"] != r["rotated_pred"]),
        },
        "window_offset": 512,
        "note": ("digital no-RF three-layer: orig=clean reference (offline only), "
                 "exact=quantization roundtrip, rotated=frozen-window (capture phase 0). "
                 "Real RF adds analog IQ imbalance/CFO/gain/arbitrary phase, NOT "
                 "reproduced here."),
    }
    with open(out_dir / "digital_replay_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_BLIND_CLEAN1_DIGITAL_REPLAY orig=%d/%d exact=%d/%d rotated=%d/%d "
          "out_dir=%s" %
          (orig_correct, len(out_rows), exact_correct, len(out_rows),
           rot_correct, len(out_rows), out_dir))
    print("RADIOML_BLIND_CLEAN1_DIGITAL_REPLAY_DONE")
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-48s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # reconstruction roundtrip on a known waveform (no icraft-run needed)
    wf = GEN.generate_class("QPSK", BC.SEED_BASE + 4)
    ci16 = BC.quantize_ci16(wf, BC.TX_SCALE)
    z = reconstruct_from_i16(ci16.tobytes())
    rel = float(np.sqrt(np.mean(np.abs(wf - z) ** 2)) /
                np.sqrt(np.mean(np.abs(wf) ** 2)))
    check("reconstruct rel RMS < 1e-2", rel < 1e-2, "rel=%.3e" % rel)

    z_rot = rotated_blind_window(z)
    check("rotation preserves RMS", abs(np.sqrt(np.mean(np.abs(z_rot) ** 2)) -
          np.sqrt(np.mean(np.abs(z) ** 2))) < 1e-9)
    check("rotation is 512-shift", np.allclose(z_rot, np.concatenate([z[512:], z[:512]])))

    # per-layer stats + aligned correlation/residual
    rms, dc_re, dc_im = tensor_stats(wf)
    check("orig RMS ~ TARGET_RMS(=1.0)", abs(rms - 1.0) < 1e-2, "rms=%.4f" % rms)
    corr, resid = aligned_corr_residual(wf, z)
    check("A<->B correlation ~ 1.0", corr > 0.9999, "corr=%.6f" % corr)
    check("A<->B normalized residual < 1e-2", resid < 1e-2, "resid=%.3e" % resid)

    # manifest parse (temp package)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tx = d / "tx"
        BC.write_tx_package(tx)
        rows = load_tx_package(tx)
        check("load_tx_package: 24 rows", len(rows) == 24
              and rows[0]["source_index"] == 1)
        # regenerated original must be byte-exact vs the manifest original_sha256
        r0 = rows[0]
        wf0 = GEN.generate_class(r0["class_name"], r0["seed"])
        check("regenerated original matches manifest SHA",
              BC.sha256_bytes(BC.tensor_to_bytes(wf0)) == r0["original_sha256"])

    all_ok = all(checks)
    print("RADIOML_BLIND_CLEAN1_DIGITAL_REPLAY_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
