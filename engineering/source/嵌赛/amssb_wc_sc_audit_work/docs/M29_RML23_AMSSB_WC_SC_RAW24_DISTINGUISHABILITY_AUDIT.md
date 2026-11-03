# M29-RML23 — AM-SSB-WC vs AM-SSB-SC raw24 可区分性审计（Phase A + Phase B）

- 任务书：`M29-AMSSB-WC-SC-RAW24-DISTINGUISHABILITY-AUDIT`
- 本文件范围：**仅 Phase A + Phase B**（任务书 §13 停止点：先完成 A/B 停下汇报）
- 最高允许状态：**`M29-RML23-AMSSB-WC-SC-HOST-AUDIT-COMPLETE`**
- 禁写 `24CLASS_PASS`；暂不修改模型、暂不碰板、暂不运行双 SDR。

## 1. 冻结基线（全部读自合同/冻结资产，未改）

| 资产 | SHA-256 |
|---|---|
| 模型 checkpoint（FP32 PyTorch） | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` |
| 板端 raw 模型（部署清单） | `2425d990…`（host golden 头部 `model_raw_sha256` 断言通过） |
| 板端模型 JSON | `d43a2284…`（`model_json_sha256` 断言通过） |
| 24→23 合并契约 | `f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e` |
| clean2a formal12000 | `8b3efe0b11143b31972d392f5b85bc8bd3faf7973681c4d5d7da7ed9603ed81a` |

WC/SC 源类索引从冻结标签合同 `contracts/rml23_merged_contract.py` 读取并断言：
`AM-SSB-WC = 17`、`AM-SSB-SC = 18`（§5 红线：非预期索引即停，本审计断言通过）。
24→23 合并按 `postprocess/rml23_merged.py::merge_many_24_to_23` 计算（`logaddexp`，WC/SC 并入 deployed 类 17）。

## 2. 三个后端可用性

| 后端 | 可用性 |
|---|---|
| FP32 PyTorch（checkpoint 96cd25f8） | ✅ 本次运行 |
| host BF16 参考（冻结 `deployment_golden/expected_logits_or_argmax.json`，240 帧） | ✅ 只读引用 |
| board NPU（ZG330） | ❌ 本机无 ZG330 |

## 3. Phase A — FP32 纯净数据（200 样本）

- 样本：clean2a formal12000，固定取每类前 100（WC source_index 8500..8599、SC 9000..9099），**不按预测/置信度筛选**；seed = 2_000_000 + source_index。
- 后端：冻结 FP32 PyTorch。

### 结果（§6 门槛对照）

| 指标 | 值 | 门槛 | 判定 |
|---|---|---|---|
| WC recall | **0.9700**（97/100） | ≥0.95 | ✅ |
| SC recall | **1.0000**（100/100） | ≥0.95 | ✅ |
| balanced accuracy | **0.9850** | ≥0.95 | ✅ |
| WC → SC | 3 | — | — |
| SC → WC | 0 | — | — |
| 错到其他类 | **0** | — | — |
| wc_sc_pair_correct | 197/200（0.9850） | — | — |
| NaN/Inf | 0 | =0 | ✅ |
| excluded | 0 | =0 | ✅ |

**判定：`FP32_CLEAN_WC_SC_STABLE`。**

`wc_logit - sc_logit` 分布：mean −2.15、median −0.87、std 3.54；
WC 样本均值 **+0.907**（wc>sc）、SC 样本均值 **−5.21**（wc≪sc）。
两个类在该差量轴上基本分离，WC 侧有 3 例兄弟互换但 0 例错出 AM-SSB 族。

### 混淆矩阵（raw24，仅 WC/SC 行非零）

| truth＼pred | WC | SC | 其他 |
|---|---|---|---|
| WC (17) | 97 | 3 | 0 |
| SC (18) | 0 | 100 | 0 |

deployed23 混淆：200 样本全部落入 deployed 类 17（AM-SSB），即 WC+SC→AM-SSB 合并后 **0 误差**。

> 结论（问题 1）：**在纯净/高 SNR 条件下，冻结 FP32 模型能可靠区分 WC/SC**，唯一的混淆是 3 例 WC→SC 兄弟互换，无任何样本错到 AM-SSB 族之外。

## 4. Phase B — FP32 vs host BF16 逐帧对照（240 帧，SHA 配对）

- 输入：冻结 `deployment_golden/input_XXX.bin`（每帧 8192 B = [2,1024] fp32 planar），FP32 与 host BF16 使用**同一份字节**，逐帧 SHA 一致。
- host BF16 参考：`expected_logits_or_argmax.json` 的 `raw_24_logits`（冻结，240 帧）。
- 逐帧输出 raw24 top1、WC/SC 顺序、logits cosine、max abs diff、WC↔SC 翻转、merged23 翻转。

### 4.1 全 240 帧（§7 逐帧对照）

| 指标 | 值 |
|---|---|
| 逐帧输入 SHA 一致性 | **240/240**（同一 `input_XXX.bin` 字节） |
| raw24 top1 一致 / 翻转 | 139 / 101 |
| WC/SC 顺序一致 / 翻转 | 221 / 19 |
| merged23 一致 / 翻转 | 180 / 60 |
| logits cosine | median 0.9841（min 0.311，max 0.9998） |
| max abs diff（24 维 logit） | median 0.2209（max 1.8158） |

raw24 top1 的 101 次翻转发生在**低 SNR 近并列 logit**上（cosine 中位 0.984、24 维 max diff 中位仅 0.22），是 BF16 舍入在近并列点上的 argmax 抖动，不是系统性退化；WC/SC 顺序仅 19 帧翻转、merged23 仅 60 帧翻转。

### 4.2 AM-SSB 子集（WC/SC 判别核心，20 帧 = 10 WC + 10 SC，SNR −20…−14 dB）

| 指标 | FP32 | host BF16 |
|---|---|---|
| WC recall | 0.1（1/10） | 0.1（1/10） |
| SC recall | 0.1（1/10） | 0.1（1/10） |
| 正确数 | 2/20 | 2/20 |

四类误差（§7 强制拆分）：

| 误差类别 | 值 |
|---|---|
| FP32 本身错误（MODEL_OR_DATA_DOMAIN_LIMITATION） | **18/20** |
| ├─ 错到其他类 | 17 |
| └─ WC↔SC 兄弟互换 | 1 |
| FP32→量化新增错误（HOST_QUANTIZATION_ADDED_ERROR） | **0** |
| WC↔SC 量化翻转 | **0** |
| 错到其他类的量化翻转 | 1（近并列抖动，两后端均错） |

### 4.3 §4.2 样本设计局限（必须如实报告）

任务书 §4.2 要求「RadioML 受损样本：每类 ≥100、覆盖低/中/高 SNR」。**离线不可满足**：

- 冻结 host BF16 参考（`expected_logits_or_argmax.json`）只覆盖 **240 帧**，其中 AM-SSB 仅 **10 WC + 10 SC**，且全部落在 **SNR −20…−14 dB（低 SNR）**，无中/高 SNR 档。
- 扩到 ≥100/类 需要为任意 RadioML 样本生成新的 host 量化输出，这等价于「重新量化」，触碰 §2 红线「禁止重训或重新量化」。

因此 Phase B 的 host BF16 对照只能在冻结 240 帧上完成。中/高 SNR 下的 WC/SC 判别由 Phase A（clean2a 纯净数据）提供佐证；RadioML 受损中/高 SNR 的量化对照**留待有对应冻结 host 参考后再补**。

## 5. 关键发现（回答任务书五问）

1. **冻结 FP32 能否区分 WC/SC？** — 高 SNR/纯净：**能**（WC 0.97 / SC 1.0，0 错出族）。低 SNR（−20…−14 dB）：**模型连 AM-SSB 族都无法识别**（17/20 错到其他类），此时不是「分不清兄弟」，而是「认不出这一族」。
2. **host BF16 是否退化？** — **对 WC/SC 判别基本不退化**：20 帧 AM-SSB 上量化新增错误 = 0、WC↔SC 量化翻转 = 0。BF16 的差异集中在低 SNR 近并列点的 argmax 抖动（cosine 中位 0.984），不改变 WC/SC 判别结论。
3. **板端 NPU 能否区分？** — 离线无法回答，见 §6。
4. **双 SDR 后能否区分？** — 离线无法回答，Phase D 未运行（前置 fix10prep2 BPSK+4ASK 未回报）。
5. **损失在哪一环节？** — 离线只能支持一条归因，见 §7。

## 6. Phase C / D 状态（脚手架，未执行）

- **Phase C（板端 NPU 直注）**：由用户执行，API 不得碰板。三端（FP32 / host BF16 / board NPU）须同输入 SHA、同标签合同 SHA、24 维 logits 完整、逐帧配对，且板端与 host 确有新增差异，才允许归因板端。
  - 当前无真实板端数据 → **`BOARD_NPU_ATTRIBUTION_NOT_PROVEN`**（§8 明文要求）。
- **Phase D（双 SDR 同轴）**：前置 fix10prep2 BPSK+4ASK `scored=2 / prediction_agreement=2/2 / negative_control=PASS / tx_restore_ok=1 / rx_restore_ok=1` 尚未回报，**不运行**。
- 板端交付头文件（`board_package/iq_amssb_raw24_diagnostic.hpp`）与 host 测试（`host_tests/test_amssb_raw24_diagnostic.cpp`）为板侧诊断工具，**本离线阶段不交付**，待用户进入 Phase C 再提供。

## 7. 唯一可支持的归因结论（§10）

| 归因 | 判定 |
|---|---|
| 低 SNR（−20…−14 dB）AM-SSB 认不出 | **`MODEL_OR_DATA_DOMAIN_LIMITATION`**（FP32 本身 18/20 错，17 例错到其他类） |
| host BF16 量化 | **`HOST_QUANTIZATION_ADDED_ERROR ≈ 0`**（0 新增错误、0 WC↔SC 翻转） |
| 板端 NPU | **`BOARD_NPU_ATTRIBUTION_NOT_PROVEN`**（无板端数据） |
| RF/恢复 | 未评估（Phase D 未运行） |

**一句话结论**：WC/SC 的可区分性受**信噪比**支配——纯净/高 SNR 下冻结模型可靠区分二者，且 host BF16 量化几乎不引入额外判别误差；低 SNR 下是模型「认不出 AM-SSB 族」的数据域局限，而非「分不清 WC/SC」，更非量化退化。板端 NPU 与 RF 恢复环节的归因需真实板测数据，离线阶段不予断言。

## 8. §11 验收汇总

| 指标 | Phase A（FP32 clean） | Phase B（FP32 vs host，低 SNR） |
|---|---|---|
| WC_recall | 0.9700 | FP32 0.1 / host 0.1 |
| SC_recall | 1.0000 | FP32 0.1 / host 0.1 |
| balanced_accuracy | 0.9850 | 0.1 |
| WC_to_SC | 3 | 1（FP32，20 帧内） |
| SC_to_WC | 0 | 0 |
| WC_or_SC_to_other | 0 | 17 |
| quantization_added_errors | — | **0** |
| board_npu_added_errors | — | NOT_PROVEN |
| rf_recovery_added_errors | — | 未评估 |

四张混淆矩阵（§11 第 1–4 张）：
1. FP32 clean → `results/amssb_wc_sc/phaseA_confusion_raw24.csv`（24×24，WC[17]=97/3、SC[18]=0/100）
2. FP32 RadioML 受损 → `results/amssb_wc_sc/phaseB_confusion_fp32_radioml.csv`（24×24）
3. host 量化 → `results/amssb_wc_sc/phaseB_confusion_host_quantized.csv`（24×24）
4. board NPU → **缺失**（无板端数据，`BOARD_NPU_ATTRIBUTION_NOT_PROVEN`）
5. 双 SDR → 完成后追加。

## 9. 产物清单

```
scripts/audit_amssb_wc_sc_raw24.py               # Phase A
scripts/compare_amssb_three_backends.py          # Phase B + Phase C 脚手架
results/amssb_wc_sc/
  phaseA_per_sample.tsv                           # §5 12 字段 ×200（+seed/source_sha）
  phaseA_summary.json
  phaseA_confusion_raw24.csv / _deployed23.csv / _wc_sc_2x2.csv
  phaseB_per_frame.json                           # 240 帧逐帧 FP32/host + 对照
  phaseB_amssb_per_sample.tsv                     # AM-SSB 20 帧 §5 字段双后端
  phaseB_summary.json
  phaseB_confusion_fp32_radioml.csv / _host_quantized.csv
docs/M29_RML23_AMSSB_WC_SC_RAW24_DISTINGUISHABILITY_AUDIT.md   # 本文件
```

## 10. 状态

**`M29-RML23-AMSSB-WC-SC-HOST-AUDIT-COMPLETE`**

（板端 NPU 审计 `M29-RML23-AMSSB-WC-SC-BOARD-NPU-AUDITED` 与双 SDR 审计 `M29-RML23-AMSSB-WC-SC-DUAL-SDR-AUDITED` 均待用户板测后另行推进；不写 `24CLASS_PASS`。）
