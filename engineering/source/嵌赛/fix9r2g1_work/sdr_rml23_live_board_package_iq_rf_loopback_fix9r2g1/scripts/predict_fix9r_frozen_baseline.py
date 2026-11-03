#!/usr/bin/env python3
"""fix9r2g1 — 生成 R8 冻结基线预测 TSV（确定性推理，无 RF、无标签参与）。

用冻结的 24 类离线模型（checkpoint 96cd25f8…）对 46 个 D2 recovered tensor
（[2,1024] fp32 平面实/虚，RMS≈1.0）执行一次确定性推理：

    frozen_baseline_pred = SOURCE_TO_DEPLOYED[argmax_24class_logits]

该映射恒成立（由 ``rml23_merged.hpp`` 的 ``merge_logits_23`` logaddexp 单调折叠
证明，argmax 保持 24→23 合并映射），故对每个 holdout 输出真实模型预测，**禁止**
用 ``deployed_class`` 填充。

输出 3 列 TSV：``source_index  file_name  frozen_baseline_pred``，供
``build_route_f_fix9r_exact_baseline.py`` 精确合并（按 source_index 严格键匹配）。

本脚本仅在 API 机（有 torch + RML24 工程）运行；不进入板端运行路径。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

# 24→23 AM 合并映射（与 C++ rml23_merged.hpp 的 kSourceToDeployed 一致）。
# source 17 = AM-SSB-WC、source 18 = AM-SSB-SC 均合并到 deployed 17 = AM-SSB。
SOURCE_TO_DEPLOYED = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
]

PRED_HEADER = ["source_index", "file_name", "frozen_baseline_pred"]

# 24 列 D2 manifest 列序（与 build_route_d2_rf_artifacts.py 的 D2_COLS 一致）。
D2_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_d2_manifest(path: Path) -> list[dict[str, str]]:
    """解析 24 列 D2 manifest，fail-closed。返回 holdout 行（保持原序）。"""
    if not path.is_file():
        fail(f"manifest 不存在: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("manifest 为空")
    header = lines[0].rstrip("\n").split("\t")
    if header != D2_HEADER:
        fail(f"manifest 头不匹配 24 列 D2_COLS，得到 {len(header)} 列")
    rows = []
    seen_sample: set[int] = set()
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        fields = line.rstrip("\n").split("\t")
        if len(fields) != len(D2_HEADER):
            fail(f"manifest 第 {lineno} 行 {len(fields)} 列（期望 {len(D2_HEADER)}）")
        row = dict(zip(D2_HEADER, fields))
        sid = int(row["sample_index"])
        if sid in seen_sample:
            fail(f"manifest 重复 sample_index={sid}（第 {lineno} 行）")
        seen_sample.add(sid)
        rows.append(row)
    if not rows:
        fail("manifest 无数据行")
    return rows


def load_recovered_tensor(tensor_dir: Path, file_name: str) -> torch.Tensor:
    """载入 recovered tensor 为 [1,2,1024] fp32（实/虚平面，RMS≈1.0）。"""
    raw = (tensor_dir / file_name).read_bytes()
    n = 2 * 1024
    if len(raw) != n * 4:
        fail(f"{file_name} 大小 {len(raw)}B（期望 {n * 4}B = 8192B）")
    arr = np.frombuffer(raw, dtype="<f4").reshape(2, 1024).copy()
    return torch.from_numpy(arr).unsqueeze(0)  # [1,2,1024]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rml24-root", required=True,
                    help="RML24 工程根目录（含 models/ contracts/ training/）")
    ap.add_argument("--config", default="configs/rml24_base.yaml",
                    help="RML24 配置 yaml（相对 --rml24-root）")
    ap.add_argument("--checkpoint", required=True, help="冻结 checkpoint .pt 路径")
    ap.add_argument("--d2-manifest", required=True, help="24 列 D2 manifest TSV")
    ap.add_argument("--tensor-dir", required=True, help="recovered tensor .f32 所在目录")
    ap.add_argument("--out", required=True, help="输出 3 列预测 TSV 路径")
    ap.add_argument("--expect-holdout", type=int, default=46)
    args = ap.parse_args(argv)

    rml24_root = Path(args.rml24_root).resolve()
    if str(rml24_root) not in sys.path:
        sys.path.insert(0, str(rml24_root))

    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import build_rml24_model
    from training.utils import load_yaml

    # 1) 载入配置 + checkpoint（与 evaluate_rml24._load_model 同路径）。
    config = load_yaml(rml24_root / args.config)
    model_cfg = config["model"]
    ckpt_path = Path(args.checkpoint).resolve()
    if not ckpt_path.is_file():
        fail(f"checkpoint 不存在: {ckpt_path}")
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if ckpt.get("class_names") not in (None, LABEL_ORDER_24) and \
            list(ckpt.get("class_names", [])) != list(LABEL_ORDER_24):
        fail("checkpoint class_names 与 LABEL_ORDER_24 不一致")
    print(f"[infer] checkpoint epoch={ckpt.get('epoch')} model_name={ckpt.get('model_name')}")

    # 2) 构建 24 类模型，严格载入冻结权重，eval + 无梯度（确定性）。
    model = build_rml24_model(24, **model_cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    # 3) 解析 manifest，取 holdout 行。
    rows = parse_d2_manifest(Path(args.d2_manifest))
    holdouts = [r for r in rows if r["split_role"] == "holdout"]
    if len(holdouts) != args.expect_holdout:
        fail(f"holdout 数量 {len(holdouts)}（期望 {args.expect_holdout}）")

    tensor_dir = Path(args.tensor_dir)

    # 4) 逐 holdout 确定性推理，映射到 23 类部署预测。
    out_lines = ["\t".join(PRED_HEADER)]
    seen_src: set[int] = set()
    with torch.inference_mode():
        for r in holdouts:
            src = int(r["source_index"])
            fname = r["recovered_tensor_file"]
            if src in seen_src:
                fail(f"holdout 重复 source_index={src}")
            seen_src.add(src)
            x = load_recovered_tensor(tensor_dir, fname)          # [1,2,1024]
            logits, _ = model(x)                                   # [1,24]
            arg24 = int(torch.argmax(logits[0]).item())
            pred = SOURCE_TO_DEPLOYED[arg24]
            if not (0 <= pred < 23):
                fail(f"source_index={src} 非法 deployed pred {pred}")
            out_lines.append(f"{src}\t{fname}\t{pred}")

    out_path = Path(args.out)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"[infer] wrote {len(holdouts)} predictions -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
