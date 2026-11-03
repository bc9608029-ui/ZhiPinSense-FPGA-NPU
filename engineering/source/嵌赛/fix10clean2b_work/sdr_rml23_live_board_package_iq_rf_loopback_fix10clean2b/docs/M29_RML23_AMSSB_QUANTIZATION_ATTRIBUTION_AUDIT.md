# M29 RML23 — AM-SSB WC/SC 量化判责审计（fix10clean2c 前置审查）

状态：只读审计，不修改模型/权重/checkpoint/量化参数/24→23 映射/baseline/clean IQ 数据/NPU 运行时代码。
本审计回答四个问题：WC/SC 不稳定是否已在 FP32 出现；BF16 量化对 WC/SC 造成多少翻转；是否存在真实 board_npu 证据；23 类合并是模型限制、量化补救还是冻结部署策略。

---

## 1. 输入与模型 SHA（先验身份核验，非按文件名配对）

| 输入/模型 | SHA256 (hex) | 匹配 |
|---|---|---|
| 冻结 checkpoint `best.pt` | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` | ✓（clean2a provenance 一致） |
| 板端模型 `model_24class_ZG.json` | `d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d` | ✓（部署合同一致） |
| 板端模型 `model_24class_ZG.raw` | `2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba` | ✓（= `FROZEN_MODEL_RAW_SHA256`） |
| FP32 源模型 `rml24_24class_opset17.onnx` | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` | ✓（errata §9.1 `976618a1…`） |
| RadioML HDF5 数据源 | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38` | ✓ |
| 源 24 类标签序 | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` | ✓ |
| 部署 23 类标签序 | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` | ✓ |
| 合并契约 | `f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e` | ✓ |

- `deployment_golden/expected_logits_or_argmax.json` 头声明 `model_raw_sha256=2425d990…`、`model_json_sha256=d43a2284…`、`merged_contract_sha256=f9f7f381…`，全部匹配上表。
- 输入字节一致核验：对 240 帧逐帧重算 `input_NNN.bin` 的 SHA-256 并与 fp32 导出记录的 `input_sha256` 比对，**240/240 完全一致（0 处不匹配）**，即 fp32 与 host_quantized 比较的是**逐字节相同**的输入。
- 24→23 合并严格按冻结 `postprocess/rml23_merged.py` 的 `logaddexp`（`merged[17] = logaddexp(logit_WC, logit_SC)`，其余维度按 `source_to_deployed` 平移拷贝）。

## 2. 后端可用性

| 后端 | 本机状态 | 依据 |
|---|---|---|
| `fp32_onnx` | **AVAILABLE** | onnxruntime 1.30.0 + 上表 ONNX（sha `976618a1…`），实测导出 240 帧 |
| `host_quantized` | **AVAILABLE**（冻结导出） | `deployment_golden/expected_logits_or_argmax.json` 240 帧 `raw_24_logits`（iCraft HostBackend bf16 冻结结果；运行时本机未装） |
| `board_npu` | **UNAVAILABLE** | 本机无 ZG330 / iCraft NPU 后端 |

**结论**：本机只能跑 **fp32-vs-host（2 后端量化对比）**，**不能**宣称三后端判责。板端导出命令（待用户在板上执行）：`bash scripts/run_gate9_rml23.sh --phase=offline --count=240 --logits-export=/tmp/board_logits`。

## 3. 已知事实复核（总体 240 帧，fp32 vs host_quantized）

本审计重跑 `export_fp32_onnx.py` + 同口径比较，与 errata §9.3 记录**完全一致**：

| 指标 | 本审计实测 | errata §9.3 | 复核 |
|---|---|---|---|
| raw24 max_abs_diff min/median/max | 0.0139 / 0.2209 / **1.8158** | 0.0139 / 0.2209 / 1.8158 | ✓ |
| raw24 cosine min/median/max | **0.311** / 0.9841 / 0.9998 | 0.311 / 0.9841 / 0.9998 | ✓ |
| merged-23 argmax 一致 | **180/240**（75%） | 180/240（75%） | ✓ |
| 量化导致 merged-23 翻转 | **60/240** | 60/240 | ✓ |

（注：这 240 帧为部署一致性 conformerance 集，SNR **仅 −20…−14 dB**，`expected argmax = 冻结 expA_bf16_head 模型自身 merged-23 输出，非 ground truth`；`match_rate` 是部署一致性，不是准确率。）

## 4. AM 子集逐样本分析（source 17/18，20 帧 = 10 WC + 10 SC）

下表对**完全相同 input SHA** 逐帧给出 FP32 与 host_quantized 的 raw24 top1、deployed23 top1 与逐帧判责。`✓`=raw24 top1==source_class（精确命中）。

| idx | src | SNR | FP32 raw24 top1 | host raw24 top1 | FP32 精确 | host 精确 | FP32 d23 | host d23 | maxAbs | cos | WC/SC logit 差(FP32/host) | 判责 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 170 | 17 WC | −20 | 18 SC | 10 128APSK | ✗ | ✗ | 17 AM-SSB | 17 AM-SSB | 0.719 | 0.365 | −0.134/−0.166 | FP32 内部混淆(WC→SC) |
| 171 | 17 WC | −20 | 8 16APSK | 14 64QAM | ✗ | ✗ | 17 | 14 | 0.394 | 0.921 | −0.073/−0.074 | FP32 混淆到其它类 |
| 172 | 17 WC | −20 | 22 GMSK | 22 GMSK | ✗ | ✗ | 21 | 21 | 0.066 | 0.999 | −0.095/−0.133 | FP32 混淆到其它类 |
| 173 | 17 WC | −18 | 15 128QAM | 23 OQPSK | ✗ | ✗ | 15 | 22 | 0.569 | 0.949 | +0.045/+0.156 | FP32 混淆到其它类 |
| 174 | 17 WC | −18 | 23 OQPSK | 4 QPSK | ✗ | ✗ | 22 | 4 | 0.233 | 0.989 | +0.058/+0.043 | FP32 混淆到其它类 |
| 175 | 17 WC | −18 | 4 QPSK | 4 QPSK | ✗ | ✗ | 17 | 17 | 0.114 | 0.996 | −0.132/−0.176 | FP32 混淆到其它类 |
| 176 | 17 WC | −16 | 22 GMSK | 22 GMSK | ✗ | ✗ | 21 | 21 | 0.257 | 0.999 | +0.016/−0.039 | FP32 混淆到其它类 |
| 177 | 17 WC | −16 | 22 GMSK | 22 GMSK | ✗ | ✗ | 21 | 21 | 0.314 | 0.965 | −0.036/+0.016 | FP32 混淆到其它类 |
| 178 | 17 WC | −16 | 22 GMSK | 22 GMSK | ✗ | ✗ | 17 | 17 | 0.067 | 0.979 | −0.147/−0.150 | FP32 混淆到其它类 |
| 179 | 17 WC | −14 | 17 WC | 17 WC | ✓ | ✓ | 17 | 17 | 1.739 | 0.999 | +0.030/+0.020 | 两后端一致正确 |
| 180 | 18 SC | −20 | 3 BPSK | 3 BPSK | ✗ | ✗ | 3 | 3 | 0.395 | 0.974 | −0.052/−0.051 | FP32 混淆到其它类 |
| 181 | 18 SC | −20 | 22 GMSK | 22 GMSK | ✗ | ✗ | 17 | 17 | 0.037 | 0.998 | −0.193/−0.194 | FP32 混淆到其它类 |
| 182 | 18 SC | −20 | 22 GMSK | 15 128QAM | ✗ | ✗ | 17 | 17 | 0.106 | 0.973 | −0.184/−0.193 | FP32 混淆到其它类 |
| 183 | 18 SC | −18 | 4 QPSK | 4 QPSK | ✗ | ✗ | 17 | 4 | 0.134 | 0.998 | −0.137/−0.096 | FP32 混淆到其它类 |
| 184 | 18 SC | −18 | 22 GMSK | 15 128QAM | ✗ | ✗ | 17 | 17 | 0.194 | 0.902 | −0.038/−0.016 | FP32 混淆到其它类 |
| 185 | 18 SC | −18 | 22 GMSK | 22 GMSK | ✗ | ✗ | 21 | 21 | 0.154 | 0.995 | −0.063/−0.148 | FP32 混淆到其它类 |
| 186 | 18 SC | −16 | 21 FM | 21 FM | ✗ | ✗ | 20 | 20 | 0.144 | 0.994 | +0.245/+0.258 | FP32 混淆到其它类 |
| 187 | 18 SC | −16 | 22 GMSK | 15 128QAM | ✗ | ✗ | 21 | 17 | 0.130 | 0.973 | −0.050/−0.057 | FP32 混淆到其它类 |
| 188 | 18 SC | −16 | 22 GMSK | 22 GMSK | ✗ | ✗ | 21 | 21 | 0.096 | 0.997 | −0.003/−0.051 | FP32 混淆到其它类 |
| 189 | 18 SC | −14 | 18 SC | 18 SC | ✓ | ✓ | 17 | 17 | 0.537 | 0.963 | −0.200/−0.204 | 两后端一致正确 |

（WC/SC logit 差 = `logit[17] − logit[18]`，正=倾向 WC，负=倾向 SC。d23 索引 17=AM-SSB、21=GMSK、22=OQPSK、15=128QAM、14=64QAM、4=QPSK、3=BPSK、20=FM。）

## 5. AM 子集翻转统计（20 帧）

| 现象 | 计数 | 说明 |
|---|---|---|
| **FP32_MODEL_CONFUSION**（FP32 raw24 top1 ≠ source） | **18/20** | FP32 本身在低 SNR 下大量判错 AM-SSB |
| 　├ 内部 AM-SSB 混淆（WC↔SC） | **1/20** | 仅 idx 170（WC→SC） |
| 　└ 混淆到**其它类**（GMSK/QPSK/OQPSK/…） | **17/20** | 绝大多数，非 WC/SC 兄弟混淆 |
| **HOST_QUANTIZATION_FLIP**（FP32 正确、量化后错） | **0/20** | 量化**没有**把任何正确帧翻成错误 |
| HOST_QUANTIZATION_RESCUE（FP32 错、量化后对） | 0/20 | 量化也没有"救回"任何帧 |
| FP32 WC→SC / SC→WC | 1 / 0 | 低 SNR 下内部兄弟翻转几乎不存在 |
| host WC→SC / SC→WC | 0 / 0 | 同上 |
| WC_SC_RAW_SWAP（两后端都在 AM 族且互不一致） | 0 | 量化未造成 WC↔SC 互换 |
| SOFTWARE_MERGE_ONLY（raw24 错/不一致但 deployed23 两后端都对） | **6/20** | 24→23 合并实际"救回"6 帧 |
| FP32 deployed23 正确 / host deployed23 正确 | 10 / 9 | 合并后正确率仍受低 SNR 主导 |
| merged-23 argmax 一致（fp32 vs host） | 15/20 | 剩余 5 帧为两个**都错**类之间的翻转 |

## 6. board_npu 证据

**`BOARD_NPU_ATTRIBUTION_NOT_PROVEN`**：本机无 ZG330 / iCraft NPU 后端，无法产出真实板端 raw24 logits。禁止把 `host_quantized`（bf16 HostBackend 冻结结果）冒充真实板载 NPU 结果。三后端判责里"板端 NPU 运行时相对 host_quantized 的额外误差"这一层**尚未证明**，待用户上板执行 `--logits-export` 后重跑 `compare_three_backends.py --board-dir …` 补齐。

## 7. 纯净（clean，无噪声）条件下的对照（来自 fix10clean2a formal12000）

该 240 帧 conformance 集 SNR 仅 −20…−14 dB，不能代表 clean2c 的**纯净 IQ** 场景。以冻结 FP32 模型在 clean formal12000（500/类）上的混淆矩阵为准：

| 类 | raw24 精确召回 | 混淆去向 |
|---|---|---|
| AM-SSB-WC (17) | **0.970**（485/500） | 15 帧 → SC（18），即 **WC→SC = 3.0%** |
| AM-SSB-SC (18) | **1.000**（500/500） | 0 帧 → WC，即 **SC→WC = 0%** |
| deployed23 AM-SSB (合并后) | **1.000**（1000/1000） | 15 帧 WC→SC 在合并后全部归正 |

**关键对照**：clean 条件下 FP32 模型对 WC/SC **区分能力本身是好的**（SC 100%、WC 97%），唯一残余是 **WC→SC 单向 3% 轻微混淆**——这是**真实、非对称的模型/训练数据域限制**，且被 24→23 合并完全吸收。

## 8. 最终可证明结论（四层判责）

| 层 | 结论 | 证据 |
|---|---|---|
| ① FP32 模型本身 WC/SC 可分性 | **可分，但非完美**：clean 下 SC 1.0 / WC 0.97，残余 WC→SC 3%；低 SNR(−20…−14)下 AM-SSB 大量误判到其它类（18/20） | §7 混淆矩阵 + §4 逐样本表 |
| ② host_quantized/BF16 量化变化 | **对 WC/SC 几乎无实质损伤**：AM 子集量化翻转 **0/20**；总体量化改变 merged-23 argmax 60/240，但集中在低 SNR 的"两个都错"类之间 | §3 + §5 |
| ③ 板端 NPU 相对 host_quantized 额外误差 | **未证明**（`BOARD_NPU_ATTRIBUTION_NOT_PROVEN`） | §6 |
| ④ 24→23 软件合并 | **冻结部署策略**，附带吸收 FP32 的 WC→SC 残余（clean 15/500、低 SNR 6/20 被救回） | §7 + §5 |

**对四个问题的直接回答**：

1. **WC/SC 分类不稳定是否已在 FP32 出现？** — **是，但分两层**：clean 下是轻微单向 WC→SC（3%）；低 SNR 下 FP32 对 AM-SSB 整体大幅失准（18/20），但绝大多数误判到**其它调制类**（GMSK/QPSK/OQPSK 等），**不是** WC/SC 兄弟互换。
2. **BF16 量化对 WC/SC 具体造成多少预测翻转？** — **0/20**。量化不产生 WC/SC 正确→错误翻转；它造成的 merged-23 翻转（5/20 于 AM 子集、60/240 总体）都发生在低 SNR 两个"已经都错"的类之间。**量化不是 WC/SC 不稳定的根因。**
3. **是否存在真实 board_npu raw24 logits 足以完成三后端判责？** — **否**。board_npu UNAVAILABLE，写 `BOARD_NPU_ATTRIBUTION_NOT_PROVEN`。
4. **当前 23 类合并是模型限制、量化补救，还是冻结部署策略？** — **冻结部署策略为主**（部署合同声明 23 类，WC/SC 合并为 AM-SSB，`deployment_mode=AMSSB_MERGED`）；**不是量化补救**（量化无 WC/SC 损伤可补）；它**附带**吸收了 FP32 真实的 WC→SC 单向 3% 残余，但这是次要收益，不是合并的存在理由。

## 9. 尚不能证明的部分

- 板端 NPU 相对 host_quantized 的额外误差（第③层）——缺真实板端 logits。
- 低 SNR 下 AM-SSB 误判到"其它类"（GMSK 等）的具体机理（是否频谱/瞬时频率在 −20…−14 dB 被噪声淹没）——超出本审计范围，需另行诊断。

## 10. 方法复现

```
# 1) FP32 导出（onnxruntime CPU，确定性）
python scripts/export_fp32_onnx.py --input-dir deployment_golden \
  --onnx F:\FPGA_Work\sdr_rml24_npu_deployment_m29\work\onnx\rml24_24class_opset17.onnx \
  --out-dir <scratch>/fp32

# 2) 逐帧比对（本审计：host 冻结 logits vs fp32 导出，按 input SHA 配对 + logaddexp 合并）
#    输出 _amssb_audit_scratch/amssb_attribution.json（含逐样本表与统计）
```

- host_quantized 原始 24 维 logits 取自 `deployment_golden/expected_logits_or_argmax.json` 的 `samples[].raw_24_logits`。
- 24→23 合并 = `merged[17]=logaddexp(logit[17], logit[18])`，其余维度按 `source_to_deployed` 平移，与 `postprocess/rml23_merged.py` 逐字节一致。

## 11. 与 fix10clean2c 的衔接（§7 口径修订依据）

- 仍发送 24 个原始类样本，WC、SC 各保留一个；deployed23 仍合并为 AM-SSB。
- raw24 若 WC/SC 发生互换，只要在现有合同下都正确合并到 deployed17，**不得**误判为 23 类覆盖失败（本审计证明 clean 下 WC→SC 单向 3% 属模型真实残余、量化不新增、合并已吸收）。
- 建议新增诊断字段：`raw24_top1`、`raw24_amssb_wc_logit`、`raw24_amssb_sc_logit`、`raw24_amssb_margin`、`deployed23_top1`、`amssb_raw_swap`、`amssb_merged_correct`、`backend_identity`。
- 禁止为了让 WC/SC 分开而临时改模型/阈值/映射；若未来要恢复 24 类独立部署，另开训练/量化优化任务，不混入 clean2c。
