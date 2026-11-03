#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_regression.py -- fix1 第 6 节回归套件：保留旧测 + 新增反例回归。

跑全部 5 个离线模块自检（34 项）+ 反例回归核验（读取 replay 产物，不重跑 icraft）。

  旧测保留（5 模块自检）：
    radioml_independent_rx_contract --self-test   (10)
    radioml_waveform_correctness    --self-test   ( 7)
    radioml_public_protocol_tx      --self-test   ( 7)
    radioml_independent_rx_replay   --self-test   ( 4)
    judge_radioml_independent_rx    --self-test   ( 6)
    合计 34 项。

  新增反例回归（读 --replay-dir 产物，不重跑 icraft）：
    反例 1：公共协议恢复无固定旋转 -> recovered == orig（应 24/24 无翻转）。
    反例 2：固定 512 旋转 -> 复现 blind-clean1 的 AM-SSB-WC->SC 单翻转（23/24）。

Usage:
    python -I host_tests/run_regression.py [--replay-dir <replay_out>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable  # 须为 D:/Anaconda/python.exe；外部调用已用 -I

MODULES = [
    "radioml_independent_rx_contract",
    "radioml_waveform_correctness",
    "radioml_public_protocol_tx",
    "radioml_independent_rx_replay",
    "judge_radioml_independent_rx",
]


def run_self_tests():
    results = {}
    for m in MODULES:
        p = subprocess.run([PY, "-I", str(SCRIPTS / (m + ".py")), "--self-test"],
                           capture_output=True, text=True)
        tail = (p.stdout or "").strip().splitlines()
        last = tail[-1] if tail else ""
        results[m] = (p.returncode == 0, last)
    return results


def check_counterexample(replay_dir: Path):
    """读取 replay 产物核验反例（不重跑 icraft）。"""
    tsv = replay_dir / "independent_rx_replay.tsv"
    if not tsv.is_file():
        return False, "replay tsv missing (run radioml_independent_rx_replay first)"
    rows = []
    for ln in tsv.read_text(encoding="utf-8").splitlines()[1:]:
        if ln.strip():
            rows.append(ln.rstrip("\n").split("\t"))
    n = len(rows)
    # 列：0 sid, 1 class_index, 2 name, 3 orig_pred, 4 orig_correct,
    #      5 recovered_pred, 6 recovered_correct, 7 rotated_pred, 8 rotated_correct
    rec_flips = [r[2] for r in rows if r[5] != r[3]]
    rot_flips = ["%s:%s->%s" % (r[2], r[5], r[7]) for r in rows if r[7] != r[5]]
    ok = (len(rec_flips) == 0) and (len(rot_flips) == 1) and \
         (rot_flips[0].startswith("AM-SSB-WC:") if rot_flips else False)
    return ok, {"n": n, "rec_flips": rec_flips, "rot_flips": rot_flips}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay-dir", default=str(ROOT / "replay_out"))
    args = ap.parse_args()

    self_tests = run_self_tests()
    total = 0
    passed = 0
    print("== 保留旧测（5 模块自检）==")
    for m, (ok, last) in self_tests.items():
        total += 1
        passed += 1 if ok else 0
        print("  %-40s %s  %s" % (m, "PASS" if ok else "FAIL", last))
    print("  模块自检 %d/%d" % (passed, total))

    ce_ok, ce_detail = check_counterexample(Path(args.replay_dir))
    print("== 新增反例回归 ==")
    if ce_ok:
        print("  PASS  recovered==orig 无翻转; fixed-512 旋转 = 单个 AM-SSB-WC->SC 翻转")
    else:
        print("  FAIL  %s" % ce_detail)

    all_ok = (passed == total) and ce_ok
    print("REGRESSION_SUITE %s (self_test %d/%d, counterexample %s)" %
          ("PASS" if all_ok else "FAIL", passed, total,
           "PASS" if ce_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
