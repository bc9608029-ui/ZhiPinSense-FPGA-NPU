# M29 RML24 fix10class24-full24-accuracy1 — 24 类真实 RF 样本识别审计

状态：**`M29-RML24-FIX10CLASS24-FULL24-ACCURACY1-AUDIT-COMPLETE`**（Phase A 真值审计已完成；
四指标与结论已落 `summary.json`）。

任务：用 rxrecovery1 采集 **24 个 raw24 类各 1 个真实双 SDR 样本**，回答
「最新系统对 24 类真实 RF 样本到底能识别对多少个」。**不修改**生产门限 / 模型 / 恢复器。

---

## 0. 结论（已得出）

归档 `rml24_full24_accuracy1_1773372865.tar.gz`（SHA256 `93ecb5e2…`）24 样本真值审计完成。
结论 = **`MODEL_RF_ROBUSTNESS_INSUFFICIENT`**（决策 B：forced 18/24 < 24/24）。

| 指标 | 值 |
|---|---|
| **生产端到端准确率** | **10/24**（被 0.100 门拒 = 失败） |
| **门禁内条件准确率** | **10/15**（coverage = 15/24 = 0.625） |
| **scalar 强制全覆盖准确率** | **18/24** |
| **wide-linear 强制全覆盖准确率** | **18/24**（`scalar_wide_linear_disagree = 0`） |

15 gated（`RF_PRESERVES_IQ`）/ 9 rejected（`RF_DISTORTS_IQ`）。**6 个错误**（forced 空间，
全部「同族升阶」类混淆）：

| 真实 | 判为 | 路径 |
|---|---|---|
| 4ASK | 8ASK | gated（板端 NPU） |
| 16PSK | 32PSK | rejected（host BF16 强制仍误判） |
| 64QAM | 256QAM | gated |
| 128QAM | 256QAM | gated |
| AM-DSB-WC | AM-DSB-SC | gated |
| OQPSK | 32PSK | gated |

被拒 9 样本 host BF16 强制分类 8/9 对（唯一错 16PSK→32PSK）；logit_finite = 24/24。

> **核心负面事实**：即使把 0.100 门**完全旁路**（强制全覆盖），也只得 18/24 = 75%，且错在
> 确定性「同族升阶」（噪声/失真把低阶调制成像成高阶：4ASK→8ASK、64/128QAM→256QAM、
> AM-DSB-WC→AM-DSB-SC、16PSK/OQPSK→32PSK）。3 次重复捕获的多数投票 / logit 平均大概率**无法**
> 修复这类系统性同向偏移——这构成对 NORETRAIN Phase C「多捕获融合能否明显改善」的强负面证据。
> 被拒样本的「正确」是 host BF16 强制分类，**不代表板端 NPU 过门链可复现**；本表 18/24 是
> forced 全覆盖上界，不是生产端到端。

---

## 1. 基线 + 固定测试参数

- 基线 = rxrecovery1 FULL `6fd93f780770401056fe5c3717cf819238b1c5a0b25ed668425656b3654d6a36`。
- 独立新工作树 `F:\嵌赛\fix10class24_full24_accuracy1_work\`，未改 rxrecovery1 原地。
- 固定参数：TX −40 dB / RX gain 35 dB / RX bw 18 MHz / center 2.4 GHz / 2.56 Msps /
  direct-cable / 24 raw24 类 × 1 样本（full_run）。

---

## 2. 三阶段

- **Phase A**（用户执行，我不碰板）：PC TX 预热全部 24 个 source_index + 板端 RX 24 样本采集。
  命令见 `M29_RML24_FIX10CLASS24_FULL24_ACCURACY1_BOARDTEST_PLAN.md`。
- **Phase B**：对过门样本 → `BOARD_NPU_GATED_CLASSIFICATION`（板端 NPU argmax）。
  对被 0.100 门拒绝的样本 → failed-RX dump → canonical 强制分类导出
  **scalar 与 wide-linear 两套 provisional model input** → 冻结 BF16 离线前向 →
  `HOST_BF16_FORCED_DIAGNOSTIC`。**禁止用标签选择 scalar vs wide-linear，两套都如实报告。**
- **Phase C**：三套指标 + 24×24 混淆 + 逐样本 + 决策。

---

## 3. 三套指标（全部如实报告）

1. **端到端**：`end_to_end_correct/24` —— 被门拒 = 失败（只有过门且 NPU 正确才计数）。
2. **过门**：`gated_correct/scored` + `coverage = scored/24`。
3. **强制全覆盖**：`scalar_forced_correct/24` + `wide_linear_forced_correct/24`
   （过门样本用板端 argmax，被拒样本用 host BF16 强制分类）。

**决策规则**（主决策固定用 wide-linear，因那是 rxrecovery1 实际部署的恢复路径；
scalar 仅作透明对照，绝不用标签挑哪个正确）：
- A) forced 24/24 正确 → `MODEL_RF_ACCURACY_PROVISIONALLY_SUPPORTED`
- B) forced <24/24 → `MODEL_RF_ROBUSTNESS_INSUFFICIENT`
- C) 输入不可重放 → `FULL24_ACCURACY_AUDIT_BLOCKED`

主决策的 `wide_linear` 选择是**先验固定规则**，不因 scalar/wide-linear 哪个得分更高而改；
`summary.json` 同时记录 `scalar_wide_linear_disagree` 供透明披露。

---

## 4. 交付物（5 文件，`results/full24_accuracy1/`）

| 文件 | 内容 |
|---|---|
| `per_sample_results.tsv` | 24 行逐样本（gated/rejected、board/forced 预测、正确性、残差、SHA、层） |
| `raw24_logits.tsv` | 24 维 logits：过门样本无 logits（板端只出 argmax，标 NA）；被拒样本 scalar（+wide_linear 若 applicable） |
| `confusion_24.csv` | 主 forced 答案的 24×24 混淆（gated=板端 argmax，rejected=wide-linear(适用)/scalar） |
| `summary.json` | 三套指标 + 决策 + 逐样本 + 逐类 |
| `M29_RML24_FIX10CLASS24_FULL24_ACCURACY1_AUDIT.md` | 本审计 |

> 诚实限制：板端 runner 只导出 argmax `raw24_pred`，**不导出 24 维 logits**。因此
> `raw24_logits.tsv` 的完整 24 维 logits 仅覆盖被拒（host BF16）样本；过门样本的 logits
> 记为 NA（不可得），但 `raw24_pred` 对全部 24 样本都记录。

---

## 5. 编排器用法

```bash
# (板端采集回传后) 被拒样本 canonical 强制分类导出（WSL）
cd <工作树>
CAPDIR=<回传的 --out-dir 目录> \
  bash host_tools/run_force_classify_full24_accuracy1_sweep.sh

# 校验板端产物（Windows radioconda）
D:\radioconda\python.exe -I scripts\audit_fix10class24_full24_accuracy1.py \
  --phase inventory \
  --captures-dir "<回传目录>" \
  --manifest clean24_smoke\clean24_smoke_manifest.tsv \
  --out-dir results\full24_accuracy1

# host BF16 强制分类 + 三套指标 + 5 交付物
D:\radioconda\python.exe -I scripts\audit_fix10class24_full24_accuracy1.py \
  --phase classify \
  --captures-dir "<回传目录>" \
  --manifest clean24_smoke\clean24_smoke_manifest.tsv \
  --forced-classify-dir results\full24_accuracy1\forced_classify_export \
  --model-dir model_rml24_bf16 \
  --icraft-run D:\icraft\bin\icraft-run.exe \
  --out-dir results\full24_accuracy1
```

`--phase classify` 会 fail-closed 校验冻结 BF16 模型 json `28272abc…` / raw `c1781aec…`，
误跑错模型直接拒绝。

---

## 6. 离线自测（已跑，禁碰板/禁 icraft）

`host_tests/test_fix10class24_full24_accuracy1.py` —— **53 pass / 0 fail**，覆盖：

- `compute_metrics` 三套指标 + A/B/C 决策：全对→SUPPORTED；一处错→INSUFFICIENT；
  被拒端到端计失败但 forced 可恢复；wide-linear 主决策固定（不因 scalar 得分改判）；
  blocked 优先于正确计数；24×24 对角混淆。
- `parse_board_results` / `parse_manifest` fail-closed（源集错/表头错/行数错）。
- `phase_inventory` fail-closed（gated 却有多余 dump / rejected 缺 dump / 缺文件 /
  raw_rx SHA 不符 / JSON 缺字段）。
- `classify` 端到端（合成 captures + export，注入假 host 前向，不碰 icraft-run）：
  5 交付物齐全、指标计数、conclusion、raw24_logits 行数（22 gated + 2 scalar + 1 wl）。

已注册进 `host_tests/run_tests.sh`（`python3 ./test_fix10class24_full24_accuracy1.py`）。

---

## 7. 安全与红线

- 不碰板 / 不 API 碰板 / 不开 SDR / 不 SSH 关网卡。
- 不改 0.100 生产门 / 最大捕获次数 3 / BF16 模型 json·raw / 24 类标签序 / 24→23 合同 /
  canonical 资产 / 恢复器 / runner / TX −40 上限 / RX gain 35·bw 18 默认条件 /
  UI / 瀑布图 / 无信号状态机。
- 不用标签或 baseline_pred 做运行时门禁；不因强制分类正确就放宽门。

---

## 8. 停止条件

报告生成后**暂停**，不自动改门/重训/改恢复器。结论上限即 A 的
`MODEL_RF_ACCURACY_PROVISIONALLY_SUPPORTED`（provisional，非板端 NPU 实测的 24 类
全样本准确率——被拒样本的「正确」是 host BF16 强制分类，不代表板端 NPU 过门链可复现）。
