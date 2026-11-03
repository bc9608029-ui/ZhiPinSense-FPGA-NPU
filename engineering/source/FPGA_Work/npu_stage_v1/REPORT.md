# NPU-only 真板测试前准备 —— 完成报告（A–M）

本报告对应"NPU-only 真板测试前全部准备工作"。结论：**全部准备已完成**，
下一轮只做板卡运行（见 L 节边界）。全程未触发任何停止条件（见 K 节）。

---

## A. 冻结资产保护状态 —— 通过

本轮所有新产物均写入英文路径 `F:/FPGA_Work/npu_stage_v1/`（可读中文路径、不写）。
下列 10 项冻结资产未被改动、未被覆盖：

1. 六个 Mandatory Core RTL —— 未改
2. `AI_Mate.edif` —— 未改、未加 false path
3. Golden —— 未改
4. FMSH patch —— 未改
5. `best.pt` —— 未改（SHA-256 `f9e4b5e5…d71a6`）
6. 原始 ONNX —— 未改（`time_power_phase_npu_partition_opset17.onnx`，SHA-256 `2e501465…0051d`）
7. 当前 Tensor 数值与排列 —— 未改（5-plane，19 帧，97,280 B）
8. 已验证 hardware capture —— 未改（`expected_tensor_plddr.bin`，SHA-256 `7f4bce13…2af5`）
9. 未重新训练、未接 SDR、未改 FPGA 工程、未重新生成 bitstream
10. 本轮未连接板卡、未运行 NPU、未改 Vivado 工程

## B. iCraft 3.39 编译 —— 完成（5 阶段全 PASS）

工具 `C:/Icraft/CLI v3.39.0/bin/icraft.exe`，配置 `compile/compile_config.toml`。
parse → optimize → quantize → adapt → generate 全部 exit 0。

- 最终产物：`compile/jsonraw/rfnet_npu_ZG.json`（140,873 B，SHA-256 `ad57fc0b…a2e4`）
  与 `rfnet_npu_ZG.raw`（2,507,348 B，SHA-256 `c48979b3…0b42a`）
- 87 ops = 85 HardOp（全部 `@zhuget(330)`）+ Input + Output（`@hostt`）
- 无算子删除/替换、无结构改动、无 HostBackend 回退、无输入 shape/量化规则改动
- 记录的非致命告警（非 waive）：AvgPool `count_include_pad`（已验证 pad=0 无影响）、
  `no_imagemake` 在 zhuge 无效、`ConcatNormratio` 归一、nvfuser DLL 缺失
- 完整 SHA-256 与各阶段输出见 `compile/compile_report.md`

## C. 校准输入 —— 完成（168 样本，非随机）

`calibration/generate_calibration.py` 复用冻结 FPGA golden 路径生成 168 个 FP32
校准样本（train/val 分布，seed 2026，未触 final_blind_test）。

- 边界确认为 **FP32**（从 `export_deployment_candidate.py` 与 ONNX 输入确认）
- 校准域 = 反量化 FPGA 域：iq = int8×(1/127)、physical = int8×(2/127)
- 产物：`cal_data/iq_N.bin`、`physical_N.bin`、`forward_list.txt`、`calibration_manifest.json`

## D. compiled_model_gate —— PASS（13 项全通过）

`compiled_model_gate/verify_compiled_gate.py` 从最终 `rfnet_npu_ZG.json` 逐项校验，
16 项检查（13 项契约 + 3 项扩展）全部 PASS：

- 输入 2 个：`iq [1,2,1024]` FP32、`physical_features [1,3,1024]` FP32，layout `**C`（channel-first），batch=1
- 输入字节 8,192 + 12,288；输出 `logits [1,8]` FP32（32 B）
- 内部存储 `@sint(8)`（int8 量化生效）；iq 内部 scale 0.0071911365、physical 0.011158751（对称，z=0）
- 无 HostBackend 回退；target `@zhuget(330)`

**关键契约结论**：编译模型输入是 FP32（非 SInt8）。因此主机侧适配器用冻结参考
反量化（iq×1/127、physical×2/127）把 FPGA SInt8 转成 FP32 再喂 NPU，NPU 内部再按
其自有 scale 量化。这是纯适配层数学转换，未改 Mandatory Core/Golden，未伪造 PASS，
原始 FPGA tensor 逐字节保留（`expected_tensor_plddr.bin`）供 bit-exact 核对。

## E. PC 参考推理 —— 完成（19 帧，PyTorch best.pt）

`reference/pc_reference_inference.py`（无 onnxruntime）对 `expected_tensor_plddr.bin`
做 19 帧推理，输出 8 logits + argmax + softmax + top1-top2 margin。

- 产物：`reference/pc_reference_19frames.json`（SHA-256 `108b8e04…0febb`）与 `.csv`
- 帧 0-6 = OOD（记录 logits、不计入准确率）；帧 7-18 = BPSK/QPSK/16QAM/64QAM @ +20/0/−10 dB
- 首个有效帧 = **frame 7**（BPSK +20 dB，argmax=0 BPSK，conf 0.9493）

**诚实记录（非 bug）**：有效帧 argmax 准确率 = 4/12（33%）。已用独立诊断核对：
(1) 物理特征反量化（×2/127）与模型自身 `physical_frontend` 一致到 ~1e-4，说明参考路径
正确；(2) 浮点域（训练尺度）本身仅 7/12（58%），64QAM 与 16QAM/QPSK 系统混淆，低 SNR
帧经 `_int16_from_complex` 峰值归一 + int8 量化后 RMS 被压缩（~2.3→~0.27），进一步掉点。
参考结果仍是无误的 NPU 对照基准——NPU 与参考应 argmax 一致。

## F. NPU-only 测试程序 —— 完成（源码 + CMake + 构建脚本 + API 静态核对）

`npu_program/npu_only_smoke.cpp`（gnu++17），基于官方 API 静态核对
（`C:/Icraft/CLI v3.39.0/include/` 下 `Session::Create<…>`、`Tensor::write/read`、
`ScalarType::isFP32`、`Network::CreateFromJsonFile` 等签名均已确认）。

- 支持 `--frame 7` 与 `--all-frames`；读 97,280 B tensor，按契约切分
- 主机侧反量化（iq×1/127、physical×2/127）后喂 FP32
- 仅 `Session::Create<ZG330Backend>`，禁止 HostBackend 回退
- 输出 8-class 结果 + argmax + 计时；加载 `reference_argmax.txt` 对有效帧做 class-match
- 无 /dev/mem、无内核驱动、无 AXI DMA；错误即退出（exit 1）
- 无 aarch64 交叉编译器 → 交付源码 + CMake + `build_on_board.sh`，板端 g++ 编译是首个板端动作

## G. board_package —— 完成（12 文件，自包含）

`board_package/`：`model.json`、`model.raw`、`expected_tensor_plddr.bin`、
`pc_reference_19frames.json/.csv`、`reference_argmax.txt`、`npu_only_smoke.cpp`、
`CMakeLists.txt`、`build_on_board.sh`、`run_frame7.sh`、`run_all_frames.sh`、
`README.md`、`sha256_manifest.txt`。

板端脚本均不自动写 QSPI、不改 SD 启动、不自动升级系统、不 apt 安装、不自动下载
bitstream、不自动重试。

## H. README 执行顺序 —— 完成（11 步）

`README.md` 给出 11 步板端执行顺序（连接板卡 → 确认 bitstream → 确认运行时 → 拷贝
包 → 校验 SHA-256 → 板端编译 → 单帧推理 → 单帧核对 → 19 帧推理 → 与参考比较 →
记录保存）。

**保留已知项**：1 GHz BUFG Min-Period 路径
`Required 1.409 ns / Actual 1.000 ns / Slack -0.409 ns`，不 waive、不加 false path、
不改 EDIF、不降频。

## I. 本轮边界遵守 —— 通过

本轮未连接板卡、未运行 NPU、未修改 Vivado 工程、未接 SDR、未重新训练、未重新生成
bitstream。所有动作均为只读分析 + 新文件生成（英文路径）。

## J. 契约一致性总览

| 环节 | 结果 |
|---|---|
| ONNX 输入边界 | FP32（export 代码 + iCraft 解析双重确认）|
| 编译模型输入 | FP32 [1,2,1024]+[1,3,1024]（gate PASS）|
| 适配器转换 | iq×1/127、physical×2/127（冻结参考）|
| NPU 内部量化 | iq 0.0071911365、physical 0.011158751（对称）|
| FPGA 输出 | SInt8 5-plane（逐字节保留）|

FPGA 输出 scale 与编译模型输入边界不同 → 已按指示在独立 Linux/NPU 适配器做数学
转换（不 fake PASS），并保留原始 FPGA tensor 供 bit-exact 核对。

## K. 停止条件检查 —— 均未触发

只有以下 5 类情形才停止，本轮**未发生**：

1. 需修改模型数学 —— 未发生
2. 需重新训练 —— 未发生
3. 需安装/下载软件 —— 未发生
4. iCraft 编译器不可恢复错误 —— 未发生（5 阶段全 PASS）
5. 编译产物与 FPGA tensor 契约不兼容 —— 未发生（契约已核对，适配器已定义）

## L. 下一轮边界（唯一允许动作）

下一轮**只做**：

1. 连接板卡
2. 下载/确认 bitstream
3. 板端编译或运行程序
4. 单帧 NPU 推理（frame 7）
5. 19 帧 NPU 推理
6. 与参考结果比较

不重跑任何准备步骤。

## M. 遗留与风险（已记录，不阻塞）

1. 有效帧参考准确率 4/12（模型 + int8 峰值归一化共同导致），NPU 对照以 argmax
   一致为准，不以 label 准确率为准。
2. `reference_argmax.txt` 与 `pc_reference_19frames.*` 的 SHA-256 需在板端
   `sha256sum -c` 前与 manifest 一致。
3. 板端 aarch64 编译依赖 iCraft 3.39 运行时 `/usr/cmake` 配置；若缺失，属"需安装
   软件"停止条件，应上报而非擅自安装。
4. 1 GHz BUFG Min-Period 已知项在 NPU 阶段保持不变，不因 NPU 测试而 waive。
