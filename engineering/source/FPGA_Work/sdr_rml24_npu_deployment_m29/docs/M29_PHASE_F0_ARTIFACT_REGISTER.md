# M29 Phase F0 — 现有证据与产物盘点（只读）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（未变）
> 本阶段性质：**只读盘点**，不生成候选、不晋升、不碰板、不访问 test。
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁写 FINAL_*/NPU_PASS 等。

---

## 0. 结论（TL;DR）

1. **四个候选的身份全部盘点完毕，且三份 vendor INT8 候选的 24 维原始 logits 已在盘面上**（`*.logits.npy`，1536×24 float32），无需重跑 icraft-run（长时间量化）。
2. **FP32 参考候选的原始 24 维 logits 未落盘**（`subset_index.npz` 只存了 `sub_fp32`=argmax 预测，int64）。F2 需用 **ONNX Runtime CPU 推理**补齐 FP32 原始 logits——该路径已实证与 PyTorch FP32 的 Top-1 一致率 = **1.000000**（`subset_onnx_agreement_report.json`），bit 级保真，非「长时间量化」，允许且必要。
3. **目标器件确认为 `@zhuget(330)`**：三个 INT8 候选的 `model_24class_ZG.json` 均含 `ai_target="@zhuget(330)"`。
4. **输出确认为可比较的 24 维原始 logits**：ONNX 输出 `logits [1,24] float32`；冻结契约 `OUTPUT_KIND="raw_logits_no_softmax"`；icraft-run 每个样本读出 24 个 float32（`exp_quant_eval_m29.py` 断言 `logits.size==24`）。

---

## 1. 四个候选的身份寄存器

### 1.1 FP32（源模型，参考基线）

| 项 | 值 |
|---|---|
| 模型名 | `RML2018_24_BENCHMARK`（seed 2027） |
| checkpoint 路径 | `F:\FPGA_Work\24class_results\rml24_seed2027_best.pt` |
| checkpoint SHA256 | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` |
| ONNX 路径 | `work\onnx\rml24_24class_opset17.onnx` |
| ONNX SHA256 | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` |
| 冻结契约文件 | `_frozen\contracts\rml24_contract.py`（文件 SHA `164b216d05ea1c491794bc098fc9d2c03a77f3a1db4b335074ed42ffabb9c3bb`） |
| 标签契约语义 SHA（24 类序） | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |
| 输入契约 | `[1,2,1024]` fp32 平面 I/Q，RMS≈1.0，无归一化 |
| 输出契约 | 24 维 raw logits（`OUTPUT_KIND="raw_logits_no_softmax"`） |
| 原始 24 维 logits（1536 子集） | **未落盘**（仅 `sub_fp32` argmax）；F2 由 ONNX Runtime 补齐 |

### 1.2 三份 vendor INT8 候选（NPU `model_24class_ZG`）

| 候选 | json SHA256 | raw SHA256 | params_md5 | ai_target | 原始 logits（1536×24） |
|---|---|---|---|---|---|
| **D384 全 INT8**（Phase D 基线，op179 int8） | `e09f1549ff973763dfad67198536596d9c9ae7b8b6a814369a02ef53b43be06e` | `5e7be89471147a642d40ef2f880e607014d913f48b279a79c93e324567dd82f5` | `3171971f31a7bb0e1f2e2338cd6cd5e5` | `@zhuget(330)` | `work\eval_quant\quant_logits.npy` ✅ |
| **expA 分类头 BF16**（Phase D.1，op179→bf16） | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` | `7966a4829fc713b2e8ea6c04168be263` | `@zhuget(330)` | `_tmp_24class_expA_bf16_head_384_20261010_eval_result\expA_logits.npy` ✅ |
| **DRA384 全 INT8**（Phase D.3，幅度分层重校准） | `654c2f3d97c76c5724cdd3b5c0da352e07aa830dde4ae3993125a6500cff68c4` | `a588814e718ecc97745692647ebed945ae556e60d3d0219c5841d15b5be526b2` | `185cdf381e6a5df055ce394b03b6adb7` | `@zhuget(330)` | `_tmp_24class_dra_384_20261011_eval_result\dra384_logits.npy` ✅ |

> 说明：三份 `model_24class_ZG.json/.raw` 各自位于其独立 `jsonraw/` 目录（`_tmp_24class_adapt_generate_384_20261010\jsonraw\`、`_tmp_24class_expA_bf16_head_384_20261010\jsonraw\`、`_tmp_24class_dra_384_20261011\jsonraw\`），互不覆盖。三份 `params_md5` 互不相同，证明为三份不同的量化参数产物。

---

## 2. 固定 1536 诊断集

| 项 | 值 |
|---|---|
| 路径 | `work\eval_full\subset_index.npz`（SHA 见寄存器 JSON） |
| 大小 | 1536 = 64/类 × 24 类，seed 2028，按类 + SNR 分层抽取 |
| 数组 | `sub_indices`(int64 1536) / `sub_labels`(int64 1536) / `sub_snrs`(float32 1536) / `sub_fp32`(int64 1536) / `sub_int8`(int64 1536) |
| 分割 | `radioml2018_validation`（**非 test**） |
| 注意 | `sub_fp32` / `sub_int8` 是 **argmax 预测**（int64），**不是原始 logits** |

---

## 3. 已落盘的 icraft-run 原始输出（优先复用，不重跑量化）

每个候选的 eval 结果目录都保存了三件套（`{label}_logits.npy` + `{label}_preds.npy` + `{label}_report.json`）：

| 候选 | logits.npy | preds.npy | report.json |
|---|---|---|---|
| D384 | `work\eval_quant\quant_logits.npy`（147584B = 1536×24 fp32） | `quant_preds.npy`（12416B = 1536 int64） | `work\eval_quant\quantized_agreement_report.json` |
| expA | `expA_logits.npy`（147584B） | `expA_preds.npy`（12416B） | `expA_report.json` |
| DRA384 | `dra384_logits.npy`（147584B） | `dra384_preds.npy`（12416B） | `dra384_report.json` |

> **所有 `.npy` 均为 1536×24 float32 原始 logits + 1536 int64 argmax 预测**（`exp_quant_eval_m29.py` 直接从 icraft-run 的 `.ftmp` 输出逐样本读出 24 个 float32）。原始输出**完整**，故 F2 **不得**为了方便重跑 icraft-run。

### 无法复用的既有 FP32 文件

- `work\calibration_384\_fp32_logits_384.npy` = (384, 24)，是 **384 校准集**（16/类）的 FP32 logits，**不是** 1536 诊断子集，F2 不可用。
- `subset_index.npz` 的 `sub_fp32` = argmax 预测，非 logits。

因此 F2 的 FP32 参考 logits 需由 ONNX Runtime 补齐（见 §0.2）。

---

## 4. 目标器件与输出语义确认（F0 点 8 / 9）

- **目标器件 = `@zhuget(330)`**（ZG330，8 TOPS INT8），三个 INT8 候选一致。
- **输出 = 24 维原始分数/logits，可跨候选直接比较**：ONNX 输出张量 `logits [1,24] float32`；icraft-run 每样本 24 float32；三候选 logits.npy 形状一致 `[1536,24]`。合并与 23 类 argmax 在软件后处理对同一 24 维原始 logits 做 `logaddexp` 后取 argmax，语义成立。

---

## 5. 对后续阶段的影响

| 阶段 | 影响 |
|---|---|
| F1（23 类契约） | 基于冻结 `LABEL_ORDER_24` 派生；`source_class_count=24`、`deployed_class_count=23`、`npu_output_dim=24`、`deployment_mode=AMSSB_MERGED`；AM-SSB 两源索引 = **17（WC）/ 18（SC）** |
| F2（23 类重评估） | 三份 INT8 原始 logits **直接复用**；FP32 原始 logits **由 ONNX Runtime 补齐**（bit 级保真，非量化重跑） |
| F3（冻结清单） | 可写入的 `source_checkpoint_sha256` / `source_npu_json_sha256` / `source_npu_raw_sha256` / `params_md5` / `target_device` 均已在 §1 取齐 |
| F4（板端集成） | 三候选 target 均为 `@zhuget(330)`，位流不变、仅软件/模型 |

---

## 6. 证据清单

- `artifacts/m29_phase_f0_artifact_register.json`（本盘点的机器可读寄存器）
- `scripts/f0_artifact_inventory.py`（本盘点脚本，只读）
- `work/eval_quant/quantized_agreement_report.json`、`*_report.json`（三候选评估报告，含 model json/raw SHA）
- `work/eval_full/subset_onnx_agreement_report.json`（ONNX vs FP32 Top-1 一致率 = 1.0）
- `_frozen/contracts/rml24_contract.py`（冻结 24 类契约：标签序 / I/O / OUTPUT_KIND）
