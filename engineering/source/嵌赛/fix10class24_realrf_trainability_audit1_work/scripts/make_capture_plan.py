#!/usr/bin/env python3
"""make_capture_plan.py -- Phase C / taskbook 10 capture plan (read-only, no board).

Emits the exact next-capture contract needed to lift the trainability verdict from
CURRENT_DATA_INSUFFICIENT_FOR_FINAL_FINETUNING to FULL-FINETUNE-CANDIDATE, per
taskbook 6.2 / 9.4 / 10: >=5 independent real-RF sessions, >=20 independent source
realizations per class, session-level train/val/test split, no cross-session leakage.

No training, no board/SDR/transmit, no gate change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

N_CLASSES = 24
PLAN = {
    "token": "M29-RML24-REALRF-TRAINABILITY-AUDIT1-CAPTURE-PLAN",
    "goal": "lift data sufficiency to FULL-FINETUNE-CANDIDATE (final finetune only)",
    "n_classes": N_CLASSES,
    "sessions": {
        "n_independent_real_rf_sessions": 5,      # >=5, taskbook 6.2
        "session_role_split": "train:val:test = 3:1:1 by SESSION (never within-session)",
        "reason": "single session uses one shared LO/SDR/temperature state; splitting "
                  "within a session leaks that state across train/val/test",
    },
    "source_waveforms": {
        "n_independent_realizations_per_class": 20,   # taskbook 6.2
        "n_total": 20 * N_CLASSES,
        "requirement": "each of the 24 classes gets >=20 DISTINCT source realizations "
                       "(distinct symbol sequences / seeds), not the same 24 bursts "
                       "repeated across sessions",
        "forbidden": "re-using the current 24 tx_package source waveforms as the only "
                     "realizations (they are already consumed as the 2-session audit set)",
    },
    "capture_contract": {
        "points_per_frame": 1024,
        "dtype": "complex64 / [2,1024] float32 model input",
        "per_frame_record": ["source_index", "class_index", "realization_seed",
                             "source_sha256", "raw_rx_sha256", "recovered_tensor_sha256",
                             "training_residual_rel", "gated", "board_pred",
                             "forced_logits_sha256"],
        "forced_export": "gate-rejected frames MUST still export recovered tensor + "
                         "frozen-model logits (diagnostic bypass), never dropped",
        "no_label_driven_selection": "recovery / DC / scale params chosen WITHOUT using "
                                     "labels or per-sample source identity",
    },
    "leakage_controls": {
        "split_unit": "SESSION (a whole session goes to exactly one of train/val/test)",
        "no_realization_duplication": "a source realization may not appear in more than "
                                      "one session split",
        "no_gate_exclusion": "all 24 classes stay in the 24 denominator; no dropping of "
                             "gate-rejected / wrong / non-finite samples",
    },
    "stop_conditions": {
        "proceed_to_final_finetune": ">=5 sessions captured, >=20 realizations/class, "
                                     "residual distribution passes recovery gate at a "
                                     "rate making finetune meaningful (else fix RX first)",
        "do_not_finetune_until": "receive-chain residual no longer systematically "
                                 "exceeds the 0.100 gate (finetuning on residual-limited "
                                 "recoveries reinforces the RX distortion)",
        "authorization_required": "training/finetuning requires explicit user "
                                  "authorization; the standing red line is 不训练",
    },
}

MD = """# M29-RML24-REALRF-TRAINABILITY-AUDIT1 — 采集计划（taskbook §10）

状态：`…-CAPTURE-PLAN-READY`（纯离线，不碰板；采集由用户串口执行）。

## 1. 为什么需要新采集

现有真实 RF 数据 = 2 个双 SDR 会话 × **同一组 24 个源波形**（`fix1v2-waveform-corrected-24waveforms`，
`source_index=class_index+1`，1 波形/类）。跨会话源波形重叠 **24/24** → 无法形成
train/val/test 独立切分；且同一会话内共享 LO/SDR/温度状态，会话内切分会把该状态泄漏
到 train/val/test。故当前数据只够「探测性」结论，不够最终微调（taskbook §4.2/§6.2/§9.4）。

## 2. 采集合同

| 项 | 值 |
|---|---|
| 独立真实 RF 会话数 | **≥ 5**（train:val:test = 3:1:1，按**会话**切分） |
| 每类独立源实现数 | **≥ 20**（24 类 × 20 = 480 独立源波形） |
| 每帧点数 | 1024（[2,1024] f32 模型输入） |
| 每帧记录 | source_index / class_index / realization_seed / source_sha256 / raw_rx_sha256 / recovered_tensor_sha256 / training_residual_rel / gated / board_pred / forced_logits_sha256 |
| 门拒样本 | **必须**仍导出 recovered tensor + 冻结模型 logits（诊断旁路），**不得**丢弃 |

## 3. 泄漏控制

- 切分单位 = **会话**（一整会话只进 train/val/test 之一）。
- 一个源实现不得出现在多个切分。
- 24 类全部留在 24 分母；不剔除门拒/错误/非有限样本。
- 恢复/DC/尺度参数不得用标签或逐样本源身份选择。

## 4. 停止条件（衔接 §12）

- **进入最终微调**：≥5 会话 + ≥20 实现/类，且接收链残差分布不再系统性越过 0.100 门。
- **不得在接收链修好前微调**：在残差受限的恢复上微调会强化接收链失真。
- **训练需用户显式授权**（站立红线「不训练」）。

## 5. 禁止

禁止复用现有 24 个 `tx_package` 源波形作为唯一实现（它们已作为 2 会话审计集消耗）。
"""


def main() -> int:
    out = ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture_plan.json").write_text(json.dumps(PLAN, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "CAPTURE_PLAN.md").write_text(MD, encoding="utf-8")
    print(json.dumps(PLAN, indent=2, ensure_ascii=False))
    print("\nwrote results/capture_plan.json + docs/CAPTURE_PLAN.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
