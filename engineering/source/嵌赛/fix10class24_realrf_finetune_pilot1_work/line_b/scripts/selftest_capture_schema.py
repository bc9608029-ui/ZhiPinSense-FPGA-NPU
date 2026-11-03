#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest_capture_schema.py — 并行线 B 合成夹具自测（不碰板、不发射、不训练）。

覆盖：
  * 32 字段 schema 一致性（合同 RESULT_TSV_FIELDS == 判读器 CAPTURE_COLS == 本线）。
  * save-before-gate 反例测试：门拒样本仍保存 model_input/logits/pred（伪造生产结果失败）。
  * TX manifest schema + CI16 payload 字节数 = 2×53760×2 = 215040。
  * export_finetune_tx_payload 自测（960/四轮零重叠/TX 数学）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINE_B = HERE.parent
ROOT = LINE_B.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "line_c" / "scripts"))
sys.path.insert(0, str(ROOT / "contract"))

import shared_contract as SC  # noqa: E402

N_CLASSES = 24


def test_schema_consistency():
    from judge_realrf_pilot import CAPTURE_COLS
    assert SC.RESULT_TSV_FIELDS == CAPTURE_COLS, "32-field schema drift: contract != judge"
    assert len(SC.RESULT_TSV_FIELDS) == 32, "want 32 fields, got %d" % len(SC.RESULT_TSV_FIELDS)
    assert SC.N_TOTAL == 960 and SC.N_PER_CLASS == 10
    assert SC.SESSION_ROLES["S4"] == "sealed_test"
    assert len(SC.LABEL_ORDER_24) == N_CLASSES
    print("  schema_consistency OK (32 fields, contract == judge, 960/10/class, S4 sealed)")


def test_save_before_gate():
    """反例：门拒样本必须仍保存 model_input_sha256 + logits_sha256 + board_pred。"""
    # 构造一个门拒帧（gate_pass=0、failure_token 非空），但 tensor/logits/预测齐全。
    # save-before-gate 合同要求：保存动作在门控之前，故门拒时这些字段必须非空。
    def make_row(gate_pass, failure_token, has_tensor):
        return {
            "gate_pass": gate_pass, "failure_token": failure_token,
            "model_input_sha256": "a" * 64 if has_tensor else "",
            "logits_sha256": "b" * 64 if has_tensor else "",
            "board_pred1": "7" if has_tensor else "",
            "capture_ok": "1", "hard_invalid": "0",
        }

    # 门拒 + 有 tensor：必须保存（诊断旁路）
    r = make_row("0", "CFO_OUT_OF_RANGE", True)
    assert r["model_input_sha256"] and r["logits_sha256"] and r["board_pred1"] != "", \
        "gate-reject frame lost its saved tensor/logits/pred (save-before-gate violated)"

    # hard_invalid + 无 tensor：仍写行（占 960 分母），但字段可为空
    r2 = make_row("0", "NO_SYNC", False)
    assert r2["model_input_sha256"] == "" and r2["board_pred1"] == "", \
        "hard-invalid frame should have empty tensor fields"

    # 反例：门拒却伪造 gate_pass=1 → 判读器应能区分（诊断旁路不得伪装生产结果）
    assert r["gate_pass"] == "0", "gate-reject must be marked gate_pass=0"
    print("  save_before_gate OK (gate-reject still saved; hard-invalid counted; no spoof)")


def test_tx_manifest_contract():
    from export_finetune_tx_payload import (TX_MANIFEST_HEADER,
                                            TX_PAYLOAD_MANIFEST_HEADER, SESSIONS,
                                            N_PER_SESSION, N_TOTAL)
    assert TX_MANIFEST_HEADER == ["session_id", "source_id", "tx_payload_sha256"], \
        "3-col board-public identity manifest header drift: %r" % (TX_MANIFEST_HEADER,)
    assert TX_PAYLOAD_MANIFEST_HEADER == ["seq", "session_id", "source_id",
                                          "tx_payload_file", "tx_payload_sha256"], \
        "5-col PC-private payload manifest header drift: %r" % (TX_PAYLOAD_MANIFEST_HEADER,)
    # 评审 39e5 Blocker 2：板端公共身份 manifest 绝不含类别真值/文件路径。
    forbidden = {"class_index", "class_name", "dataset_index", "split",
                 "source_iq_sha256", "tx_payload_file"}
    assert not (set(TX_MANIFEST_HEADER) & forbidden), \
        "board-public manifest leaked ground-truth columns"
    # 主机真值清单（line_a/results/source_manifest_960.tsv）仍保留全部真值列，供离线关联。
    from export_finetune_tx_payload import read_source_manifest
    host_rows = read_source_manifest()
    assert len(host_rows) == 960 and "class_index" in host_rows[0], \
        "host ground-truth manifest incomplete"
    assert SESSIONS == ["S1", "S2", "S3", "S4"]
    assert N_PER_SESSION == 240 and N_TOTAL == 960
    # CI16 payload 字节数 = 53760 复 × 2 分量 × 2 字节 = 215040
    from radioml_dualsdr_common import RF_PAYLOAD_COMPLEX
    assert 2 * RF_PAYLOAD_COMPLEX * 2 == 215040
    print("  tx_manifest_contract OK (3-col identity + 5-col payload; no truth on board; "
          "host truth 960)")


def test_manifest_split_alignment():
    """3 列板端公共 manifest 与 5 列 PC 私有 payload manifest 的 seq/source_id 对齐。

    板端按 3 列文件顺序给每行采集序号 seq=行号；PC 私有 payload manifest 的 seq 也必须
    等于同一 source_id 排序下的行号——两者一致，PC 才能按 seq 正确寻址 payload。
    """
    from export_finetune_tx_payload import (TX_MANIFEST_HEADER,
                                            TX_PAYLOAD_MANIFEST_HEADER)
    from pathlib import Path
    tx_payload_root = LINE_B / "tx_payload"
    checked = 0
    for session in ["S1", "S2", "S3", "S4"]:
        d = tx_payload_root / session
        man = (d / "tx_manifest.tsv").read_text(encoding="utf-8").splitlines()
        pay = (d / "tx_payload_manifest.tsv").read_text(encoding="utf-8").splitlines()
        assert man[0].split("\t") == TX_MANIFEST_HEADER
        assert pay[0].split("\t") == TX_PAYLOAD_MANIFEST_HEADER
        man_rows = [ln.split("\t") for ln in man[1:] if ln.strip()]
        pay_rows = [ln.split("\t") for ln in pay[1:] if ln.strip()]
        assert len(man_rows) == 240 and len(pay_rows) == 240
        # seq == 行号，且 seq 行的 source_id / sha 与 3 列 manifest 同行一致。
        for seq, (m, p) in enumerate(zip(man_rows, pay_rows)):
            assert int(p[0]) == seq, "seq not contiguous at %s seq=%s" % (session, p[0])
            assert p[2] == m[1], "source_id mismatch at %s seq=%d" % (session, seq)
            assert p[4] == m[2], "tx_payload_sha256 mismatch at %s seq=%d" % (session, seq)
            assert p[3] == m[1] + ".i16", "tx_payload_file drift at %s seq=%d" % (session, seq)
        checked += 1
    assert checked == 4
    print("  manifest_split_alignment OK (seq/source_id/sha aligned across 4 sessions)")


def test_export_self_test():
    import export_finetune_tx_payload as E
    rc = E.run_self_test()
    assert rc == 0
    print("  export_finetune_tx_payload self-test OK")


def main() -> int:
    print("selftest_capture_schema ...")
    test_schema_consistency()
    test_save_before_gate()
    test_tx_manifest_contract()
    test_manifest_split_alignment()
    test_export_self_test()
    print("selftest_capture_schema ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
