#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_finetune_tx_payload.py — 并行线 B：960 源 IQ → 分会话 TX CI16 payload。

把并行线 A 选出的 960 个源 IQ（line_a/inputs/S{sn}/{source_id}.bin，[2,1024] f32 LE）
应用**确定性、类无关**的传输适配（循环铺排 1024→53760 + 固定公开幅度合同 S 量化，逐字
复用冻结 `radioml_dualsdr_common`），按会话 S1/S2/S3/S4 各产出 240 个 `<source_id>.i16`
CI16 payload + 3 列板端公共 manifest + 5 列 PC 私有 payload manifest + SHA256SUMS。
原始输入与 TX 派生输入分开存储。

评审 39e5 Blocker 1/2：TX 数字缩放改为**统一公开常数 S**（`C.TX_DIGITAL_SCALE`），不再
逐样本写 native_rms/tx_scale/unscale/peak/clip；manifest 拆成三份——板端公共身份（3 列：
session_id/source_id/tx_payload_sha256，绝不含类别真值）、PC 私有 payload（5 列：
seq/session_id/source_id/tx_payload_file/tx_payload_sha256，含 tx_payload_file）、主机真值
（line_a/results/source_manifest_960.tsv，采集后离线按 source_id 关联）。板端只持
session_id/source_id/控制身份，不读 .i16 的逐样本幅度。S 保证量化后最大分量恰
1600（无削顶）。

红线：不改模型/恢复/门/协议；传输适配类无关、确定性；不按类选择；不发射（离线）。

用法：
    python -I scripts/export_finetune_tx_payload.py --all
    python -I scripts/export_finetune_tx_payload.py --session S1
    python -I scripts/export_finetune_tx_payload.py --self-test
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LINE_B = HERE.parent
LINE_A = Path(r"F:\嵌赛\fix10class24_realrf_finetune_pilot1_work\line_a")

# 冻结公共数学（权威 rf_constants，只读引用；随本树 line_b/scripts 一起分发，
# 不从其它工作树绝对路径导入，保证干净目录可复现）
sys.path.insert(0, str(HERE))
import radioml_dualsdr_common as C  # noqa: E402

SESSIONS = ["S1", "S2", "S3", "S4"]
N_PER_SESSION = 240
N_TOTAL = 960

# 分会段 TX 派生 manifest 表头（pilot1 口径；source_id 与采集/判读共享）。
# 评审 39e5 Blocker 2：拆成三份。板端公共身份 manifest（3 列，逐字节与 C++ 头
# pilot1_tx_manifest.hpp 一致）绝不含类别真值；PC 私有 payload manifest（5 列）含
# tx_payload_file 与采集序号 seq；主机真值清单（source_manifest_960.tsv）离线关联。
TX_MANIFEST_HEADER = ["session_id", "source_id", "tx_payload_sha256"]
TX_PAYLOAD_MANIFEST_HEADER = [
    "seq", "session_id", "source_id", "tx_payload_file", "tx_payload_sha256",
]


def read_source_manifest() -> list[dict]:
    p = LINE_A / "results" / "source_manifest_960.tsv"
    lines = [ln.rstrip("\r\n") for ln in p.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    assert header == ["session_id", "source_id", "class_index", "class_name",
                      "dataset_index", "split", "snr_db", "instance",
                      "source_iq_sha256"], f"manifest header mismatch: {header}"
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rows.append({
            "session_id": f[0], "source_id": f[1], "class_index": int(f[2]),
            "class_name": f[3], "dataset_index": int(f[4]), "split": f[5],
            "source_iq_sha256": f[8],
        })
    assert len(rows) == N_TOTAL, f"manifest has {len(rows)} rows (want {N_TOTAL})"
    return rows


def build_tx_payload(original_iq: np.ndarray) -> dict:
    """确定性 TX 适配：1024→53760 循环铺排 → CI16(固定公开幅度合同 S)。逐字复用冻结数学。"""
    tiled = C.cyclic_tile_1024_to_payload(original_iq)
    ci16 = C.quantize_ci16(tiled, C.TX_DIGITAL_SCALE)
    peak_post = float(np.abs(ci16).max())
    return {
        "payload_i16": ci16, "peak_post": peak_post,
        "clip": bool(peak_post >= 32767.0),
    }


def export_session(rows: list[dict], session: str) -> Path:
    out = LINE_B / "tx_payload" / session
    out.mkdir(parents=True, exist_ok=True)
    sess_rows = [r for r in rows if r["session_id"] == session]
    assert len(sess_rows) == N_PER_SESSION, f"{session} has {len(sess_rows)} rows"

    man_lines = ["\t".join(TX_MANIFEST_HEADER)]
    pay_lines = ["\t".join(TX_PAYLOAD_MANIFEST_HEADER)]
    sha_lines = []
    clip_count = 0
    for seq, r in enumerate(sorted(sess_rows, key=lambda r: r["source_id"])):
        bin_path = LINE_A / "inputs" / session / f"{r['source_id']}.bin"
        raw = bin_path.read_bytes()
        assert len(raw) == 2 * C.MODEL_SAMPLES * 4, f"bad .bin size {bin_path}"
        assert C.sha256_bytes(raw) == r["source_iq_sha256"], f"SHA drift {r['source_id']}"
        iq = C.load_tensor_2x1024(bin_path)
        ev = build_tx_payload(iq)
        payload_file = f"{r['source_id']}.i16"
        payload_bytes = ev["payload_i16"].tobytes()
        assert len(payload_bytes) == 2 * C.RF_PAYLOAD_COMPLEX * 2, "bad payload size"
        (out / payload_file).write_bytes(payload_bytes)
        psha = C.sha256_bytes(payload_bytes)
        if ev["clip"]:
            clip_count += 1
        # 3 列板端公共身份 manifest（无类别真值、无文件路径）。
        man_lines.append("\t".join([r["session_id"], r["source_id"], psha]))
        # 5 列 PC 私有 payload manifest（按采集序号 seq 键控，含 tx_payload_file）。
        pay_lines.append("\t".join([
            str(seq), r["session_id"], r["source_id"], payload_file, psha,
        ]))
        sha_lines.append(f"{psha}  {payload_file}")

    (out / "tx_manifest.tsv").write_text("\n".join(man_lines) + "\n", encoding="utf-8")
    (out / "tx_payload_manifest.tsv").write_text("\n".join(pay_lines) + "\n", encoding="utf-8")
    (out / "SHA256SUMS.txt").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    assert clip_count == 0, f"{session} has {clip_count} clipped frames"
    return out


def run_self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(ok)
        print("SELF-TEST %-44s %s%s" % (name, "PASS" if ok else "FAIL",
                                         (" -- " + detail) if detail else ""))

    rows = read_source_manifest()
    check("960 source rows", len(rows) == N_TOTAL, "rows=%d" % len(rows))
    check("4 sessions", sorted({r["session_id"] for r in rows}) == SESSIONS)
    per = {s: sum(1 for r in rows if r["session_id"] == s) for s in SESSIONS}
    check("240/session", all(v == N_PER_SESSION for v in per.values()), str(per))
    # 四轮 dataset_index / source_iq_sha256 零重叠
    by = {s: set() for s in SESSIONS}
    for r in rows:
        by[r["session_id"]].add(r["dataset_index"])
    overlap = any(by[a] & by[b] for a in SESSIONS for b in SESSIONS if a < b)
    check("4-way dataset_index zero overlap", not overlap)
    # TX 数学自洽（单帧）：循环铺排 53760 复 → 交错 CI16 2×53760 int16 = 215040 B
    iq = np.zeros(1024, dtype=np.complex64) + 1.0
    ev = build_tx_payload(iq)
    check("cyclic tile -> 53760 complex (CI16 interleaved)",
          len(ev["payload_i16"]) == 2 * C.RF_PAYLOAD_COMPLEX,
          "len=%d" % len(ev["payload_i16"]))
    check("payload bytes == 215040",
          ev["payload_i16"].tobytes().__len__() == 2 * C.RF_PAYLOAD_COMPLEX * 2)
    check("CI16 int range", np.issubdtype(ev["payload_i16"].dtype, np.integer))
    print("export_finetune_tx_payload SELF_TEST %s (%d/%d)" %
          ("PASS" if all(checks) else "FAIL", sum(checks), len(checks)))
    return 0 if all(checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="导出全部 4 会话")
    ap.add_argument("--session", default="", help="只导出一个会话 S1..S4")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return run_self_test()

    rows = read_source_manifest()
    sessions = SESSIONS if args.all else ([args.session] if args.session else [])
    if not sessions:
        print("need --all or --session S1..S4 (or --self-test)")
        return 2
    for s in sessions:
        out = export_session(rows, s)
        print("FINETUNE_TX_PAYLOAD session=%s frames=%d out=%s" % (s, N_PER_SESSION, out))
    print("FINETUNE_TX_PAYLOAD_DONE sessions=%d" % len(sessions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
