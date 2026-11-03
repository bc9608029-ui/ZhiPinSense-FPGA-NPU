#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_independent_rx_replay.py -- fix1 主验收臂数字回放：公共协议三层诊断 + 反例
（纯离线，icraft Host BF16，不碰板/不发射/不训练）。

对 24 个公共协议波形跑三层（第 5 节），并把 blind-clean1 的「固定窗口」降级为
单个数字反例：

  A  orig      = generate_class(name, seed)                （离线对齐参考，不进接收推理）
  B  recovered = 公共参考估计 -> 恢复载荷[:1024]*(1/S)      （数字域主验收臂）
  B' rotated   = np.roll(B, 512)                           （blind-clean1 固定窗口反例）

关键反例回归（第 6 节）：
  * B（公共协议恢复，无固定旋转）应 24/24 无翻转 —— 修复了 blind-clean1 的
    固定窗口 [512,1536) 旋转导致的 AM-SSB-WC→SC 翻转。
  * B'（固定 512 旋转）复现 blind-clean1 的 23/24（AM-SSB-WC→SC 翻转），证明
    「任意固定旋转只代表一个数字实验，不代表真实捕获的未知相位」。

每源输出三层模型输入与 logits（全量留存），并核验 SHA：
  * model_input_sha256 由 B 层模型输入 [2,1024] f32 逐字节计算，落盘 + 与喂给
    icraft 的字节一致（第 5 节「读实际模型输入并核验 SHA」在数字域的等价物）。

Usage:
    python -I scripts/radioml_independent_rx_replay.py \
        --tx-dir <public-protocol tx dir> --out-dir <fresh dir> \
        [--icraft-run D:/icraft/bin/icraft-run.exe] [--model-dir <model dir>]
    python -I scripts/radioml_independent_rx_replay.py --self-test
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
import radioml_independent_rx_contract as IRX      # noqa: E402
import radioml_public_protocol_tx as TX            # noqa: E402
import radioml_clean_contract as GEN               # noqa: E402

NETWORK_NAME = "model_24class"
TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-REPLAY"

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
    "corr_orig_recovered", "resid_orig_recovered",
    "model_input_sha256",
]


def load_manifest(tx_dir: Path):
    m = tx_dir / "public_protocol_tx_manifest.tsv"
    lines = m.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header == TX.MANIFEST_HEADER, "manifest header mismatch"
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


def recover_from_burst(burst_bytes: bytes) -> np.ndarray:
    """burst 字节 -> 公共参考恢复 -> 模型输入（complex1024）。"""
    inter = np.frombuffer(burst_bytes, dtype="<i2")
    assert inter.size == 2 * IRX.K_TOTAL_BURST_COMPLEX
    rx = IRX.C.deinterleave_int16(inter)
    est = IRX.estimate_public_reference(rx)
    return IRX.recover_model_input(rx, est)


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
        assert IRX.sha256_bytes(burst_bytes) == r["burst_sha256"], \
            "burst SHA mismatch for %s" % r["burst_file"]

        wf = IRX.generate_waveform(r["class_index"])                    # A
        assert IRX.sha256_bytes(IRX.tensor_to_bytes(wf)) == r["model_input_sha256"], \
            "model_input_sha256 mismatch for %s" % r["burst_file"]

        zb = recover_from_burst(burst_bytes)                            # B
        zr = np.roll(zb, 512)                                           # B' fixed window

        layer_inputs = {"orig": wf, "recovered": zb, "rotated": zr}
        results = {}
        logit_rows = {}
        for label, zi in layer_inputs.items():
            tb = IRX.tensor_to_bytes(zi)
            (layers_dir / ("%d.%s.tensor.bin" % (r["source_index"], label))) \
                .write_bytes(tb)
            with tempfile.TemporaryDirectory(prefix="indeprx_") as td:
                logits = run_host_infer(icraft_run, model_json, model_raw, tb, Path(td))
            finite = bool(np.all(np.isfinite(logits)))
            pred = int(np.argmax(logits)) if finite else -1
            results[label] = {"pred": pred, "finite": finite, "logits": logits}
            logit_rows[label] = logits

        o = IRX.three_layer_stats(wf, wf)
        bst = IRX.three_layer_stats(wf, zb)

        with open(layers_dir / ("%d.logits.tsv" % r["source_index"]), "w",
                  encoding="utf-8", newline="\n") as lf:
            lf.write("layer\t" + "\t".join("logit_%02d" % c for c in range(24)) +
                     "\tpred\n")
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
            "model_input_sha256": IRX.sha256_bytes(IRX.tensor_to_bytes(zb)),
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
                "%.9g" % r["orig_rms"], "%.9g" % r["orig_dc_real"],
                "%.9g" % r["orig_dc_imag"],
                "%.9g" % r["recovered_rms"], "%.9g" % r["recovered_dc_real"],
                "%.9g" % r["recovered_dc_imag"],
                "%.9g" % r["corr_orig_recovered"], "%.9g" % r["resid_orig_recovered"],
                r["model_input_sha256"],
            ]) + "\n")

    orig_ok = sum(r["orig_correct"] for r in out_rows)
    rec_ok = sum(r["recovered_correct"] for r in out_rows)
    rot_ok = sum(r["rotated_correct"] for r in out_rows)
    flips = [r for r in out_rows if r["recovered_pred"] != r["orig_pred"]]
    rot_flips = [r for r in out_rows if r["rotated_pred"] != r["recovered_pred"]]
    summary = {
        "token": TOKEN,
        "backend": "icraft-host-bf16",
        "three_layer": {
            "orig_correct": "%d/%d" % (orig_ok, len(out_rows)),
            "recovered_correct": "%d/%d" % (rec_ok, len(out_rows)),
            "rotated_fixed_window_correct": "%d/%d" % (rot_ok, len(out_rows)),
        },
        "counterexample": {
            "public_protocol_no_flip": [r["class_name"] for r in flips],
            "fixed_512_rotation_flips": [
                "%s:%d->%d" % (r["class_name"], r["recovered_pred"],
                               r["rotated_pred"]) for r in rot_flips],
            "note": ("public-protocol recovery (no fixed rotation) must be 24/24; "
                     "the fixed-512 rotation reproduces blind-clean1's single "
                     "AM-SSB-WC->SC digital flip, proving a fixed rotation is one "
                     "digital experiment, not a real unknown-phase capture."),
        },
        "window": "first 1024 of recovered payload (public-reference located)",
        "fixed_window_offset_for_counterexample": 512,
    }
    with open(out_dir / "independent_rx_replay_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_INDEPENDENT_RX_REPLAY orig=%d/%d recovered=%d/%d rotated=%d/%d "
          "out_dir=%s" %
          (orig_ok, len(out_rows), rec_ok, len(out_rows), rot_ok, len(out_rows), out_dir))
    print("RADIOML_INDEPENDENT_RX_REPLAY_DONE")
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # 不跑 icraft：验证公共协议恢复与固定窗口旋转机制。
    wf = IRX.generate_waveform(4)                     # QPSK
    burst = IRX.build_public_protocol_burst(wf)
    zb = recover_from_burst(burst.tobytes())
    rel = float(np.sqrt(np.mean(np.abs(wf - zb) ** 2)) /
                np.sqrt(np.mean(np.abs(wf) ** 2)))
    check("public-protocol recovery rel RMS < 1e-2", rel < 1e-2, "rel=%.3e" % rel)

    zr = np.roll(zb, 512)
    check("fixed window is 512-shift", np.allclose(zr, np.concatenate([zb[512:], zb[:512]])))
    # 全 24 类恢复均 < 1e-2
    max_rel = 0.0
    for ci in range(IRX.N_CLASSES):
        b = IRX.build_public_protocol_burst(IRX.generate_waveform(ci))
        zi = recover_from_burst(b.tobytes())
        max_rel = max(max_rel, float(np.sqrt(np.mean(np.abs(IRX.generate_waveform(ci) - zi) ** 2)) /
                                     np.sqrt(np.mean(np.abs(IRX.generate_waveform(ci)) ** 2))))
    check("24/24 recovery rel RMS < 1e-2", max_rel < 1e-2, "max_rel=%.3e" % max_rel)
    # SHA 落盘自洽
    tb = IRX.tensor_to_bytes(zb)
    check("model input SHA is byte-derived", IRX.sha256_bytes(tb) ==
          IRX.sha256_bytes(IRX.tensor_to_bytes(zb)))

    all_ok = all(checks)
    print("RADIOML_INDEPENDENT_RX_REPLAY_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
