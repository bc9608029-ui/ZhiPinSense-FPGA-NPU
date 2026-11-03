#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_board_vs_baseline.py -- 板测结果 vs 冻结数字基线判读器（收口第 3 点）。

输入：
  --baseline  冻结 v2 数字基线 JSON（freeze_v2_baseline.py 产物，逐样本 SHA 绑定）
  --board     板端结果 TSV（11 列，见板端 runner independent_rx_result_header）
  --out-json  判读结论 JSON

板端结果 TSV 11 列（固定顺序）：
  source_index  class_index  class_name  gated  finite  board_pred
  residual  corr  coarse_cfo_hz  fine_cfo_hz  model_input_sha256

三项统计（分母恒为基线 n_sources，绝不因失败/门拒/非有限/缺失而剔除）：
  (a) real_label_accuracy    = board_pred == class_index（真实标签准确率）
  (b) board_vs_baseline_agree= board_pred == 基线 orig_pred（板端 vs 数字基线逐样本一致率）
  (c) denominator            = 恒 n_sources；gated=0（门拒）/ finite=0（hard_invalid
                               /非有限，board_pred=-1）/ 缺失行 全部保留在分母，
                               只计入错误或一致失败，不剔除。

判定口径（诚实）：
  * 板端 board_pred 与数字基线同错（board_pred==orig_pred 且都≠真值）→ 记为
    「数字与板端同错」，不自动归因 RF。
  * 板端新增翻转（board_pred≠orig_pred）→ 单独列出，不自动归因 RF（归因须单独证据）。
  * 门拒（gated=0）样本仍计：board_pred 若 finite 则照常比对，否则计错。

纯离线；只读判定；不碰板/不发射/不训练。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOKEN = "M29-RML24-FIX10CLASS24-BOARD-VS-BASELINE-JUDGER"

BOARD_HEADER = ["source_index", "class_index", "class_name", "gated", "finite",
                "board_pred", "residual", "corr", "coarse_cfo_hz", "fine_cfo_hz",
                "model_input_sha256"]


def load_baseline(path: Path):
    b = json.loads(path.read_text(encoding="utf-8"))
    rows = {s["source_index"]: s for s in b["samples"]}
    return b, rows


def load_board(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header == BOARD_HEADER, "board header mismatch: %s" % header
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sid = int(f[0])
        rows[sid] = {
            "source_index": sid, "class_index": int(f[1]), "class_name": f[2],
            "gated": int(f[3]), "finite": int(f[4]), "board_pred": int(f[5]),
            "residual": float(f[6]), "corr": float(f[7]),
            "coarse_cfo_hz": float(f[8]), "fine_cfo_hz": float(f[9]),
            "model_input_sha256": f[10],
        }
    return rows


def judge(baseline_path, board_path, out_json):
    baseline, b_rows = load_baseline(baseline_path)
    board_rows = load_board(board_path)

    n = baseline["n_sources"]
    errors, warnings = [], []
    seen = set()
    for sid in board_rows:
        if sid in seen:
            errors.append("DUPLICATE board source_index=%d" % sid)
        seen.add(sid)
        b = b_rows.get(sid)
        if b is None:
            errors.append("board source_index=%d not in baseline" % sid)
            continue
        if board_rows[sid]["class_index"] != b["class_index"]:
            errors.append("IDENTITY_MISMATCH source_index=%d board class %d != baseline %d"
                          % (sid, board_rows[sid]["class_index"], b["class_index"]))
    missing = sorted(set(b_rows) - seen)
    if missing:
        warnings.append("INCOMPLETE missing board sources=%s (denominator stays %d)"
                        % (missing, n))

    # 三项统计：分母恒 n，缺失/门拒/非有限一律保留
    per_sample = []
    n_label_correct = 0
    n_agree = 0
    n_same_wrong = 0          # board 与基线同错（都≠真值且相等）
    n_new_flips = []          # board 相对基线新增翻转
    n_gated = 0
    n_finite = 0
    for sid in range(1, n + 1):
        b = b_rows[sid]
        r = board_rows.get(sid)
        if r is None:
            per_sample.append({"source_index": sid, "present": False})
            continue
        board_pred = r["board_pred"]
        true_ci = b["class_index"]
        base_pred = b["orig_pred"]
        gated = r["gated"]
        finite = r["finite"]
        n_gated += gated
        n_finite += finite
        label_ok = (board_pred == true_ci)
        agree = (board_pred == base_pred)
        if label_ok:
            n_label_correct += 1
        if agree:
            n_agree += 1
        if (not label_ok) and agree:
            n_same_wrong += 1
        if not agree:
            n_new_flips.append({"source_index": sid, "class": b["class_name"],
                                "baseline_orig_pred": base_pred,
                                "board_pred": board_pred,
                                "gated": gated, "finite": finite})
        per_sample.append({
            "source_index": sid, "present": True, "class_name": b["class_name"],
            "class_index": true_ci, "gated": gated, "finite": finite,
            "board_pred": board_pred, "baseline_orig_pred": base_pred,
            "label_correct": 1 if label_ok else 0,
            "agrees_baseline": 1 if agree else 0,
            "residual": r["residual"], "corr": r["corr"],
            "board_model_input_sha256": r["model_input_sha256"],
            "baseline_recovered_model_input_sha256": b["recovered_model_input_sha256"],
        })

    verdict = {
        "token": TOKEN,
        "kind": "board-vs-baseline",
        "n_sources": n,
        "n_board_rows": len(board_rows),
        "n_gated": n_gated,
        "n_finite": n_finite,
        "errors": errors,
        "warnings": warnings,
        "real_label_accuracy": "%d/%d" % (n_label_correct, n),
        "board_vs_baseline_agree": "%d/%d" % (n_agree, n),
        "denominator_note": ("分母恒 %d；缺失/门拒(gated=0)/非有限(finite=0,board_pred=-1) "
                             "全部保留，不剔除。" % n),
        "same_wrong_as_baseline": n_same_wrong,
        "new_flips_vs_baseline": n_new_flips,
        "attribution": ("板端与数字基线同错 %d 处、新增翻转 %d 处。任何 RF 归因须单独证据，"
                        "本判读器不自动归因 RF。" % (n_same_wrong, len(n_new_flips))),
        "per_sample": per_sample,
    }
    if out_json:
        out_json = Path(out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        # 写原始字节（不经 Windows 换行翻译），保持输出字节稳定
        out_json.write_bytes(json.dumps(verdict, indent=2, sort_keys=True,
                                        ensure_ascii=False).encode("utf-8"))
    print("JUDGE_BOARD n=%d label_correct=%d/%d agree=%d/%d same_wrong=%d new_flips=%d "
          "errors=%d warnings=%d" %
          (n, n_label_correct, n, n_agree, n, n_same_wrong, len(n_new_flips),
           len(errors), len(warnings)))
    print("JUDGE_BOARD new_flips=%s" % n_new_flips)
    print("JUDGE_BOARD_DONE")
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", default="")
    ap.add_argument("--board", default="")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.baseline or not args.board:
        ap.error("--baseline and --board required (or --self-test)")
    judge(Path(args.baseline), Path(args.board),
          Path(args.out_json) if args.out_json else None)
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    import tempfile, json as _json
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # 合成基线（4 样本，样本 3 数字基线错）
        samples = []
        for sid, ci, nm, pred in [(1, 0, "OOK", 0), (2, 1, "4ASK", 1),
                                  (3, 2, "8ASK", 9), (4, 3, "BPSK", 3)]:
            samples.append({"source_index": sid, "class_index": ci, "class_name": nm,
                            "seed": 0, "burst_file": "", "burst_sha256": "",
                            "payload_ci16_sha256": "",
                            "manifest_model_input_sha256": "m%d" % sid,
                            "recovered_model_input_sha256": "r%d" % sid,
                            "orig_pred": pred,
                            "orig_correct": 1 if pred == ci else 0})
        base = {"token": TOKEN, "n_sources": 4, "samples": samples}
        base_path = d / "baseline.json"
        base_path.write_text(_json.dumps(base), encoding="utf-8")

        # 板端结果：4 行全 present；样本3 板端同错=9；样本4 门拒(gated=0)但 finite=1
        board_lines = ["\t".join(BOARD_HEADER)]
        # sid,ci,name,gated,finite,pred,residual,corr,cfo,fine,sha
        board_lines += ["1\t0\tOOK\t1\t1\t0\t0.01\t0.999\t1.0\t0.5\tb1"]
        board_lines += ["2\t1\t4ASK\t1\t1\t1\t0.01\t0.999\t1.0\t0.5\tb2"]
        board_lines += ["3\t2\t8ASK\t1\t1\t9\t0.01\t0.999\t1.0\t0.5\tb3"]  # 同错
        board_lines += ["4\t3\tBPSK\t0\t1\t3\t0.12\t0.980\t1.0\t0.5\tb4"]  # 门拒仍计
        board_path = d / "board.tsv"
        board_path.write_text("\n".join(board_lines) + "\n", encoding="utf-8")

        v = judge(base_path, board_path, d / "out.json")
        check("real_label_accuracy = 3/4", v["real_label_accuracy"] == "3/4",
              v["real_label_accuracy"])
        check("board_vs_baseline_agree = 4/4", v["board_vs_baseline_agree"] == "4/4",
              v["board_vs_baseline_agree"])
        check("same_wrong = 1", v["same_wrong_as_baseline"] == 1)
        check("new_flips empty", v["new_flips_vs_baseline"] == [])
        check("gated=0 kept in denominator", v["n_gated"] == 3)

        # 缺失 1 行（删样本4）→ 分母仍 4，INCOMPLETE warning，样本4缺失计错 real acc 2/4
        board_path2 = d / "board2.tsv"
        board_path2.write_text("\n".join(board_lines[:-1]) + "\n", encoding="utf-8")
        v2 = judge(base_path, board_path2, None)
        check("missing row -> INCOMPLETE, denom still 4",
              any("INCOMPLETE" in w for w in v2["warnings"])
              and v2["real_label_accuracy"] == "2/4",
              v2["real_label_accuracy"])
        # 非有限（finite=0, pred=-1）仍保留分母：改样本2
        board_lines3 = board_lines[:2] + ["2\t1\t4ASK\t1\t0\t-1\t0.01\t0.999\t1.0\t0.5\tb2"] + board_lines[3:]
        board_path3 = d / "board3.tsv"
        board_path3.write_text("\n".join(board_lines3) + "\n", encoding="utf-8")
        v3 = judge(base_path, board_path3, None)
        check("finite=0 pred=-1 kept, label_correct=2/4", v3["real_label_accuracy"] == "2/4",
              v3["real_label_accuracy"])

    all_ok = all(checks)
    print("BOARD_VS_BASELINE_JUDGER_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
