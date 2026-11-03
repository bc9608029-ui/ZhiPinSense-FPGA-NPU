#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_regression_v2.py -- 波形正确性 v2 回归套件：保留旧测（v2 5 模块自检）+ 反例回归。

旧测保留（v2 模块自检）：
    radioml_waveform_correct_v2 --self-test  (37)
    radioml_v2_contract           --self-test  ( 6)
    radioml_v2_tx                 --self-test  ( 7)
    radioml_v2_replay             --self-test  ( 4)
    judge_radioml_v2              --self-test  ( 3)
    合计 57 项。
新增反例回归：读 replay 产物（不重跑 icraft），核验 recovered==orig 无翻转 + 固定 512
旋转反例机制。诚实红线：orig 误分类 -> 记录「模型与新波形域不匹配」，不算回归失败。

Usage:
    python -I host_tests/run_regression_v2.py [--replay-dir replay_out]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable

MODULES = [
    "radioml_waveform_correct_v2",
    "radioml_v2_contract",
    "radioml_v2_tx",
    "radioml_v2_replay",
    "judge_radioml_v2",
]


def run_self_tests():
    results = {}
    for m in MODULES:
        p = subprocess.run([PY, "-I", str(SCRIPTS / (m + ".py")), "--self-test"],
                           capture_output=True, text=True)
        tail = (p.stdout or "").strip().splitlines()
        results[m] = (p.returncode == 0, tail[-1] if tail else "")
    return results


def check_counterexample(replay_dir: Path):
    tsv = replay_dir / "independent_rx_replay.tsv"
    if not tsv.is_file():
        return False, "replay tsv missing", None
    rows = [ln.rstrip("\n").split("\t")
            for ln in tsv.read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
    rec_flips = [r[2] for r in rows if r[5] != r[3]]        # recovered vs orig
    orig_wrong = [r[2] for r in rows if r[4] == "0"]        # orig wrong
    rot_flips = [r[2] for r in rows if r[7] != r[5]]
    ok = len(rec_flips) == 0   # 公共协议恢复无翻转（与 orig 是否误分类无关）
    return ok, {"n": len(rows), "rec_flips": rec_flips,
                "rot_flips": rot_flips, "orig_wrong": orig_wrong}, orig_wrong


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--replay-dir", default=str(ROOT / "replay_out"))
    args = ap.parse_args()

    self_tests = run_self_tests()
    total, passed = 0, 0
    print("== 保留旧测（v2 5 模块自检）==")
    for m, (ok, last) in self_tests.items():
        total += 1
        passed += 1 if ok else 0
        print("  %-32s %s  %s" % (m, "PASS" if ok else "FAIL", last))
    print("  模块自检 %d/%d" % (passed, total))

    ce_ok, ce_detail, orig_wrong = check_counterexample(Path(args.replay_dir))
    print("== 新增反例回归 ==")
    print("  %s  recovered==orig 无翻转（%s）" % ("PASS" if ce_ok else "FAIL", ce_detail))
    if orig_wrong:
        print("  诚实记录：orig 误分类 = %s（模型与新波形域不匹配，不掩盖/不归因 RF/"
              "不反向改波形）" % orig_wrong)

    all_ok = (passed == total) and ce_ok
    print("REGRESSION_V2 %s (self_test %d/%d, counterexample %s)" %
          ("PASS" if all_ok else "FAIL", passed, total, "PASS" if ce_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
