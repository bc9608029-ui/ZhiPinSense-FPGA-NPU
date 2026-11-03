#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judge_realrf_pilot.py — 并行线 C 职责B：真实 RF 微调 pilot 判读器。

固定 960 分母（缺失/门拒/非有限/无同步/削顶/hard-invalid 均不剔除）。合并板端采集
结果（32 字段 TSV）与数字基线，输出 coverage / gated accuracy / end-to-end accuracy /
forced diagnostic accuracy / macro-F1 / per-class accuracy / confusion matrix /
digital agreement / 每会话+总结果，并检测重复 ID、SHA 漂移、文件缺失、模型身份不符。

纯离线；不上板、不发射、不训练。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LINE_C = HERE.parent
LINE_A = LINE_C.parent / "line_a"
sys.path.insert(0, str(HERE))
from gt_join import backfill_truth, load_ground_truth  # noqa: E402

N_CLASSES = 24
N_TOTAL = 960
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)

CAPTURE_COLS = [
    "session_id", "source_id", "class_index", "class_name", "dataset_index",
    "split", "source_iq_sha256", "tx_payload_sha256", "raw_rx_sha256",
    "model_input_sha256", "logits_sha256", "digital_pred", "digital_label_correct",
    "board_pred1", "board_pred2", "label", "capture_ok", "no_sync", "rx_clipped",
    "hard_invalid", "gate_pass", "failure_token", "coarse_cfo_hz",
    "fractional_timing", "timing_offset", "corr", "training_residual",
    "training_residual_rel", "a_real", "a_imag", "b_real", "b_imag",
]


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def read_tsv(path: Path, expect_cols: list[str]) -> list[dict]:
    lines = [ln.rstrip("\r\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    if header != expect_cols:
        fatal("%s header mismatch:\n got %r\n want %r" % (path.name, header, expect_cols))
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(expect_cols):
            fatal("%s row field count %d != %d" % (path.name, len(f), len(expect_cols)))
        rows.append(dict(zip(expect_cols, f)))
    return rows


def _int(v, name):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


TRAINABLE_SESSIONS = ("S1", "S2", "S3")
SEALED_SESSION = "S4"


def load_frozen_proof(path: Path) -> dict:
    """解封 S4 一次前必读的「模型+超参已冻结」证明（自证 + 结构校验）。

    证明必须是 JSON，且：
      * task == 本任务 token；
      * frozen_checkpoint_sha256 / hyperparameters_hash 为 64 小写 hex；
      * selection_split == "S3"（所有选模/早停/超参只用 S3，未用 S4）；
      * statement 明确声明 S4 在模型与超参数确定前未参与任何决策。
    任一不符 fail-closed（拒绝解封）。证明本身无法防恶意，但把「一次性解封」动作化、
    留痕、可审计 —— S4 泄漏只能发生在有意识提交证明之后。
    """
    if not path.is_file():
        fatal("--frozen-proof not found: %s" % path)
    try:
        p = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fatal("--frozen-proof not valid JSON: %s (%s)" % (path, e))
    if p.get("task") != "M29-RML24-REALRF-FINETUNE-PILOT1":
        fatal("--frozen-proof task mismatch: %r" % p.get("task"))
    for key in ("frozen_checkpoint_sha256", "hyperparameters_hash"):
        v = p.get(key, "")
        if not (isinstance(v, str) and len(v) == 64 and
                all(c in "0123456789abcdef" for c in v)):
            fatal("--frozen-proof %s not 64-hex" % key)
    if p.get("selection_split") != "S3":
        fatal("--frozen-proof selection_split must be 'S3' (S4 未参与选模)")
    st = p.get("statement", "")
    if "S4" not in st or "S3" not in st:
        fatal("--frozen-proof statement must assert S3-only selection, S4 untouched")
    return p


def compute_metrics(rows: list[dict], digital: dict[str, dict]) -> dict:
    n = len(rows)
    # 覆盖率：capture_ok 且非 hard_invalid 且有有限 board_pred1
    def has_pred(r):
        p = _int(r.get("board_pred1"), "board_pred1")
        return p is not None and 0 <= p < N_CLASSES

    covered = [r for r in rows if r.get("capture_ok") == "1" and not (r.get("hard_invalid") == "1") and has_pred(r)]
    gated = [r for r in covered if r.get("gate_pass") == "1"]
    forced = [r for r in covered if r.get("gate_pass") != "1"]  # 诊断旁路（门拒但有 tensor）
    hard_invalid = [r for r in rows if r.get("hard_invalid") == "1" or r.get("capture_ok") != "1"]

    def acc(rs):
        if not rs:
            return None
        c = 0
        for r in rs:
            p = _int(r.get("board_pred1"), "board_pred1")
            lab = _int(r.get("label"), "label")
            c += 1 if (p is not None and lab is not None and p == lab) else 0
        return c / len(rs)

    e2e_correct = sum(1 for r in rows
                      if _int(r.get("board_pred1"), "p") is not None
                      and _int(r.get("board_pred1"), "p") == _int(r.get("label"), "l"))
    e2e_acc = e2e_correct / n if n else 0.0

    # digital agreement（板端 pred1 == 数字基线 pred）
    agree = 0
    agree_n = 0
    for r in rows:
        sid = r["source_id"]
        if sid in digital and has_pred(r):
            agree_n += 1
            if _int(r["board_pred1"], "p") == digital[sid]["digital_pred"]:
                agree += 1
    digital_agree = (agree / agree_n) if agree_n else None

    # macro-F1（end-to-end，960 分母）
    per_class = {c: {"tp": 0, "fp": 0, "fn": 0} for c in range(N_CLASSES)}
    for r in rows:
        lab = _int(r.get("label"), "l")
        p = _int(r.get("board_pred1"), "p")
        if lab is None:
            continue
        if p is not None and p == lab:
            per_class[lab]["tp"] += 1
        else:
            per_class[lab]["fn"] += 1
            if p is not None:
                per_class[p]["fp"] += 1
    f1s = []
    for c in range(N_CLASSES):
        tp = per_class[c]["tp"]; fp = per_class[c]["fp"]; fn = per_class[c]["fn"]
        f1 = (2 * tp / (2 * tp + fp + fn)) if (tp + fp + fn) > 0 else 0.0
        f1s.append(f1)
    macro_f1 = float(np.mean(f1s))

    # confusion matrix 24x24
    conf = np.zeros((N_CLASSES, N_CLASSES), dtype=int)
    for r in rows:
        lab = _int(r.get("label"), "l"); p = _int(r.get("board_pred1"), "p")
        if lab is not None and p is not None:
            conf[lab, p] += 1

    # per-class accuracy：分母取该行集合内每类真实标签数（960→40/类，单会话→10/类）
    per_class_n = Counter(_int(r.get("label"), "l") for r in rows)
    per_class_acc = {}
    for c in range(N_CLASSES):
        denom = per_class_n.get(c, 0)
        per_class_acc[c] = (per_class[c]["tp"] / denom) if denom > 0 else 0.0

    return {
        "n_total": n,
        "coverage": len(covered),
        "gated_count": len(gated),
        "forced_diagnostic_count": len(forced),
        "hard_invalid_count": len(hard_invalid),
        "gated_accuracy": acc(gated),
        "forced_diagnostic_accuracy": acc(forced),
        "end_to_end_accuracy": e2e_acc,
        "end_to_end_correct": e2e_correct,
        "macro_f1": macro_f1,
        "digital_agreement": digital_agree,
        "digital_agreement_n": agree_n,
        "per_class_accuracy": per_class_acc,
        "confusion_matrix": conf.tolist(),
    }


def check_identity(rows: list[dict], digital: dict[str, dict]) -> list[str]:
    problems = []
    # 960 固定分母
    if len(rows) != N_TOTAL:
        problems.append("capture rows=%d != 960" % len(rows))
    sids = [r["source_id"] for r in rows]
    if len(set(sids)) != len(sids):
        dup = [k for k, v in Counter(sids).items() if v > 1]
        problems.append("duplicate source_id: %s" % dup[:5])
    missing = [s for s in digital if s not in set(sids)]
    if missing:
        problems.append("missing from capture (present in digital): %d e.g. %s" % (len(missing), missing[:3]))
    extra = [s for s in sids if s not in digital]
    if extra:
        problems.append("extra in capture (absent from digital): %d" % len(extra))
    # dataset_index / source_iq_sha256 一致性（捕获 vs 数字基线）
    for r in rows:
        sid = r["source_id"]
        if sid in digital:
            d = digital[sid]
            if _int(r.get("dataset_index"), "di") != d.get("dataset_index"):
                problems.append("%s dataset_index drift" % sid)
            if r.get("source_iq_sha256") != d.get("model_input_sha256"):
                problems.append("%s source_iq_sha256 drift" % sid)
    # 四轮零重叠（source_id 前导会话号 + dataset_index）
    for a in "S1 S2 S3 S4".split():
        for b in "S1 S2 S3 S4".split():
            if a < b:
                ra = {r["dataset_index"] for r in rows if r["session_id"] == a}
                rb = {r["dataset_index"] for r in rows if r["session_id"] == b}
                if ra & rb:
                    problems.append("%s/%s dataset_index overlap" % (a, b))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-tsv", required=True, help="板端采集结果 TSV（32 字段）")
    ap.add_argument("--baseline-tsv", default=str(LINE_C / "results" / "digital_baseline_960.tsv"))
    ap.add_argument("--ground-truth", default=str(LINE_A / "results" / "source_manifest_960.tsv"),
                    help="主机真值清单（9 列，source_manifest_960.tsv）——采集后离线关联")
    ap.add_argument("--out-dir", default=str(LINE_C / "results"))
    ap.add_argument("--unseal-s4", action="store_true",
                    help="解封 S4 一次（最终评估；必须同时给 --frozen-proof）")
    ap.add_argument("--frozen-proof", default="",
                    help="模型+超参已冻结证明 JSON（unseal-s4 时必填）")
    args = ap.parse_args()

    cap_path = Path(args.capture_tsv)
    base_path = Path(args.baseline_tsv)
    if not cap_path.is_file():
        fatal("--capture-tsv not found: %s" % cap_path)
    if not base_path.is_file():
        fatal("--baseline-tsv not found: %s (run run_digital_baseline.py first)" % base_path)

    frozen_proof = None
    if args.unseal_s4:
        if not args.frozen_proof:
            fatal("--unseal-s4 requires --frozen-proof=<frozen_proof.json>")
        frozen_proof = load_frozen_proof(Path(args.frozen_proof))

    rows = read_tsv(cap_path, CAPTURE_COLS)
    # 评审 39e5 Blocker 2：板端真值列必须为空（接收端不得持有类别真值），按 source_id
    # 从主机真值清单离线回填 class_index/class_name/dataset_index/split/source_iq_sha256/label。
    backfill_truth(rows, load_ground_truth(Path(args.ground_truth)))
    base_rows = read_tsv(base_path, [  # digital baseline cols
        "source_id", "class_index", "class_name", "dataset_index", "split", "label",
        "digital_pred", "digital_label_correct", "model_input_sha256", "finite",
        "repeat_argmax", "repeat_logits_byte", "result_layer"] +
        [f"logit_{k:02d}" for k in range(N_CLASSES)])
    digital = {r["source_id"]: {**r, "digital_pred": _int(r["digital_pred"], "digital_pred"),
                                "dataset_index": _int(r["dataset_index"], "di")}
               for r in base_rows}

    # 身份/SHA/四轮零重叠检查始终在 960 全集上做（不涉标签/预测，无泄漏）。
    problems = check_identity(rows, digital)
    if problems:
        for p in problems:
            sys.stderr.write("JUDGE-PROBLEM: %s\n" % p)
        fatal("identity check failed (%d problems)" % len(problems))

    # ---- S4 封存：默认只对 S1+S2+S3 出指标；S4 只在 --unseal-s4 + 证明后解封一次 ----
    if args.unseal_s4:
        metric_rows = rows
        metric_scope = "S1+S2+S3+S4"
    else:
        metric_rows = [r for r in rows if r["session_id"] in TRAINABLE_SESSIONS]
        metric_scope = "S1+S2+S3"

    m = compute_metrics(metric_rows, digital)
    m["metric_scope"] = metric_scope
    m["s4_sealed"] = not args.unseal_s4

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "judge_summary.json").write_text(
        json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    per_session = {}
    for s in TRAINABLE_SESSIONS:
        srows = [r for r in rows if r["session_id"] == s]
        per_session[s] = compute_metrics(srows, digital)
    if args.unseal_s4:
        s4rows = [r for r in rows if r["session_id"] == SEALED_SESSION]
        per_session[SEALED_SESSION] = compute_metrics(s4rows, digital)
        per_session[SEALED_SESSION]["unsealed"] = True
        per_session[SEALED_SESSION]["frozen_checkpoint_sha256"] = \
            frozen_proof["frozen_checkpoint_sha256"]
    else:
        per_session[SEALED_SESSION] = {
            "sealed": True,
            "note": "S4 密封；模型与超参数确定后以 --unseal-s4 --frozen-proof 解封一次",
        }
    (out_dir / "judge_per_session.json").write_text(
        json.dumps(per_session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.unseal_s4:
        print("judge OK (S4 UNSEALED, scope=%s): e2e_acc=%.4f macro_f1=%.4f coverage=%d/960 "
              "gated_acc=%s digital_agree=%s" %
              (metric_scope, m["end_to_end_accuracy"], m["macro_f1"], m["coverage"],
               (("%.4f" % m["gated_accuracy"]) if m["gated_accuracy"] is not None else "n/a"),
               (("%.4f" % m["digital_agreement"]) if m["digital_agreement"] is not None else "n/a")))
    else:
        print("judge OK (S4 SEALED, scope=%s): e2e_acc=%.4f macro_f1=%.4f coverage=%d/%d "
              "gated_acc=%s digital_agree=%s" %
              (metric_scope, m["end_to_end_accuracy"], m["macro_f1"], m["coverage"],
               len(metric_rows),
               (("%.4f" % m["gated_accuracy"]) if m["gated_accuracy"] is not None else "n/a"),
               (("%.4f" % m["digital_agreement"]) if m["digital_agreement"] is not None else "n/a")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
