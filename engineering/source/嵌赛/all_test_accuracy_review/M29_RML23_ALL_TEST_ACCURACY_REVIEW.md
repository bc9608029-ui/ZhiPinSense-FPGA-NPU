# M29 RML23 — 从开发至今全量测试与识别准确性综合审查报告

> 状态：**只读审查**（本报告为唯一生成物，未改任何生产文件 / 测试 / 包 / 权重 / 标签 / MEMORY）
> 日期：2026-10-17
> 覆盖：RML24 24 类模型 → 24→23 合并 → 12 类前身 → M20 OOD-U → fix8/fix9 Route F → fix9r2g1 → fix10-prep/prep2/prep3 → clean2a/2b/class24 → AM-SSB WC/SC 判别 → UI
> 取证：4 个只读子代理并行 + 主进程对关键冲突项（tarball SHA、24 类 per-class）磁盘复核

---

## 0. TL;DR（结论摘要）

1. **「识别准确率」存在三套彼此不可混用的口径**，任何报告若不加前缀地写一个数字，都构成口径混用：
   - **纯净 IQ 全/高 SNR（离线 host FP32）**：24 类 raw24 **0.99325**、deployed23 **0.99450**（clean2a，formal12000）——这是「纯净 RadioML 信号」路径能达到的天花板。
   - **真实 RadioML2018 全 SNR 分布（离线 host FP32，511680 样本最终盲测）**：acc **0.630808**、rated_0_20 **0.891981**——这才是 24 类模型对「真实数据分布」的客观能力，低 SNR（−20…−14 dB）单点准确率仅 0.045–0.063。
   - **板端真实 RF（三后端判责）**：模型对真实外部 QPSK 捕获 **78/78 帧全部判成 QAM、0 帧 QPSK** → 判责 `MODEL_DOMAIN_GENERALIZATION`（模型/真实域泛化问题，非 NPU 量化/板卡问题）。

2. **全链没有一条「板上识别准确率 PASS」证据**。23 类 runner、12 类模型、UI 真屏，全部只有离线数字或 `READY-FOR-BOARD-TEST` 离线态；唯一一次真实板测是 fix10prep3（training_corr=0.720230 < 0.9 → classification SKIPPED，原始日志未归档 PC，记 E1-R）。

3. **24 类直接部署之所以被 REJECTED，根因在模型域而非量化域**：AM-SSB-SC 在 FP32 全 SNR 下 recall 仅 0.5383（24 类倒数第 4），INT8 进一步崩塌到 0.078125（5/64），QAT 又因 iCraft 3.39 无接口而「救不回来」。但**高 SNR 纯净下 AM-SSB WC/SC 是可判别的**（WC 0.97 / SC 1.0，错出族 0）——低 SNR 的失败是「认不出 AM-SSB 族」而非「WC↔SC 混淆」。

4. **本轮新发现 1 处版本资产变更**：fix10prep3 打包 tarball 在上一轮审计后被重新生成，记忆 SHA 已过期（磁盘现为 `729bde8a…`(full) / `1df9f0e7…`(patch)，原记录 `3fdfc4ca…` / `8f2ae869…` 作废）。

---

## 1. 方法与证据级别

| 级别 | 定义 | 本报告中出现位置 |
|---|---|---|
| **E1** | 板端原始日志/机读结果已落 PC 磁盘 | 三后端判责 JSON（78 帧 QPSK 捕获） |
| **E1-R** | 板测已做、原始日志未归档，仅任务书/审计转述 | fix10prep3 真实板测；Stage A/B/C 判责 |
| **E2** | 离线 host 证据（测试、确定性打包、SHA、数字回环） | 绝大部分「识别准确率」数字 |
| **E3** | 仅文档声明、无独立落盘产物 | （本报告未采信 E3 作为数字来源） |
| **E4** | 待做 / 无证据 | 所有板端 PASS 类数字 |

方法：只读审计，4 个只读子代理并行取证（模型域 / clean·class24·AMSSB / fix8–fix10prep3 / 12 类·UI），本主进程汇总并对**所有冲突项**磁盘复核。**识别准确率 = 分类正确率（accuracy/recall/F1/confusion）**，与「恢复保真（corr/NMSE）」「同步精度（CFO 估计）」「自洽率（golden self-consistency）」严格分开标注——后者不是识别准确率。

---

## 2. 识别准确性总表（核心）

### 2.1 24 类模型域（ADAMRV11Net，checkpoint `96cd25f8…`）

**三套评估面（不得混用）：**

| 评估面 | 样本数 | accuracy | rated_0_20 | 备注 |
|---|---|---|---|---|
| **最终盲测 test（权威）** | 511680 | **0.6308083177** | **0.8919807834** | `rml24_closed_set_final.json`（E2 机读） |
| 全量 validation | 511056 | 0.630469 | 0.891030 | 另一评估面 |
| 选点（validation） | — | （selection_score 0.6917906） | 0.89099789 | `final_checkpoint_manifest.json::selection_value` |

> 「0.630457 / 0.890998」是**选点/验证侧残留值**，不是最终盲测值；最终盲测以 `0.630808 / 0.891981` 为准。记忆里的 0.630457 无对应 JSON，已裁定为口径残留，非数据损坏。

**最终盲测汇总指标（逐字）：**

| 指标 | 值 |
|---|---|
| accuracy | 0.6308083176985616 |
| macro_f1 | 0.6365206591363646 |
| rated_0_20_accuracy | 0.8919807834441981 |
| high_10_20_accuracy | 0.977269647696477 |
| snr_0_accuracy | 0.5733231707317074 |
| min_per_class_accuracy | 0.5176360225140713（256QAM） |
| selection_score | 0.6917906095057865 |

**24 类 per-class accuracy（最终盲测，逐字，按类序）：**

| 类 | accuracy | 类 | accuracy |
|---|---|---|---|
| OOK | 0.753189 | AM-SSB-WC | 0.646060 |
| 4ASK | 0.654315 | AM-SSB-SC | **0.538321** |
| 8ASK | 0.692402 | AM-DSB-WC | 0.755488 |
| BPSK | 0.737383 | AM-DSB-SC | 0.600985 |
| QPSK | 0.669700 | FM | **0.832552**（最高） |
| 8PSK | 0.604690 | GMSK | 0.777533 |
| 16PSK | 0.540807 | OQPSK | 0.684053 |
| 32PSK | 0.582786 | | |
| 16APSK | 0.627439 | | |
| 32APSK | 0.625516 | | |
| 64APSK | 0.543433 | | |
| 128APSK | 0.559897 | | |
| 16QAM | 0.574672 | | |
| 32QAM | 0.560694 | | |
| 64QAM | 0.529081 | | |
| 128QAM | 0.530769 | | |
| 256QAM | **0.517636**（最低） | | |

**最弱 5 类（`top5_weakest`）：** 256QAM 0.5176 → 64QAM 0.5291 → 128QAM 0.5308 → AM-SSB-SC 0.5383 → 16PSK 0.5408。

**per-SNR accuracy（逐字，关键点）：**

| SNR | acc | SNR | acc |
|---|---|---|---|
| −20 dB | 0.045122 | 0 dB | 0.573323 |
| −18 dB | 0.043496 | 6 dB | 0.917226 |
| −16 dB | 0.048323 | 10 dB | 0.972917 |
| −14 dB | 0.063008 | 18 dB | 0.979472 |
| −12 dB | 0.094665 | 24 dB | 0.977693 |
| −10 dB | 0.147053 | 30 dB | 0.977896 |
| −6 dB | 0.255488 | | |

> 低 SNR（−20…−14 dB）准确率 0.043–0.063 是「全 SNR 均值只有 0.6308」的主因；高 SNR（≥10 dB）稳定在 0.97+。

### 2.2 24→23 合并（部署类 = 23，AM-SSB WC/SC → 类 17）

| 候选 | accuracy | AM-SSB recall | 32PSK | 是否选中 |
|---|---|---|---|---|
| FP32 | 0.578125 | 0.9140625 | 0.53125 | — |
| d384_int8 | 0.571615 | 0.90625 | 0.40625（−12.5pp） | 否 |
| **expA_bf16_head** | **0.570964** | **0.890625** | 0.5 | **是（all_pass=true）** |
| dra384_int8 | 0.574870 | 0.90625 | 0.390625（−14.06pp） | 否 |

**24 类 INT8 崩塌（24 类直接部署被 REJECT 的量化侧证据）：** AM-SSB-SC：fp32 0.515625（33/64）→ vendor_int8 **0.078125（5/64）**；@SNR≥12：fp32 0.85 → vendor 0.1。

### 2.3 12 类前身（`12CLASS_CHAIN_VALIDATION_MODEL`，raw `2ae95275…`）

**权威冻结源** `ad_amr_12class_robust_v2\docs\V1_BASELINE_FREEZE.md`（E2）：

| 指标 | 值 |
|---|---|
| mean_full_accuracy | 0.736706 |
| mean_full_macro_f1 | 0.736574 |
| **mean_rated_0_20_accuracy** | **0.963384** |
| mean_high_10_20_accuracy | 0.982870 |
| each_seed_snr_0 | 2026=0.886111 / 2027=0.9 |
| each_seed_min_rated_class | 2026=0.854545 / 2027=0.836364 |
| fake_int8_accuracy_drop | 2026=0.008862 / 2027=0.000397 |
| onnx_runtime_parity max_abs_diff | 5.4836e-6 |
| 部署黄金集自洽（10dB） | 236/240（98.3%）**← 非模型准确率** |

**12 类 per-class recall（rated_0_20，fp32 formal validation 7560 样本，逐字）：**

| 类 | seed2026 | seed2027 |
|---|---|---|
| OOK | 0.993939 | 0.996970 |
| 4ASK | 0.993939 | 0.993939 |
| AM-DSB | 1.0 | 1.0 |
| WBFM | 0.990909 | 0.987879 |
| 2FSK | 0.993939 | 0.987879 |
| GFSK | 1.0 | 1.0 |
| BPSK | 0.993939 | 0.972727 |
| QPSK | 0.921212 | 0.930303 |
| 8PSK | 0.978788 | 0.960606 |
| 16QAM | 0.875758 | 0.875758 |
| 64QAM | 0.854545 | 0.836364 |
| OFDM | 0.990909 | 0.990909 |

> 12 类模型的 0.963384 是**离线 formal 验证集**数字；**磁盘无任何 12 类「板上准确率 PASS」**（见 §4 诚实边界）。

### 2.4 M20 12 类 OOD-U 拒识（`sdr_amr_12class_ood_u_v1`，E2）

| 指标 | 值 |
|---|---|
| score_method / id_accept_99 阈值 | logit_margin / **−0.1527441120** |
| id_accept_95 / far_ood_target | −0.4829905 / −15.2389773 |
| 校准 overall_auroc / fpr95 | 0.788327 / 0.601389 |
| 盲测 overall_auroc | 0.803692 |
| 盲测 aupr_in / aupr_out / fpr95 | 0.750652 / 0.826504 / 0.575 |
| 盲测 id_accept_rate / id_false_reject | 0.983333 / 0.016667 |
| 盲测 ood_reject / near_reject / far_reject | 0.072222 / 0.060256 / 0.103333 |
| 盲测 ood_detection_accuracy | 0.436667 |
| logits parity PyTorch↔ONNX | max_abs_diff 9.5367e-6 / argmax 1.0 |
| **npu_logits_provided** | **false**（阈值未取自真实 NPU logits，待上板） |
| 板回放（95 样本）decision/class agreement | 1.0 / 1.0 |

### 2.5 板端真实 RF 识别（三后端判责，E1 — 唯一机读板测证据）

真实外部 QPSK 捕获 78 帧，三后端（board NPU / host / FP32）：

| 判责 | 值 |
|---|---|
| PRIMARY VERDICT | **`MODEL_DOMAIN_GENERALIZATION`**（模型/真实域泛化问题） |
| 板端 NPU 输出 | **78/78 帧全部 QAM、0 帧 QPSK** |
| 一致率 | NPU vs Host 78/78；NPU vs FP32 63/78；Host vs FP32 63/78；三后端全一致 63/78 |
| 板端混淆直方图 | 256QAM=28 / 16QAM=25 / 64QAM=19 / 128QAM=6 / **QPSK=0** |
| Stage A/B/C 复核 | `MIXED_PREPROCESS_AND_MODEL_DOMAIN`（带宽对齐后 0/78→35/78 即 44.9%；残余 43/78 折叠进 QAM；CAVEAT=INSUFFICIENT_INDEPENDENT_SESSIONS，不推翻上一轮） |

> 这是全链**唯一一条有落盘机读结果的真实 RF 识别证据**，结论是负面的：模型对真实 QPSK 不泛化。

### 2.6 恢复保真 / 同步精度（**非识别准确率**，单列避免混用）

| 项 | 值 | 类型 |
|---|---|---|
| class24 D2 恢复 | corr ≥ 0.999652 / NMSE ≤ 7.470e-04 / rms_scale_error ≤ 7.611e-03 | 恢复保真 |
| clean2b roundtrip 4ASK(500) | corr 0.999925 / nmse 1.523e-04 | 恢复保真 |
| clean2b roundtrip BPSK(1500) | corr 0.999877 / nmse 2.649e-04 | 恢复保真 |
| fix10-prep coarse-CFO | 实测 197.45 vs 真 200（±625 Hz 无歧义） | 同步精度 |
| fix10prep3 板测 payload_training_corr | 0.989795（训练块去斜正常） | 恢复保真 |
| fix10prep3 板测 training_corr | **0.720230 < 0.9 → classification SKIPPED** | 恢复保真（未过门） |

---

## 3. host 测试计数（非识别准确率，但为完整性列出）

| 阶段 | 测试 | 计数 |
|---|---|---|
| fix8 | test_iq_rf_loopback / level_sweep / ab | 75/0 · 40/0 · 28/0 |
| fix9 | test_iq_rf_loopback_23class | 17/0（93 断言）；后期口径 pass=94/93 |
| fix9 系列 | fix9r=72/0 · fix9r2=66/0 · fix9r2a=38/0 · fix9r2b=43/0 · fix9r2d=76/0 · fix9r2g=80/0 | — |
| fix9r2g1 | baseline E2E / 生成器 self-test | 9/9 · 11/11 |
| fix10prep2 | host 全套 / pc_tx self-test | ALL PASSED · 14/14 |
| fix10prep3 | 全量回归 / test_fix10_canonical_frame | FULL_REGRESSION_EXIT=0 · 44/0 |
| clean2a | formal12000 评估 | 29 passed |
| clean2b | smoke_d2 / smoke_protocol | 37/0 · 18/0 |
| class24 | 离线测试 | 16 passed |

> 「17/0」与「93/94 断言」不冲突：前者按测试用例计、后者按断言计，且分属不同时点。

---

## 4. 交叉对账与矛盾裁决

| # | 冲突 | 裁决 |
|---|---|---|
| 1 | acc 0.630457/0.890998 vs 0.630808/0.891981 | **口径区分，非错误**：前者=选点/验证侧残留，后者=最终盲测权威。已裁定以 0.630808/0.891981 为准。 |
| 2 | 12 类准确率「不在磁盘」 | **在磁盘，但树不同**：在 `ad_amr_12class_robust_v2`（0.963384 rated_0_20），不在 `sdr_rml24_npu_deployment_m29`。 |
| 3 | test_iq_rf_loopback_23class 17/0 vs 93/94 | **用例 vs 断言口径 + 不同时点**，不冲突。 |
| 4 | fix10prep3 打包 SHA `3fdfc4ca…`/`8f2ae869…`（记忆+上一轮审计）vs 磁盘 `729bde8a…`/`1df9f0e7…` | **tarball 已重新生成**（主进程磁盘复核：full 4366950 B vs 原 4365780 B，patch 215308 B vs 原 214237 B，字节数也变）。记忆与 `final_system_audit_prep1\results\sha_registry.tsv` 里的 fix10prep3 包 SHA 已过期，须更新。 |
| 5 | 合并合同 `rml23_merged_contract.py` 部署侧 f9f7f381… vs clean2a/class24 树 31deebc0… | **版本混用待复核**（可能是合法演进，也可能资产混用），离线不可裁决，须用户确认差异来源。 |

---

## 5. 诚实边界（什么「识别准确率」其实不存在）

以下「准确率」在磁盘上**没有证据**，任何报告若写出即构成状态夸大：

1. **23 类 runner 板端准确率 / 混淆矩阵**：`ROUTE_F_23CLASS_ACCURACY_*` 实测数字**磁盘不存在**；fix9 仅 `READY-FOR-BOARD-TEST`，R8 两样本 / R9 46 样本**未跑**。
2. **12 类模型板端准确率**：**不存在**。唯一一次板上 Gate 7 实测失败（3/240 = 0.0125，低于随机 8.3%），根因 ZG330 陈旧帧，修复后**从未再上板复测**（状态 NEEDS-GATE7-NPU-REARM-FIX）。
3. **24 类直接部署板端准确率**：不存在，且方案已 REJECTED/BLOCKED。
4. **UI 星座图真实显示器验收 / 截图 / FPS**：未做。离屏烟测 exit 124 通过 ≠ 真实渲染验收（`M29-RML23-UI-CONSTELLATION-DESKTOP-GUI-VERIFIED` 未取得）。
5. **M20 OOD-U 真实 NPU logits 阈值**：`npu_logits_provided=false`，阈值仅来自 fp32+int8 仿真。
6. **fix10prep3 板测原始日志**：未归档 PC（E1-R）；磁盘审计文档仍写 `CANONICAL-FRAME-READY-FOR-BOARD-TEST` 离线态，不含板测失败数字。

---

## 6. 缺失数字清单（Q6）

1. fix10prep3 板测**原始日志**（training_corr/classification 板端原始输出）。
2. 23 类准确率 + 混淆矩阵（`route_f_fix9_summary.json` / `confusion_23.csv`）。
3. UI 真实显示器截图。
4. 包 tarball 完整 SHA（fix9r2g1 / fix10-prep / fix10clean2a，树内仅前缀；**fix10prep3 已重生成需更新台账**）。
5. 8 类模型完整 SHA（仅前缀 `c48979b3…`）。
6. 12 类模型「最终板端实测准确率」（全链无）。
7. 合并合同 f9f7f381… vs 31deebc0… 的差异来源裁决（须用户确认）。

---

## 7. 结论与下一步

**识别准确性的真实图景（按证据强度从高到低）：**

- **唯一确证的高准确率** = 纯净 IQ 离线 host FP32：24 类 raw24 0.99325 / deployed23 0.99450（clean2a）；12 类 rated_0_20 0.963384。
- **模型对真实数据分布的能力上限** = 24 类最终盲测 0.630808 / rated_0_20 0.891981，瓶颈在低 SNR（−20…−14 dB 仅 0.043–0.063）与高阶调制/AM-SSB 族。
- **板端真实 RF 识别 = 未证实且有一例负面证据**：真实 QPSK 78/78 判成 QAM，判责 `MODEL_DOMAIN_GENERALIZATION`。
- **24→23 合并是「可离线交付」的次优解**（expA_bf16_head all_pass，deployed23 0.99450 于 clean 域），但它绕开的是 24 类 AM-SSB-SC 的模型域弱点 + INT8 崩塌，**没有改变板端真实 RF 泛化未证的事实**。

**下一步（按依赖顺序，非本报告任务）：**
1. 用户确认 §4#5 合并合同版本差异来源。
2. 更新 `final_system_audit_prep1` 台账中 fix10prep3 打包 SHA（已过期）。
3. Part 0：24 类可行性重评（本报告是它的证据底座），须**分两条路径**——纯净 RadioML（离线可答：clean2a 已 YES）vs 双 SDR RadioML（未证：被 fix10prep3 板测失败阻塞）。

---

> 本报告所有数字均逐字取自磁盘冻结文件；只读审查，唯一生成物即本报告。禁写清单（`RF_PASS` / `FIX10_READY` / `ROUTE_F_23CLASS_ACCURACY_MEASURED` / `PROJECT_COMPLETE` / `FINAL_*` 等）全程未触碰。
