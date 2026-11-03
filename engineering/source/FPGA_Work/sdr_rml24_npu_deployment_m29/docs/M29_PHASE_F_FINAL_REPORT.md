# M29 Phase F — RML23 合并部署评估与板端候选包 · 最终报告

> 最终状态：**`M29-RML23-MERGED-BOARD-PACKAGE-READY-FOR-TEST`**（最高允许；真实上板前禁止更高）
> 原状态保留：`RML24_PTQ_CANDIDATES=REJECTED`、`RML24_BOARD_DEPLOYMENT=BLOCKED`
> 红线遵守：禁碰板 / 禁写 Flash / 禁访问 test / 禁自动启动 QAT / 不训练专家模型 /
>           不覆盖 M22/M23/M24 / 未写 FINAL_*/NPU_PASS / 板端包无 Windows/x86/WSL 二进制。

---

## 一、最终报告 18 问

### 1. 哪些已有 vendor 输出被复用？

复用三份 INT8 候选已保存的 icraft-run 原始 24 维 logits 与 json/raw 产物：

| 候选 | 复用的 24 维 logits | 复用的 json/raw |
|---|---|---|
| d384_int8 | `work/eval_quant/quant_logits.npy`（1536×24） | `_tmp_24class_adapt_generate_384_20261010/jsonraw/model_24class_ZG.{json,raw}` |
| expA_bf16_head | `_tmp_24class_expA_bf16_head_384_20261010_eval_result/expA_logits.npy` | `_tmp_24class_expA_bf16_head_384_20261010/jsonraw/model_24class_ZG.{json,raw}` |
| dra384_int8 | `_tmp_24class_dra_384_20261011_eval_result/dra384_logits.npy` | `_tmp_24class_dra_384_20261011/jsonraw/model_24class_ZG.{json,raw}` |

FP32 参考原始 logits 未落盘（仅存 argmax `sub_fp32`），故以 ONNX Runtime 重算补全（与 PyTorch argmax 一致率 1.000000，bit 级保真），非量化重跑。

### 2. 是否重新运行了 iCraft？为什么？

**否。** 三份 INT8 候选的原始输出完整（均为 1536×24 float32 logits），按「原始输出完整不得为了方便重跑长时间量化」直接复用。唯一补算的是 FP32 参考 logits，走 CPU ONNX 推理（非 iCraft 量化管线），因为历史上只保存了其 argmax。

### 3. 23 类标签顺序是什么？

```
OOK, 4ASK, 8ASK, BPSK, QPSK, 8PSK, 16PSK, 32PSK,
16APSK, 32APSK, 64APSK, 128APSK, 16QAM, 32QAM, 64QAM,
128QAM, 256QAM, AM-SSB, AM-DSB-WC, AM-DSB-SC, FM, GMSK, OQPSK
```

其余 22 类保持 24 类原顺序；AM-SSB-SC/WC 合并为唯一 `AM-SSB`，落在原 WC 位置（index 17）。确定性标签序 SHA256 = `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88`。

### 4. 两个 AM-SSB 原始索引是什么？

24 类序中 **index 17 = AM-SSB-WC**、**index 18 = AM-SSB-SC**（合并映射 17/18 → 17）。

### 5. 合并使用的数学方法是什么？

```
merged_AMSSB = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)
             = log( exp(logit_SC) + exp(logit_WC) )
```

数值稳定形式 `m + log1p(exp(min(a,b) - m))`，其中 `m = max(a,b)`。这是 log 域概率质量求和 `P(AM-SSB)=P(SC)+P(WC)`，单调、对两个参数对称、保留完整 SC+WC 信号——非删除某一类、非未经解释的平均。已审计 vendor 输出语义为 raw logits（`OUTPUT_KIND=raw_logits_no_softmax`），故 log 域求和数学上正确。

### 6. FP32 合并后 23 类指标是多少？

| acc | macro-F1 | rated_0_20 | snr0 | min-class | AM-SSB 合并 |
|---|---|---|---|---|---|
| 0.578125 | 0.586542 | 0.881944 | 0.597222 | 64APSK 0.4062 | 0.9141 |

### 7. 每个 INT8 候选的 23 类指标是多少？

| 候选 | acc | macro-F1 | rated_0_20 | snr0 | min-class | AM-SSB | Top-1 一致 |
|---|---|---|---|---|---|---|---|
| d384_int8 | 0.571615 | 0.593063 | 0.873264 | 0.583333 | 128QAM 0.3594 | 0.9062 | 0.7611 |
| **expA_bf16_head** | **0.570964** | 0.579727 | 0.876736 | 0.569444 | 64APSK 0.4062 | 0.8906 | **0.8737** |
| dra384_int8 | 0.574870 | 0.595872 | 0.869792 | 0.583333 | 128QAM 0.3438 | 0.9062 | 0.7507 |

### 8. 哪个候选通过全部硬门？

仅 **`expA_bf16_head`**（Phase D.1 实验 A：前段 INT8 + 分类头 op179 BF16）。d384 因 G7（32PSK −12.5pp）失败、dra384 因 G5（min-class 128QAM −6.25pp）+G7（32PSK −14.06pp）失败，均 REJECTED。

### 9. 合并后 AM-SSB 准确率是多少？

expA = **0.8906**（vs FP32 0.9141，−2.34pp，门内）。对比：24 类下 AM-SSB-SC 崩塌至 0.078–0.203，合并根治崩塌。

### 10. 仍误判为 OOK 的比例是多少？

- expA_bf16_head：**0/64 = 0.0**
- FP32：0/64 = 0.0；d384：2/64 = 0.015625；dra384：1/64 = 0.0078125

### 11. 最差类别变成了哪一类？

expA 与 FP32 同为 **64APSK（0.4062，无退化）**。全 INT8 候选因 32PSK/128QAM 崩塌，最差类变为 128QAM（d384 0.3594 / dra 0.3438）——这正是它们被拒的原因。

### 12. 其余 22 类是否出现退化？

- expA：**无新崩塌**，其余 22 类相对 FP32 最大偏差 **±3.125pp**（门内 ≤5pp）。
- d384 / dra384：出现新崩塌（32PSK −12.5 / −14.06pp，dra384 另有 128QAM −6.25pp），拒绝。

### 13. 是否访问过 final/test？

**否。** 全程只用固定 1536 validation 诊断子集（`work/eval_full/subset_index.npz`，seed 2028，64/类）。manifest 已写入 `final_test_accessed=false`、`ood_final_test_accessed=false`。候选选择只依据 validation，不事后依据 final/test。

### 14. 是否修改预处理、模型或标签原契约？

**否。** 未改 24 类 checkpoint、24 类标签顺序、输入预处理、24 维索引。新增独立的 23 类部署契约（`contracts/rml23_merged_contract.*`），不改 `_frozen/contracts/rml24_contract.py`。

### 15. 是否需要新 bitstream？

**否。** 本任务为软件 + 模型层变更，沿用现有 bitstream，不重新生成位流、不启动 Vivado。

### 16. 板端包路径、大小和 SHA256 是什么？

- 路径：`dist/sdr_rml23_amssb_merged_board_package.tar.gz`
- 大小：**505575 字节**
- SHA256：`33e051e93e2468c973eefaf1e7da96882f42f11022316ad89b38629b67212be5`

### 17. 如何上传、校验、启动、停止和回滚？

见 `docs/M29_PHASE_F4_BOARD_INTEGRATION.md` 第 5 节与包内 `README.md`：

```sh
scp sdr_rml23_amssb_merged_board_package.tar.gz <board>:/opt/sdr/
mkdir -p /opt/sdr/rml23 && tar -xzf ... -C /opt/sdr/rml23 && cd /opt/sdr/rml23
./scripts/verify_package.sh          # 校验（fail-closed）
./scripts/build_board.sh             # 板端 aarch64 源码构建 + 自测
./scripts/test_1000_frames.sh  ...   # 1000 帧测试
./scripts/test_10000_frames.sh ...   # 10000 帧稳定性测试
./scripts/start_rml23.sh ...  / stop_rml23.sh
./scripts/rollback.sh                # 回滚至 model.prev/（不碰 Flash/位流）
```

### 18. 后续专家模型如何接入，但本轮是否保持关闭？

已预留禁用态接口：结果协议含 `expert_enabled`（本轮恒 **false**）与 `expert_result`（本轮恒 **NOT_RUN**）；原始 24 维 logits 已在链路上保存，供未来专家训练。后续在 23 类主链外新增 AM-SSB-SC/WC 二分类专家，读取已保存的 raw24 logits 输出细分结果。**本轮不训练、不启用、无假专家、无规则式 SC/WC 拆分。**

---

## 二、17 项离线测试对照（Phase F 第九节）

| # | 测试要求 | 结果 |
|---|---|---|
| 1 | 24→23 标签映射唯一且完整 | pytest `test_rml23_merged_contract` ✅ |
| 2 | 两个 AM-SSB 索引正确 | pytest + C++ `test_mapping`（17/18→17）✅ |
| 3 | logaddexp 数值稳定性 | C++ `test_logaddexp`（±inf、支配、无下溢）✅ |
| 4 | 极大/极小 logit | C++（1000/-1000/-inf/+inf）✅ |
| 5 | NaN/Inf fail-closed | C++ `test_synthetic_merge` ✅ |
| 6 | 非 24 维输入拒绝 | `postprocess/rml23_merged.validate_logits24` ✅ |
| 7 | 标签 SHA 不匹配拒绝 | `assert_source_order_matches` ✅ |
| 8 | 模型 SHA 不匹配拒绝 | `verify_package.sh` + F0 寄存器逐项校验 ✅ |
| 9 | manifest 只写一次 | `f3_freeze_deployment_manifest.py` 拒绝静默覆盖 ✅ |
| 10 | raw24 输出得到保留 | 结果协议记录 `raw_24_top1` ✅ |
| 11 | expert 默认关闭 | `expert_enabled=false`（契约+结果协议+C++）✅ |
| 12 | UI 不得显示虚假 SC/WC | `check_ui_result.sh` 拒绝 AM-SSB-SC/WC ✅ |
| 13 | 候选选择只使用 validation | `f2_rml23_merged_eval.py` 只读 validation 子集 ✅ |
| 14 | 代码不得访问 test/ood_final_test | grep 审计 0 命中（manifest 两标志 false）✅ |
| 15 | 既有 12 类/M22 测试不得退化 | 纯新增文件、零改 M22/M23/M24 树 ✅ |
| 16 | compileall/bash -n/C++ 测试全通过 | compileall ✅ / bash -n 8 脚本 ✅ / C++ 40/40 ✅ |
| 17 | 解包后 SHA256 逐项校验通过 | `sha256sum -c` 19/19 OK ✅ |

---

## 三、状态与红线

- 最高状态：**`M29-RML23-MERGED-BOARD-PACKAGE-READY-FOR-TEST`**（重评估通过 + 板端包生成后允许）。
- 原状态保留：`RML24_PTQ_CANDIDATES=REJECTED`、`RML24_BOARD_DEPLOYMENT=BLOCKED`。
- 未声明（真实上板前禁止）：`RML23_HARDWARE_PASS / RML24_NPU_PASS / FULL_24CLASS_PASS / PROJECT_COMPLETE / DEPLOYMENT_COMPLETE` 及 FINAL_* 族。
