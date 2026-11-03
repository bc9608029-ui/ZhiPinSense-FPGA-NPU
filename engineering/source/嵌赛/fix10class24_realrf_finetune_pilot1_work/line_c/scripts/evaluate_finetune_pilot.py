#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate_finetune_pilot.py — 并行线 C 职责D：微调候选在 S4 密封测试集上的判读。

S4（240 帧真实 RF 采集，sealed，模型/超参确定前不看）固定分母 240：缺帧、门拒、
非有限、无同步、削顶、hard-invalid 一律不剔除。对每个 E0-E3 微调 checkpoint 在 S4
恢复 IQ 张量上跑 Host PyTorch 前向，输出 per-class accuracy / macro-F1 /
end-to-end accuracy，并与数字基线 S4 精度 + E0 冻结基线对比。

最终判级由 judge_realrf_pilot.py 汇总，本脚本只产出 E0-E3 候选的量化分数表。
纯离线；不上板、不发射、不训练。默认 --selftest 用合成夹具自测（不跑真模型）。
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
sys.path.insert(0, str(HERE))
from gt_join import load_ground_truth, BOARD_EMPTY_TRUTH_COLS  # noqa: E402

N_CLASSES = 24
S4_TOTAL = 240
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def read_s4_from_capture(capture_tsv: Path, gt=None) -> list[dict]:
    """从板端采集 TSV（32 字段）取 S4 行，返回 source_id/label/class_index/hard_invalid/
    capture_ok/model_input_sha256。

    有限 tensor 的权威信号是 model_input_sha256（板端只在 tensor 落盘且有限时回填）。
    gt 提供时（真实采集）：断言板端真值列全空并按 source_id 离线回填 class_index/label
    （评审 39e5 Blocker 2）；gt=None（合成夹具）直接读真值列。
    """
    lines = [ln.rstrip("\r\n") for ln in capture_tsv.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    ci = {h: i for i, h in enumerate(header)}
    for k in ("session_id", "source_id", "capture_ok", "hard_invalid", "gate_pass",
              "model_input_sha256") + BOARD_EMPTY_TRUTH_COLS:
        if k not in ci:
            fatal("capture TSV missing col %s" % k)
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if f[ci["session_id"]] != "S4":
            continue
        rec = {
            "source_id": f[ci["source_id"]],
            "capture_ok": f[ci["capture_ok"]],
            "hard_invalid": f[ci["hard_invalid"]],
            "gate_pass": f[ci["gate_pass"]],
            "model_input_sha256": f[ci["model_input_sha256"]],
        }
        for c in BOARD_EMPTY_TRUTH_COLS:
            rec[c] = f[ci[c]]
        rows.append(rec)
    if gt is not None:
        for rec in rows:
            for c in BOARD_EMPTY_TRUTH_COLS:
                if rec.get(c, "") not in ("", None):
                    fatal("board capture leaked ground-truth col %s (%s)"
                          % (c, rec["source_id"]))
            sid = rec["source_id"]
            if sid not in gt:
                fatal("source_id %r not in ground-truth manifest" % sid)
            rec["class_index"] = gt[sid]["class_index"]
            rec["label"] = gt[sid]["class_index"]
    else:
        for rec in rows:
            rec["class_index"] = int(rec["class_index"])
            rec["label"] = int(rec["label"])
    return rows


def _is_sha64(v: str) -> bool:
    if len(v) != 64:
        return False
    try:
        int(v, 16)
    except ValueError:
        return False
    return True


def load_tensor(bin_path: Path) -> np.ndarray:
    b = bin_path.read_bytes()
    if len(b) != 8192:
        fatal("%s is %d bytes (want 8192)" % (bin_path.name, len(b)))
    x = np.frombuffer(b, dtype="<f4").reshape(2, 1024).astype(np.float32)
    if not np.all(np.isfinite(x)):
        fatal("%s has non-finite values" % bin_path.name)
    return x


def merge_predictions(valid_preds: list[int], labels: list[int],
                      has_tensor: list[bool]) -> list[int]:
    """把有效 tensor 的预测按 has_tensor 插回全 240 序列；无 tensor 位填 -1（记错）。

    评审 39e5 Blocker 4：缺 tensor / hard-invalid / no_sync / non-finite 帧 pred=-1，
    计入错误但保留在 240 固定分母里，不得跳过或剔除。
    """
    assert len(has_tensor) == len(labels)
    assert sum(has_tensor) == len(valid_preds)
    preds = [-1] * len(labels)
    vi = 0
    for i, h in enumerate(has_tensor):
        if h:
            preds[i] = valid_preds[vi]
            vi += 1
    return preds


def compute_scores(preds: list[int], labels: list[int]) -> dict:
    n = len(labels)
    assert len(preds) == n
    e2e_correct = sum(1 for p, l in zip(preds, labels) if p == l)
    per_class = {c: {"tp": 0, "fp": 0, "fn": 0} for c in range(N_CLASSES)}
    for p, l in zip(preds, labels):
        if p == l:
            per_class[l]["tp"] += 1
        else:
            per_class[l]["fn"] += 1
            if 0 <= p < N_CLASSES:
                # 越界预测（pred=-1 表示无 tensor）只记 fn 不记 fp，避免崩溃
                per_class[p]["fp"] += 1
    f1s = []
    accs = {}
    for c in range(N_CLASSES):
        tp = per_class[c]["tp"]; fp = per_class[c]["fp"]; fn = per_class[c]["fn"]
        f1s.append((2 * tp / (2 * tp + fp + fn)) if (tp + fp + fn) > 0 else 0.0)
        accs[c] = tp / 10.0  # S4 每类 10
    return {
        "n": n,
        "end_to_end_accuracy": (e2e_correct / n) if n else 0.0,
        "end_to_end_correct": e2e_correct,
        "macro_f1": float(np.mean(f1s)),
        "per_class_accuracy": accs,
    }


def _model_forward(torch, model, tensors: list[np.ndarray]) -> list[int]:
    """批量前向（CPU），返回 argmax 列表。"""
    model.eval()
    preds = []
    x = torch.from_numpy(np.stack(tensors, axis=0))
    with torch.no_grad():
        for i in range(0, len(x), 64):
            logits, _ = model(x[i:i + 64])
            preds.extend(logits.argmax(dim=1).tolist())
    return preds


def selftest() -> int:
    # 合成夹具：20 类各 10 预测，验证固定分母与宏 F1 不剔缺
    import random
    random.seed(0)
    preds = [random.randint(0, N_CLASSES - 1) for _ in range(S4_TOTAL)]
    labels = [i // 10 for i in range(S4_TOTAL)]
    s = compute_scores(preds, labels)
    assert s["n"] == S4_TOTAL
    assert 0.0 <= s["end_to_end_accuracy"] <= 1.0
    assert 0.0 <= s["macro_f1"] <= 1.0
    assert set(s["per_class_accuracy"].keys()) == set(range(N_CLASSES))
    # 完美预测 = 1.0
    s2 = compute_scores(labels, labels)
    assert s2["end_to_end_accuracy"] == 1.0 and s2["macro_f1"] == 1.0
    # 评审 39e5 Blocker 4 反例：pred=-1（无 tensor）不崩溃、记为错误、分母不变。
    bad = labels[:]
    bad[0] = -1   # 类 0 第一帧无 tensor
    s3 = compute_scores(bad, labels)
    assert s3["n"] == S4_TOTAL
    assert s3["end_to_end_correct"] == S4_TOTAL - 1
    assert abs(s3["end_to_end_accuracy"] - (S4_TOTAL - 1) / S4_TOTAL) < 1e-9
    assert s3["per_class_accuracy"][0] == 0.9  # 类 0 只对 9/10
    # merge_predictions：无 tensor 位填 -1 且插回正确。
    merged = merge_predictions([5, 7], [0, 1, 2, 3], [True, False, True, False])
    assert merged == [5, -1, 7, -1], merged
    print("evaluate_finetune_pilot SELFTEST OK: fixed-240 denominator + macro-F1 metrics "
          "+ no-tensor pred=-1 handling")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="合成夹具自测（不跑真模型）")
    ap.add_argument("--capture-tsv", default="", help="板端采集 TSV（32 字段）")
    ap.add_argument("--ground-truth", default="",
                    help="主机真值清单（9 列，source_manifest_960.tsv；默认自动定位）")
    ap.add_argument("--checkpoint", default="", help="微调 checkpoint .pt")
    ap.add_argument("--tensor-dir", default="", help="S4 恢复 IQ 张量目录（<source_id>.bin）")
    ap.add_argument("--out", default=str(LINE_C / "results" / "finetune_scores.json"))
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not (args.capture_tsv and args.checkpoint and args.tensor_dir):
        ap.print_help()
        return 2

    import torch
    sys.path.insert(0, r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1")
    from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402
    from train_finetune_pilot import MODEL_KWARGS  # noqa: E402

    ck = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=N_CLASSES, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()

    gt = load_ground_truth(Path(args.ground_truth)) if args.ground_truth else \
        load_ground_truth()
    rows = read_s4_from_capture(Path(args.capture_tsv), gt=gt)
    if len(rows) != S4_TOTAL:
        fatal("S4 rows=%d != 240" % len(rows))
    if len(set(r["source_id"] for r in rows)) != len(rows):
        fatal("S4 duplicate source_id")

    tdir = Path(args.tensor_dir)
    labels, has_tensor, tensors = [], [], []
    for r in sorted(rows, key=lambda r: r["source_id"]):
        labels.append(r["class_index"])
        p = tdir / f"{r['source_id']}.bin"
        # 有限 tensor 才送入模型；无 tensor / hard-invalid / no_sync / non-finite
        # 记 pred=-1（错误），保留在 240 固定分母。
        ok = _is_sha64(r["model_input_sha256"]) and p.is_file()
        has_tensor.append(ok)
        if ok:
            tensors.append(load_tensor(p))

    valid_preds = _model_forward(torch, model, tensors)
    preds = merge_predictions(valid_preds, labels, has_tensor)
    scores = compute_scores(preds, labels)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("evaluate OK: e2e=%.4f macro_f1=%.4f (%d/%d)" %
          (scores["end_to_end_accuracy"], scores["macro_f1"],
           scores["end_to_end_correct"], scores["n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
