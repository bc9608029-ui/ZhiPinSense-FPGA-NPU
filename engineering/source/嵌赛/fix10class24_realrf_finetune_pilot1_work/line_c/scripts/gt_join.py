#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gt_join.py — 主机真值清单离线关联（评审 39e5 Blocker 2）。

板端采集 TSV 的真值列在采集时一律置空（接收端不得持有类别真值 / 原始 IQ SHA / 数据集
索引 / split / label）；采集结束后，主机端用本模块按 source_id 从
line_a/results/source_manifest_960.tsv 离线回填这些列，并 fail-closed 断言板端确实
未带回任何真值（红线：接收端不得读取类别真值）。

回填列：class_index / class_name / dataset_index / split / source_iq_sha256 / label，
其中 label == class_index（与数字基线 run_digital_baseline.py 的 label 语义一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path

LINE_A = Path(__file__).resolve().parent.parent.parent / "line_a"

GROUND_TRUTH_HEADER = [
    "session_id", "source_id", "class_index", "class_name", "dataset_index",
    "split", "snr_db", "instance", "source_iq_sha256",
]

# 采集 TSV 中必须为空（否则接收端拿到了真值）的列。
BOARD_EMPTY_TRUTH_COLS = (
    "class_index", "class_name", "dataset_index", "split",
    "source_iq_sha256", "label",
)


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def load_ground_truth(path=None) -> dict[str, dict]:
    p = Path(path) if path is not None else (LINE_A / "results" / "source_manifest_960.tsv")
    if not p.is_file():
        fatal("ground-truth manifest not found: %s" % p)
    lines = [ln.rstrip("\r\n") for ln in p.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    if header != GROUND_TRUTH_HEADER:
        fatal("ground-truth header mismatch:\n got %r\n want %r" % (header, GROUND_TRUTH_HEADER))
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(GROUND_TRUTH_HEADER):
            fatal("ground-truth row field count %d != %d" % (len(f), len(GROUND_TRUTH_HEADER)))
        out[f[1]] = {
            "session_id": f[0],
            "class_index": int(f[2]),
            "class_name": f[3],
            "dataset_index": int(f[4]),
            "split": f[5],
            "source_iq_sha256": f[8],
        }
    if len(out) != 960:
        fatal("ground-truth manifest has %d rows (want 960)" % len(out))
    return out


def backfill_truth(rows: list[dict], gt: dict[str, dict] | None = None,
                   path=None) -> list[dict]:
    """按 source_id 把主机真值回填进采集行；板端真值列必须为空（fail-closed）。

    就地修改并返回 rows。rows 需已含 `source_id` 及 BOARD_EMPTY_TRUTH_COLS 全部键。
    任一真值列非空（接收端拿到了真值）或 source_id 未知 → fail-closed。
    """
    if gt is None:
        gt = load_ground_truth(path)
    for r in rows:
        for c in BOARD_EMPTY_TRUTH_COLS:
            if r.get(c, "") not in ("", None):
                fatal("board capture leaked ground-truth column %s (source_id=%s, value=%r)"
                      % (c, r.get("source_id"), r.get(c)))
        sid = r.get("source_id")
        if sid not in gt:
            fatal("source_id %r not in ground-truth manifest" % sid)
        g = gt[sid]
        r["class_index"] = str(g["class_index"])
        r["class_name"] = g["class_name"]
        r["dataset_index"] = str(g["dataset_index"])
        r["split"] = g["split"]
        r["source_iq_sha256"] = g["source_iq_sha256"]
        r["label"] = str(g["class_index"])
    return rows
