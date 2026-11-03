# 十二类 NPU 部署契约（MODEL_DEPLOYMENT_CONTRACT）

任务 39e5 §四 交付物。本文冻结十二类 raw-I/Q NPU 分区从 ONNX 到 iCraft 编译产物的
**全部部署事实**，作为 Gate 7 / Gate 9 板端程序加载 `model_12class.json/.raw` 的
权威依据。所有 SHA 均在本机实测；本工程**只读**源工程，未改动任何上游资产。

---

## 0. 模型身份与标签

| 项 | 值 |
|---|---|
| 模型标签 | **`12CLASS_CHAIN_VALIDATION_MODEL`** |
| 用途 | 十二类 SDR→FPGA/NPU→UI 完整链路（Gate 6–9）的**通路验证模型** |
| **非** | 非「最终鲁棒模型」、非「最终准确率 PASS」、非「OOD PASS」 |
| OOD 门 | **NO_GO**（源工程 `acceptance.json` OOD gate 未过，本模型仅验证链路通路） |
| 类别数 | 12（frozen 顺序，见 §3） |

> 措辞红线：任何报告不得把本模型写成「最终鲁棒模型 / 最终准确率 PASS / OOD PASS」。

---

## 1. 源 ONNX（链路上唯一推理模型）

| 项 | 值 |
|---|---|
| 路径 | `F:/FPGA_Work/_tmp_ad_amr_results_verify/ad_amr_data_v3_12class_ff2b3fb3_run/outputs/ad_amr_v1_1_data_v3_12class/formal/export/onnx/ad_amr_v1_1_opset17.onnx` |
| SHA256 | `f77587152b52cda9a467b28790bc62d0eb0c639db2c39da82642c00ca8deda5a` |
| opset / IR | opset 17 / IR 8 |
| 输入 | 单输入 `iq` `[1,2,1024]` fp32（channel 0 = I，channel 1 = Q） |
| 输出 | 单输出 `logits` `[1,12]` fp32 |
| 算子 | Add(12) / Conv(28) / Gemm(2) / ReduceMean(1) / Relu(24) |
| 导出报告 | 同目录 `export/onnx/export_report.json`（PyTorch↔ONNX 一致性 `ort_parity max_abs_diff 5.48e-6`，见 SOURCE_PROVENANCE_SHA256.txt §A） |

> 与 8 类基线（`rfnet_npu`）的**架构差异**（勿静默混用）：
> - 8 类 = **双输入** `iq[1,2,1024]` + `physical_features[1,3,1024]`，来自 FPGA Mandatory
>   Core 反量化域（iq×1/127、physical×2/127）；
> - 12 类 = **单输入** raw I/Q `[1,2,1024]`（训练域 RMS=1.0），无 FPGA 特征提取、无反量化，
>   模型内部自算特征。

---

## 2. 编译工具与流水线

| 项 | 值 |
|---|---|
| 编译器 | iCraft（复旦微/FMSH vendor 工具）CLI **v3.39.0** |
| 可执行 | `C:/Icraft/CLI v3.39.0/bin/icraft.exe` |
| 目标 | `zhuge` / `ZHUGE` / `@zhuget(330)`（FMQL30TAI NPU） |
| 流水线 | `parse → optimize → quantize → adapt → generate`（五阶段，全 exit 0） |
| 编译脚本 | `model_12class/compile/run_compile.sh` |
| 编译配置 | `model_12class/compile/compile_config.toml` |

**关键编译参数（`compile_config.toml`）**：

```toml
[parse]   framework="Onnx"  network=<源ONNX>  inputs="1,2,1024"
          inputs_layout="FD"  inputs_dtype="fp32"  pre_method="nop"  target="zhuge"
[quantize] qdtype="int8"  bits=8  saturation="kld"  per="channel"
          no_transinput=true  no_imagemake=true
          forward_dir=<cal_data>  forward_list=<forward_list.txt>
[generate] rows=4  cols=4
```

冻结约束（与 8 类一致，已遵守）：不删/不换模型算子、不改数学、不静默 HostBackend 回退、
非图像输入（no_transinput / no_imagemake 关闭）、校准集仅取冻结 train split。

---

## 3. 类别顺序（FROZEN，权威源）

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 类 | OOK | 4ASK | AM-DSB | WBFM | 2FSK | GFSK | BPSK | QPSK | 8PSK | 16QAM | 64QAM | OFDM |

来源 = `sdr_adapter/categories.hpp` `cat::target_12()`（SHA `cd3f336d…`，两处逐字节一致，见
SOURCE_PROVENANCE_SHA256.txt §B）。板端程序只从 `cat::target_12()` 取序，不另写。

---

## 4. 编译产物（已重命名权威文件）

| 文件 | 字节 | SHA256 |
|---|---|---|
| `model_12class/model_12class.json` | 222,804 | `51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834` |
| `model_12class/model_12class.raw` | 2,851,472 | `2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c` |
| `model_12class/model_12class.sha256` | sidecar | 见上（`sha256sum -c` 通过） |

中间产物（`compile/jsonraw/`，仅审计）：`parsed/optimized/quantized/adapted` 各 `.json/.raw`。

**编译产物内建契约（从 `model_12class_ZG.json` 实测提取）**：

| 项 | 值 |
|---|---|
| `icraft_version` | `v3.39.0` |
| `icraft_xir_version` | `3.39.0.0` |
| `ai_target` | `@zhuget(330)` |
| `framework_kind` / `framework_version` | `ONNX` / `opset17` |
| `params_bytes` | 2,851,472 |
| `params_md5` | `3b0f3b4a1f2e7b882a1fd9ed04d0791f` |
| `tags` | `stage: quantized` |
| op 统计 | 1×Input + 1×Output（`@hostt`）+ 128×HardOp（`@zhuget(330)`） |
| **输入** | `[1,2,1024]`，`element_dtype @fp(32)`，layout `@layout(**C)`，`@hostt` |
| **输出** | `[1,12]`，`element_dtype @fp(32)`，layout `@layout(*C)`，`@hostt` |

---

## 5. 量化（INT8，非 FP16）

| 项 | 值 |
|---|---|
| 方案 | **INT8**（非 FP16） |
| 存储 dtype | `@sint(8)`（276 处权重/激活）；输入/输出边界 `@tf(32)`（22 处） |
| 对称性 | **对称**（`zero_points: []`，无零点） |
| 粒度 | **per-channel**（`scale: @scales([axis=-1]…)`，按输出通道） |
| 饱和方式 | KLD（`saturation="kld"`） |
| 输入量化 | **否**（`no_transinput=true`，输入保持 fp32，不量化为 int8） |
| 输出反量化 | 运行时自动（输出为 fp32 logits，板端程序不接触 int8 标度） |
| 示例首层权重标度 | `@scales([axis=-1]1024*0.23273507)`（首 Conv 1024 输出通道 per-channel 标度 0.23273507） |

**板端含义**：程序喂 fp32 `[1,2,1024]`（连续 8192 字节，C 序：先 1024 个 I，再 1024 个 Q），
读回 fp32 `[1,12]`（48 字节）；无需任何 int8 换算。

---

## 6. 校准集（量化 forward 数据）

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_12class_calibration.py`（只读源工程） |
| 样本数 | 252（12 类 × 21） |
| split | `ad_amr_v1_1_train`（冻结训练命名空间） |
| seed / split_code | 2026 / blake2s("ad_amr_v1_1_train")[:4] |
| RNG | 复刻 `ADAMRPairDataset.__getitem__` 的 `SeedSequence([seed, split_code, 0, index])` |
| 域 | 训练输入域：`generate_iq`(RMS=1.0) → ChannelPipeline → `np.stack((real, imag))` → fp32 `[2,1024]` |
| 样本字节 | 8192 B/条 |
| forward_list | `model_12class/calibration/forward_list.txt`（单列 `iq_N.bin`）SHA `6419217933…` |
| manifest | `model_12class/calibration/calibration_manifest.json` SHA `c073f92663cf37c677c7341a71491d2d3c48fd5aaa54866aa3d7b6a7e2dfa078` |

---

## 7. 部署黄金集（PyTorch→ONNX Runtime→NPU 验证）

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_deployment_golden.py`（ONNX Runtime，CPU） |
| 样本数 | 240（12 类 × 20），`input_000.bin … input_239.bin` |
| 输入 | fp32 `[1,2,1024]`（8192 B/条），SNR 固定 10 dB |
| 期望 | `deployment_golden/expected_logits_or_argmax.json`（argmax/class/confidence/12 维 logits） |
| manifest | `deployment_golden/manifest.json` SHA `81592ef13495a1d99fdee31ed6e8ce35db857816c16538c2db0627d288164b7c` |
| 自洽性 | argmax 与标签一致 **236/240 (98.3%)**（10 dB 高 SNR 下接近满，证明域/顺序正确，非 ~8.3% 随机） |

> Gate 7 用此黄金集验证 NPU：逐条喂 `input_N.bin` → NPU 输出 12 logits → argmax 与
> `expected_logits_or_argmax.json` 的 `argmax_idx` 比较。int8 量化后允许少量 argmax 翻转，
> 判定阈值与说明见 `docs/GATE6_9_BOARD_TEST.md`。

---

## 8. 状态

- 编译产物离线生成、契约实测核验完成。
- **未上板**：NPU 产物尚未在 FMQL30TAI 上跑通（`Device::Open` 需板端 iCraft 运行时）。
- 状态措辞：**`READY-FOR-12CLASS-NPU-COMPILE`**（编译阶段）→ 上板跑通 Gate 7 后由用户本人确认。
