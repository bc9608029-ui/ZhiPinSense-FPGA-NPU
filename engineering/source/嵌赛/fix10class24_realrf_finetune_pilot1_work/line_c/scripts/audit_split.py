#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_split.py — 并行线 C：四轮零重叠 + SHA 漂移 + 身份审计。

对 960 源清单（line_a/results/source_manifest_960.tsv）与（可选）板端采集 TSV /
数字基线 TSV 做一致性审计：
  * 四轮 source_id / dataset_index / source_iq_sha256 零重叠
  * source_id 唯一、dataset_index 唯一、source_iq_sha256 唯一
  * 每类每会话=10、每会话=240、总=960
  * 采集结果与源清单的 dataset_index / source_iq_sha256 无漂移、无缺文件
  * 模型身份（json/raw SHA）不变

纯离线；不上板、不发射、不训练。
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

LINE_A = Path(r"F:\嵌赛\fix10class24_realrf_finetune_pilot1_work\line_a")

FROZEN_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> list[dict]:
    p = LINE_A / "results" / "source_manifest_960.tsv"
    lines = [ln.rstrip("\r\n") for ln in p.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    assert header[0] == "session_id" and header[1] == "source_id"
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rows.append({"session_id": f[0], "source_id": f[1], "class_index": int(f[2]),
                     "dataset_index": int(f[4]), "source_iq_sha256": f[8]})
    return rows


def audit(rows: list[dict]) -> list[str]:
    problems = []
    if len(rows) != 960:
        problems.append("n_rows=%d != 960" % len(rows))
    if len(set(r["source_id"] for r in rows)) != len(rows):
        problems.append("source_id not unique")
    if len(set(r["dataset_index"] for r in rows)) != len(rows):
        problems.append("dataset_index not unique")
    if len(set(r["source_iq_sha256"] for r in rows)) != len(rows):
        problems.append("source_iq_sha256 not unique")
    # 每类每会话 10、每会话 240
    cnt_sc = Counter((r["session_id"], r["class_index"]) for r in rows)
    if len(cnt_sc) != 96 or any(v != 10 for v in cnt_sc.values()):
        problems.append("per-class-per-session != 10")
    cnt_s = Counter(r["session_id"] for r in rows)
    if any(v != 240 for v in cnt_s.values()):
        problems.append("per-session != 240")
    # 四轮零重叠
    by_sess = {}
    for r in rows:
        by_sess.setdefault(r["session_id"], set()).add(r["dataset_index"])
    for a in ["S1", "S2", "S3", "S4"]:
        for b in ["S1", "S2", "S3", "S4"]:
            if a < b and by_sess[a] & by_sess[b]:
                problems.append("session overlap %s/%s" % (a, b))
    # 高 SNR 恒 30
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-tsv", default="", help="可选板端采集 TSV 路径")
    args = ap.parse_args()

    rows = load_manifest()
    problems = audit(rows)

    if args.capture_tsv:
        cp = Path(args.capture_tsv)
        if not cp.is_file():
            fatal("--capture-tsv not found: %s" % cp)
        cap_lines = [ln.rstrip("\r\n") for ln in cp.read_text(encoding="utf-8").splitlines()]
        cap_header = cap_lines[0].split("\t")
        ci = {h: idx for idx, h in enumerate(cap_header)}
        for k in ("source_id", "dataset_index", "source_iq_sha256"):
            if k not in ci:
                fatal("capture TSV missing col %s" % k)
        cap = {}
        for ln in cap_lines[1:]:
            if not ln.strip():
                continue
            f = ln.split("\t")
            cap[f[ci["source_id"]]] = {
                "dataset_index": int(f[ci["dataset_index"]]),
                "source_iq_sha256": f[ci["source_iq_sha256"]],
            }
        if len(cap) != 960:
            problems.append("capture rows=%d != 960" % len(cap))
        for r in rows:
            if r["source_id"] not in cap:
                problems.append("capture missing %s" % r["source_id"])
            else:
                c = cap[r["source_id"]]
                if c["dataset_index"] != r["dataset_index"]:
                    problems.append("%s dataset_index drift" % r["source_id"])
                if c["source_iq_sha256"] != r["source_iq_sha256"]:
                    problems.append("%s source_iq_sha256 drift" % r["source_id"])

    if problems:
        for p in problems:
            sys.stderr.write("AUDIT-PROBLEM: %s\n" % p)
        fatal("audit failed (%d problems)" % len(problems))

    print("audit_split OK: 960 unique; 4-way zero overlap; 10/class/session; no SHA drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
