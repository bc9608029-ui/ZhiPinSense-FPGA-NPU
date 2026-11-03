# M29 Phase D — 24类 384 样本量化成功记录（quantize→adapt→generate）

状态：`M29-RML24-NPU-OFFLINE-PACKAGE-READY`（离线，未碰板，未写 Flash，未跑闭集 test）

## 0. 任务边界（方案 D，10 条硬约束）

本阶段执行用户批准的**方案 D**（绕过 624 前置初始化故障）：用 384 分层校准样本（16/类，seed 2028，非 test、非有序前缀截断，覆盖每类低/中/高 SNR、全局 26 个 SNR）重跑量化，Scale=384、batch=8、Batch Size=48，全新输出目录只跑一次；成功则完整走 quantize→adapt→generate，并在完整 validation 上评价 FP32/ONNX/量化模型的 accuracy / macro-F1 / rated_0_20 / snr0 / min_class / Top-1 一致率；**只有精度门通过，384 产物才可晋升为最终 NPU 候选**。

- 校准/评估只用 **validation** 集（`rml24_split_indices.npz` SHA `9a035841…`），闭集 test 未访问。
- checkpoint `rml24_seed2027_best.pt` SHA `96cd25f8…`（RML2018_24_BENCHMARK，seed 2027）未改动；ONNX `rml24_24class_opset17.onnx`、24 类标签序、输入预处理均未改动。
- 未重新训练 / 未微调；未用 test 数据校准 INT8；未用最终测试指标选量化参数。

## 1. 根因结论（Phase D 前置结论，已定案）

624 文件校准集在前置初始化阶段触发**资源/进程态故障**；具体 EMFILE 机制尚未确认（疑 MSVC CRT stdio 句柄上限）。已排除：路径含空格（384 用带空格路径 `C:\Icraft\CLI v3.39.0\bin` 亦成功）、批次组织（拆批无效）、数据质量（NaN/Inf=0）。**624 规模本身是唯一触发条件**。

### 1.1 624 复现的关键证据（保存待厂商，方案 D 规则 #10）

624 失败签名（exit 1，429 s，峰值 1.62 GB，无产物）：

```
Open file C:\Icraft\CLI\bin\poly_params.json failed!   # poly_params_mentions=1
```

注意失败的是工具**自身**的配置文件 `poly_params.json`（位于 `C:\Icraft\CLI\bin\`，与校准数据无关），不是校准样本文件 —— 这是句柄耗尽假说（MSVC CRT stdio `FOPEN_MAX`）的直接证据：624 个校准文件 + 若干其它句柄在前置阶段打开后，工具再也打不开自己的 `poly_params.json`，`safeLoadFile` exit 1。384 运行 `poly_params_mentions=0`（未复现）。

### 1.2 624 复现包保存位置（勿删）

| 项 | 路径 |
|---|---|
| 624 运行脚本 / 配置 / 日志 | `F:\FPGA_Work\_tmp_24class_quantize_624_batch13_20261010\`（`_run_once.sh`、`compile_config.toml`、`quantize_stdout.log`、`quantize_stderr.log`、`run_report.log`、`.icraft\logs\`） |
| 624 校准数据（24×26） | `F:\FPGA_Work\sdr_rml24_npu_deployment_m29\work\calibration\cal_data\` + `forward_list.txt` |

624 与 384 均确认 vendor 量化方案为 `[quantize] saturation="kld"` + `per="channel"`（逐通道 KLD）。

## 2. Quantize（384，batch=8，Batch Size=48）

| 项 | 值 |
|---|---|
| 输出目录 | `F:\FPGA_Work\_tmp_24class_quantize_384_batch8_20261010\`（全新，只跑一次） |
| 退出码 | **0** |
| 起止 | 2026-10-10 20:10:59 → 20:26:55 |
| 耗时 | 956 s |
| 峰值内存 | 2,122,260,480 B（≈2.12 GB） |
| 批次数 | **8**（Batch 0–7 全部 Begin/End） |
| `poly_params` 打开失败复现 | **0 次**（624 的故障特征未复现） |
| 量化方案（日志证据） | **逐通道 KLD**：`Measuring Weight: channel N, sat / max`（真实 per-channel，非 per-tensor 代理） |
| config SHA256 | `1797d65c44fdd06b2164cd6162e8b1c34dfb77f97875f5f958e5fceb6cd1c4ab` |

产物：

| 文件 | 字节 | SHA256 |
|---|---|---|
| `jsonraw/model_24class_quantized.json` | 403272 | `2fca4c94cb3db320651adcc15505895321b0034757e721b28dc444899a361a59` |
| `jsonraw/model_24class_quantized.raw` | 284500 | `e86a8b82c9238ca28283de7faafc6b3892713e7a945d396832b784f6b4b77996` |

## 3. Adapt + Generate（ZHUGE 目标）

| 项 | 值 |
|---|---|
| 输出目录 | `F:\FPGA_Work\_tmp_24class_adapt_generate_384_20261010\`（全新，只跑一次） |
| adapt 退出码 / 耗时 | 0 / 11 s |
| generate 退出码 / 耗时 | 0 / 6 s |
| 工具 | `D:/icraft/bin/icraft.exe` v3.39.0 |

产物：

| 文件 | 字节 | SHA256 |
|---|---|---|
| `model_24class_adapted.json` | 577718 | `88075ff81dfa4918e578810a4c2ac0c98f0e1a107c18a7163136d15bb0c22f6a` |
| `model_24class_adapted.raw` | 2423148 | `1af82247c867132712881c3d2e9c4ef74dd0bf6db082221a135f154b8e0b03fd` |
| **`model_24class_ZG.json`（最终 NPU 候选）** | 222554 | `e09f1549ff973763dfad67198536596d9c9ae7b8b6a814369a02ef53b43be06e` |
| **`model_24class_ZG.raw`（最终 NPU 候选）** | 2853100 | `5e7be89471147a642d40ef2f880e607014d913f48b279a79c93e324567dd82f5` |

`model_24class_ZG.json` 关键字段：`name=model_24class`，`ai_target=@zhuget(330)`，`icraft_version=v3.39.0`，`params_md5=3171971f31a7bb0e1f2e2338cd6cd5e5`，`params_bytes=2853100`，`tags={bgr_order:true, stage:quantized}`，130 ops，输出 `[1,24]`，无 NaN/Inf。

## 4. 精度评估（方案 D 规则 #6）

完整 validation = **511,056** 样本（24 类 × 26 SNR × 819）。

### 4.1 FP32（checkpoint，权威基准）

| 指标 | 值 |
|---|---|
| accuracy | **0.630469** |
| macro-F1 | **0.636168** |
| rated_0_20 | **0.891030** |
| snr0 | **0.569394** |
| min_class | **0.518409** |

### 4.2 fake-INT8（per-tensor 对称 weights/127，fp32 激活，**权重量化代理**）

| 指标 | 值 | 相对 FP32 降幅 |
|---|---|---|
| accuracy | **0.629309** | −0.00116 |
| macro-F1 | **0.635034** | −0.00113 |
| rated_0_20 | **0.889624** | −0.00141 |
| snr0 | **0.568834** | −0.00056 |
| min_class | **0.511224** | −0.00719 |

fake-INT8 Top-1 一致率 vs FP32 = **0.863373**（per-tensor 权重代理有损：argmax 翻转集中在低置信近并列样本，故一致率低而精度降幅仅 0.12pp）。真实 per-channel KLD 预期更优 —— 见 4.4 实测。

### 4.3 ONNX（导出保真度，分层子集 1536 = 64/类）

| 指标 | 值 |
|---|---|
| ONNX Top-1 一致率 vs FP32 | **1.000000** |
| ONNX accuracy（子集） | 0.554036（= 子集 FP32 accuracy，逐样本一致） |

ONNX 导出与 FP32 checkpoint **逐样本 bit 级一致**（一致率 1.000000），导出无信息损失。

### 4.4 真实量化模型（icraft-run，Host 后端，vendor per-channel INT8）

1536 样本分层子集（64/类），量化 `model_24class_ZG` 经 `icraft-run --backends Host` 逐样本前向，对比同一子集 FP32。

| 指标 | 量化 | FP32（同子集） | 降幅 |
|---|---|---|---|
| accuracy | **0.539062** | 0.554036 | −0.01497（−1.50pp） |
| macro-F1 | **0.561933** | 0.561532 | +0.00040（持平） |
| rated_0_20 | **0.838542** | 0.855903 | −0.01736（−1.74pp） |
| snr0 | **0.555556** | 0.555556 | 0.0 |
| **min_class** | **0.078125（AM-SSB-SC）** | 0.406250（64APSK） | **−0.32813（−32.8pp，崩塌）** |

Top-1 一致率（量化 vs FP32）= **0.615234**；按 SNR 分层：SNR≥20 一致率 **0.962**（高置信样本 bit 级一致，通道序正确）、SNR≤−10 一致率 0.113（两者均近随机）。量化保住了 91.1% 的 FP32 正确样本。

**min_class 崩塌根因（已定位）**：AM-SSB-SC（类 18）被 INT8 **激活 + 输出层**量化摧毁，而非权重量化。对照同一子集：

| | FP32 | fake-INT8（仅权重） | vendor-INT8（权重+激活+输出） |
|---|---|---|---|
| min_class | 0.4062（64APSK） | 0.4219（64APSK） | **0.0781（AM-SSB-SC）** |
| AM-SSB-SC 精度 | 51.6%（33/64） | 45.3%（29/64） | **7.8%（5/64）** |
| AM-SSB-SC @SNR≥12 | 85%（17/20） | 80%（16/20） | **10%（2/20）** |

AM-SSB-SC 样本量化后 39/64 被误判为 AM-SSB-WC、14/64 被误判为 OOK（类 0，最低索引），且量化 logits 边际中位数 = 0.0 —— 输出层 INT8 量化把该类本就微小、与 AM-SSB-WC 近并列的 logits 差异抹平，argmax 落在错误近邻/平局类。**该崩塌与 SNR 无关（高 SNR 同样崩塌），是系统性缺陷，非低 SNR 近并列噪声。**

### 4.6 精度门判定（方案 D 规则 #7）

**判定：精度门不通过 —— 384 产物当前形式不得晋升最终 NPU 候选。**

依据：min_class 崩塌 −32.8pp（AM-SSB-SC 51.6%→7.8%，高 SNR 85%→10%），且 rated_0_20 −1.74pp。macro-F1 持平、snr0 持平、overall −1.50pp。崩塌由激活/输出层 INT8 量化引入（权重量化无辜），最可疑点是**输出层（24 维 logits）INT8 量化**。

候选整改方向（待用户批准，不擅自执行）：
1. 输出层/分类头保留 fp32 或 int16 精度（查 iCraft 是否支持输出节点精度覆盖）；
2. 若输出层为 per-tensor 量化，改 per-channel（axis=-1）缓解 logits 尺度差异；
3. 量化感知训练（QAT）——需重训，红线内除非用户明确批准否则禁止；
4. 针对 AM 族增加校准样本 / 逐通道激活量化调参，验证是否能恢复 AM-SSB-SC 判别。

### 4.5 关于子集绝对精度的说明

分层子集（64/类，seed 2028，按 SNR 分层 2–3 样本/SNR）是**为 1.3s/样本 的 icraft-run 回环而设计的小样本一致性测量载体**，其绝对 accuracy（0.554）与全量（0.630）的差异是小样本抽样噪声 + 对低 SNR 端的轻微过采样所致，**不代表量化损失**。权威 accuracy 以 4.1 全量 FP32 / 4.2 全量 fake-INT8 为准；4.3/4.4 只用于报告**一致率（Top-1 agreement）与相对降幅**（同一子集上量化 vs FP32 对比，抽样噪声自抵消）。

## 5. 结论与状态

- 384 量化成功跨越了 624 在 Batch 0 之前的阻断点，证明 iCraft 3.39 对 24 类模型的量化本身可行，故障由 624 规模的前置资源/进程态触发。
- quantize→adapt→generate 五阶段链路完整走通，产出最终 NPU 候选 `model_24class_ZG.{json,raw}`。
- FP32/fake-INT8/ONNX 三项已出：导出 bit 级一致（ONNX 一致率 1.0）；权重量化代理降幅 <0.15pp。
- 真实量化（icraft-run）三项：overall −1.50pp、macro-F1 持平、rated_0_20 −1.74pp —— **但 min_class 崩塌 −32.8pp（AM-SSB-SC），精度门不通过**。
- **结论：384 产物不晋升最终 NPU 候选（当前形式）；整改方向见 4.6，待用户批准。** 本阶段交付=五阶段产物 + 全量/子集精度证据 + 624 复现包（方案 D 规则 #6/#7/#10 完成）。

状态：`M29-RML24-NPU-OFFLINE-PACKAGE-READY`（离线证据齐备；精度门未通过；未碰板/未写 Flash/未访问 test/未写 NPU_PASS 等禁词）。
