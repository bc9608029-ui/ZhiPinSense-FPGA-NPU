# M29 RML23 — 24 类部署可行性重评（Part 0，只读）

> 状态：**只读审查**（唯一生成物=本报告）。不改任何生产/测试/包/权重/标签/MEMORY，不碰板、不重训、不量化、不打包。
> 日期：2026-10-17
> 任务来源：fix10class24_dualsdr_prep2 之 Part 0（「先只读重评 24 类可行性」）
> 覆盖两条路径（按用户要求分开）：**① 纯净 RadioML 信号**（离线可答）；**② 双 SDR RadioML 信号**（未证，被板测失败阻塞）。

---

## 0. 结论（TL;DR）

**24 类直接部署（保留 24 原始类、不合并）在当前证据 + 当前工具链（iCraft 3.39）下不可行，且不可行性独立于信号路径（纯净 vs 双 SDR）。**

- 唯一且决定性的拦路虎在**量化域**：AM-SSB-SC 与 AM-SSB-WC 的 logits 是 24 类里最接近的一对，24 维**输出层 INT8 量化**抹平了这个微小边界 → AM-SSB-SC 崩塌到 WC（vendor 全 INT8 recall **0.078125 = 5/64**），且 **SNR 无关**（@SNR≥12 仍 0.1）。
- 唯一可能补救的 QAT 已被 E0 硬门禁否决：iCraft 3.39 **无任何 QAT 接口**（无 Q/DQ 算子、量化阶段必重新校准覆盖 scale）。
- 已评估的 4 个量化变体里，最优的 expA_bf16_head（分类头 op179→BF16）也只是把 SC→WC 从 39/64 降到 **34/64**（仍丢一半多），24 类 AM-SSB-SC 仍不可用。

**两条路径的分野在「叠了几层不可行」：**

| 路径 | 模型域（FP32 高 SNR） | 量化域（INT8） | RF 链路 | RF 泛化 | 24 类裁决 |
|---|---|---|---|---|---|
| ① 纯净 RadioML | ✅ 已解（raw24 **0.99325**，WC 0.97/SC 1.0） | ❌ SC 崩塌 0.078 | 不涉及 | 不涉及 | **不可行（量化域）** |
| ② 双 SDR RadioML | （同 24 类模型） | ❌ 同上 | ❌ fix10prep3 未过 | ❌ 三后端 QPSK→QAM | **不可行（量化+RF 三重）** |

**结论：23 合并（WC/SC→AM-SSB 类 17）仍是当前唯一可离线交付的路径；24 类直接部署需要一条当前不存在的前提（输出层/激活高精度化或可用 QAT），不能宣称可行。**

---

## 1. 24 类直接部署的失败链（证据回顾）

### 1.1 模型域：AM-SSB-SC 是 24 类里最弱之一（但非不可分）

- 最终盲测 24 类 per-class：AM-SSB-SC **0.5383**（24 类倒数第 4）、AM-SSB-WC 0.6461；最弱 5 类 256QAM 0.5176 / 64QAM 0.5291 / 128QAM 0.5308 / AM-SSB-SC 0.5383 / 16PSK 0.5408。
- 但**高 SNR 纯净下 WC/SC 可分**：Phase A clean WC 0.9700 / SC 1.0000 / 错出族 0（`FP32_CLEAN_WC_SC_STABLE`）。
- 低 SNR 的失败是「认不出 AM-SSB 族」（17/20 错到其他类），**不是 WC↔SC 混淆**（仅 1/20 兄弟互换）。

→ 模型域本身在**高 SNR/纯净**下不构成 24 类部署的障碍；障碍在下一步量化把它放大成崩塌。

### 1.2 量化域：输出层 INT8 抹平近邻 logits → SC 崩塌（决定性）

来源 `artifacts/m29_quantized_min_class_collapse_analysis.json`（24 类 1536 集，per-class 64，seed 2028）：

| 量化方式 | AM-SSB-SC recall | @SNR≥12 | 说明 |
|---|---|---|---|
| fp32 | 0.515625（33/64） | 0.85 | 基线 |
| fake_int8（**仅权重**） | 0.453125（29/64） | 0.8 | **不崩塌** |
| **vendor_int8（全量）** | **0.078125（5/64）** | **0.1** | **崩塌** |

vendor 全 INT8 的 SC 预测分布（64 样本）：WC=39 / OOK=14 / SC=5 / BPSK=3 / 4ASK=2 / 8ASK=1。

**归因（逐字）**：`AM-SSB-SC collapse is introduced by activation + output-layer INT8 quantization (weights-only fake-INT8 does NOT collapse it). Collapse is SNR-independent (present at SNR>=12), systematic... Most suspicious point = 24-dim output-layer INT8 quantization erasing the small near-tied logits of AM-SSB-SC vs AM-SSB-WC.`

→ **崩塌是「激活 + 输出层」INT8 的共同作用，权重-only 量化不崩。** 这意味着：只要 NPU 需要 INT8 激活 + INT8 输出层，24 类 AM-SSB-SC 就必然崩塌，与 IQ 是否纯净、是否走 RF 无关。

### 1.3 QAT 补救：E0 硬门禁 FAILED，无接口

来源 `docs/M29_PHASE_E0_QAT_FEASIBILITY_GATE.md`：

- iCraft 3.39 **不接受**带 Q/DQ 节点的 ONNX（支持算子清单无 QuantizeLinear/DequantizeLinear）。
- 量化阶段对 INT8 **强制前向校准并重新计算全部 scale（含输入层）**，无「保留/导入已学习 scale」开关。
- 判决（E0.3 停止条件触发）：`iCraft 会重新校准并覆盖输入 scale → QAT 无法解决输入端信息丢失 → 停止`。
- 唯一出路 = 向 FMSH 索取 SDK 缺失的《QAT 用户手册》+ 配套工具，且须先验证其输入 scale 保留路径。**在取得前，PTQ 与 QAT 均告尽。**

### 1.4 已评估量化变体：全崩或半崩（24 类口径）

来源 `artifacts/m29_rml23_merged_candidate_comparison.json` 的 `amssb_diagnostics`（24 类输出层误路由，amssb_true_total=128=64WC+64SC）：

| 候选 | SC→WC（/64） | WC→SC（/64） | 24 类 AM-SSB-SC 可用性 |
|---|---|---|---|
| fp32 | 16 | 14 | 可（模型域基线） |
| d384_int8 | 39 | 1 | 不可（SC 几乎全崩到 WC） |
| **expA_bf16_head（唯一全门禁过）** | **34** | 10 | **仍不可（丢一半多）** |
| dra384_int8 | 36 | 2 | 不可 |

→ 最优候选 expA_bf16_head 仅把分类头改 BF16，24 类 SC→WC 仍 34/64；即便不算 SC→其他类的误路由，SC recall 上限也仅 ~0.47。**没有评估过任何「全网络 BF16 / 输出层 FP32」变体，当前 NPU 也不支持。**

---

## 2. 路径一：纯净 RadioML 信号（离线可答）

- **模型域**：✅ 已解。clean2a formal12000 FP32：raw24 **0.99325**、deployed23 0.99450、min recall 0.956(OQPSK)、top-2 0.99958；高 SNR WC 0.97 / SC 1.0。
- **量化域**：❌ **未解且 SNR 无关**。即使 IQ 纯净，NPU 必须 INT8（激活+输出层），AM-SSB-SC 仍崩塌到 0.078。clean2a 的 0.99325 是 **FP32 host**，不是 NPU INT8；纯净路径没有任何一份「clean-IQ × INT8 × 24 类」证据显示 AM-SSB-SC 可用。
- **裁决**：纯净 RadioML 的 24 类部署**在 FP32 层面可行、在 NPU INT8 层面不可行**。除非拿到可用 QAT 或输出层高精度化，否则 24 类纯净路径也无法上 NPU。

## 3. 路径二：双 SDR RadioML 信号（未证，且叠额外阻塞）

在量化域崩塌之上，双 SDR 路径还叠两道未证/负面：

1. **RF 链路未过**：fix10prep3 真实两样本板测 `training_corr=0.720230 < 0.9 → classification=SKIPPED`（payload_training_corr=0.989795 正常，但训练帧保真门未过）；原始日志未归档 PC（E1-R）。→ 双 SDR 训练帧跨架构一致性在真实 RF 下尚未验证通过。
2. **RF 泛化未证且有一例负面**：三后端判责真实外部 QPSK 捕获 78 帧，板端 NPU **78/78 全判成 QAM、0 帧 QPSK**，判责 `MODEL_DOMAIN_GENERALIZATION`（模型对真实 RF 域不泛化）。

→ 双 SDR 24 类即使量化域有解，也**尚未证明**「真实 RF 信号能被 24 类模型正确识别」。

## 4. 未评估的潜在路径（诚实标注「未证」，不当作可行）

1. **全网络 BF16 / 输出层 FP32 混合精度**：仅 expA 把分类头单层改了 BF16；未评估整条输出路径高精度化。当前 ZG330 以 INT8 为主，全网络 BF16 支持度未验证。
2. **厂商 QAT 手册 + 工具**：E0 明确指出须向 FMSH 索取《QAT 用户手册》，取得并验证输入/激活 scale 保留路径后重估。当前未取得。
3. **分层分类（23 类 + AM-SSB 亚类判别器）**：未评估；属新架构设计，超出「沿用冻结模型」范围。

以上三条**均不能在本报告内判为可行**，只能列为「未评估前提」。

---

## 5. 对后续 Step 1–9 的含义

- 本 Part 0 裁决：**24 类直接部署不可行，23 合并路径维持。**
- 因此 fix10class24_dualsdr_prep2 的 Step 1–9（身份审计/模式兼容/选择逻辑/结果字段/prewarm 预算/Gate A/B/C/接受门/命令模板/报告模板）应**以 23 部署类为准**进行准备，而非 24 原始类。
- 若用户仍坚持 24 类，唯一可继续的前提是先解决 §4 第 1/2 条（输出层高精度化或 QAT 工具），且需先补齐双 SDR 路径的 RF 链路（fix10prep3 重过板）与 RF 泛化（重跑三后端 QPSK）证据——**这些都不属于只读 Part 0 范围**。

---

> 本报告所有数字逐字取自磁盘冻结文件（`m29_quantized_min_class_collapse_analysis.json`、`m29_rml23_merged_candidate_comparison.json`、`M29_PHASE_E0_QAT_FEASIBILITY_GATE.md`、`rml24_closed_set_final.json`、clean2a/AMSSB 审计）。只读审查，唯一生成物即本报告；禁写 token（`RF_PASS` / `FIX10_READY` / `ROUTE_F_23CLASS_ACCURACY_MEASURED` / `PROJECT_COMPLETE` / `FINAL_*`）全程未触碰。
