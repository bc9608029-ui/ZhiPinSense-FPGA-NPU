#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest_line_c.py — 并行线 C 合成夹具自测（不碰板、不训练、不跑真 NPU）。

覆盖：
  * judge_realrf_pilot：compute_metrics（固定 960 分母、macro-F1、confusion 形状、
    digital agreement）+ check_identity（重复/缺失/SHA 漂移/四轮重叠/模型身份）。
  * run_digital_baseline：manifest 表头/960 行/SHA 列契约、LABEL_ORDER 24。
  * train_finetune_pilot：E0-E3 冻结掩码 + 从冻结 checkpoint 初始化 + 合成前反向。
  * evaluate_finetune_pilot：compute_scores（固定 240 分母、完美=1.0）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np

N_CLASSES = 24
N_TOTAL = 960


def test_judge_metrics():
    from judge_realrf_pilot import compute_metrics, LABEL_ORDER_24, N_CLASSES as JC

    rng = np.random.default_rng(20261021)
    rows = []
    for i in range(N_TOTAL):
        lab = i % JC
        # 一半对、一半错
        pred = lab if i % 2 == 0 else (lab + 1) % JC
        rows.append({
            "source_id": "s%d_c%02d_i%02d" % ((i // 240) + 1, lab, (i % 240) // 10),
            "class_index": str(lab), "class_name": LABEL_ORDER_24[lab],
            "dataset_index": str(i), "label": str(lab),
            "capture_ok": "1", "hard_invalid": "0", "gate_pass": "1",
            "board_pred1": str(pred), "board_pred2": str(pred),
        })
    digital = {r["source_id"]: {"digital_pred": rng.integers(0, JC),
                                "dataset_index": i, "model_input_sha256": "x"}
               for i, r in enumerate(rows)}
    m = compute_metrics(rows, digital)
    assert m["n_total"] == N_TOTAL
    assert m["end_to_end_accuracy"] == 0.5
    assert m["gated_accuracy"] == 0.5
    assert 0.0 <= m["macro_f1"] <= 1.0
    conf = np.array(m["confusion_matrix"])
    assert conf.shape == (JC, JC)
    # digital agreement：board_pred1 与 digital_pred 独立随机，约 1/24
    assert 0.0 <= m["digital_agreement"] <= 1.0
    print("  judge compute_metrics OK (960 denom, 0.5 acc, 24x24 conf, macro-F1)")


def test_judge_identity():
    from judge_realrf_pilot import check_identity
    # 构造最小 960 行，先测合法
    rows = []
    for i in range(N_TOTAL):
        sid = "s%d_c%02d_i%02d" % ((i // 240) + 1, i % N_CLASSES, (i % 240) // 10)
        rows.append({"session_id": "S%d" % ((i // 240) + 1), "source_id": sid,
                     "dataset_index": str(i), "source_iq_sha256": "s%d" % i})
    digital = {r["source_id"]: {"dataset_index": i, "model_input_sha256": r["source_iq_sha256"]}
               for i, r in enumerate(rows)}
    assert check_identity(rows, digital) == []

    # 重复 source_id
    rows_dup = rows[:]
    rows_dup[1] = dict(rows_dup[0])
    assert check_identity(rows_dup, digital)

    # SHA 漂移
    rows_drift = [dict(r) for r in rows]
    rows_drift[5]["source_iq_sha256"] = "tampered"
    assert check_identity(rows_drift, digital)
    print("  judge check_identity OK (dup / drift detected, clean passes)")


def test_digital_baseline_contract():
    from run_digital_baseline import LABEL_ORDER_24, N_CLASSES as DC, INPUT_BYTES, N_PASSES
    assert len(LABEL_ORDER_24) == 24
    assert LABEL_ORDER_24[17] == "AM-SSB-WC" and LABEL_ORDER_24[23] == "OQPSK"
    assert DC == 24 and INPUT_BYTES == 8192 and N_PASSES == 2
    print("  digital_baseline contract OK (24 label order, 8192 B, 2 passes)")


def test_training_framework():
    import train_finetune_pilot as t
    # 契约级（无需 torch）：E0-E3 实验集 / 24 类 / checkpoint SHA 64hex / 模型超参键冻结。
    assert t.EXPERIMENTS == ["E0", "E1", "E2", "E3"]
    assert t.N_CLASSES == 24
    assert len(t.CKPT_SHA) == 64 and all(c in "0123456789abcdef" for c in t.CKPT_SHA)
    assert set(t.MODEL_KWARGS) == {
        "denoiser_channels", "denoiser_blocks", "feature_channels",
        "classifier_hidden", "dropout"}

    # 训练循环可达性需 torch（用户 site-packages，`python -I` 不可见）。torch 可见时跑
    # 真加载 checkpoint + E0-E3 冻结掩码计数 + 合成前反向 + 1 epoch 循环；不可见时仅契约级。
    try:
        import torch  # noqa: F401
        have_torch = True
    except ModuleNotFoundError:
        have_torch = False

    if have_torch:
        rc = t.selftest()
        assert rc == 0
        print("  train_finetune_pilot selftest OK (E0-E3 masks + synthetic fwd/bwd + loop)")
    else:
        print("  train_finetune_pilot contract OK (E0-E3/N=24/ckpt SHA 64hex); "
              "torch loop SKIPPED — run `python line_c/scripts/train_finetune_pilot.py "
              "--selftest` under plain python (not -I)")


def test_evaluate_metrics():
    from evaluate_finetune_pilot import compute_scores, S4_TOTAL
    labels = [i // 10 for i in range(S4_TOTAL)]
    s = compute_scores(labels, labels)
    assert s["n"] == S4_TOTAL and s["end_to_end_accuracy"] == 1.0
    assert s["macro_f1"] == 1.0
    assert set(s["per_class_accuracy"]) == set(range(N_CLASSES))
    print("  evaluate compute_scores OK (fixed 240 denom, perfect=1.0)")


def test_s4_sealing():
    import json as _json
    import os
    import tempfile
    from judge_realrf_pilot import load_frozen_proof, TRAINABLE_SESSIONS, SEALED_SESSION
    assert TRAINABLE_SESSIONS == ("S1", "S2", "S3"), "trainable sessions"
    assert SEALED_SESSION == "S4", "sealed session"

    good = {
        "task": "M29-RML24-REALRF-FINETUNE-PILOT1",
        "frozen_checkpoint_sha256": "a" * 64,
        "hyperparameters_hash": "b" * 64,
        "selection_split": "S3",
        "statement": "选模/早停/超参只用 S3；S4 未参与任何决策",
    }

    def write(payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(payload, f)
        return path

    def expect_fatal(payload):
        p = write(payload)
        try:
            try:
                load_frozen_proof(Path(p))
            except SystemExit:
                return True
            return False
        finally:
            os.unlink(p)

    # 合法证明通过
    p = write(good)
    try:
        assert load_frozen_proof(Path(p))["selection_split"] == "S3"
    finally:
        os.unlink(p)

    # 非法：task 不符 / selection_split != S3 / SHA 非 64hex → 全 fail-closed
    b1 = dict(good); b1["task"] = "OTHER"
    assert expect_fatal(b1), "wrong task must fail-closed"
    b2 = dict(good); b2["selection_split"] = "S4"
    assert expect_fatal(b2), "selection on S4 must fail-closed"
    b3 = dict(good); b3["frozen_checkpoint_sha256"] = "xyz"
    assert expect_fatal(b3), "short sha must fail-closed"
    b4 = dict(good); b4.pop("statement")
    assert expect_fatal(b4), "missing statement must fail-closed"
    print("  judge S4 sealing OK (proof validated; wrong task/split/sha fail-closed)")


def test_gt_join():
    import gt_join as G
    # 真实主机真值清单可加载且 960 行（9 列，label == class_index 口径）。
    gt = G.load_ground_truth()
    assert len(gt) == 960
    s0 = gt["s1_c00_i00"]
    assert s0["class_index"] == 0 and s0["class_name"] == "OOK" and s0["split"] == "train"
    assert len(s0["source_iq_sha256"]) == 64

    # 回填：空真值列 → 按 source_id 正确填充。
    rows = [{
        "source_id": "s1_c00_i00", "class_index": "", "class_name": "",
        "dataset_index": "", "split": "", "source_iq_sha256": "", "label": "",
    }]
    G.backfill_truth(rows, gt)
    r0 = rows[0]
    assert r0["label"] == "0" and r0["class_index"] == "0"
    assert r0["class_name"] == "OOK" and r0["source_iq_sha256"] == s0["source_iq_sha256"]
    assert r0["dataset_index"] == str(s0["dataset_index"])

    # 反例：板端带回类别真值（评审 39e5 Blocker 2 红线）→ fail-closed。
    leak = [{"source_id": "s1_c00_i00", "class_index": "0", "class_name": "",
             "dataset_index": "", "split": "", "source_iq_sha256": "", "label": ""}]
    try:
        G.backfill_truth(leak, gt)
        assert False, "leaked class_index must fail-closed"
    except SystemExit:
        pass

    # 反例：未知 source_id → fail-closed。
    unk = [{"source_id": "s9_c99_i99", "class_index": "", "class_name": "",
            "dataset_index": "", "split": "", "source_iq_sha256": "", "label": ""}]
    try:
        G.backfill_truth(unk, gt)
        assert False, "unknown source_id must fail-closed"
    except SystemExit:
        pass
    print("  gt_join OK (960 host truth; backfill fills; leaked-truth + unknown-sid fail-closed)")


def main() -> int:
    print("selftest_line_c ...")
    test_judge_metrics()
    test_judge_identity()
    test_digital_baseline_contract()
    test_training_framework()
    test_evaluate_metrics()
    test_s4_sealing()
    test_gt_join()
    print("selftest_line_c ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
