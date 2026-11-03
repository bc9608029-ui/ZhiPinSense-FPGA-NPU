# M29 Phase F2 — 23 类合并重评估（固定 1536 集，四候选）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（未变，待 F3 冻结）
> 性质：只读重评估；不重跑量化、不碰板、不访问 test。
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁写 FINAL_*/NPU_PASS 等。

---

## 0. 结论（TL;DR）

1. **部署层合并根治 AM-SSB 崩塌**：四候选（含 FP32）合并后 AM-SSB 类精度 **0.8906–0.9141**（24 类下 AM-SSB-SC 崩塌至 0.078–0.203）。FP32 合并后 AM-SSB = **0.9141**。
2. **合并暴露第二处崩塌（仅全 INT8 候选）**：输出层 INT8 还摧毁 **32PSK**（d384 −12.5pp / dra384 −14.06pp）与 **128QAM**（dra384 min-class −6.25pp）。这些在 24 类下被 AM-SSB-SC 的 min_class 掩盖。
3. **唯一全门通过候选 = `expA_bf16_head`**（分类头 op179→bf16）：非 AM-SSB 其余 22 类最大偏差仅 **±3.125pp**，AM-SSB 0.8906（−2.34pp），min-class 与 FP32 同为 64APSK 0.4062。全 INT8 候选（d384/dra384）因 32PSK/128QAM 崩塌 **不通过门禁**。

**选择结果**：`RML23_MERGED_CANDIDATE_SELECTED=expA_bf16_head`（唯一 all-gates-passed）。

---

## 1. 评估对象与复用（只读）

| 候选 | 原始 24 维 logits 来源 | 是否重跑 |
|---|---|---|
| FP32（参考） | ONNX Runtime 重算（`work/onnx/rml24_24class_opset17.onnx`，SHA `976618a1…`），与 PyTorch `sub_fp32` argmax 一致率 = **1.000000** | 是（CPU 推理，bit 级保真，非量化） |
| d384_int8 | `work/eval_quant/quant_logits.npy` | 否（复用） |
| expA_bf16_head | `expA_logits.npy` | 否（复用） |
| dra384_int8 | `dra384_logits.npy` | 否（复用） |

三份 INT8 模型 json/raw 均按 F0 寄存器逐项 SHA 校验通过（identity verifiable）；源 24 类标签序 SHA 校验通过。

---

## 2. 23 类指标（1536=64/类，validation，非 test）

| 候选 | acc | macro-F1 | rated_0_20 | snr0 | min_class | AM-SSB 合并 | Top-1 一致(23类) | NaN/Inf |
|---|---|---|---|---|---|---|---|---|
| **FP32** | **0.578125** | **0.586542** | **0.881944** | **0.597222** | 64APSK 0.4062 | **0.9141** | 1.0 | 0 |
| d384_int8 | 0.571615 | 0.593063 | 0.873264 | 0.583333 | 128QAM 0.3594 | 0.9062 | 0.7611 | 0 |
| **expA_bf16_head** | **0.570964** | 0.579727 | 0.876736 | 0.569444 | 64APSK 0.4062 | 0.8906 | **0.8737** | 0 |
| dra384_int8 | 0.574870 | 0.595872 | 0.869792 | 0.583333 | 128QAM 0.3438 | 0.9062 | 0.7507 | 0 |

> 注：FP32 的 23 类 acc（0.578）高于其 24 类 acc（0.5540）——合并「易混的 WC/SC」后任务本身变易（不再要求区分 WC↔SC），属预期。

### AM-SSB 合并诊断（24 类 raw argmax 视角）

| 候选 | SC→WC 误路由(24) | WC→SC 误路由(24) | 合并后仍误判 OOK | 合并后 OOK 率 |
|---|---|---|---|---|
| FP32 | 16 | 14 | 0 | 0.0 |
| d384_int8 | 39 | 1 | 2 | 0.015625 |
| expA_bf16_head | 34 | 10 | 0 | **0.0** |
| dra384_int8 | 36 | 2 | 1 | 0.0078125 |

- 原 AM-SSB-SC 崩塌主要体现为「SC→WC 误路由」（d384 39/64、dra 36/64、expA 34/64），合并后这些**全部计入正确**（WC/SC 同属 AM-SSB）。
- 「合并后仍误判 OOK」几乎归零（expA = 0，d384 = 2，dra = 1），logaddexp 合并抬升 AM-SSB 分数足以压过 OOK。

---

## 3. 23 类晋升门禁（全部 vs FP32，同 1536 集）

| 门禁 | 阈值 | d384 | expA | dra384 |
|---|---|---|---|---|
| G1 accuracy | ≤2pp | −0.65pp ✅ | −0.72pp ✅ | −0.33pp ✅ |
| G2 macro-F1 | ≤2pp | −0.65pp ✅ | −0.68pp ✅ | −0.93pp ✅ |
| G3 rated_0_20 | ≤2pp | −0.87pp ✅ | −0.52pp ✅ | −1.22pp ✅ |
| G4 snr0 | ≤3pp | −1.39pp ✅ | −2.78pp ✅ | −1.39pp ✅ |
| G5 min-class | ≤5pp | −4.69pp ✅ | **0.0pp ✅** | −6.25pp ❌ |
| G6 AM-SSB 无系统崩塌 | ≤5pp 且 ≥0.5 | −0.78pp ✅ | −2.34pp ✅ | −0.78pp ✅ |
| G7 其余 22 类无新崩塌 | ≤5pp | **−12.5pp ❌ (32PSK)** | **−3.13pp ✅** | **−14.06pp ❌ (32PSK)** |
| G8 无 NaN/Inf | =0 | 0 ✅ | 0 ✅ | 0 ✅ |

**判决**：
- **d384_int8**：G7 失败（32PSK 0.5312→0.4062，−12.5pp）。REJECTED。
- **expA_bf16_head**：**全部通过**。SELECTED。
- **dra384_int8**：G5（min-class 128QAM −6.25pp）+ G7（32PSK −14.06pp）失败。REJECTED。

---

## 4. 选择（多候选通过 → 依序比 min-class → AM-SSB → Top-1 → 板端复杂度）

仅 `expA_bf16_head` 通过全部门禁，直接选定，无需次级比较。

**选定候选**：`expA_bf16_head`（Phase D.1 实验 A：前段 INT8 + 分类头 op179 BF16）
- json SHA `d43a2284…` / raw SHA `2425d990…` / params_md5 `7966a482…` / target `@zhuget(330)`

---

## 5. 产物

- `artifacts/m29_rml23_merged_candidate_comparison.json`（机器可读：四候选指标/门禁/选择/逐类 delta）
- `artifacts/m29_rml23_merged_confusion_matrix.csv`（四候选 × 23×23 混淆矩阵）
- `scripts/f2_rml23_merged_eval.py`（只读评估脚本）

---

## 6. 证据清单

- `work/eval_quant/quant_logits.npy` + `_tmp_*_eval_result/*_logits.npy`（复用原始 INT8 logits）
- `work/eval_full/subset_index.npz`（固定 1536 集）
- `work/onnx/rml24_24class_opset17.onnx`（FP32 参考，SHA `976618a1…`）
- `_frozen/contracts/rml24_contract.py`（源 24 类契约）
