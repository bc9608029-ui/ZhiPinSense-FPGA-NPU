# M29 Phase D.1 — 实验 A（末层 FC→BF16）结果与晋级门判定

> **勘误（2026-10-10，用户 39e5 指示）**：
> 1. **Top-1 agreement 门槛 = 0.98**（原定门槛，不得静默降低）。实验 A 实测 0.810 < 0.98 → **标为 FAIL**（原文误标「✅ 提升」，已更正）。
> 2. **因果断言收紧**：当前只能确认「head 之外的量化主干导致剩余崩塌」，**不得提前断言**全部由 28 层 Conv 激活量化造成——具体敏感层待 Phase D.2 中间张量定位（本文 §6 已相应改写）。

- 工程：`F:\FPGA_Work\sdr_rml24_npu_deployment_m29\`
- 实验 A 输出目录：`F:\FPGA_Work\_tmp_24class_expA_bf16_head_384_20261010\`
- 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（**实验 A 不通过晋级门，不晋升**）
- 红线遵守：未碰板 / 未写 Flash / 未访问 test / 未启动 QAT / 未重训 / 未写任何 FINAL_* / NPU_PASS 等禁词。

---

## 1. 实验配置（单变量改动，官方语义）

- 改动：`mix_precision` CSV 将末层 FC **op 179** 置 `bf16`；其余 130 op 全 `int8`（Input/Output 宿主节点维持 fp32）。
- 不变：无 softmax / 无结构改动 / 无 QAT / 无重训 / 标签序与预处理不变 / 同一 384 校准集（seed 2028，24×16，26 SNR）/ 同一 1536 固定评测集 / 全新目录只跑一次。
- 产物确证（`model_24class_quantized.json`）：
  - op 179 输出 logits：`storage_dtype=@bf(16)` / `expressed_dtype=@fp(32)` / `zero_points=[]` / **无 int8 scale**（Phase D 的 1.2439321 已消失）。
  - op 179 权重 `@bf(16)`、激活输入 `@bf(16)`、bias `@tf(32)`。
  - 前端保持 int8：op 176（Mean）、op 177（FC1）输入仍 `@sint(8)`。

## 2. 编译产物

| 阶段 | exit | 耗时 | 峰值内存 |
|---|---|---|---|
| quantize | 0 | 901 s | 2.12 GB |
| adapt | 0 | 4 s | 6.7 MB |
| generate | 0 | 25 s | 6.7 MB |

| 产物 | 字节 | SHA256 |
|---|---|---|
| `model_24class_ZG.json` | 223501 | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` |
| `model_24class_ZG.raw` | 2857720 | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` |

（评测脚本 `scripts/exp_quant_eval_m29.py`；结果 `…_eval_result/expA_report.json`。注：ExpA 图输出张量 v_id 变化，icraft-run dump 文件为 `924.ftmp` 而非 Phase D 的 `922.ftmp`，已改为 glob 动态定位。）

## 3. 精度结果（1536 子集 = 64/类，validation 非 test）

| 指标 | fp32 | Phase D 全 int8 | 实验 A（head bf16） |
|---|---|---|---|
| accuracy | 0.554036 | 0.539062 | **0.539062** |
| macro-F1 | 0.561532 | 0.561933 | **0.542665** |
| rated_0_20 | 0.855903 | 0.838542 | **0.842014** |
| snr0 | 0.555556 | 0.555556 | **0.527778** |
| min_class（值/类） | 0.406250 / 64APSK | 0.078125 / AM-SSB-SC | **0.203125 / AM-SSB-SC** |
| Top-1 一致率 vs fp32 | 1.000（定义） | 0.615234 | **0.809896** |

## 4. AM-SSB-SC（类 18）混淆分解

| 项 | fp32 | Phase D 全 int8 | 实验 A |
|---|---|---|---|
| 正确率 | 51.6% (33/64) | 7.8% (5/64) | **20.3% (13/64)** |
| → AM-SSB-WC | — | 39/64 | **34/64** |
| → OOK | — | 14/64 | **2/64** |
| → 其它 | — | ~6/64 | **15/64** |
| 12–30 dB 正确率 | ~85%（记忆） | ~10% | **10.0% (2/20)** |

logits top1–top2 边际：全样本中位数 0.992 / AM-SSB-SC 中位数 **0.422**（Phase D 为 0.0，近并列）。

## 5. 晋级门判定（实验 A vs fp32）

| 门 | 阈值 | 实验 A | 判定 |
|---|---|---|---|
| accuracy 降幅 | ≤2pp | −1.50pp | ✅ |
| macro-F1 降幅 | ≤2pp | −1.89pp | ✅（临界） |
| rated_0_20 降幅 | ≤2pp | −1.39pp | ✅ |
| snr0 降幅 | ≤3pp | −2.78pp | ✅（临界） |
| min_class 降幅 | ≤5pp | **−20.31pp** | ❌ |
| 无单类系统性崩塌 | — | **AM-SSB-SC −31.3pp** | ❌ |
| Top-1 一致率 | ≥0.98（原定，不降） | **0.810** | ❌ |
| 无 NaN/Inf | — | 无 | ✅ |

**结论：实验 A 不通过晋级门，不晋升。** `model_24class_ZG`（Phase D 全 int8）与实验 A 产物均保留为 REJECTED 证据。

## 6. 根因结论（决定性与新增发现）

1. **输出层 int8 是首要触发，已由实验 A 修复**：末层 FC→bf16 后，除 AM-SSB-SC 外其余 23 类全部恢复到 fp32 ±3.1pp 以内；Phase D 的 OOK 崩塌（0.938→0.688，且 14 例误判 OOK 降为 2 例）消失；Top-1 一致率 0.615→0.810。
2. **新增发现（因果断言收紧）**：head→bf16 后，除 AM-SSB-SC 外其余 23 类全部恢复 fp32 ±3.1pp 以内，唯 AM-SSB-SC 仍 −31.3pp。据此只能确认「**head 之外的量化主干**（前端 int8 各层）导致剩余崩塌」，**不能提前断言**具体由哪一层/是否全部由 28 层 Conv 激活量化造成——该定位交由 Phase D.2 中间张量逐层分析（cosine/SQNR/MAE/饱和率/动态范围，分 AM-SSB-SC/AM-SSB-WC/其它类统计，找首次明显偏离层）。
3. **饱和率**：head（op 179）bf16 无 int8 量化 → 无饱和（N/A）；前端 int8 层饱和率与 Phase D 相同（同一校准集/同一量化设置，head dtype 不反作用于前端 scale）。

## 7. 实验 B 判定（不执行）

实验 B = 「末层 FC/output per-channel」。判定为**无意义/被 A 覆盖**：末层 FC 权重默认已 per-channel（`per=channel`）；而 head 已置 bf16（完全无量化），激活/output 的 per-channel int8 是更低分辨率手段（激活张量标准为 per-tensor，iCraft 无 per-channel 激活量化语义）。故 **B ≡ A，无需重复运行**。

## 8. 下一步（方向 1 已获批：有界敏感层定位，见 Phase D.2）

head-only 整改已用尽且不达标。剩余瓶颈 = head 之外的量化主干（前端 int8 各层），具体层待定位。用户已批准方向 1，但**禁止 28 层逐层盲跑**，改用**有界敏感层定位**（Phase D.2，另立文档 `docs/M29_PHASE_D2_SENSITIVE_LAYER_LOCALIZATION.md`）：

- **A 路（优先，只读）**：中间张量逐层分析——FP32 vs INT8 各层输出，算逐层 cosine/SQNR/MAE/饱和率/动态范围，分 AM-SSB-SC / AM-SSB-WC / 其它类统计，找首次明显偏离层。已确认 `icraft-run --dump_ftmp` 可导出中间张量（不传参数 = dump 全部 ftmp）。
- **B 路（仅当 A 不可行）**：28 层按网络阶段分 4 组，分组 bf16 二分；首轮 ≤4 次、只细分最敏感组、总编译实验 ≤8 次、每次只改一组精度。
- **C 数据纪律**：同一 1536 诊断子集；不碰 test；不换校准集；不按单个 AM 样本选配置；最小敏感层集冻结后对完整 validation 评估一次。
- **D 最终候选须报**：acc/macro-F1/rated/snr0/min_class、AM-SSB-SC 及 AM-SSB-WC 精度、Top-1 agreement、中间层误差、bf16 层数、NPU 映射率、是否 CPU fallback、模型大小、预计/实测延迟与内存。
- **E 晋级门不变**：无单类系统性崩塌、min_class 降幅 ≤5pp、Top-1 agreement 门槛 0.98 **不得静默降低**、不允许 CPU fallback 冒充 NPU 部署成功。
- **F 停止条件**：最小敏感层集仍无法恢复 AM-SSB-SC / 混合精度导致关键算子 CPU fallback / 资源或延迟明显不可接受 → 停止 PTQ，提交证据后再申请 QAT，不自动重训。
