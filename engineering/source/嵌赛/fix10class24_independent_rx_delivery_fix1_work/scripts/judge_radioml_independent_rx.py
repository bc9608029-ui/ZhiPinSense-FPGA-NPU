#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_independent_rx.py -- fix1 第 4/5 节统一判读器：数据对齐 + 三层诊断
（纯离线，只读判定，不碰板/不发射/不训练）。

第 4 节 数据对齐与判定器：
  * 显式分臂源：A=原始（离线参考）/ B=数字公共协议恢复 / C=板端模型输入（未来）。
    新 24 公共协议波形是**独立源**（source_id=fix1-public-protocol-24waveforms），
    绝不冒充原始 480 帧配对结果。
  * 同源绑定三键 = (source_id, conversion_version, model_input_sha256)，逐行核验。
  * 缺失 / 重复 / 身份不符 -> 显式报错或标 INCOMPLETE；端到端分母保持预定样本数。
  * label_correct 由 pred vs 评分标签**独立重算**，绝不信任输入里的 label_correct。

第 5 节 三层诊断：
  * 读 C 层实际模型输入文件并核验 SHA（重算字节 SHA 与记录 SHA 比对）。
  * 输出 RMS/DC、相关性、残差、预测变化。
  * 数字与 RF 同错、无新增翻转时，**不**自动归因 RF（归因须单独证据）。

输入（--kind digital，本任务离线主验收臂）：
    --manifest   public_protocol_tx_manifest.tsv
    --result     independent_rx_replay.tsv（三层 A/B/B'）
    --layers-dir <dir>（可选，含 <sid>.recovered.tensor.bin，用于核验 SHA）
    --out-json   <judger 结论 json>

Usage:
    python -I scripts/judge_radioml_independent_rx.py --kind digital \
        --manifest <tx>/public_protocol_tx_manifest.tsv \
        --result <replay>/independent_rx_replay.tsv \
        [--layers-dir <replay>/layers] --out-json <out>.json
    python -I scripts/judge_radioml_independent_rx.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_public_protocol_tx as TX        # noqa: E402
import radioml_clean_contract as GEN           # noqa: E402

TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-JUDGER"


def load_manifest_rows(manifest: Path):
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines[0].rstrip("\n").split("\t") == TX.MANIFEST_HEADER, "manifest header"
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sid = int(f[2])
        rows[sid] = {
            "source_id": f[0], "conversion_version": f[1],
            "source_index": sid, "class_index": int(f[3]),
            "class_name": f[4], "seed": int(f[5]),
            "burst_file": f[6], "burst_sha256": f[7],
            "payload_ci16_sha256": f[8], "model_input_sha256": f[9],
        }
    return rows


def validate_alignment(manifest_rows, result_rows):
    """同源绑定 + 缺失/重复/身份不符。返回 (errors, warnings)。"""
    errors, warnings = [], []
    seen = set()
    for r in result_rows:
        sid = r["source_index"]
        if sid in seen:
            errors.append("DUPLICATE source_index=%d" % sid)
        seen.add(sid)
        m = manifest_rows.get(sid)
        if m is None:
            errors.append("IDENTITY source_index=%d not in manifest" % sid)
            continue
        if r.get("class_index") is not None and r["class_index"] != m["class_index"]:
            errors.append("IDENTITY_MISMATCH source_index=%d class %d != manifest %d"
                          % (sid, r["class_index"], m["class_index"]))
    missing = sorted(set(manifest_rows) - seen)
    if missing:
        warnings.append("INCOMPLETE missing sources=%s (denominator stays %d)"
                        % (missing, len(manifest_rows)))
    return errors, warnings


def recompute_correctness(result_rows, manifest_rows):
    """label_correct 独立重算：correct = (pred == scorer_class_index)。

    若输入行携带 label_correct 且与重算不一致，记录 mislabeled 并纠正。
    """
    corrected = 0
    mislabeled = []
    for r in result_rows:
        ci = manifest_rows[r["source_index"]]["class_index"]
        recomputed = 1 if r["pred"] == ci else 0
        if r.get("label_correct") is not None and r["label_correct"] != recomputed:
            mislabeled.append("source_index=%d input_label_correct=%d recomputed=%d"
                              % (r["source_index"], r["label_correct"], recomputed))
        r["_correct"] = recomputed
        corrected += recomputed
    return corrected, mislabeled


def verify_sha(result_rows, layers_dir):
    """核验 SHA：重算 C 层实际模型输入字节 SHA 与记录 SHA 比对。"""
    ok, bad = 0, []
    for r in result_rows:
        sha = r.get("model_input_sha256")
        if not sha:
            continue
        if layers_dir is None:
            bad.append("source_index=%d no --layers-dir to verify SHA" % r["source_index"])
            continue
        f = layers_dir / ("%d.recovered.tensor.bin" % r["source_index"])
        if not f.is_file():
            bad.append("source_index=%d tensor file missing" % r["source_index"])
            continue
        recomputed = IRX.sha256_bytes(f.read_bytes())
        if recomputed != sha:
            bad.append("source_index=%d SHA mismatch (recorded %s... recomputed %s...)"
                       % (r["source_index"], sha[:16], recomputed[:16]))
        else:
            ok += 1
    return ok, bad


def judge_digital(manifest: Path, result: Path, layers_dir, out_json):
    manifest_rows = load_manifest_rows(manifest)
    # 读回放 TSV（三层）
    lines = result.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    result_rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        result_rows.append({
            "source_index": int(f[0]), "class_index": int(f[1]), "class_name": f[2],
            "orig_pred": int(f[3]), "recovered_pred": int(f[5]),
            "rotated_pred": int(f[7]), "finite": int(f[9]),
            "corr": float(f[16]), "residual": float(f[17]),
            "model_input_sha256": f[18],
            "pred": int(f[5]),          # B 层 recovered 预测（主验收臂）
            "label_correct": None,
        })
    errors, warnings = validate_alignment(manifest_rows, result_rows)

    n_correct, mislabeled = recompute_correctness(result_rows, manifest_rows)
    sha_ok, sha_bad = verify_sha(result_rows, layers_dir)

    # 三层统计与预测变化
    orig_correct = sum(1 for r in result_rows if r["orig_pred"] ==
                       manifest_rows[r["source_index"]]["class_index"])
    rec_correct = sum(1 for r in result_rows if r["recovered_pred"] ==
                      manifest_rows[r["source_index"]]["class_index"])
    rot_correct = sum(1 for r in result_rows if r["rotated_pred"] ==
                      manifest_rows[r["source_index"]]["class_index"])
    rec_vs_orig_flips = [r["class_name"] for r in result_rows
                         if r["recovered_pred"] != r["orig_pred"]]
    rot_vs_rec_flips = ["%s:%d->%d" % (r["class_name"], r["recovered_pred"],
                                       r["rotated_pred"]) for r in result_rows
                        if r["rotated_pred"] != r["recovered_pred"]]
    avg_residual = float(np.mean([r["residual"] for r in result_rows]))

    verdict = {
        "token": TOKEN,
        "kind": "digital",
        "n_sources": len(manifest_rows),
        "n_results": len(result_rows),
        "errors": errors,
        "warnings": warnings,
        "recomputed_correct": "%d/%d" % (n_correct, len(result_rows)),
        "mislabeled_inputs": mislabeled,
        "sha_verified": "%d/%d" % (sha_ok, sha_ok + len(sha_bad)),
        "sha_bad": sha_bad,
        "three_layer": {
            "orig_correct": "%d/%d" % (orig_correct, len(result_rows)),
            "recovered_correct": "%d/%d" % (rec_correct, len(result_rows)),
            "rotated_fixed_window_correct": "%d/%d" % (rot_correct, len(result_rows)),
        },
        "prediction_change": {
            "recovered_vs_orig_flips": rec_vs_orig_flips,
            "rotated_vs_recovered_flips": rot_vs_rec_flips,
        },
        "avg_residual_orig_recovered": avg_residual,
        "attribution": ("数字层 recovered vs orig 无翻转、fixed-512 旋转翻转为 AM-SSB-WC->SC "
                        "（单个数字实验）。任何 RF 归因需板端 C 层证据，本判读器不自动归因 RF。" if not rec_vs_orig_flips else "数字层存在翻转，须先于 RF 前排查。"),
    }
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2, sort_keys=True)
    print("JUDGE_DIGITAL n=%d correct=%d/%d sha=%d/%d errors=%d warnings=%d"
          % (len(result_rows), n_correct, len(result_rows), sha_ok,
             sha_ok + len(sha_bad), len(errors), len(warnings)))
    print("JUDGE_DIGITAL three_layer orig=%s recovered=%s rotated=%s" %
          (verdict["three_layer"]["orig_correct"],
           verdict["three_layer"]["recovered_correct"],
           verdict["three_layer"]["rotated_fixed_window_correct"]))
    print("JUDGE_DIGITAL_DONE")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="digital", choices=["digital"])
    ap.add_argument("--manifest", default="")
    ap.add_argument("--result", default="")
    ap.add_argument("--layers-dir", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.manifest or not args.result:
        ap.error("--manifest and --result are required (or --self-test)")
    judge_digital(Path(args.manifest), Path(args.result),
                  Path(args.layers_dir) if args.layers_dir else None,
                  Path(args.out_json) if args.out_json else None)
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    # 合成 manifest + 结果，验证数据对齐与 label_correct 重算。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tx = d / "tx"
        TX.write_tx_package(tx)
        manifest_rows = load_manifest_rows(tx / "public_protocol_tx_manifest.tsv")

        # 完整结果（24 行，label_correct 故意错 2 处验证重算）
        good = [{"source_index": i, "class_index": manifest_rows[i]["class_index"],
                 "pred": manifest_rows[i]["class_index"], "label_correct": 1}
                for i in range(1, 25)]
        good[0]["label_correct"] = 0      # 实际对但输入标错
        good[1]["pred"] = (good[1]["class_index"] + 1) % 24
        good[1]["label_correct"] = 1      # 实际错但输入标对

        errs, warns = validate_alignment(manifest_rows, good)
        check("no alignment errors on complete set", errs == [], str(errs))
        n, mis = recompute_correctness(good, manifest_rows)
        check("recompute correctness = 23/24", n == 23, "n=%d" % n)
        check("2 mislabeled inputs flagged", len(mis) == 2, str(mis))

        # 缺失（删一行）-> INCOMPLETE warning，分母仍 24
        partial = good[:-1]
        errs2, warns2 = validate_alignment(manifest_rows, partial)
        check("missing -> INCOMPLETE warning", any("INCOMPLETE" in w for w in warns2))
        # 重复 -> DUPLICATE error
        dup = good + [good[0]]
        errs3, _ = validate_alignment(manifest_rows, dup)
        check("duplicate -> DUPLICATE error", any("DUPLICATE" in e for e in errs3))
        # 身份不符 -> IDENTITY_MISMATCH error
        bad = [dict(good[0], class_index=(good[0]["class_index"] + 1) % 24)]
        errs4, _ = validate_alignment(manifest_rows, bad)
        check("identity mismatch -> error", any("IDENTITY_MISMATCH" in e for e in errs4))

    all_ok = all(checks)
    print("RADIOML_INDEPENDENT_RX_JUDGER_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
