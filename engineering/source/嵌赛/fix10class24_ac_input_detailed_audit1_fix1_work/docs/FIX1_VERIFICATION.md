# FIX1 — 验证记录

纯离线只读验证；未碰板 / SDR / 训练 / 模型 / 恢复器 / 0.100 门限。全部命令在 `fix10class24_ac_input_detailed_audit1_fix1_work/` 下执行。

## 1. 自测

```
python -I scripts/selftest_ac_audit.py
→ SELFTEST 12/12 PASS
```

12 项 = 原 8 项（layout/size、DC/缩放/IQ 相关、单音/双音/噪声 PSD 与带宽、旧 bin 口径 vs 连续区间可区分、缺失/NaN/Inf/身份、同源重复不独立、无 B↔C 混入、基线 7 字段与 threedomain 一致）+ 新 4 项（复单音 lag1=0.9990234375、相位旋转不变、flatness_floor 非度量、严格 wrong-size）。

## 2. 全流水线复算

```
python -I scripts/run_ac_audit.py
→ AUDIT_OK status=M29-RML24-FIX10CLASS24-AC-INPUT-DETAILED-AUDIT1-FIX1-COMPLETE
```

- P1：A HDF5 身份（size+mtime，sha 继承）+ split SHA 复核通过；58 C 张量 layout/finite/SHA 核验通过。
- P2：9600 A 参考帧缓存（seed=20261019，每类每 SNR N=100）。
- P3：58 C 样本特征提取。
- P4：2842 (样本,度量) 行。
- P5：441 (类,度量) 行，对/错 C 值分列 + `n_unique_sources`。
- P6：evidence_table / summary.json / 6 图 / metric_definitions 生成。

（运行中的 `All-NaN slice` / `Degrees of freedom <= 0` RuntimeWarning 属预期：个别类个别度量（如恒定包络下 amp_skew 等）为 NaN，聚合用 nanmedian/nanquantile 忽略，与前版行为一致。）

## 3. 关键不变量核对

| 检查 | 结果 |
|---|---|
| A 参考索引 `a_reference_index.tsv` vs FIX1 前 | **逐字节一致**（`diff -q` → IDENTICAL；未重采、未改索引/58 张量身份） |
| 度量数 | **49**（移除 flatness_floor） |
| 反例复现（vs 复核独立计算） | `bw99_cont` 64QAM pct 0.73 / 128QAM **0.04** / 256QAM 0.68；`amp_roc_mean` 64QAM 0.86 / 128QAM 0.43 / 256QAM **0.98**；`phase_inc_std` 64QAM 0.89 / 128QAM 0.30 / 256QAM 0.57 —— **与 REVIEW_2026-10-19.md 独立计算逐项一致** |
| summary verdict | `AUDIT_COMPLETE_DESCRIPTIVE_ONLY`，`correlation_tested=false`，`causal_attribution=none`，`retracted_conclusions` 6 条 |

## 4. 撤回结论（6 条，已写入 summary.json）

1. 0 of 50 metrics correlates with the 64QAM/128QAM→256QAM collapse
2. class-specific domain difference excluded
3. misclassification attributed to decision-boundary sensitivity
4. all 24 classes show a universal / uniform A↔C shift
5. C effective SNR ~= 25 dB (spectral peak-to-outer-band used as an SNR)
6. all differences are small, unidirectional and within the A reference distribution

## 5. 边界与不越界

- 状态止于 `…-FIX1-COMPLETE`（纯离线审计）；不写 RF_PASS / PROJECT_COMPLETE / ROOT_CAUSE_PROVEN。
- 不因「特征不同」写「特征导致错误」；不赋 C 确定 SNR；不据此建议放宽 0.100 门或微调；不声称已定位单一成因或已排除类特定差异。
