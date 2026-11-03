# Fix3 实现报告（FIX3_IMPLEMENTATION_REPORT）

任务：`M29-RML24-FIX10CLASS24-INDEPENDENT-RX-PAYLOAD-FIDELITY-FIX3`
状态：`FIX3_REVIEW_R1_STATIC_DC_MARGINAL_NO_RECOVERY`（纯离线，未上板/未训练；本轮为方法论更正版，撤回前版「必须微调」结论）

---

## 1. 交付物总览

| 类别 | 文件 |
|---|---|
| 共享 | `scripts/fix3_common.py`（冻结身份 + fail-closed I/O）、`scripts/fix3_recovery.py`（字节级复现板端 fix2 恢复） |
| Phase A | `scripts/audit_fix3_inputs.py`、`scripts/classify_fix3_tensors.py` |
| Phase B | `scripts/analyze_fix3_layers.py` |
| Phase C | `scripts/validate_fix3_models.py` |
| Phase C（重估版） | `scripts/reestimate_fix3_r1.py`（每个候选去直流后完整重估 CFO/定时/a/b/residual + 门禁） |
| 判定 | `scripts/judge_fix3.py`（作废）、`scripts/judge_fix3_r1.py`（中性，本轮有效） |
| 自测 | `host_tests/test_fix3_{no_oracle,offset_models,intended_dc_preservation,interpolation_boundaries,r1_reestimate}.py` |
| 文档 | `docs/{ROOT_CAUSE_AUDIT,LIMITATIONS,BOARDTEST_FIX3}.md` |

结果文件（`results/`）：`archive_identity.json`、`integrity_audit.tsv`、`inference_crosscheck.tsv`、`per_class_metrics.tsv`、`confusion_matrix.tsv`、`per_sample_layer_metrics.tsv`、`offset_model_comparison.tsv`、`heldout_validation.tsv`、`cross_session_validation.tsv`、`synthetic_counterexamples.tsv`、`timing_breakdown.tsv`、`summary.json`、`validation_summary.json`、`final_verdict.json`。

---

## 2. 三阶段方法

### Phase A — 只读可信度审计
核验 24 帧原始 `.raw.i16` / 恢复张量 / logits 的完整性（大小、SHA、有限性、解析），并用 Host 后端逐字节复现板端 24 维 logits，确认「坍缩」是恢复后张量本身的问题，而非板端 NPU / 落地 bug。

- 结论：`logit_byte_agree=23/23`，Host 与板端完全一致；1/24 正确，19×AM-SSB-SC + 4×AM-SSB-WC + 1 门拒。

### Phase B — 分层差异定位
逐帧在恢复链各层（对齐 → 去 CFO → 广线性逆 → 分数延迟 → ×1/S）测量 DC/RMS，并与干净 TX 张量比对（corr / best-gain / 残差）。

- 结论：恢复后张量带 ~3.5j 虚假直流（零均值类本应 ~0）；直流在载荷内从 +7.9j 漂到 −6.8j（时变）；广线性矩阵良态（cond≈1.1），偏置增益 ≈1/|a|≈32×（**不是**前版误称的 denom≈0.001 → 10³ 放大）。

### Phase C — 候选修正验证
对 6 个候选偏移模型（M0 基线 / M1 settle-DC / M2 guard-DC / M3 settle+guard / M4 线性漂移 / M5 oracle 上界）重新分类并计分（24 帧分母不变，门拒不剔除）。

- 结论（前版，作废）：全部 1/24，去直流不恢复正确。**更正（review item 1）**：前版每个候选复用修正前参数，导致「全部 1/24」伪象。完整重估后 M1–M5 = 2/24（额外恢复被门拒的 AM-SSB-WC 帧），但仍不恢复 24 类准确率（20/24 仍坍缩 SSB）。跨会话隔离（数字 |a|≈1 → 23/24 vs RF |a|≈0.031 → 1/24）+ 合成反例（同一 DC 被 RF 信道放大约 9–15×，与偏置增益 1/|a|≈32 一致）共同锁定 RF 域根因。

---

## 3. 复现命令（纯离线，主机侧）

```bash
cd F:/嵌赛/fix10class24_independent_rx_payload_fidelity_fix3_work

# Phase A（已产出 results/ 下 Phase A 文件）
python -I scripts/audit_fix3_inputs.py --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 --out-dir results
python -I scripts/classify_fix3_tensors.py --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 --model-dir F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1/model_rml24_bf16 --icraft-run D:/icraft/bin/icraft-run.exe --out-dir results

# Phase B
python -I scripts/analyze_fix3_layers.py --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 --clean-dir F:/嵌赛/fix10class24_waveform_correct_v2_work/replay_out/layers --out-dir results

# Phase C（144 次 Host 推理，约数分钟）
python -I scripts/validate_fix3_models.py --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 --file-capture-dir F:/嵌赛/board_capture/rml24_fix2_v2_file_1773373830_244 --model-dir F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1/model_rml24_bf16 --icraft-run D:/icraft/bin/icraft-run.exe --out-dir results

# 自测
python -I host_tests/test_fix3_no_oracle.py
python -I host_tests/test_fix3_intended_dc_preservation.py
python -I host_tests/test_fix3_interpolation_boundaries.py
python -I host_tests/test_fix3_offset_models.py --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244

# 最终判定
python -I scripts/judge_fix3.py --results-dir results --model-dir F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1/model_rml24_bf16
```

### 本轮更正（FIX3-REVIEW-R1，替换上面的 Phase C 结论）

```bash
# 完整重估（每个候选去直流后重估 CFO/定时/a/b/residual + 门禁；144 次 Host 推理）
python -I scripts/reestimate_fix3_r1.py \
  --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
  --old-capture-dir F:/嵌赛/board_capture/rml24_independent_v2_dual_1773374217_210 \
  --model-dir F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1/model_rml24_bf16 \
  --icraft-run D:/icraft/bin/icraft-run.exe \
  --out-dir results

# 中性判定（本轮有效，替换 final_verdict.json）
python -I scripts/judge_fix3_r1.py --results-dir results \
  --model-dir F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/sdr_rml24_fix10class24_original_radioml_npu_ab1/model_rml24_bf16 \
  --out results/final_verdict_r1.json

# 重估逻辑自测
python -I host_tests/test_fix3_r1_reestimate.py
```

---

## 4. 自测结果

| 测试 | 结果 |
|---|---|
| `test_fix3_no_oracle.py` | PASS（M1–M4 只读静默区，M5 确认读载荷，签名无标签/source_id） |
| `test_fix3_intended_dc_preservation.py` | PASS（24 类静默区≈0；去静默均值不改载荷均值；DC 载波类 |mean|/rms>0.5 保留） |
| `test_fix3_interpolation_boundaries.py` | PASS（锚点 1536/57856；插值有界；退化 settle==guard 精确） |
| `test_fix3_offset_models.py` | PASS（M0 复现板端张量 SHA 24/24；M1–M4 改变张量且有限/1024） |
| `test_fix3_r1_reestimate.py` | PASS 16/16（cond 良态≈1.09、denom 小因 |a| 小、增益 1/|a|≈32 非 1/denom、M4 真逐样本斜坡、静默区只读、M0 复现板端 residual 0.0986） |
| `judge_fix3.py` | 作废（预设负面 + 「10³ 放大」表述） |
| `judge_fix3_r1.py` | 7/7 checks passed，verdict `FIX3_REVIEW_R1_STATIC_DC_MARGINAL_NO_RECOVERY` |

---

## 5. 红线合规声明

- 未上板、未操作 SDR、未发射、未训练、未改冻结模型/标签/波形/幅度合同/门限。
- 偏移模型 M1–M4 只读静默区（settle/guard）估计 DC，**不读原始载荷 IQ / 标签 / source ID / 逐样本 DC·RMS·相位·缩放**；M5（oracle）明确标注为禁用上界，仅诊断。
- 门拒样本（source 18）未从 24 分母剔除；0.100 门未放宽。
- 原始载荷 IQ 仅用于恢复参数冻结后的离线诊断，未进入任何接收算法。
- 未将任何离线结果宣称为 RF_PASS / 项目完成。
