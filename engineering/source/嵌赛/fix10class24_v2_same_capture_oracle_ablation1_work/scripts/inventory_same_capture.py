#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventory_same_capture.py -- Phase 0：逐帧完整性/溯源清单（纯离线只读）。

产出 results/provenance.tsv：每帧会话、源身份、标签、raw/burst/payload/生产张量
的路径与 SHA、生产门/残差/预测、数字基线预测。任何 SHA 不匹配即 fail-closed 停止。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_common as OC  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "results"

HEADER = [
    "session_id", "source_index", "class_index", "class_name",
    "raw_rx_file", "raw_rx_sha256",
    "burst_off", "burst_sha256", "payload_sha256",
    "production_tensor_file", "production_tensor_sha256",
    "production_gate", "production_residual", "production_pred",
    "production_cfo", "production_tau",
    "digital_baseline_pred",
]


def burst_bytes(rx_full: np.ndarray, off: int, start: int, count: int) -> bytes:
    """rx_full 为 complex128；重建其 int16 切片字节（原始交错 i16 的切片）。"""
    # 从 complex 回到交错 i16（lround），与 quantize 一致但只用于 SHA 溯源
    inter = np.empty(count * 2, dtype="<i2")
    seg = rx_full[start:start + count]
    inter[0::2] = C_lround(seg.real).astype("<i2")
    inter[1::2] = C_lround(seg.imag).astype("<i2")
    return inter.tobytes()


def C_lround(x: np.ndarray) -> np.ndarray:
    return np.where(x >= 0, np.floor(x + 0.5), np.ceil(x - 0.5))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "provenance.tsv"
    rows = []
    for sess in OC.SESSIONS:
        board = OC.load_board_rows(sess["capture_dir"])
        cap = Path(sess["capture_dir"])
        for sid in range(1, 25):
            br = board[sid]
            raw_file = "%d.raw.i16" % sid
            raw_bytes = (cap / raw_file).read_bytes()
            raw_sha = OC.sha256_bytes(raw_bytes)
            if raw_sha != br["raw_rx_sha256"]:
                raise SystemExit("raw SHA mismatch %s sid=%d" % (sess["name"], sid))

            rx_full = OC.read_raw_complex(cap / raw_file)
            off, _ = OC.locate_preamble(rx_full, len(rx_full) - OC.K_TOTAL)
            rx_burst = rx_full[off:off + OC.K_TOTAL]

            # burst / payload 的 int16 切片 SHA（溯源，非恢复）
            inter = np.frombuffer(raw_bytes, dtype="<i2")
            b_sha = OC.sha256_bytes(inter[2 * off:2 * (off + OC.K_TOTAL)].tobytes())
            p_sha = OC.sha256_bytes(
                inter[2 * (off + OC.K_PAYLOAD_START):
                      2 * (off + OC.K_PAYLOAD_START + OC.K_PAYLOAD)].tobytes())

            # 生产张量文件 + SHA（须与 model_input_sha256 一致）
            tensor_file = "%d.recovered.tensor.bin" % sid
            tensor_sha = OC.sha256_bytes((cap / tensor_file).read_bytes())
            if tensor_sha != br["model_input_sha256"]:
                raise SystemExit("tensor SHA mismatch %s sid=%d" % (sess["name"], sid))

            tau = br.get("fractional_timing", "")
            rows.append([
                sess["name"], sid, int(br["class_index"]), br["class_name"],
                raw_file, raw_sha,
                off, b_sha, p_sha,
                tensor_file, tensor_sha,
                br["gated"], br["training_residual_rel"], br["board_pred"],
                br["coarse_cfo_hz"], tau,
                str(OC.DIGITAL_BASELINE_PRED[sid - 1]),
            ])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    print("provenance.tsv written: %d rows -> %s" % (len(rows), out_path))
    print("sessions: %s" % ", ".join(s["name"] for s in OC.SESSIONS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
