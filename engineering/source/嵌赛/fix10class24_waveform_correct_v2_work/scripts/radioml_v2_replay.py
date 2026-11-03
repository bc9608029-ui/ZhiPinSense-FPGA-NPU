#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_v2_replay.py -- 波形正确性 v2 数字回放：orig / recovered / rotated 三层
（icraft host BF16，纯离线，不碰板/不发射/不训练）。

A  orig      = generate_waveform_v2(ci)                   （v2 原始，直接送模型）
B  recovered = 公共协议恢复 -> recover_model_input_v2      （1/S_v2 归一化）
B' rotated   = np.roll(B, 512)                            （blind-clean1 固定窗口反例）

诚实红线：不反向改波形凑 24/24。若 orig 在冻结 BF16 下误分类，如实记录为
「模型与新波形域不匹配」，不掩盖、不归因 RF。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_v2_contract as V2                 # noqa: E402
import radioml_independent_rx_contract as V1     # noqa: E402
import radioml_clean_contract as GEN             # noqa: E402

NETWORK_NAME = "model_24class"
TOKEN = "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2-REPLAY"

DEFAULT_ICRAFT_RUN = r"D:\icraft\bin\icraft-run.exe"
DEFAULT_MODEL_DIR = (
    r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
    r"\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16")

REPLAY_HEADER = [
    "source_index", "class_index", "class_name",
    "orig_pred", "orig_correct", "recovered_pred", "recovered_correct",
    "rotated_pred", "rotated_correct", "finite",
    "orig_rms", "orig_dc_real", "orig_dc_imag",
    "recovered_rms", "recovered_dc_real", "recovered_dc_imag",
    "corr_orig_recovered", "resid_orig_recovered", "model_input_sha256",
]


def load_manifest(tx_dir: Path):
    m = tx_dir / "public_protocol_tx_manifest.tsv"
    lines = m.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header == ["source_id", "conversion_version", "source_index",
                      "class_index", "class_name", "seed", "burst_file",
                      "burst_sha256", "payload_ci16_sha256", "model_input_sha256"], \
        "manifest header mismatch"
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        rows.append({
            "source_id": f[0], "conversion_version": f[1],
            "source_index": int(f[2]), "class_index": int(f[3]),
            "class_name": f[4], "seed": int(f[5]),
            "burst_file": f[6], "burst_sha256": f[7],
            "payload_ci16_sha256": f[8], "model_input_sha256": f[9],
        })
    rows.sort(key=lambda r: r["source_index"])
    return rows


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
                         % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-2000:]))
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

    rows = load_manifest(tx_dir)
    out_rows = []
    for r in rows:
        burst_bytes = (tx_dir / r["burst_file"]).read_bytes()
        assert V1.sha256_bytes(burst_bytes) == r["burst_sha256"], \
            "burst SHA mismatch for %s" % r["burst_file"]

        wf = V2.generate_waveform_v2(r["class_index"])                # A
        assert V1.sha256_bytes(V1.tensor_to_bytes(wf)) == r["model_input_sha256"], \
            "model_input_sha256 mismatch for %s" % r["burst_file"]

        zb = V2.recover_from_burst_v2(burst_bytes)                    # B
        zr = np.roll(zb, 512)                                         # B'

        layer_inputs = {"orig": wf, "recovered": zb, "rotated": zr}
        results, logit_rows = {}, {}
        for label, zi in layer_inputs.items():
            tb = V1.tensor_to_bytes(zi)
            (layers_dir / ("%d.%s.tensor.bin" % (r["source_index"], label))).write_bytes(tb)
            with tempfile.TemporaryDirectory(prefix="v2replay_") as td:
                logits = run_host_infer(icraft_run, model_json, model_raw, tb, Path(td))
            finite = bool(np.all(np.isfinite(logits)))
            results[label] = {"pred": int(np.argmax(logits)) if finite else -1,
                              "finite": finite, "logits": logits}
            logit_rows[label] = logits

        o = V1.three_layer_stats(wf, wf)
        bst = V1.three_layer_stats(wf, zb)

        with open(layers_dir / ("%d.logits.tsv" % r["source_index"]), "w",
                  encoding="utf-8", newline="\n") as lf:
            lf.write("layer\t" + "\t".join("logit_%02d" % c for c in range(24)) + "\tpred\n")
            for label in ("orig", "recovered", "rotated"):
                lg = logit_rows[label]
                lf.write(label + "\t" + "\t".join("%.9g" % v for v in lg) +
                         "\t%d\n" % results[label]["pred"])

        finite = all(results[l]["finite"] for l in ("orig", "recovered", "rotated"))
        out_rows.append({
            "source_index": r["source_index"],
            "class_index": r["class_index"],
            "class_name": r["class_name"],
            "orig_pred": results["orig"]["pred"],
            "orig_correct": 1 if results["orig"]["pred"] == r["class_index"] else 0,
            "recovered_pred": results["recovered"]["pred"],
            "recovered_correct": 1 if results["recovered"]["pred"] == r["class_index"] else 0,
            "rotated_pred": results["rotated"]["pred"],
            "rotated_correct": 1 if results["rotated"]["pred"] == r["class_index"] else 0,
            "finite": 1 if finite else 0,
            "orig_rms": o["rms"], "orig_dc_real": o["dc_real"], "orig_dc_imag": o["dc_imag"],
            "recovered_rms": bst["rms"], "recovered_dc_real": bst["dc_real"],
            "recovered_dc_imag": bst["dc_imag"],
            "corr_orig_recovered": bst["corr"], "resid_orig_recovered": bst["residual"],
            "model_input_sha256": V1.sha256_bytes(V1.tensor_to_bytes(zb)),
        })

    with open(out_dir / "independent_rx_replay.tsv", "w", encoding="utf-8",
              newline="\n") as f:
        f.write("\t".join(REPLAY_HEADER) + "\n")
        for r in out_rows:
            f.write("\t".join([
                str(r["source_index"]), str(r["class_index"]), r["class_name"],
                str(r["orig_pred"]), str(r["orig_correct"]),
                str(r["recovered_pred"]), str(r["recovered_correct"]),
                str(r["rotated_pred"]), str(r["rotated_correct"]),
                str(r["finite"]),
                "%.9g" % r["orig_rms"], "%.9g" % r["orig_dc_real"], "%.9g" % r["orig_dc_imag"],
                "%.9g" % r["recovered_rms"], "%.9g" % r["recovered_dc_real"],
                "%.9g" % r["recovered_dc_imag"],
                "%.9g" % r["corr_orig_recovered"], "%.9g" % r["resid_orig_recovered"],
                r["model_input_sha256"],
            ]) + "\n")

    orig_ok = sum(r["orig_correct"] for r in out_rows)
    rec_ok = sum(r["recovered_correct"] for r in out_rows)
    rot_ok = sum(r["rotated_correct"] for r in out_rows)
    orig_wrong = [(r["class_name"], r["orig_pred"]) for r in out_rows
                  if r["orig_correct"] == 0]
    rec_flips = [(r["class_name"], r["orig_pred"], r["recovered_pred"])
                 for r in out_rows if r["recovered_pred"] != r["orig_pred"]]
    rot_flips = ["%s:%s->%s" % (r["class_name"], r["recovered_pred"], r["rotated_pred"])
                 for r in out_rows if r["rotated_pred"] != r["recovered_pred"]]

    domain_mismatch = (len(orig_wrong) > 0)
    summary = {
        "token": TOKEN,
        "backend": "icraft-host-bf16",
        "three_layer": {
            "orig_correct": "%d/%d" % (orig_ok, len(out_rows)),
            "recovered_correct": "%d/%d" % (rec_ok, len(out_rows)),
            "rotated_fixed_window_correct": "%d/%d" % (rot_ok, len(out_rows)),
        },
        "orig_misclassified": [{"class": c, "pred": p} for c, p in orig_wrong],
        "model_vs_new_waveform_domain_mismatch": domain_mismatch,
        "honest_note": ("orig 是 v2 修正波形的数字直送（无 RF/无恢复误差）。若 orig "
                        "误分类，如实记录为『模型与新波形域不匹配』，不掩盖、不归因 RF，"
                        "也不反向改波形凑 24/24。" if domain_mismatch else
                        "orig 24/24 全对：修正波形在冻结 BF16 下仍被模型识别。"),
        "counterexample": {
            "public_protocol_recovered_flips": rec_flips,
            "fixed_512_rotation_flips": rot_flips,
        },
        "window": "first 1024 of recovered payload (public-reference located)",
    }
    with open(out_dir / "independent_rx_replay_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_V2_REPLAY orig=%d/%d recovered=%d/%d rotated=%d/%d "
          "domain_mismatch=%s out_dir=%s" %
          (orig_ok, len(out_rows), rec_ok, len(out_rows), rot_ok, len(out_rows),
           domain_mismatch, out_dir))
    print("RADIOML_V2_REPLAY_DONE")
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))
    wf = V2.generate_waveform_v2(4)
    burst = V2.build_public_protocol_burst_v2(wf)
    zb = V2.recover_from_burst_v2(burst.tobytes())
    rel = float(np.sqrt(np.mean(np.abs(wf - zb) ** 2)) / np.sqrt(np.mean(np.abs(wf) ** 2)))
    check("v2 public-protocol recovery rel RMS < 1e-2", rel < 1e-2, "rel=%.3e" % rel)
    zr = np.roll(zb, 512)
    check("fixed window is 512-shift", np.allclose(zr, np.concatenate([zb[512:], zb[:512]])))
    max_rel = 0.0
    for ci in range(V2.N_CLASSES):
        b = V2.build_public_protocol_burst_v2(V2.generate_waveform_v2(ci))
        zi = V2.recover_from_burst_v2(b.tobytes())
        max_rel = max(max_rel, float(np.sqrt(np.mean(np.abs(V2.generate_waveform_v2(ci) - zi) ** 2)) /
                                     np.sqrt(np.mean(np.abs(V2.generate_waveform_v2(ci)) ** 2))))
    check("v2 24/24 recovery rel RMS < 1e-2", max_rel < 1e-2, "max_rel=%.3e" % max_rel)
    tb = V1.tensor_to_bytes(zb)
    check("v2 model input SHA byte-derived", V1.sha256_bytes(tb) ==
          V1.sha256_bytes(V1.tensor_to_bytes(zb)))
    all_ok = all(checks)
    print("RADIOML_V2_REPLAY_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
