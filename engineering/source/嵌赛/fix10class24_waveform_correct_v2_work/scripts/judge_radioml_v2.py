#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_v2.py -- 波形正确性 v2 判读器：数据对齐 + 三层诊断 + SHA 核验。
结构与 fix1 判读器一致，只换 v2 manifest / result。纯离线，只读判定。

重点：若 orig（v2 修正波形数字直送）误分类，如实记录「模型与新波形域不匹配」，
不掩盖、不归因 RF、不反向改波形。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_v2_contract as V2                 # noqa: E402
import radioml_independent_rx_contract as V1     # noqa: E402

TOKEN = "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2-JUDGER"


def load_manifest_rows(manifest: Path):
    lines = manifest.read_text(encoding="utf-8").splitlines()
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sid = int(f[2])
        rows[sid] = {"source_id": f[0], "conversion_version": f[1],
                     "source_index": sid, "class_index": int(f[3]),
                     "class_name": f[4], "seed": int(f[5]),
                     "burst_file": f[6], "burst_sha256": f[7],
                     "payload_ci16_sha256": f[8], "model_input_sha256": f[9]}
    return rows


def validate_alignment(manifest_rows, result_rows):
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
        if r["class_index"] != m["class_index"]:
            errors.append("IDENTITY_MISMATCH source_index=%d" % sid)
    missing = sorted(set(manifest_rows) - seen)
    if missing:
        warnings.append("INCOMPLETE missing=%s (denominator stays %d)"
                        % (missing, len(manifest_rows)))
    return errors, warnings


def verify_sha(result_rows, layers_dir):
    ok, bad = 0, []
    for r in result_rows:
        sha = r["model_input_sha256"]
        if layers_dir is None:
            bad.append("source_index=%d no --layers-dir" % r["source_index"])
            continue
        f = layers_dir / ("%d.recovered.tensor.bin" % r["source_index"])
        if not f.is_file():
            bad.append("source_index=%d tensor missing" % r["source_index"])
            continue
        recomputed = V1.sha256_bytes(f.read_bytes())
        if recomputed != sha:
            bad.append("source_index=%d SHA mismatch" % r["source_index"])
        else:
            ok += 1
    return ok, bad


def judge(manifest: Path, result: Path, layers_dir, out_json):
    manifest_rows = load_manifest_rows(manifest)
    lines = result.read_text(encoding="utf-8").splitlines()
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
        })
    errors, warnings = validate_alignment(manifest_rows, result_rows)
    sha_ok, sha_bad = verify_sha(result_rows, layers_dir)

    def ci(r):
        return manifest_rows[r["source_index"]]["class_index"]
    orig_correct = sum(1 for r in result_rows if r["orig_pred"] == ci(r))
    rec_correct = sum(1 for r in result_rows if r["recovered_pred"] == ci(r))
    rot_correct = sum(1 for r in result_rows if r["rotated_pred"] == ci(r))
    # label_correct 独立重算（orig 层）
    rec_mis = [r["class_name"] for r in result_rows if r["orig_pred"] != ci(r)]
    orig_mis = [{"class": r["class_name"], "pred": r["orig_pred"]} for r in result_rows
                if r["orig_pred"] != ci(r)]

    verdict = {
        "token": TOKEN, "kind": "digital",
        "n_sources": len(manifest_rows), "n_results": len(result_rows),
        "errors": errors, "warnings": warnings,
        "recomputed_label_correct": "%d/%d" % (orig_correct, len(result_rows)),
        "orig_misclassified": orig_mis,
        "model_vs_new_waveform_domain_mismatch": len(orig_mis) > 0,
        "sha_verified": "%d/%d" % (sha_ok, sha_ok + len(sha_bad)),
        "sha_bad": sha_bad,
        "three_layer": {
            "orig_correct": "%d/%d" % (orig_correct, len(result_rows)),
            "recovered_correct": "%d/%d" % (rec_correct, len(result_rows)),
            "rotated_fixed_window_correct": "%d/%d" % (rot_correct, len(result_rows)),
        },
        "honest_note": ("orig 是 v2 修正波形数字直送。若误分类，如实记录为『模型与新波形域"
                        "不匹配』，不掩盖、不归因 RF、不反向改波形。" if len(orig_mis) > 0
                        else "orig 24/24 全对：修正波形在冻结 BF16 下被模型识别。"),
    }
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2, sort_keys=True)
    print("JUDGE_V2 n=%d orig_correct=%d/%d recovered=%d/%d rotated=%d/%d "
          "sha=%d/%d errors=%d domain_mismatch=%s" %
          (len(result_rows), orig_correct, len(result_rows), rec_correct,
           len(result_rows), rot_correct, len(result_rows), sha_ok,
           sha_ok + len(sha_bad), len(errors), len(orig_mis) > 0))
    print("JUDGE_V2 orig_misclassified=%s" % orig_mis)
    print("JUDGE_V2_DONE")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="")
    ap.add_argument("--result", default="")
    ap.add_argument("--layers-dir", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.manifest or not args.result:
        ap.error("--manifest and --result required (or --self-test)")
    judge(Path(args.manifest), Path(args.result),
          Path(args.layers_dir) if args.layers_dir else None,
          Path(args.out_json) if args.out_json else None)
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))
    # 合成 manifest + 结果验证对齐逻辑。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tx = d / "tx"
        from radioml_v2_tx import write_tx_package
        write_tx_package(tx)
        mr = load_manifest_rows(tx / "public_protocol_tx_manifest.tsv")
        good = [{"source_index": i, "class_index": mr[i]["class_index"]}
                for i in range(1, 25)]
        e, w = validate_alignment(mr, good)
        check("no errors on complete set", e == [])
        dup = good + [good[0]]
        e3, _ = validate_alignment(mr, dup)
        check("duplicate -> error", any("DUPLICATE" in x for x in e3))
        bad = [dict(good[0], class_index=(good[0]["class_index"] + 1) % 24)]
        e4, _ = validate_alignment(mr, bad)
        check("identity mismatch -> error", any("IDENTITY_MISMATCH" in x for x in e4))
    all_ok = all(checks)
    print("JUDGE_RADIOML_V2_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
