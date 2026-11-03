# M29-RML24-FIX10CLASS24-DUALSDR-NORETRAIN 审计

任务书 **39e5** · 无重训多捕获融合（三阶段：A 真实 RF 审计 / B 诊断导出 / C 冻结融合）。

状态：**`M29-RML24-FIX10CLASS24-DUALSDR-NORETRAIN-STOPPED-FUSION-NO-GO`**

> 停止条件命中：融合在离线历史数据上**无法**明显改善 → **立即停止，不生成板测包**。
> Phase B（dump 开关）与 Phase C（融合模块）代码已实现并单测通过，但**不打包、不做 72 样本前瞻脚本**。

---

## 0. 结论（一句话）

Phase A 已经证明：**即使把生产门限 0.100 完全旁路、24 个样本全部强制分类，也只有 18/24（75%）**，且 6 个错误全部是**确定性同族升阶混淆**（4ASK→8ASK、64QAM→256QAM、128QAM→256QAM、AM-DSB-WC→AM-DSB-SC、OQPSK→32PSK、16PSK→32PSK）。多捕获融合（argmax 多数投票 / logits 平均 / 中位数 / 质量加权）只能聚合**同方向**的重复输出，无法修复**每次捕获都错在同一方向**的确定性混淆。因此融合前提在结构上被否定，按任务书停止条件**不生成板测包**。

## 1. Phase A（真实 RF 审计，已完成，独立任务树 full24-accuracy1）

对归档 `board_capture/full24_accuracy1/rml24_full24_accuracy1_1773372865.tar.gz`（SHA `93ecb5e2…`）的 24 个真实 RF 样本做完整审计。四个强制口径：

| 口径 | 结果 |
|---|---|
| 生产端到端（0.10 门 + 板端 NPU 语义） | **10/24** |
| 门禁内条件（15 个 gated 样本） | **10/15**（coverage 0.625） |
| scalar 强制全覆盖（门旁路） | **18/24** |
| wide-linear 强制全覆盖（门旁路） | **18/24**（scalar↔WL disagree=0） |

结论：`MODEL_RF_ROBUSTNESS_INSUFFICIENT`。**0.100 门完全旁路也只 18/24，错在确定性同族升阶** → NORETRAIN 多捕获融合大概率无法修复。

（完整证据见独立审计 `docs/M29_RML24_FIX10CLASS24_FULL24_ACCURACY1_AUDIT.md` 与记忆 `sdr-m29-fix10class24-full24-accuracy1`。）

## 2. Phase B（诊断导出，已完成 + 单测）

新增 `board_package/iq_fix10class24_noretrain_dump.hpp`（namespace `iqfix10dump`），两个**默认关闭**的加法开关：

- `--dump-raw24-logits`：仅对 **gated** 样本，落盘 NPU 24 维原始 logits + 产生它的精确模型输入。
- `--dump-all-rx`：对**每个**样本（gated 与门拒）落盘完整诊断包（raw RX / 恢复诊断 / 模型输入 / 24 维 logits / gate 结果 / SHA256SUMS）。

每样本布局 `<out_dir>/dump_rx/<source_index>/`：

| 文件 | 内容 | 开关 |
|---|---|---|
| `raw24_logits_f32le.bin` | 24×fp32 NPU logits | gated only |
| `model_input_f32le.bin` | [2,1024] fp32 aligned tensor | gated only |
| `classification_dump.json` | source_index/gate/pred/flags | 两者 |
| `SHA256SUMS.txt` | `SHA256  name` 清单 | gated only |

关键字段契约：
- **gated**：`diagnostic_gate_bypass=0`、`production_gate_modified=0`、`raw24_pred`/`raw24_label`/`logit_finite`/`top1_logit`/`top2_logit`/`margin`/`model_input_sha256`/`raw24_logits_sha256`。
- **门拒**：`diagnostic_gate_bypass=1`、`production_gate_modified=0`、`raw24_pred=-1`、`raw24_logits_present=0`、`model_input_present=0`——**绝不把 host 侧 provisional 输入冒充板端 NPU 结果**。

红线：两开关纯加法；都不传时 runner 与 rxrecovery1（FULL `6fd93f78…`）字节/行为一致。

runner `iq_pc_tx_board_rx_24class_bf16_fix10.hpp` 改动（5 处，见 §4 diff）：
1. `#include "iq_fix10class24_noretrain_dump.hpp"`
2. 解析两开关 + `--out-dir` 强制（缺参 throw）
3. 门拒路径写 refused marker（仅 `--dump-all-rx`）
4. gated 路径写 gated logits（`--dump-raw24-logits` 或 `--dump-all-rx`）

## 3. Phase C（冻结融合，已完成 + 单测）

新增 `board_package/iq_fix10class24_logits_fusion.hpp`（namespace `iqfusion`）。**仅 4 个固定策略**，禁 label/baseline_pred/"哪个正确"动态选策略：

1. argmax 多数投票（`majority_vote`，平票/任何无效 → -1）
2. raw-logits 等权平均（`average_logits`）
3. 每维中位数（`median_logits`）
4. 质量加权平均（`quality_weighted_logits`）

**硬无效先拒**（`is_hard_invalid`）：logits 空/非有限、`rx_clipped`、`sync_valid=false`、`cfo_finite=false`、`cfo_in_range=false`、`has_signal=false`。

**预注册冻结质量权**（仅 label 无关字段，无逐类参数）：
```
w = clamp(corr,0,1) / (1 + payload_training_residual / 0.100)
```
`payload_training_residual > 0.100` 的门拒捕获**可参与诊断融合**，但**绝不**冒充过 0.100 门。

## 4. 红线核验（diff 干净）

`diff -rq` 基线 rxrecovery1 树 vs 新 noretrain1 树，**唯一差异**：

- **新增 4**：`iq_fix10class24_noretrain_dump.hpp`、`iq_fix10class24_logits_fusion.hpp`、`test_fix10class24_noretrain_dump.cpp`、`test_fix10class24_logits_fusion.cpp`
- **修改 3**：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（5 处，全为 §2 所列加法）、`build_host_tests.sh`（+2 构建行）、`run_tests.sh`（+2 运行行）
- 其余差异仅为 `bin/` 编译产物 + `.pyc` 缓存（时间戳）

未碰：BF16 模型 json `28272abc…` / raw `c1781aec…` / checkpoint `96cd25f8…`、24 类标签序、24→23 合同、canonical 三组件、TX -40dB 上限、训练量化资产、RX 增益/带宽默认、0.100 门、最大捕获次数 3、UI/瀑布图/无信号状态机。

## 5. 测试结果

- `build_host_tests.sh` → **BUILD_RC=0**
- `run_tests.sh` → **RUN_RC=0**、**ALL HOST TESTS PASSED**（全套回归）
- 新测试：`test_fix10class24_noretrain_dump` **27/0** + `test_fix10class24_logits_fusion` **30/0**

## 6. 诚实局限

1. **runner 改动是板端专有**：`iq_pc_tx_board_rx_24class_bf16_fix10.hpp` 含 iCraft SDK，host 不可编译；dump/fusion 头本身 host 可编译并单测，但 runner 内 5 处接线**只能由板端构建验证**（我禁碰板）。
2. **融合无法离线实测**：归档均为 1 样本/类，**不存在 3 捕获/类**的多捕获数据；Phase C 只能单测算法，无法做端到端融合改善的实证。
3. **Phase A 已否定前提**：0.100 门旁路也只 18/24 + 6 个确定性同族升阶错误 → 聚合无法修复同方向确定性错误。

## 7. 停止结论

按任务书停止条件（「融合在离线历史数据上都不能明显改善 → 立即停止，不生成板测包」+「融合 <24/24 → NO-GO」）：

- **不生成 FULL/PATCH 板测包**
- **不做 72 样本前瞻验证脚本**
- 交付物止于：Phase B dump 头 + Phase C 融合头 + 2 单测 + runner 加法接线（板端构建验证待用户，如后续决定重开）

（Phase A 独立结论仍成立：`MODEL_RF_ROBUSTNESS_INSUFFICIENT`，0.10 门正确拒真实 RF 失真。）
