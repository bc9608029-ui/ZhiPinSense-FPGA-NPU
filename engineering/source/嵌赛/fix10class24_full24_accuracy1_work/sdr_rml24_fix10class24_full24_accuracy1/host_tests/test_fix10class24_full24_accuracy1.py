#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host tests for the offline logic of the full24-accuracy1 audit script
(scripts/audit_fix10class24_full24_accuracy1.py).

Covers, offline (no board, no icraft-run):
  - compute_metrics 三套指标 + A/B/C 决策（含 scalar/wide-linear 主决策固定、blocked 优先）。
  - 24×24 混淆对角。
  - parse_board_results / parse_manifest fail-closed（源集错/表头错）。
  - phase_inventory fail-closed（gated 却有多余 dump / rejected 缺 dump / 缺文件 /
    raw_rx SHA 不符 / JSON 缺字段）。

纯 check()/main() 约定，供 run_tests.sh 直接 `python3 ./<this>.py`（WSL python3 有 numpy）。
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "..", "scripts")
sys.path.insert(0, _SCRIPTS)

import audit_fix10class24_full24_accuracy1 as audit  # noqa: E402

g_pass = 0
g_fail = 0


def check(ok, what):
    global g_pass, g_fail
    if ok:
        g_pass += 1
    else:
        g_fail += 1
        print("  FAIL: %s" % what)


def assert_fail_closed(fn, substr):
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            fn()
        check(False, "expected fail-closed, but call succeeded: %s" % substr)
    except SystemExit as e:
        check(int(e.code) == 1, "fail-closed exit code 1 for %s" % substr)
        check(substr in err.getvalue(), "fail-closed message contains %r (got %r)"
              % (substr, err.getvalue()[:200]))


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# 合成逐样本 dict（compute_metrics 纯逻辑）
# ---------------------------------------------------------------------------
def _gated(sc, pred, correct, valid=1):
    return {
        "source_index": sc * 500, "source_class": sc, "modulation": "M%d" % sc,
        "result_layer": audit.BOARD_LAYER, "gated": 1, "rf_verdict": audit.GATE_VERDICT,
        "board_raw24_pred": pred, "baseline_pred": -1, "board_label_correct": correct,
        "end_to_end_correct": 1 if correct == 1 else 0,
        "scalar_raw24_pred": pred, "scalar_label_correct": 1 if pred == sc else 0,
        "wl_applicable": 0, "wl_raw24_pred": pred,
        "wl_label_correct": 1 if pred == sc else 0,
        "forced_raw24_pred": pred, "forced_label_correct": 1 if pred == sc else 0,
        "logit_finite": valid, "blocked_reason": None,
    }


def _rejected(sc, scalar_pred, wl_pred, wl_applicable=1, blocked=None):
    sc_ok = 1 if scalar_pred == sc else 0
    wl_ok = 1 if wl_pred == sc else 0
    forced_pred = wl_pred if wl_applicable else scalar_pred
    forced_ok = wl_ok if wl_applicable else sc_ok
    return {
        "source_index": sc * 500, "source_class": sc, "modulation": "M%d" % sc,
        "result_layer": audit.HOST_LAYER, "gated": 0, "rf_verdict": "RF_DISTORTS_IQ",
        "board_raw24_pred": -1, "baseline_pred": -1, "board_label_correct": -1,
        "end_to_end_correct": 0,
        "scalar_raw24_pred": scalar_pred, "scalar_label_correct": sc_ok,
        "wl_applicable": wl_applicable, "wl_raw24_pred": wl_pred,
        "wl_label_correct": wl_ok,
        "forced_raw24_pred": forced_pred, "forced_label_correct": forced_ok,
        "logit_finite": 1, "blocked_reason": blocked,
    }


# ---------------------------------------------------------------------------
# compute_metrics + 决策
# ---------------------------------------------------------------------------
def test_all_gated_correct_supported():
    s = [_gated(k, k, 1) for k in range(24)]
    m = audit.compute_metrics(s)
    check(m["conclusion"] == audit.CONCL_SUPPORTED, "all-correct -> SUPPORTED")
    check(m["end_to_end_correct"] == "24/24", "end_to_end 24/24")
    check(m["gated_correct"] == "24/24", "gated 24/24")
    check(m["coverage"] == 1.0, "coverage 1.0")
    check(m["wide_linear_forced_correct"] == "24/24", "wl forced 24/24")
    check(not m["blocked"], "not blocked")


def test_one_wrong_insufficient():
    s = [_gated(k, k, 1) for k in range(24)]
    s[7] = _gated(7, 3, 0)  # 32PSK 误判为 BPSK
    m = audit.compute_metrics(s)
    check(m["conclusion"] == audit.CONCL_INSUFFICIENT, "one-wrong -> INSUFFICIENT")
    check(m["end_to_end_correct"] == "23/24", "end_to_end 23/24")
    check(m["wide_linear_forced_correct"] == "23/24", "wl forced 23/24")


def test_rejected_fails_end_to_end_but_forced_recovers():
    # 23 gated 全对 + 1 rejected；rejected 的 wide-linear 强制分类正确 -> 端到端 23/24，
    # 但 forced full coverage 24/24。
    s = [_gated(k, k, 1) for k in range(24)]
    s[16] = _rejected(16, 16, 16, wl_applicable=1)  # 256QAM 被门拒，强制分类仍正确
    m = audit.compute_metrics(s)
    check(m["end_to_end_correct"] == "23/24", "rejected counted as end-to-end fail")
    check(abs(m["coverage"] - 23.0 / 24.0) < 1e-6, "coverage 23/24")
    check(m["scored"] == 23, "scored 23")
    check(m["wide_linear_forced_correct"] == "24/24", "forced full coverage 24/24")
    check(m["conclusion"] == audit.CONCL_SUPPORTED, "forced 24/24 -> SUPPORTED")


def test_wide_linear_is_primary_and_disagree_counted():
    # rejected：scalar 错、wide-linear 对，且 applicable=1 -> 主决策用 wide-linear。
    s = [_gated(k, k, 1) for k in range(24)]
    s[10] = _rejected(10, scalar_pred=8, wl_pred=10, wl_applicable=1)
    m = audit.compute_metrics(s)
    check(m["scalar_forced_correct"] == "23/24", "scalar forced 23/24")
    check(m["wide_linear_forced_correct"] == "24/24", "wl forced 24/24")
    check(m["scalar_wide_linear_disagree"] == 1, "scalar/wl disagree counted")
    check(m["conclusion"] == audit.CONCL_SUPPORTED,
          "primary decision follows wide-linear, not scalar")


def test_blocked_priority_overrides_correct():
    s = [_gated(k, k, 1) for k in range(24)]
    s[5] = _rejected(5, 5, 5, blocked="forced_export_missing")
    m = audit.compute_metrics(s)
    check(m["blocked"], "blocked flag set")
    check(m["blocked_reasons"] == ["forced_export_missing"], "blocked reason recorded")
    check(m["conclusion"] == audit.CONCL_BLOCKED, "blocked -> BLOCKED even if 23/24 correct")


def test_confusion_diagonal():
    s = [_gated(k, k, 1) for k in range(24)]
    m = audit.compute_metrics(s)
    conf = m["confusion_24"]
    check(all(conf[i][i] == 1 for i in range(24)), "diagonal all 1")
    check(all(conf[i][j] == 0 for i in range(24) for j in range(24) if i != j),
          "off-diagonal all 0")


# ---------------------------------------------------------------------------
# 合成板端产物树
# ---------------------------------------------------------------------------
def _manifest_lines():
    header = "\t".join(audit.MANIFEST_HEADER)
    lines = [header]
    for k in range(24):
        sid = k * 500
        row = [str(k), str(sid), str(k), str(k if k < 17 else 17), "M%d" % k, "nan",
               "holdout", "2048", "0", "0", "1", "1", "53760", "2560000", "893", "2613",
               "0", "zero", "832", "0" * 64, "1" * 64, "2" * 64, "x.ci16", "rt.f32",
               "2.29", str(k), str(k if k < 17 else 17)]
        lines.append("\t".join(row))
    return "\n".join(lines) + "\n"


def _board_row(sid, verdict):
    pred = sid // 500 if verdict == audit.GATE_VERDICT else -1
    correct = 1 if verdict == audit.GATE_VERDICT else -1
    valid = 1 if verdict == audit.GATE_VERDICT else 0
    return "\t".join([
        "f%d" % sid, str(sid), str(sid // 500), "M%d" % (sid // 500), "nan", "holdout",
        str(valid), str(pred), "-1", str(correct), "-1", "-1",
        "0.99", "0.05", "0", "1.0", "0.0", "0", "0", "0", "0", verdict,
    ])


def _board_lines(rejected=()):
    lines = ["\t".join(audit.BOARD_RESULTS_HEADER)]
    for k in range(24):
        sid = k * 500
        verdict = "RF_DISTORTS_IQ" if sid in rejected else audit.GATE_VERDICT
        lines.append(_board_row(sid, verdict))
    return "\n".join(lines) + "\n"


def _dump_json(sid, raw_sha):
    return {
        "source_index": sid,
        "target_rms": 2048,
        "tx_scale": 2.29,
        "failure_enum": 10,
        "payload_training_residual": 0.12,
        "timing_offset": 50000,
        "coarse_cfo_hz": -100.0,
        "fine_cfo_hz": 0.3,
        "raw_rx_sha256": raw_sha,
    }


def _write_dump(d, sid, raw_sha):
    os.makedirs(d, exist_ok=True)
    raw = ("raw-%d" % sid).encode() * 8
    j = _dump_json(sid, raw_sha)
    for name in audit.REQUIRED_FILES:
        p = os.path.join(d, name)
        if name == "raw_rx_ci16le.bin":
            with open(p, "wb") as f:
                f.write(raw)
        elif name == "recovery_diagnostics.json":
            with open(p, "w", encoding="utf-8") as f:
                json.dump(j, f)
        elif name == "SHA256SUMS.txt":
            with open(p, "w", encoding="utf-8") as f:
                f.write("%s  raw_rx_ci16le.bin\n" % raw_sha)
        else:
            with open(p, "wb") as f:
                f.write(b"x")


def _full_tree(root, rejected=()):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "manifest.tsv"), "w", encoding="utf-8") as f:
        f.write(_manifest_lines())
    with open(os.path.join(root, "route_f_fix10class24_bf16_pc_tx_board_rx_results.tsv"),
              "w", encoding="utf-8") as f:
        f.write(_board_lines(rejected))
    fd = os.path.join(root, "failed_rx")
    for sid in rejected:
        raw_sha = sha(("raw-%d" % sid).encode() * 8)
        _write_dump(os.path.join(fd, str(sid)), sid, raw_sha)


def _out(root):
    return os.path.join(root, "out")


# ---------------------------------------------------------------------------
# parse fail-closed
# ---------------------------------------------------------------------------
def test_parse_board_results_wrong_set():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "r.tsv")
        with open(p, "w", encoding="utf-8") as f:
            f.write(_board_lines())
        # 删掉 source_index=0 那一行，改为 24 行但少一个源。
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines = [ln for ln in lines if not ln.startswith("f0\t")]  # 去掉 0
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(lines)
        assert_fail_closed(lambda: audit.parse_board_results(p), "source_index")


def test_parse_board_results_header_mismatch():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "r.tsv")
        with open(p, "w", encoding="utf-8") as f:
            f.write("foo\tbar\n1\t2\n")
        assert_fail_closed(lambda: audit.parse_board_results(p), "header")


def test_parse_manifest_wrong_count():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.tsv")
        with open(p, "w", encoding="utf-8") as f:
            f.write(_manifest_lines())
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(lines[:-1])  # 少一行
        assert_fail_closed(lambda: audit.parse_manifest(p), "24")


# ---------------------------------------------------------------------------
# inventory fail-closed
# ---------------------------------------------------------------------------
def test_inventory_ok():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500,))  # 1 个被拒
        audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td))
        check(os.path.isfile(os.path.join(_out(td), "inventory.tsv")),
              "inventory.tsv written")
        with open(os.path.join(_out(td), "inventory.tsv"), encoding="utf-8") as f:
            rows = f.readlines()
        check(len(rows) == 25, "inventory has 24 data rows + header")


def test_inventory_gated_unexpected_dump():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=())
        # 给 gated 的 0 塞一个 dump 目录
        _write_dump(os.path.join(td, "failed_rx", "0"), 0, sha(b"x"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "unexpected")


def test_inventory_rejected_missing_dump():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500,))
        # 板端 TSV 说 3500 被拒，但 failed_rx 无 3500
        os.remove(os.path.join(td, "route_f_fix10class24_bf16_pc_tx_board_rx_results.tsv"))
        with open(os.path.join(td, "route_f_fix10class24_bf16_pc_tx_board_rx_results.tsv"),
                  "w", encoding="utf-8") as f:
            f.write(_board_lines(rejected=(3500,)))
        import shutil
        shutil.rmtree(os.path.join(td, "failed_rx", "3500"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "missing failed_rx")


def test_inventory_missing_file():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500,))
        os.remove(os.path.join(td, "failed_rx", "3500", "coarse_corrected_rx_cf64le.bin"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "missing")


def test_inventory_raw_sha_mismatch():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500,))
        p = os.path.join(td, "failed_rx", "3500", "raw_rx_ci16le.bin")
        with open(p, "wb") as f:
            f.write(b"tampered")
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "SHA")


def test_inventory_json_missing_field():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500,))
        p = os.path.join(td, "failed_rx", "3500", "recovery_diagnostics.json")
        j = json.load(open(p, encoding="utf-8"))
        del j["fine_cfo_hz"]
        json.dump(j, open(p, "w", encoding="utf-8"))
        assert_fail_closed(
            lambda: audit.phase_inventory(td, os.path.join(td, "manifest.tsv"), _out(td)),
            "fine_cfo_hz")


# ---------------------------------------------------------------------------
# classify 端到端（合成 captures + export，注入假 host 前向，不碰 icraft-run）
# ---------------------------------------------------------------------------
def _write_export(export_root, capture_id, sid, wl_applicable):
    d = os.path.join(export_root, capture_id, str(sid))
    os.makedirs(d, exist_ok=True)
    mi = b"\x00" * audit.MODEL_INPUT_BYTES
    with open(os.path.join(d, "model_input_f32le.bin"), "wb") as f:
        f.write(mi)
    j = {
        "capture_id": capture_id, "source_index": sid, "source_class": sid // 500,
        "raw_rx_sha256": sha(b"x"), "payload_training_residual": 0.12,
        "payload_training_corr": 0.99, "model_input_finite": 1,
        "wide_linear": {"applicable": wl_applicable, "reason": "test",
                        "model_input_finite": 1},
    }
    with open(os.path.join(d, "forced_recovery.json"), "w", encoding="utf-8") as f:
        json.dump(j, f)
    if wl_applicable:
        with open(os.path.join(d, "wide_linear_model_input_f32le.bin"), "wb") as f:
            f.write(mi)


def _fake_infer(mi_path):
    # 假分类器：固定 argmax=0，不读标签、不读目录名（只验证编排管道）。
    logits = audit.np.zeros(24, dtype=audit.np.float64)
    logits[0] = 1.0
    return logits, 0, True


def test_classify_end_to_end_synthetic():
    with tempfile.TemporaryDirectory() as td:
        _full_tree(td, rejected=(3500, 8000))
        capture_id = os.path.basename(os.path.abspath(td))
        export = os.path.join(td, "export")
        _write_export(export, capture_id, 3500, wl_applicable=1)
        _write_export(export, capture_id, 8000, wl_applicable=0)
        out_dir = os.path.join(td, "results")
        args = argparse.Namespace(
            captures_dir=td, manifest=os.path.join(td, "manifest.tsv"),
            forced_classify_dir=export, out_dir=out_dir,
            icraft_run=None, model_dir=None)
        audit.phase_classify(args, infer=_fake_infer)

        for fn in ["per_sample_results.tsv", "raw24_logits.tsv",
                   "confusion_24.csv", "summary.json"]:
            check(os.path.isfile(os.path.join(out_dir, fn)), "deliverable %s written" % fn)

        summ = json.load(open(os.path.join(out_dir, "summary.json"), encoding="utf-8"))
        check(summ["metrics"]["end_to_end_correct"] == "22/24", "end_to_end 22/24")
        check(summ["metrics"]["scalar_forced_correct"] == "22/24", "scalar forced 22/24")
        check(summ["metrics"]["wide_linear_forced_correct"] == "22/24",
              "wl forced 22/24")
        check(summ["conclusion"] == audit.CONCL_INSUFFICIENT,
              "conclusion INSUFFICIENT (2 rejected misclassify)")
        check(summ["no_label_driven_variant_selection"] == 1,
              "no label-driven variant selection flag set")

        with open(os.path.join(out_dir, "per_sample_results.tsv"), encoding="utf-8") as f:
            check(len(f.readlines()) == 25, "per_sample has 24 data rows")

        # 22 gated + 2 scalar + 1 wide_linear（仅 3500 applicable）= 25 data rows
        with open(os.path.join(out_dir, "raw24_logits.tsv"), encoding="utf-8") as f:
            check(len(f.readlines()) == 26, "raw24_logits has 25 data rows")

        # confusion 24 行 + 表头
        with open(os.path.join(out_dir, "confusion_24.csv"), encoding="utf-8") as f:
            check(len(f.readlines()) == 25, "confusion has 24 rows + header")


def main():
    tests = [
        ("all_gated_correct_supported", test_all_gated_correct_supported),
        ("one_wrong_insufficient", test_one_wrong_insufficient),
        ("rejected_fails_end_to_end_but_forced_recovers",
         test_rejected_fails_end_to_end_but_forced_recovers),
        ("wide_linear_is_primary_and_disagree_counted",
         test_wide_linear_is_primary_and_disagree_counted),
        ("blocked_priority_overrides_correct", test_blocked_priority_overrides_correct),
        ("confusion_diagonal", test_confusion_diagonal),
        ("parse_board_results_wrong_set", test_parse_board_results_wrong_set),
        ("parse_board_results_header_mismatch", test_parse_board_results_header_mismatch),
        ("parse_manifest_wrong_count", test_parse_manifest_wrong_count),
        ("inventory_ok", test_inventory_ok),
        ("inventory_gated_unexpected_dump", test_inventory_gated_unexpected_dump),
        ("inventory_rejected_missing_dump", test_inventory_rejected_missing_dump),
        ("inventory_missing_file", test_inventory_missing_file),
        ("inventory_raw_sha_mismatch", test_inventory_raw_sha_mismatch),
        ("inventory_json_missing_field", test_inventory_json_missing_field),
        ("classify_end_to_end_synthetic", test_classify_end_to_end_synthetic),
    ]
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            global g_fail
            g_fail += 1
            print("  EXCEPTION in %s: %s" % (name, e))
    print("  pass=%d fail=%d" % (g_pass, g_fail))
    return 1 if g_fail else 0


if __name__ == "__main__":
    sys.exit(main())
