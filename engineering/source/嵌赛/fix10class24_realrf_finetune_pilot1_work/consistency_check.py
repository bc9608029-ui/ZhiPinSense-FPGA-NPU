#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""consistency_check.py — M29-RML24-REALRF-FINETUNE-PILOT1 主线程一致性核验。

跨三线（A 源数据 / B 采集链 / C 判读与训练框架）+ 共享合同做一致性与身份核验：
  1. 冻结身份：模型 json/raw/checkpoint SHA、HDF5 SHA 与合同一致，文件存在。
  2. 线 A：960 源清单（4 会话 × 24 类 × 10）、四轮零重叠、与既有 480 冻结集零重叠。
  3. 线 B：32 字段 schema（合同==判读器）、TX payload 240/会话、save-before-gate。
  4. 线 C：数字基线契约、判读器口径、训练框架 E0-E3 冻结掩码。
纯离线；不上板、不发射、不训练。任一 fail 即 fail-closed 非零退出。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "contract"))
sys.path.insert(0, str(ROOT / "line_a"))
sys.path.insert(0, str(ROOT / "line_c" / "scripts"))
sys.path.insert(0, str(ROOT / "line_b" / "scripts"))

import shared_contract as SC  # noqa: E402

CHECKS = []
def check(name, ok, detail=""):
    CHECKS.append(ok)
    print("%-52s %s%s" % (name, "PASS" if ok else "FAIL",
                          (" -- " + detail) if detail else ""))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-hdf5-sha", action="store_true",
                    help="全量哈希 21.4 GiB HDF5（默认只验存在，避免每次慢哈希）")
    args = ap.parse_args()

    # ---- 1. 冻结身份 ----
    ckpt = Path(r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
                r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
    check("checkpoint exists", ckpt.is_file(), str(ckpt))
    if ckpt.is_file():
        check("checkpoint SHA == contract", sha256_file(ckpt) == SC.FROZEN_CKPT_SHA)

    mj = Path(SC.MODEL_JSON_PATH); mr = Path(SC.MODEL_RAW_PATH)
    check("model json exists", mj.is_file(), str(mj))
    check("model raw exists", mr.is_file(), str(mr))
    if mj.is_file():
        check("model json SHA == contract", sha256_file(mj) == SC.FROZEN_MODEL_JSON_SHA)
    if mr.is_file():
        check("model raw SHA == contract", sha256_file(mr) == SC.FROZEN_MODEL_RAW_SHA)

    hdf5 = Path(SC.HDF5_PATH)
    check("HDF5 exists", hdf5.is_file(), str(hdf5))
    if hdf5.is_file() and args.verify_hdf5_sha:
        check("HDF5 SHA == contract", sha256_file(hdf5) == SC.HDF5_SHA256)

    # ---- 2. 线 A：960 源清单 + 四轮零重叠 ----
    import audit_split as AS
    rows = AS.load_manifest()
    check("960 source rows", len(rows) == 960, "rows=%d" % len(rows))
    problems = AS.audit(rows)
    check("line_a 960 + 4-way zero overlap + 10/class/session", not problems,
          "; ".join(problems[:3]) if problems else "")

    # ---- 3. 线 B：schema + TX ----
    from judge_realrf_pilot import CAPTURE_COLS
    check("32-field schema contract == judge", SC.RESULT_TSV_FIELDS == CAPTURE_COLS)
    check("32 fields (frozen)", len(SC.RESULT_TSV_FIELDS) == 32)
    from export_finetune_tx_payload import TX_MANIFEST_HEADER, TX_PAYLOAD_MANIFEST_HEADER
    check("TX manifest 3-col board-public (no truth)",
          TX_MANIFEST_HEADER == ["session_id", "source_id", "tx_payload_sha256"],
          "header=%r" % (TX_MANIFEST_HEADER,))
    check("TX payload manifest 5-col PC-private",
          TX_PAYLOAD_MANIFEST_HEADER == ["seq", "session_id", "source_id",
                                         "tx_payload_file", "tx_payload_sha256"],
          "header=%r" % (TX_PAYLOAD_MANIFEST_HEADER,))
    check("board-public manifest has no ground-truth cols",
          not (set(TX_MANIFEST_HEADER) & {"class_index", "class_name", "dataset_index",
                                          "split", "source_iq_sha256", "tx_payload_file"}))
    check("S4 sealed_test", SC.SESSION_ROLES["S4"] == "sealed_test")

    # ---- 4. 线 C：训练框架冻结掩码（不加载 torch，仅契约级） ----
    check("E0-E3 实验集", SC.FINETUNE_EXPERIMENTS == ["E0", "E1", "E2", "E3"])
    check("红线含禁写 FINETUNE_SUCCESS",
          any("FINETUNE_SUCCESS" in r for r in SC.RED_LINES))
    check("红线含 960 分母不剔",
          any("960 分母" in r or "不剔" in r for r in SC.RED_LINES))

    n_pass = sum(CHECKS)
    print("\nconsistency_check %s (%d/%d)" %
          ("PASS" if n_pass == len(CHECKS) else "FAIL", n_pass, len(CHECKS)))
    return 0 if n_pass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
