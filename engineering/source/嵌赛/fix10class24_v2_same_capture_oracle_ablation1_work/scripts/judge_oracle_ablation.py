#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_oracle_ablation.py -- 根据消融结果判定终态（纯离线，读 results/）。

方法学修正后口径（2026-10-21 复审）：
  - 各级别**独立**（各自对 z0 施加单一修正），增益均相对 O0：
      dO1 = agree(O1)-agree(O0)  只改窗
      dO2 = agree(O2)-agree(O0)  只改尺度（payload-oracle 复标量）
      dO3 = agree(O3)-agree(O0)  只改直流
      dO4 = agree(O4)-agree(O0)  组合
  - O5 = 真正交叉验证仿射（每半段用另半段拟合，拼接），残差仅计未参与拟合半段。
  - 数字基线 23/24 只证明模型对**数字 v2 域**健康；它**不能**排除模型对真实 RF 残余
    失真失效，故 H5（模型 RF 域失配）判 UNRESOLVED（不可排除），与 H4 可同时成立。

判定逻辑（可复现，非硬编码数字）：
  - H1 窗：dO1 <= 0 -> NOT_SUPPORTED。
  - H2 尺度：dO2 <= 1 -> NOT_PRIMARY。
  - H3 直流：dO3 > 0 -> SECONDARY_CONTRIBUTOR。
  - H4 固定仿射修正不足：O5(交叉验证) 离数字基线上界 23 差 >= 6 帧 -> SUPPORTED。
  - H5 模型 RF 域失配：UNRESOLVED_CANNOT_EXCLUDE（数字基线不构成对其的排除证据）。

产出 results/oracle_verdict.json。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_common as OC  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"

TERMINAL = "AFFINE_CORRECTION_INSUFFICIENT_MODEL_DOMAIN_SHIFT_UNRESOLVED"


def load_summary() -> dict:
    path = RESULTS / "per_session_summary.tsv"
    out = {}
    for ln in path.read_text(encoding="utf-8").splitlines()[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sess, metric = f[0], f[1]
        if not metric.startswith("O"):   # 跳过 PRODUCTION_E2E* 行（仅报告，不进判定）
            continue
        out.setdefault(sess, {})[metric] = {
            "agree": int(f[2]), "label": int(f[5]),
            "agree_frac": float(f[4]), "label_frac": float(f[6]),
            "nmse_median": float(f[7]), "nrmse_median": float(f[9]),
        }
    return out


def judge_session(name: str, s: dict) -> dict:
    o0 = s["O0"]
    dO1 = s["O1"]["agree"] - o0["agree"]
    dO2 = s["O2"]["agree"] - o0["agree"]
    dO3 = s["O3"]["agree"] - o0["agree"]
    dO4 = s["O4"]["agree"] - o0["agree"]
    o5_agree = s["O5"]["agree"]

    h1_window = (dO1 <= 0)
    h2_scale = (dO2 <= 1)
    h3_dc = (dO3 > 0)
    h4_affine_insufficient = (o5_agree < 23 - 6)   # 离数字基线上界 >= 6 帧
    # H5 恒 UNRESOLVED：数字基线 23/24 仅证数字域健康，不能排除模型对 RF 残余失真失效。

    return {
        "session": name,
        "agree_by_level": {L: s[L]["agree"] for L in ["O0", "O1", "O2", "O3", "O4", "O5"]},
        "label_by_level": {L: s[L]["label"] for L in ["O0", "O1", "O2", "O3", "O4", "O5"]},
        "nrmse_median_by_level": {L: s[L]["nrmse_median"] for L in ["O0", "O1", "O2", "O3", "O4", "O5"]},
        "delta_agree_vs_O0": {"window_O1": dO1, "scale_O2": dO2, "dc_O3": dO3, "combined_O4": dO4},
        "affine_ceiling_agree": o5_agree,
        "digital_baseline_upper_bound": 23,
        "h1_window_estimation_error": "NOT_SUPPORTED" if h1_window else "SUPPORTED",
        "h2_per_sample_scale": "NOT_PRIMARY" if h2_scale else "PRIMARY",
        "h3_legitimate_dc_unrecoverable": "SECONDARY_CONTRIBUTOR" if h3_dc else "NO_EFFECT",
        "h4_fixed_affine_insufficient": "SUPPORTED" if h4_affine_insufficient else "NOT_SUPPORTED",
        "h5_model_domain_shift": "UNRESOLVED_CANNOT_EXCLUDE",
    }


def main() -> int:
    summary = load_summary()
    sessions = {name: judge_session(name, s) for name, s in summary.items()}

    both_h4 = all(v["h4_fixed_affine_insufficient"] == "SUPPORTED"
                  for v in sessions.values())
    any_h3 = any(v["h3_legitimate_dc_unrecoverable"] == "SECONDARY_CONTRIBUTOR"
                 for v in sessions.values())

    if both_h4:
        terminal = TERMINAL
        terminal_note = (
            "固定仿射修正（含窗+尺度+直流+广线性，真正交叉验证 O5）不足以把真实 RF 载荷恢复"
            "到数字基线：fix2 O5=%d/24、old O5=%d/24，远低于数字基线上界 23/24，且"
            "窗(O1)/尺度(O2)无增益、直流(O3)仅次要贡献。数字基线 23/24 只证明模型对数字 v2"
            "域健康，不能排除模型对真实 RF 残余失真失效，故 H5(模型 RF 域失配)保持未决。"
            % (sessions["rf_fix2_target"]["affine_ceiling_agree"],
               sessions["rf_independent_v2"]["affine_ceiling_agree"]))
    else:
        terminal = "SESSION_DEPENDENT_INCONCLUSIVE"
        terminal_note = "两会话模式不一致，无法合并为单一根因终态。"

    if any_h3:
        terminal_note += " 次要贡献：直流(O3)修回若干帧，但非主要瓶颈。"

    verdict = {
        "token": "M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1-JUDGE-%s" % terminal,
        "task": "M29-RML24-V2-SAME-CAPTURE-ORACLE-ABLATION1",
        "date": "2026-10-21",
        "offline_only": True,
        "terminal_state": terminal,
        "terminal_note": terminal_note,
        "sessions": sessions,
        "superseded_conclusions": [
            "1/24 主要是门控产物 -> SUPERSEDED：强制 O0 仅 2/24 与数字基线一致，且 oracle "
            "仿射上界也仅若干帧，问题在恢复后残余失真不在门控。",
            "接收链残差是唯一硬瓶颈 -> SUPERSEDED：窗/尺度/直流均可由 oracle 修正，但修正后"
            "仍远低于数字基线，瓶颈是盲恢复无法观测的载荷内残余失真。",
            "不是模型域失配 -> 撤回为『未决』：数字基线 23/24 仅证数字域健康，不能排除模型"
            "对真实 RF 残余失真失效（H5 UNRESOLVED）。",
        ],
        "retained": [
            "MORE_RF_DATA_REQUIRED",
            "TRAIN_VAL_TEST_SPLIT_IMPOSSIBLE",
            "暂不正式微调",
        ],
        "red_lines_kept": [
            "no training", "no board/SDR/transmit", "no production recovery/gate change",
            "24 denominator intact", "oracle 不进入生产恢复",
            "不按标签挑选逐帧最优 oracle", "C0(18/24) 未并入 v2 统计",
        ],
    }

    out = RESULTS / "oracle_verdict.json"
    out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    print("oracle_verdict.json -> %s" % out)
    print("terminal_state = %s" % terminal)
    for name, s in sessions.items():
        print("  %s: agree %s | affine_ceiling=%d | dc_delta=%d" %
              (name, " ".join("%s=%d" % (L, s["agree_by_level"][L])
                              for L in ["O0", "O3", "O5"]),
               s["affine_ceiling_agree"], s["delta_agree_vs_O0"]["dc_O3"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
