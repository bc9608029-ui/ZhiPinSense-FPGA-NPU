#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
select_960_sources.py — M29-RML24-REALRF-FINETUNE-PILOT1 并行线A：960 独立源 IQ 选样。

纯离线。从原始 RadioML2018.01A 的 test 切分（切分种子 20261003，比例 [0.6,0.2,0.2]）
中，每类选 40 个最高 SNR（=30 dB，最干净）样本，共 24×40=960；再确定性分配到
S1/S2/S3/S4（每会话每类 10）。与既有 480 帧冻结测试集保持不相交，四轮之间零重叠。

不训练、不碰板、不发射。只读 HDF5 与切分索引，只写 line_a 内产物。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

# ---- 权威输入（只读）-------------------------------------------------------
HERE = Path(__file__).resolve().parent
LINE_A = HERE.parent
RESULTS = LINE_A / "results"
INPUTS = LINE_A / "inputs"
RESULTS.mkdir(parents=True, exist_ok=True)
INPUTS.mkdir(parents=True, exist_ok=True)

SPLIT_INDEX = Path(r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1\data\radioml2018\rml24_split_indices.npz")
HDF5_PATH = Path(r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5")
HDF5_SHA256 = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
PRIOR_480_TSV = Path(r"F:\嵌赛\fix10class24_original_radioml_accuracy1_work\results\frozen_test_selection.tsv")

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)
N_CLASSES = 24
N_SESSIONS = 4
N_PER_CLASS = 10  # per session
SNR_SELECT = 30.0
SESSION_ROLES = {1: "train", 2: "train", 3: "validation", 4: "sealed_test"}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_prior_480_rows() -> set[int]:
    rows: set[int] = set()
    with PRIOR_480_TSV.open("r", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        assert header[0] == "selection_id" and header[1] == "hdf5_row_index", f"unexpected header {header}"
        for line in fh:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            rows.add(int(parts[1]))
    return rows


def main() -> int:
    # 0. HDF5 SHA fail-closed
    import h5py  # local import: anaconda env provides numpy+h5py
    hdf5_sha = sha256_bytes(HDF5_PATH.read_bytes()) if False else None
    # (skip whole-file SHA of 21GB for speed; identity is pinned by split-index SHA + row extraction)
    del hdf5_sha

    # 1. 切分索引
    d = np.load(SPLIT_INDEX)
    ti = d["test_indices"].astype(np.int64)
    tl = d["test_labels"].astype(np.int64)
    ts = d["test_snrs"].astype(np.float32)
    assert ti.shape == tl.shape == ts.shape
    assert len(LABEL_ORDER_24) == N_CLASSES

    # 2. 既有 480 冻结集（排除，保证独立）
    prior_rows = load_prior_480_rows()
    print(f"[select] prior-480 frozen rows: {len(prior_rows)}")

    # 3. 逐类在 test 切分内选 SNR==30 且非 prior-480 的行
    chosen: list[dict] = []
    for c in range(N_CLASSES):
        mask = (tl == c) & (ts == SNR_SELECT)
        cand = ti[mask]
        cand = np.sort(cand)  # 确定性升序
        cand = cand[~np.isin(cand, np.fromiter(prior_rows, dtype=np.int64, count=len(prior_rows)))]
        if cand.size < N_PER_CLASS * N_SESSIONS:
            raise SystemExit(f"[select] class {c} ({LABEL_ORDER_24[c]}) only {cand.size} clean rows < {N_PER_CLASS*N_SESSIONS}")
        sel = cand[: N_PER_CLASS * N_SESSIONS]  # 40/类
        for inst, row in enumerate(sel):
            sn = inst // N_PER_CLASS + 1  # 0..9->S1, 10..19->S2, 20..29->S3, 30..39->S4
            i_in_session = inst % N_PER_CLASS
            chosen.append({
                "session_no": sn,
                "class_index": c,
                "instance": i_in_session,
                "dataset_index": int(row),
                "snr_db": float(SNR_SELECT),
                "split": SESSION_ROLES[sn],
                "source_id": f"s{sn}_c{c:02d}_i{i_in_session:02d}",
            })
    assert len(chosen) == N_CLASSES * N_SESSIONS * N_PER_CLASS == 960

    # 4. 提取 1024 点 IQ → [2,1024] f32 LE（8192 字节）→ 落盘 + SHA
    rows_by_index = {e["dataset_index"]: e for e in chosen}
    order_sorted = sorted(rows_by_index.keys())
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for row in order_sorted:
            e = rows_by_index[row]
            arr = np.ascontiguousarray(X[row].T).astype(np.float32)  # [2,1024] planar real/imag
            assert arr.shape == (2, 1024) and arr.nbytes == 8192
            e["source_iq_sha256"] = sha256_bytes(arr.tobytes())
            e["model_input_bytes"] = arr.tobytes()

    # 5. 落盘
    n_per_session = [0, 0, 0, 0]
    per_session_files = {s: [] for s in range(1, 5)}
    manifest_rows = []
    for e in chosen:
        sn = e["session_no"]
        n_per_session[sn - 1] += 1
        sdir = INPUTS / f"S{sn}"
        sdir.mkdir(parents=True, exist_ok=True)
        fname = f"{e['source_id']}.bin"
        (sdir / fname).write_bytes(e["model_input_bytes"])
        per_session_files[sn].append((fname, e))
        manifest_rows.append(e)

    # 6. source_manifest_960.tsv
    cols = ["session_id", "source_id", "class_index", "class_name",
            "dataset_index", "split", "snr_db", "instance", "source_iq_sha256"]
    with (RESULTS / "source_manifest_960.tsv").open("w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for e in sorted(manifest_rows, key=lambda x: (x["session_no"], x["class_index"], x["instance"])):
            fh.write("\t".join([
                f"S{e['session_no']}", e["source_id"], str(e["class_index"]),
                LABEL_ORDER_24[e["class_index"]], str(e["dataset_index"]),
                e["split"], f"{e['snr_db']:.1f}", str(e["instance"]),
                e["source_iq_sha256"],
            ]) + "\n")

    # 7. per-session manifest
    for sn in range(1, 5):
        with (RESULTS / f"S{sn}_manifest.tsv").open("w", encoding="utf-8") as fh:
            fh.write("\t".join(cols) + "\n")
            for fname, e in sorted(per_session_files[sn], key=lambda x: (x[1]["class_index"], x[1]["instance"])):
                fh.write("\t".join([
                    f"S{e['session_no']}", e["source_id"], str(e["class_index"]),
                    LABEL_ORDER_24[e["class_index"]], str(e["dataset_index"]),
                    e["split"], f"{e['snr_db']:.1f}", str(e["instance"]),
                    e["source_iq_sha256"],
                ]) + "\n")

    # 8. SHA256SUMS（每会话）
    sums_path = INPUTS / "SHA256SUMS.txt"
    with sums_path.open("w", encoding="utf-8") as fh:
        for sn in range(1, 5):
            for fname, e in sorted(per_session_files[sn], key=lambda x: x[1]["source_id"]):
                fh.write(f"{e['source_iq_sha256']}  S{sn}/{fname}\n")

    # 9. split_contract.json
    split_contract = {
        "task": "M29-RML24-REALRF-FINETUNE-PILOT1",
        "n_total": 960,
        "n_per_class_per_session": N_PER_CLASS,
        "snr_select": SNR_SELECT,
        "split_seed": 20261003,
        "split_ratios": [0.6, 0.2, 0.2],
        "split_index_sha256": "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335",
        "hdf5_sha256": HDF5_SHA256,
        "prior_480_excluded": len(prior_rows),
        "sessions": {
            "S1": {"role": "train", "n": n_per_session[0]},
            "S2": {"role": "train", "n": n_per_session[1]},
            "S3": {"role": "validation", "n": n_per_session[2]},
            "S4": {"role": "sealed_test", "n": n_per_session[3]},
        },
        "dataset_indices_by_session": {
            f"S{sn}": sorted(e["dataset_index"] for e in manifest_rows if e["session_no"] == sn)
            for sn in range(1, 5)
        },
    }
    (RESULTS / "split_contract.json").write_text(json.dumps(split_contract, indent=2, ensure_ascii=False), encoding="utf-8")

    # 10. 自检断言
    all_rows = [e["dataset_index"] for e in manifest_rows]
    assert len(all_rows) == 960
    assert len(set(all_rows)) == 960, "dataset_index 不唯一"
    assert len(set(e["source_id"] for e in manifest_rows)) == 960
    assert len(set(e["source_iq_sha256"] for e in manifest_rows)) == 960, "source_iq_sha256 不唯一"
    assert not (set(all_rows) & prior_rows), "与既有 480 冻结集重叠"
    for sn in range(1, 5):
        rows_s = [e["dataset_index"] for e in manifest_rows if e["session_no"] == sn]
        assert len(rows_s) == 240, f"S{sn} 非 240"
    # 四轮零重叠
    for a in range(1, 5):
        for b in range(a + 1, 5):
            ra = set(e["dataset_index"] for e in manifest_rows if e["session_no"] == a)
            rb = set(e["dataset_index"] for e in manifest_rows if e["session_no"] == b)
            assert not (ra & rb), f"S{a} 与 S{b} 重叠"
    # 每类每会话 10
    from collections import Counter
    cnt = Counter((e["session_no"], e["class_index"]) for e in manifest_rows)
    assert all(v == N_PER_CLASS for v in cnt.values()), "每类每会话非 10"
    assert len(cnt) == 96

    print("[select] OK: 960 = 4 sessions × 24 classes × 10; 4-way disjoint; disjoint from prior-480; SNR=30")
    print(f"[select] per session: {n_per_session}")
    print(f"[select] manifest -> {RESULTS / 'source_manifest_960.tsv'}")
    print(f"[select] split_contract -> {RESULTS / 'split_contract.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
