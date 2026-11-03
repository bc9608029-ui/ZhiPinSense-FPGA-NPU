# M29 Phase D — 24类 252 输入判别测试（2026-10-10）

状态：`M29-PHASE-D-QUANTIZE-BLOCKED-ROOTCAUSE-ISOLATION`（判定 **A**：24类模型可进入并完成 Quantize，问题在 624 校准集；未碰板/未写 Flash/未访问 test）

本文件按用户批准的一次性小校准集判别测试记录：24类模型/算子/量化参数/输出维**一律不动**，仅把校准输入换成 12 类刚成功的同一份 252 个 IQ 样本，全新输出目录，只跑一次。

---

## 1. 实验设计（严格对齐用户 7 点要求）

| 要求 | 执行 |
|---|---|
| 不修改 24 类模型/ONNX/算子/量化参数/输出维 | `json`/`raw` 仍指向原 `model_24class_optimized.json/.raw`（SHA `8e3d06ba…`/`7cb9c32f…`，未动） |
| 用 12 类同一份 252 校准输入（内容/顺序/dtype/shape/布局/批组织/格式/加载全一致） | `forward_dir`/`forward_list` 直接指向 12 类 `model_12class/calibration/`（**同一份文件，非拷贝**） |
| 全新输出目录、只跑一次、不覆盖历史 | `F:\FPGA_Work\_tmp_24class_quantize_252_discriminator_20261010\` |
| 主入口与 12 类成功一致 | `C:/Icraft/CLI v3.39.0/bin/icraft.exe quantize`，默认 PATH（软链接 `/c/Icraft/CLI/bin`），无 export/无 D:\icraft/无直接子工具 |

## 2. 运行前记录

- 无残留 icraft 进程；USER=shado；PATH 含 `/c/Icraft/CLI/bin`。
- 校准输入 SHA256：`forward_list.txt` = `6419217933670dd883ecdbd78a6ffb2628ebc1f9923d0834390514648e07658d`；252 个 .bin 按列表顺序合并 = `70833d08054c014c3ccab68fd3dbbf0afda02e9559e91798917d0c07712de5d2`（总 2064384 B = 252×8192）。
- 24 类模型 SHA256：`model_24class_optimized.json` = `8e3d06bac597305c805be19622d1df452dda55706910cc00d3f9be7c57fa290c`，`.raw` = `7cb9c32f8af03357da4b37a40f0adc66f48e4e23b0c000ac8cfd04125626a637`（证明未改模型）。

## 3. 运行结果

| 项 | 值 |
|---|---|
| 真实退出码 | **0** |
| 耗时 / 峰值内存 | **443 s / 1973760000 B ≈ 1.84 GB** |
| Calibration Set Size | **252**（Batch Number 1 · Batch Size 252，与 12 类一致） |
| Before ReLU | ✅ 19:23:59.420 |
| Batch 0 Begin | ✅ 19:24:44.848（+45 s；12 类 +19 s，24 类模型更重） |
| Batch 0 End | ✅ 19:30:53.691 |
| Measure End | ✅ 19:31:14.023 |
| **poly_params 打开失败** | **0 次（未复现）** |
| 量化产物 | `model_24class_quantized.json` 401400 B / `.raw` 284500 B（仅故障隔离用，非最终结论） |

## 4. 判定 = A

24 类模型用与 12 类完全相同的 252 输入后**成功进入 Batch 0 Begin 并完成 Quantize** → **24 类模型本身可进入并完成 Quantize**；问题与原 624 校准输入的**规模/组织方式/内容**有关。

对照链（模型与量化参数恒不变，仅校准集变量）：
| 校准集 | 结果 | Before ReLU → 后续 |
|---|---|---|
| 12 类 252 | 成功 | +19 s 进 Batch 0 |
| 24 类 252 | **成功** | +45 s 进 Batch 0 |
| 24 类 624（原） | 失败 | 卡 Before ReLU 后 ~170 s，poly_params 失败 |

## 5. 根因表述（遵守规则 #7，不写 EMFILE 确认）

**资源/进程态假设**：HostBackend（libtorch 校准前向引擎）初始化阶段，随"模型规模 × 校准单批大小"增长的初始化工作量，在**单批 624** 时达到某资源上限（疑 FILE*/句柄，无 errno/ProcMon 实证），导致后续 `fopen(poly_params.json)` 返回 NULL。24 类 252（45s）与 624（~170s 后失败）的耗时/结局差异与"单批规模"强相关。**EMFILE 未确认，仅为假设。**

## 6. 拆批可行性（已确认）

`[quantize]` 支持 `batch` 参数（默认 1）：`batch=N` 把校准集分成 N 份依次前向并取平均。**约束：校准集总量必须被 batch 整除。** 624 = 26×24 = 13×48，故：
- `batch=26` → 每批 24（26 批）
- `batch=13` → 每批 48（13 批）
均覆盖"24 类 × 26 SNR = 624"全量样本不变，只拆批。

## 7. 下一步（待用户批准，本轮未执行）

保持 624 样本**不变**（同内容同顺序），仅加 `batch=26`（每批 24）或 `batch=13`（每批 48）重跑 quantize。成功 → 证实单批 624 资源耗尽，拆批为最终量化路径；据此完成 quantize→adapt→generate。

## 8. 红线保持

252 样本仅用于故障隔离，**不作为**最终 24 类量化结论；未因判别成功声明 INT8 通过；未改模型/标签/预处理/量化参数；未用 test 校准；未碰板/未写 Flash；未写任何 FINAL_*/NPU_PASS/24CLASS_PASS/PROJECT_COMPLETE。本轮只跑 1 次判别测试。
