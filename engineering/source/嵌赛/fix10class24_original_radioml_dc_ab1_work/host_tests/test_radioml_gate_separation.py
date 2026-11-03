#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_radioml_gate_separation.py -- 主机测试 (fix10class24-classification-gate-separation1,
Part B 诊断旁路 + 统一判定器)。

g++ 在本 Windows 主机不可用, 板端 C++ 在 aarch64 编译; 故本测试为 Python-only, 覆盖
Part B 的最小主机不变量 (纯离线只读, 不碰板/不发射/不训练):

  1. 契约 JSON 存在 + token + classification_layer 枚举 + 六项统计键。
  2. 契约 MD 存在 + 显式旁路条件 + 生产门不变红线。
  3. 诊断头 (radioml_diagnostic_classify.hpp) 源码审计: 7 条件 + 三枚举 +
     try_diagnostic_apply 唯一放宽 rec.valid + 生产门不重写。
  4. 单/双 runner 源码审计: --diagnostic-force-classify 默认 OFF + 12 列诊断 TSV +
     .diag.json classification_layer + 六计数器。
  5. 判定器加载函数 (production/diagnostic/blind) + 指标计算 (合成数据)。
  6. 判定器端到端: 合成 480 帧 + 三 TSV + runner summary → judge_summary.json 断言
     (生产 gated=240/480 全对、诊断 120 旁路 80 对、盲 480 全对、合并 320/360)。
  7. 六项统计 reconciliation: runner summary.json 的 refused/apply_failed 被判定器读入。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import radioml_dualsdr_common as C  # noqa: E402
import judge_radioml_gate_separation as J  # noqa: E402

CONTRACT_MD = ROOT / "contract" / "classification_gate_separation_contract.md"
CONTRACT_JSON = ROOT / "contract" / "classification_gate_separation_contract.json"
DIAG_HPP = ROOT / "board_package" / "radioml_diagnostic_classify.hpp"
SINGLE_RUNNER = ROOT / "board_package" / "radioml_singlesdr_ab_runner.hpp"
DUAL_RUNNER = ROOT / "board_package" / "radioml_dualsdr_ab_runner.hpp"

TESTS = []
def test(fn):
    TESTS.append(fn)
    return fn


def run_py(args):
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / args[0])] + args[1:],
                          capture_output=True, text=True)


# ---------------------------------------------------------------------------
# 合成数据 (手算可验证)
#   480 帧: sid 1..480, raw24_class = (sid-1)%24
#   生产: gated iff sid 偶数 (240), 全对; 奇数 gate-rejected (240), 其中
#         hard_invalid iff sid%4==1 (120), forceable iff sid%4==3 (120)。
#   诊断: 120 forceable 行, board_pred_diag 错 iff sid%12==3 (40 错 / 80 对)。
#   盲:   480 行全 finite 全对, residual="NA"。
# ---------------------------------------------------------------------------
def make_manifest(dirp):
    header = ("selection_id\thdf5_row_index\traw24_class\tmodulation\t"
              "snr_db\tinput_file\tinput_sha256\thost_pred")
    rows = []
    for i in range(480):
        sid = i + 1
        c = i % 24
        snr = [0, 10, 20, 30][i % 4]
        sha = hashlib.sha256(("frame-%d" % sid).encode()).hexdigest()
        rows.append("%d\t%d\t%d\t%s\t%d\t%d.bin\t%s\t%d" %
                    (sid, i, c, C.LABEL_ORDER_24[c], snr, sid, sha, c))
    (dirp / "manifest.tsv").write_text(header + "\n" + "\n".join(rows) + "\n",
                                       encoding="utf-8")


def make_production(dirp, fname):
    hdr = "\t".join(J.BOARD_COLS)
    rows = []
    for i in range(480):
        sid = i + 1
        c = i % 24
        if sid % 2 == 0:  # gated, correct
            rows.append("%d\t%d\t%d\t30\t1\t%d\t1\t0.05\t0.999\t0\t0\t0\t0\t0\t1\t0\t0\t1\t1"
                        % (sid, i, c, c))
        elif sid % 4 == 1:  # hard_invalid (residual 0.50 > 0.30 ceiling)
            rows.append("%d\t%d\t%d\t30\t0\t-1\t0\t0.50\t0.800\t0\t0\t0\t0\t0\t1\t1\t1\t1\t1"
                        % (sid, i, c))
        else:  # forceable gate-reject (residual 0.15)
            rows.append("%d\t%d\t%d\t30\t0\t-1\t0\t0.15\t0.900\t0\t0\t0\t0\t0\t1\t1\t0\t1\t1"
                        % (sid, i, c))
    (dirp / fname).write_text(hdr + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def make_diagnostic(dirp, fname):
    hdr = "\t".join(J.DIAG_COLS)
    rows = []
    for i in range(480):
        sid = i + 1
        if sid % 4 != 3:
            continue  # only forceable frames
        c = i % 24
        wrong = (sid % 12 == 3)
        pred = (c + 1) % 24 if wrong else c
        correct = 0 if wrong else 1
        rows.append("%d\t%d\t%d\t30\t0.15\t0.900\t%d\t1\t1\tNPU_BF16_DIAGNOSTIC\t1\t%d"
                    % (sid, i, c, pred, correct))
    (dirp / fname).write_text(hdr + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def make_blind(dirp, fname):
    hdr = "\t".join(J.BOARD_COLS)
    rows = []
    for i in range(480):
        sid = i + 1
        c = i % 24
        rows.append("%d\t%d\t%d\t30\t1\t%d\t1\tNA\tNA\tNA\tNA\tNA\tNA\t0\t1\t0\t0\t1\t1"
                    % (sid, i, c, c))
    (dirp / fname).write_text(hdr + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def make_runner_summary(dirp, fname):
    s = {
        "diagnostic_bypass_total": 120,
        "diagnostic_bypass_classified": 120,
        "diagnostic_bypass_correct": 80,
        "diagnostic_bypass_accuracy": 80.0 / 120.0,
        "diagnostic_bypass_repeat_deterministic": 120,
        "diagnostic_bypass_refused": 120,
        "diagnostic_bypass_apply_failed": 0,
    }
    (dirp / fname).write_text(json.dumps(s), encoding="utf-8")


# ---------------------------------------------------------------------------
@test
def t01_contract_json_token_and_enum():
    assert CONTRACT_JSON.is_file()
    j = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    assert j["token"] == "M29-RML24-FIX10CLASS24-CLASSIFICATION-GATE-SEPARATION1-READY-FOR-BOARD-TEST"
    cl = j["classification_layer"]
    assert cl["NPU_BF16_PRODUCTION"] and cl["NPU_BF16_DIAGNOSTIC"] and cl["NOT_APPLICABLE"]
    ss = j["six_statistics"]
    for k in ["diagnostic_bypass_total", "diagnostic_bypass_classified",
              "diagnostic_bypass_correct", "diagnostic_bypass_accuracy",
              "diagnostic_bypass_repeat_deterministic", "diagnostic_bypass_refused"]:
        assert k in ss, "missing six-statistic %s" % k
    assert "diagnostic_bypass_apply_failed" in j["defensive_counter"]
    assert len(j["bypass_conditions"]) == 7
    assert j["diagnostic_flag"]["default"] is False


@test
def t02_contract_md_bypass_and_red_lines():
    md = CONTRACT_MD.read_text(encoding="utf-8")
    assert "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH" in md
    assert "0.100" in md and "0.30" in md
    assert "--diagnostic-force-classify" in md
    assert "NPU_BF16_DIAGNOSTIC" in md
    assert "board_diagnostic_results.tsv" in md
    assert "19" in md  # 19 列生产契约不变
    for cond in ["cfo_in_range", "rx_clipped", "neg_pass", "sro_ppm"]:
        assert cond in md
    assert "hard_invalid" in md


@test
def t03_diag_header_source_audit():
    src = DIAG_HPP.read_text(encoding="utf-8")
    assert "kClassificationLayerProduction" in src
    assert "kClassificationLayerDiagnostic" in src
    assert "kClassificationLayerNotApplicable" in src
    assert "is_diagnostic_bypassable" in src
    assert "try_diagnostic_apply" in src
    assert "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH" in src
    # 7 条件逐一
    for tok in ["kPayloadTrainingResidualMax", "hard_invalid_ceiling", "cfo_in_range",
                "rx_clipped", "neg_pass", "max_sro_ppm", "sro_ppm"]:
        assert tok in src
    # 唯一放宽 = 本地副本 rec.valid; apply() 逐字复用
    assert "rec_diag.valid = true" in src
    assert "iqrfrec::apply(aligned, rec_diag)" in src
    assert "apply_fractional_advance" in src
    assert "return false" in src  # fail-closed on throw


@test
def t04_runners_flag_tsv_schema_and_counters():
    for path in (SINGLE_RUNNER, DUAL_RUNNER):
        src = path.read_text(encoding="utf-8")
        assert '#include "radioml_diagnostic_classify.hpp"' in src
        assert '--diagnostic-force-classify' in src
        assert "board_diagnostic_results.tsv" in src
        assert "diagnostic_bypass_total" in src
        assert "diagnostic_bypass_classified" in src
        assert "diagnostic_bypass_correct" in src
        assert "diagnostic_bypass_repeat_det" in src
        assert "diagnostic_bypass_refused" in src
        assert "diagnostic_bypass_apply_failed" in src
        # 12 列诊断表头 (关键列)
        assert "board_pred_diag" in src
        assert "finite_diag" in src
        assert "repeat_deterministic" in src
        assert "classification_layer" in src
        assert "diagnostic_gate_bypass" in src
        assert "label_correct" in src
        # .diag.json classification_layer 三值
        assert "kClassificationLayerDiagnostic" in src
        assert "kClassificationLayerProduction" in src
        assert "kClassificationLayerNotApplicable" in src
        # 生产门不重写: 诊断只在 else(gate-reject) 分支
        assert "is_diagnostic_bypassable" in src
        assert "try_diagnostic_apply" in src


@test
def t05_judger_loaders_and_metrics():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        make_production(d, "board.tsv")
        make_diagnostic(d, "diag.tsv")
        make_blind(d, "blind.tsv")
        prod = J.load_production(str(d / "board.tsv"))
        diag = J.load_diagnostic(str(d / "diag.tsv"))
        blind = J.load_blind(str(d / "blind.tsv"))
        assert prod is not None and len(prod) == 480
        assert diag is not None and len(diag) == 120
        assert blind is not None and len(blind) == 480
        # 盲 residual = NA 被识别
        assert J._is_blind_na(blind[1]["residual"])
        # 生产 gated=1 只出现在偶数 sid
        assert int(prod[2]["gated"]) == 1 and int(prod[1]["gated"]) == 0
        # 诊断行 classification_layer 恒为 DIAGNOSTIC 且 bypass=1
        assert all(r["classification_layer"] == "NPU_BF16_DIAGNOSTIC" for r in diag.values())
        assert all(r["diagnostic_gate_bypass"] == "1" for r in diag.values())


@test
def t06_judger_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        make_manifest(d)
        make_production(d, "board_single_direct.tsv")
        make_diagnostic(d, "diag_single_direct.tsv")
        make_blind(d, "blind_single_direct.tsv")
        make_runner_summary(d, "summary_single_direct.json")
        out = d / "judge"
        r = run_py(["judge_radioml_gate_separation.py",
                    "--input-package", str(d), "--out-dir", str(out),
                    "--board-single-direct", str(d / "board_single_direct.tsv"),
                    "--diag-single-direct", str(d / "diag_single_direct.tsv"),
                    "--blind-single-direct", str(d / "blind_single_direct.tsv"),
                    "--runner-summary-single-direct", str(d / "summary_single_direct.json")])
        assert r.returncode == 0, r.stderr
        assert "RADIOML_GATE_SEPARATION_JUDGE_DONE" in r.stdout

        s = json.loads((out / "judge_summary.json").read_text(encoding="utf-8"))
        a = s["arms"]["single_direct"]

        prod = a["production"]
        assert prod["present"] == 480
        assert prod["gated"] == 240
        assert prod["gated_accuracy"] == 1.0
        assert abs(prod["end_to_end_gate_reject_is_fail"] - 0.5) < 1e-9
        assert prod["gate_reject_forceable_count"] == 120
        assert prod["hard_invalid_count"] == 120

        diag = a["diagnostic"]
        assert diag["present"] == 120
        assert diag["classified"] == 120
        assert diag["correct"] == 80
        assert abs(diag["accuracy"] - (80.0 / 120.0)) < 1e-9
        assert diag["repeat_deterministic"] == 120
        assert diag["non_finite"] == 0

        blind = a["blind"]
        assert blind["present"] == 480
        assert blind["classified"] == 480
        assert blind["correct"] == 480
        assert blind["accuracy"] == 1.0
        assert blind["residual_is_na_count"] == 480

        comb = a["combined"]
        assert comb["gated_or_diagnostic_covered"] == 360
        assert comb["gated_or_diagnostic_correct"] == 320
        assert abs(comb["accuracy"] - (320.0 / 360.0)) < 1e-9
        assert comb["diagnostic_recovered"] == 80

        # 其余三臂缺输入 = PENDING (不 auto-success)
        for key in ("single_dc", "dual_direct", "dual_dc"):
            am = s["arms"][key]
            assert am["pending"]["production"] is True
            assert am["pending"]["diagnostic"] is True
            assert am["pending"]["blind"] is True
            assert am["production"]["present"] == 0


@test
def t07_six_statistics_reconciled():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        make_manifest(d)
        make_production(d, "board_single_direct.tsv")
        make_diagnostic(d, "diag_single_direct.tsv")
        make_runner_summary(d, "summary_single_direct.json")
        out = d / "judge"
        r = run_py(["judge_radioml_gate_separation.py",
                    "--input-package", str(d), "--out-dir", str(out),
                    "--board-single-direct", str(d / "board_single_direct.tsv"),
                    "--diag-single-direct", str(d / "diag_single_direct.tsv"),
                    "--runner-summary-single-direct", str(d / "summary_single_direct.json")])
        assert r.returncode == 0, r.stderr
        s = json.loads((out / "judge_summary.json").read_text(encoding="utf-8"))
        six = s["arms"]["single_direct"]["six_statistics"]
        assert six["diagnostic_bypass_total"] == 120
        assert six["diagnostic_bypass_classified"] == 120
        assert six["diagnostic_bypass_correct"] == 80
        assert abs(six["diagnostic_bypass_accuracy"] - (80.0 / 120.0)) < 1e-9
        assert six["diagnostic_bypass_repeat_deterministic"] == 120
        assert six["diagnostic_bypass_refused"] == 120
        assert six["diagnostic_bypass_apply_failed"] == 0


def main():
    passed = 0
    for t in TESTS:
        try:
            t()
            print("PASS %s" % t.__name__)
            passed += 1
        except Exception as e:  # noqa: BLE001
            import traceback
            print("FAIL %s: %s" % (t.__name__, e))
            traceback.print_exc()
    print("RADIOML_GATE_SEPARATION_SELFTEST %d/%d passed" % (passed, len(TESTS)))
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
