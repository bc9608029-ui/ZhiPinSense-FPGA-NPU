#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_oracle_ablation.py -- Phase 2：O0-O5 oracle 消融（纯离线，逐帧均匀施加）。

每帧对每个会话：
  - 复现 O0（生产恢复，byte-exact）；
  - 用原始载荷 x_true 作 oracle，**各自独立**施加单一修正（非累积）：
      O1 = 只改窗（循环对齐）
      O2 = 只改尺度（payload-oracle 复标量 LS；非 manifest 尺度）
      O3 = 只改直流（去虚假 DC，保留合法 DC）
      O4 = 窗+尺度+直流 组合
      O5 = 真正交叉验证仿射（前 512 用后 512 拟合、后 512 用前 512 拟合，拼接）
  - 冻结 BF16 主机推理各张量，记录预测、与数字基线一致、标签正确。

口径（重要，区分不混淆）：
  - 生产 e2e（板端门控实际输出）= gate_pass / label_correct / agree，单独报告；
  - 强制 O0（主机 BF16 强制分类 z0）= 消融基线，与 O1-O5 同口径（均强制分类）。

指标：主 = 与 v2 数字基线一致 /24；次 = 标签正确 /24（上界 23/24）。
残差统一输出 NMSE=|z-x|²/|x|² 与 NRMSE=sqrt(NMSE)（参考归一化），
**不可**与生产门 training_residual_rel（训练段、接收能量归一化）直接比较。

oracle 一律均匀施加，不按标签挑选逐帧最优方案，不进入生产恢复。

产出 results/per_sample_ablation.tsv, per_session_summary.tsv,
confusion_matrices/, correction_regression_list.tsv。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_common as OC  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"
INFER_WORK = RESULTS / "infer_work"
CM_DIR = RESULTS / "confusion_matrices"

# 独立级别（各自对 z0 施加单一修正；O4 组合；O5 交叉验证仿射）
LEVELS = ["O0", "O1", "O2", "O3", "O4", "O5"]


def classify(z: np.ndarray) -> int:
    return OC.argmax_pred(OC.host_infer(OC.tensor_to_bytes(z), INFER_WORK))


def main() -> int:
    if not OC.ICRAFT_RUN.is_file():
        raise SystemExit("icraft-run not found: %s" % OC.ICRAFT_RUN)
    RESULTS.mkdir(parents=True, exist_ok=True)
    CM_DIR.mkdir(parents=True, exist_ok=True)
    INFER_WORK.mkdir(parents=True, exist_ok=True)

    sample_rows = []
    summary = {}
    prod_e2e = {}
    regression = []
    cm = {}   # (session, level) -> 24x24 confusion

    for sess in OC.SESSIONS:
        name = sess["name"]
        chain = sess["chain"]
        cap = Path(sess["capture_dir"])
        board = OC.load_board_rows(sess["capture_dir"])

        per_level = {L: {"agree": 0, "label": 0, "n": 0,
                         "nmse": [], "nrmse": []} for L in LEVELS}
        cm_sess = {L: np.zeros((24, 24), dtype=int) for L in LEVELS}
        gate_pass = correct = agree_e2e = 0

        for sid in range(1, 25):
            br = board[sid]
            ci = int(br["class_index"])                       # 0..23
            true_label = ci
            base_pred = OC.DIGITAL_BASELINE_PRED[sid - 1]     # 数字基线预测

            rx_full = OC.read_raw_complex(cap / ("%d.raw.i16" % sid))
            off, _ = OC.locate_preamble(rx_full, len(rx_full) - OC.K_TOTAL)
            rx_burst = rx_full[off:off + OC.K_TOTAL].copy()

            if chain == "fix2":
                est = OC.FIX2.estimate_public_reference_fix2(rx_burst)
            else:
                est = OC.IRX.estimate_public_reference(rx_burst)
            z0 = OC.recover_o0(chain, rx_burst, est)
            x = OC.true_waveform(sid)

            # ---- 独立 oracle 级别（各自对 z0 施加单一修正，非累积） ----
            _, z1 = OC.cyclic_align(z0, x)              # O1 只改窗
            z2 = OC.apply_scale(z0, x)                  # O2 只改尺度
            z3 = OC.apply_dc(z0, x)                     # O3 只改直流
            z4 = OC.apply_combined(z0, x)               # O4 窗+尺度+直流
            z5, _, _ = OC.apply_affine_crossval(z0, x)  # O5 交叉验证仿射

            tensors = {"O0": z0, "O1": z1, "O2": z2, "O3": z3, "O4": z4, "O5": z5}
            preds = {}
            for L in LEVELS:
                preds[L] = classify(tensors[L])

            # ---- 生产 e2e（板端门控实际输出，与强制 O0 分开统计） ----
            is_gated = int(br["gated"]) == 1
            board_pred = int(br["board_pred"])
            gate_pass += is_gated
            correct += (board_pred == true_label)
            agree_e2e += (board_pred == base_pred)

            row = [name, sid, ci, br["class_name"], base_pred,
                   int(is_gated), br["training_residual_rel"], board_pred]
            for L in LEVELS:
                p = preds[L]
                agree = int(p == base_pred)
                lab = int(p == true_label)
                nmse, nrmse = OC.nmse_nrmse(tensors[L], x)
                per_level[L]["agree"] += agree
                per_level[L]["label"] += lab
                per_level[L]["n"] += 1
                per_level[L]["nmse"].append(nmse)
                per_level[L]["nrmse"].append(nrmse)
                cm_sess[L][true_label, p] += 1
                row += [p, agree, lab, round(nmse, 6), round(nrmse, 6)]
            sample_rows.append(row)

            # 回归表：修正改变预测（O0 宿主预测 vs 各修正）
            p0 = preds["O0"]
            for L in ["O1", "O2", "O3", "O4", "O5"]:
                if preds[L] != p0:
                    regression.append([
                        name, sid, ci, br["class_name"], base_pred,
                        L, p0, preds[L],
                        "imp" if preds[L] == base_pred else "reg",
                    ])

        prod_e2e[name] = {
            "gate_pass": "%d/24" % gate_pass,
            "label_correct": "%d/24" % correct,
            "agree_baseline": "%d/24" % agree_e2e,
        }

        # 汇总（每级：agree / label / NMSE / NRMSE）
        summary[name] = {L: {
            "agree": per_level[L]["agree"],
            "agree_frac": per_level[L]["agree"] / 24.0,
            "label": per_level[L]["label"],
            "label_frac": per_level[L]["label"] / 24.0,
            "nmse_median": float(np.median(per_level[L]["nmse"])),
            "nmse_max": float(np.max(per_level[L]["nmse"])),
            "nrmse_median": float(np.median(per_level[L]["nrmse"])),
            "nrmse_max": float(np.max(per_level[L]["nrmse"])),
        } for L in LEVELS}

        # 混淆矩阵（O0 与 O5 重点）
        for L in ["O0", "O5"]:
            out = CM_DIR / ("%s_%s.tsv" % (name, L))
            with open(out, "w", encoding="utf-8") as f:
                f.write("\t" + "\t".join(OC.LABEL_ORDER_24) + "\n")
                for r in range(24):
                    f.write(OC.LABEL_ORDER_24[r] + "\t" +
                            "\t".join(str(cm_sess[L][r, c]) for c in range(24)) + "\n")

    # 写 per_sample_ablation.tsv
    header = (["session_id", "source_index", "class_index", "class_name",
               "digital_baseline_pred", "production_gate", "production_residual_rel",
               "board_pred"] +
              [c for L in LEVELS
               for c in ("%s_pred" % L, "%s_agree" % L, "%s_label" % L,
                         "%s_nmse" % L, "%s_nrmse" % L)])
    with open(RESULTS / "per_sample_ablation.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for r in sample_rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    # 写 per_session_summary.tsv（含生产 e2e 单独段 + 强制 O0-O5 段）
    with open(RESULTS / "per_session_summary.tsv", "w", encoding="utf-8") as f:
        f.write("session_id\tmetric\tagree\tn\tagree_frac\tlabel\tlabel_frac"
                "\tnmse_median\tnmse_max\tnrmse_median\tnrmse_max\n")
        for name in [s["name"] for s in OC.SESSIONS]:
            pe = prod_e2e[name]
            f.write("%s\tPRODUCTION_E2E\t%s\t24\t-\t%s\t-\t-\t-\t-\t-\n" %
                    (name, pe["agree_baseline"], pe["label_correct"]))
            f.write("%s\tPRODUCTION_E2E_GATE\t%s\t24\t-\t-\t-\t-\t-\t-\t-\n" %
                    (name, pe["gate_pass"]))
            for L in LEVELS:
                d = summary[name][L]
                f.write("%s\t%s\t%d\t%d\t%.6f\t%d\t%.6f\t%.6g\t%.6g\t%.6g\t%.6g\n" %
                        (name, L, d["agree"], 24, d["agree_frac"],
                         d["label"], d["label_frac"], d["nmse_median"], d["nmse_max"],
                         d["nrmse_median"], d["nrmse_max"]))

    # 写 correction_regression_list.tsv
    with open(RESULTS / "correction_regression_list.tsv", "w", encoding="utf-8") as f:
        f.write("session_id\tsource_index\tclass_index\tclass_name\tdigital_baseline_pred"
                "\tlevel\to0_pred\tcorrected_pred\tdirection\n")
        for r in regression:
            f.write("\t".join(str(x) for x in r) + "\n")

    # 中间 summary JSON（终态由 judge 填写）
    with open(RESULTS / "ablation_summary.json", "w", encoding="utf-8") as f:
        json.dump({"production_e2e": prod_e2e, "oracle_levels": summary},
                  f, indent=2, ensure_ascii=False)

    print("ablation complete -> %s" % RESULTS)
    for name in [s["name"] for s in OC.SESSIONS]:
        print("  %s PRODUCTION_E2E: gate=%s label=%s agree=%s" %
              (name, prod_e2e[name]["gate_pass"], prod_e2e[name]["label_correct"],
               prod_e2e[name]["agree_baseline"]))
        line = []
        for L in LEVELS:
            line.append("%s:agree=%d,label=%d,nrmse=%.3f" %
                        (L, summary[name][L]["agree"], summary[name][L]["label"],
                         summary[name][L]["nrmse_median"]))
        print("    " + "  ".join(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
