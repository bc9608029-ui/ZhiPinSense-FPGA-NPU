# sdr_preparation_v1 — SDR 到货前系统集成准备 交付报告

> 日期：2026-10-04（复验 + 本批系统集成补充）。范围：**连续联合压力测试（FPGA↔NPU）
> 的离线准备** + **SDR 到货前可离线完成的系统级准备**（类别契约 / Pluto 接口层 /
> 离线 File IQ 端到端链）。
> 状态：**只做离线准备**，未上板、未装 SDR 驱动、未接 SDR、未改任何冻结工程/数值。
>
> 工作目录：`F:/FPGA_Work/sdr_preparation_v1/`（独立英文路径）。
> 冻结基线目录（**一律未动**）：`fpga_npu_joint_v1/`、`npu_realtime_v1/`、
> `pl_ddr_mandatory_core_v1/`、`rf_cognitive_system/`、六个 Mandatory Core RTL、
> Python Golden、固定 IQ/Tensor、`model.json`/`model.raw`/`reference_argmax`、
> 已验证 bitstream/LTX/capture/STA、AI_Mate.edif/FMSH patch、Vivado 2018.3。
> 本批**未改** RTL / 位流 / NPU 冻结工程 / `board_package/continuous_joint_stress.cpp`
> / 冻结 Golden / 联合压测包。

本文按任务书「结束时汇报 A–O」逐条作答。

---

## A. 新工程路径

```
F:/FPGA_Work/sdr_preparation_v1/
├── board_package/        # 自包含板级包（连续联合压测 + 冻结 IQ/Golden/model/reference）【冻结，未改】
├── sdr_adapter/          # IQ 数据源抽象 + 帧/时序/日志/性能/状态机骨架（iCraft-free）
│                         #   + categories/preprocess/classify/result_frame（类别契约+预处理+分类接口）
│                         #   + iio_backend/mock_iio/pluto（Pluto 接口层 + mock IIO）
│                         #   + offline_chain/unix_socket_sink/offline_e2e_main（离线端到端链 + 适配器）
├── contracts/            # sampling_and_iq_contract.md（采样率 + IQ 数值契约 + 类别契约 + Pluto）
├── config/               # sdr_adapter_config.conf（含 pluto_* 运行时字段）
├── templates/            # competition_recording.md（资源/延迟/吞吐/稳定性/功耗记录模板）
├── tests/                # C++ 单元测试 + Python 离线算法校验 + run_tests.sh
└── REPORT.md             # 本报告
```

## B. 复用了哪些已验证代码（未重写）

| 复用来源 | 复用的内容 |
|---------|-----------|
| `fpga_npu_joint_v1/board_package/fpga_npu_joint_smoke.cpp`（真板 PASS） | **Phase A PL-DDR 数据路径**：`Device::Open → defaultMemRegion().malloc(175104,false,64) → 动态物理地址 → 寄存器配置 → START → 轮询 DONE → IQ/TENSOR_ACCEPTED 计数 → chunk.read → 逐字节 Golden 比对`；常量 `kFrameCount=19 / kIqFileBytes=77824 / kTensorFileBytes=97280 / kAllocationBytes=175104`；`kIqScale=1/127`、`kPhysicalScale=2/127`；`kDeviceUrl="axi://zg330aiu?npu=0x40000000&dma=0x80000000"` |
| `npu_realtime_v1/board_package/npu_realtime.cpp`（真板 PASS） | **Phase B 常驻 Device 连续推理 + `Device::reset(1)` 逐帧 re-arm**（官方文档语义「只复位 FPGA 状态」）；`Session` 一次性 `apply()` + `forward → waitForReady → argmax` |
| `fpga_npu_joint_v1/board_package/pl_ddr_register_map.hpp` | **已验证寄存器图**（`VERSION=0x20260929`，基址 `0x400C0000` 运行时传入）——**逐字节一致** |
| `pl_ddr_mandatory_core_v1`（真板 PASS 的 ps_pl_ctrl_smoke 路径） | 动态地址 + 64 B 对齐 + 寄存器配置 + START/轮询 DONE 的底层读回模式 |
| 冻结数据（`iq_input.bin` / `expected_tensor_plddr.bin` / `model.json` / `model.raw` / `reference_argmax.txt`） | **逐字节一致**（`sha256sum` 与 `fpga_npu_joint_v1/board_package` 全同，见 M） |

**唯一新增证明点**：两条已 PASS 路径能否共用**同一 Device 生命周期**，且 `Device::reset(1)`
不会破坏下一轮 PL-DDR / Mandatory Core。这正是本板级包的上板验证目标。

## C. 新增 / 修改文件

**新增（全部新建，无覆盖任何冻结/既有工程）：**

| 文件 | 内容 |
|------|------|
| `board_package/continuous_joint_stress.cpp` | 连续联合压测主程序（FPGA + NPU 单 Device） |
| `board_package/iq_source.hpp` / `iq_source.cpp` | IQ 数据源契约 + `SdrIqSource` 占位（抛错） |
| `board_package/file_iq_source.cpp` | `FileIqSource`：冻结 IQ 字节精确回放 |
| `board_package/pl_ddr_register_map.hpp` | 已验证寄存器图（与源逐字节一致） |
| `board_package/CMakeLists.txt` / `build_on_board.sh` | gnu++17 构建；`Icraft::ZG330Backend + HostBackend + pthread + dl` |
| `board_package/run_smoke.sh` / `run_basic.sh` / `run_stress.sh` | 1 / 10 / 100 循环 |
| `board_package/README.md` | 板级包说明 + PASS 规则 |
| `board_package/sha256_manifest.txt` | 板级包 SHA-256 清单 |
| `sdr_adapter/iq_frame.hpp` | IQ 帧契约 + `iq::Source` 接口（iCraft-free） |
| `sdr_adapter/iq_source.hpp` / `.cpp` | `FileIqSource` / `SyntheticIqSource` / `SdrIqSource`(占位) |
| `sdr_adapter/sequence_monitor.hpp` | drop/overflow/duplicate/reorder/discontinuity/gap 检测 |
| `sdr_adapter/perf_stats.hpp` | 六阶段延迟统计（RAII 计时 + summary） |
| `sdr_adapter/logging.hpp` | 分级日志（stderr + 可选文件） |
| `sdr_adapter/ui_report.hpp` | JSON-lines UI 接口（result/status/metric） |
| `sdr_adapter/config.hpp` | `cfg::Config` + 扁平 key=value 解析 + 默认写出（含 `pluto_*` 运行时字段） |
| `sdr_adapter/pipeline.hpp` | 三段状态机骨架 + 错误恢复决策表 |
| `sdr_adapter/categories.hpp` | `cat::Contract`：冻结 8 / 当前 10 / 目标 12 三层类别契约（校验 `[8,16]`） |
| `sdr_adapter/preprocess.hpp` | 部署预处理（physical 前端 power/lag1_real/lag1_imag）的 float 参考实现 |
| `sdr_adapter/classify.hpp` | `classify::Classifier` 接口 + `MockClassifier`（明确 MOCK logits）+ softmax/argmax/top1 |
| `sdr_adapter/result_frame.hpp` | `rf::ResultFrame` 每帧判定（mock/source/置信度/异常标志） |
| `sdr_adapter/iio_backend.hpp` | `iio::Backend` 抽象 + `RawChunk`（设备读取契约） |
| `sdr_adapter/mock_iio.hpp` | `iio::MockBackend` 假 IIO（短读/超时/overflow/discontinuity/drop/断流/背压注入） |
| `sdr_adapter/pluto.hpp` | `pluto::Config`（8 项运行时参数）+ `pluto::PlutoIqSource`（可选编译 libiio） |
| `sdr_adapter/pluto_libiio.cpp` | 真实 `iio::LibiioBackend`（`-DSDR_ADAPTER_HAVE_LIBIIO` 编译；无设备抛 `device not found`） |
| `sdr_adapter/libiio_gate.cpp` | libiio 构建门主程序（0/1 两配置；无设备快速报 device not found、exit 2） |
| `sdr_adapter/build_libiio_gate.sh` | 两配置（0/1）构建+运行脚本（日志 `tee` 到 `build_libiio/`） |
| `sdr_adapter/libiio_offline/` | 离线安装包：6 个 amd64 debs + `libiio-0.26.tar.gz` + README（AArch64/静态链接方案）+ install 脚本 + 自有 SHA 清单 |
| `sdr_adapter/unix_socket_sink.hpp` | `ui::UnixSocketSink`：HDMI/UI 的 Unix 域套接字 JSONL 适配器 |
| `sdr_adapter/offline_chain.hpp` | `chain::run`：FileIqSource→预处理→分类→ResultFrame→sink 端到端 |
| `sdr_adapter/offline_e2e_main.cpp` | 可运行离线端到端 demo（JSONL 输出 + 可选 Unix 套接字） |
| `sdr_adapter/README.md` | 本层模块/构建/测试说明 |
| `config/sdr_adapter_config.conf` | 系统配置（SDR 字段 TBD） |
| `contracts/sampling_and_iq_contract.md` | 采样率 + IQ 数值契约（正式） |
| `templates/competition_recording.md` | 记录模板 |
| `tests/test_all.cpp` / `run_tests.sh` / `offline_algo_check.py` | C++ 单元测试 + Python 参考校验 |

**修改：** `REPORT.md`（本轮改写为 A–O + P/Q/R）、`sdr_adapter/config.hpp`（新增 `pluto_*`
字段）、`sdr_adapter/ui_report.hpp`（新增 `result_frame_line` + `ui::Sink`/`StdoutSink`）、
`sdr_adapter/pluto.hpp`（`make_backend()` 按 `SDR_ADAPTER_HAVE_LIBIIO` 门控 mock/libiio）、
`config/sdr_adapter_config.conf`（新增 `pluto_*` 字段）、
`contracts/sampling_and_iq_contract.md`（§9 类别契约 + §10 Pluto 接口）、
`tests/test_all.cpp` / `tests/run_tests.sh`（新增本批模块测试）。

## D. Device / Session / MemChunk 生命周期

整个压测期间（`continuous_joint_stress.cpp`）：

- **`Device::Open`** —— 循环前**一次**；**`Device::Close`** —— 结束时**一次**（RAII `DeviceGuard` 保证全路径关闭，关闭异常不吞）。
- **`Network::CreateFromJsonFile` + `lazyLoadParamsFromFile`** —— 一次。
- **`Session::Create<ZG330Backend, HostBackend>` + `apply()`** —— 一次。
- **`defaultMemRegion().malloc(175104, false, 64)`** —— 一次（`MemChunkGuard` 保证先 `free` 后 `Close`）；**每轮**把同一地址写入 `IQ_BASE` / `TENSOR_BASE`。
- **`Device::reset(1)`** —— 每个 NPU 帧前（**除全局首次**）re-arm。
- **无**逐帧/逐轮 Device 重开、**无**重复 `Session::apply()`。

## E. FPGA 与 NPU 交替运行状态机

每个联合循环（`continuous_joint_stress.cpp` 主循环）：

1. **采集**：`FileIqSource` 取 19 帧 × 1024 复数 int16，`short_frame` 拒绝送入 FPGA；
2. **FPGA**：写 IQ → 清零 tensor → `CONTROL_CLEAR` → 写 6 个寄存器（IQ_BASE/IQ_BYTES/TENSOR_BASE/TENSOR_BYTES/FRAME_COUNT）→ `CONTROL_START` → 轮询 `STATUS DONE/ERROR` → 读 `IQ_ACCEPTED`/`TENSOR_ACCEPTED`（均须 = 19456）→ 读回 97280 B tensor 逐字节比对 Golden（mismatch≠0 即 FAIL）；
3. **NPU**：frame 7..18（12 帧），每帧 `reset(1)` re-arm（非首帧）→ `forward → waitForReady → argmax` 比对 `reference_argmax.txt`；
4. **进入下一轮前**：重新配置**全部** PL 控制寄存器，**不依赖** reset 前寄存器状态。

**失败即停**：FPGA 超时/错误/计数不符/ tensor mismatch、NPU 错误/超时均按 `AbortRun` 语义中止（不跳阶段、不在陈旧数据上推理）。每轮记录：cycle ID、FPGA 状态、IQ/Tensor 计数、mismatch、NPU frame/pred/ref、timeout/error、reset 前后 VERSION、FPGA 时间、NPU 时间、吞吐率。

## F. reset(1) 前后 PL 状态检查方式

只读体检（不写任何私有寄存器，不用 `setOpWait`/`getOpWait`，不碰 `/dev/mem`）：

- 每轮**顶部**读 `VERSION` → `version_pre`；
- 每个 NPU 帧 `reset(1)` **前后各读一次** `VERSION`（`vb`/`va`），任一 ≠ `0x20260929` → `version_fail++`；
- 每轮**末尾**读 `VERSION` → `version_post`，与 `version_pre` 不一致时输出 `STRESS_VHEALTH` 告警；
- `MemChunk` 地址为分配时固定值，每轮重写进寄存器，天然校验地址未变。

## G. 100 循环压力测试判定规则

`STRESS_RESULT=PASS` 需**八条同时满足**（对应任务书 PASS 条件）：

1. `npu_matched == npu_compared == npu_frames_done`（所有有效 NPU 帧 argmax 匹配 reference）；
2. `delay_matched == 0`（无上一帧陈旧结果，delay shift = 0）；
3. `timeout == 0`、`error == 0`；
4. `fpga_mismatch_cycles == 0`（所有循环 tensor 逐字节 0 mismatch）；
5. `version_fail == 0`（`reset(1)` 未破坏 PL-DDR / Mandatory Core 寄存器）；
6. `Device::Open` 全程只一次（仅一行 `STRESS_SETUP`）；
7. 所有 `cycles` 完整结束（`smoke=1` / `basic=10` / `stress=100`）；
8. 无丢帧/重复/错序（`FileIqSource` 字节精确 + `SequenceMonitor`）。

100 循环对应：1,945,600 IQ 样本 + 1,945,600 tensor 样本 + 100 次 FPGA 任务 + 1,200 次 NPU 推理。

## H. IQ 数据源接口

`iq::Source`（`iq_frame.hpp`，iCraft-free）统一输出契约：

- 每帧 **1024 复数 IQ**，I/Q 均为 **signed int16**，`interleaved_iq` 字序 `[I, Q]`，**小端**；
- 带 **frame_id**；预留 **timestamp / overflow / drop / discontinuity** 状态位；
- 能检测**短帧、断流、样本不连续**；**<1024 点绝不静默送入 FPGA**。

实现：
- **`FileIqSource`**（当前实际使用）：读冻结 `iq_input.bin`，**循环回放 / 单次回放 / 限定帧数**，与 Golden 逐字节一致；
- **`pluto::PlutoIqSource`**（新增，已知设备 ADALM-Pluto）：从 `iio::Backend` 帧化、单调 frame_id、异常标志透传、断流恢复；可选编译 libiio，默认 mock 后端离线运行；
- **`SdrIqSource`**：只定义接口/占位，构造即抛错（保留，供未知设备兜底）；
- **`SyntheticIqSource`**：测试用。

## I. 训练预处理审计结果（只读，来源 `deployment_*.yaml`）

依据 `rf_cognitive_system/configs/deployment_numerical_contract.yaml#frozen_training_path` 与 `deployment_contract.yaml`：

- **训练时 IQ 数值范围**：复基带 **RMS = 1.0**（`amplitude: 1.0`）。
- **归一化方式**：**逐 record 复数 RMS 归一化**（`normalization: per_record_complex_rms`，公式 `x_clean = x_raw · amplitude / sqrt(mean(I²+Q²))`）——作用于**信道前 clean record**；**信道后不做归一化**（`post_channel_normalization: none`）。
- **峰值/RMS**：用 **RMS**（complex RMS），非峰值。
- **逐帧归一化结论**：训练是「逐 record RMS（信道前）」；**部署侧 `per_record_rms_normalization: forbidden_for_frozen_candidate`** —— SDR 接入**禁止逐帧 RMS/AGC 归一化**（否则破坏信道引入的功率变化信息，与冻结模型分布冲突），改用**单一全局 `receiver_scale`** 保持绝对尺度。
- **SDR float/int12/int16 → signed int16**：`x_model[n] = adc_count[n] · adc_lsb · receiver_scale`，`adc_lsb = 1/32768`，`receiver_scale` 为全局冻结标量（reference `1.0`，**需非盲重放数据标定后冻结**）。
- **`multiplier=127/shift=15` 契约**：**保持不动**——量化器本体保存在冻结 Mandatory Core 内部；SDR 适配层只负责把真实 ADC 样本映射到「等价冻结 IQ」的 int16 尺度。
- **属于 SDR adapter（不能写进冻结 Core）的预处理**：采样率转换（若 SDR 原始采样率 ≠ 128 ksps）、`receiver_scale` 标定。**DC 去除 / FIR / FFT 当前初始划分为 `bypass / bypass / false`**（`initial_partition`）——冻结 Core 不做，SDR 层亦不擅自增加（否则改变冻结模型分布）。

## J. SDR IQ → INT16 转换契约

见 `contracts/sampling_and_iq_contract.md` §3（正式）。要点：

- FPGA 输入：`interleaved_iq`、`signed_int16`、小端、`binary_point=15`（Q1.15）、AXI-Stream `tdata=32`；
- SDR 换算：`x_model = adc_count · adc_lsb · receiver_scale`，`adc_lsb=1/32768`，`receiver_scale` 全局冻结（reference 1.0）；
- `multiplier=127/shift=15`（IQ）、`127/shift=31`（physical）保存在冻结 Core，本层不动。

## K. 缓冲与 ownership 方案

| 缓冲 | 大小 | 所有权 |
|------|------|--------|
| 采集缓冲（SDR 适配层写入；现 `FileIqSource` 只读） | 单帧 4096 B | 源层 |
| FPGA 缓冲 = Linux `MemChunk`（PL DDR） | 175104 B（IQ 77824 + tensor 97280） | 主机所有，每轮地址写入寄存器交给 PL |
| NPU 输入（`iq[1,2,1024]` + `physical[1,3,1024]` float32） | 每帧临时 | `HostDevice::MemRegion()` |
| 结果缓冲 | 每帧 verdict 即时消费 | 仅聚合计数跨轮存活 |

**背压**：短帧拒绝；NPU 未 ready 记 `timeout`，**不丢帧 / 不补帧 / 不重放**。

## L. 板端编译 / 运行命令

```sh
cd board_package
sha256sum -c sha256_manifest.txt     # 先校验（16 文件全 OK）
./build_on_board.sh                  # cmake + make（gnu++17，iCraft 3.39）
./run_smoke.sh                       # 1 循环（快速正确性）
./run_basic.sh                       # 10 循环（稳定性）
./run_stress.sh                      # 100 循环（完整压测）
```

或直接：`./build/continuous_joint_stress --model model.json --raw model.raw --iq iq_input.bin --expected-tensor expected_tensor_plddr.bin --reference reference_argmax.txt --reg-base 0x400C0000 --first 7 --last 18 --cycles 100`。

## M. SHA 校验结果

- `board_package/sha256_manifest.txt`：**16 文件，`sha256sum -c` 全 OK**（2026-10-04 复验，冻结未改）。
- 6 个冻结文件与 `fpga_npu_joint_v1/board_package` **逐字节一致**（`iq_input.bin` / `expected_tensor_plddr.bin` / `model.json` / `model.raw` / `reference_argmax.txt` / `pl_ddr_register_map.hpp`）。
- 单元测试 `tests/run_tests.sh`（WSL Ubuntu g++ 15.2.0，`-std=gnu++17 -Wall -Wextra -O2`）**零告警编译通过，`RESULT pass=212 fail=0`**（2026-10-04 复验，含本批新增模块）。
- `sdr_adapter/sha256_manifest.txt`：本批系统层文件 SHA-256 清单（见下）。
- **libiio 构建门**（Task 3）：`build_libiio_gate.sh` 两配置实编译均通过；`=1` 链接
  libiio 0.26 成功，无 Pluto 时 `device not found` 约 4ms、exit 2（不崩溃/不卡死/不回退
  MOCK）。`sdr_adapter/sha256_manifest.txt` 现 **28 文件**、`libiio_offline/sha256_manifest.txt`
  **7 资产**，均 `sha256sum -c` 全 OK（见 R）。

## N. 是否具备下一次集中上板压力测试的条件

**具备。** 板级包自包含、代码复用两条真板 PASS 路径、寄存器图与冻结数据逐字节一致、SHA 全 OK、单元测试 86/0、预处理契约已冻结。上板前唯一剩余动作是：板卡到位后按 `run_smoke → run_basic → run_stress` 顺序执行，并据 `STRESS_RESULT=PASS/FAIL` 判定。

**不具备 SDR 实机接入条件**（SDR 未到货，属预期）；但 SDR 接口层 / mock IIO /
离线端到端链 / **libiio 构建门**已离线就绪（见 P / Q / R）。

## O. SDR 信息现状（已更新：设备已知为 ADALM-Pluto）

- **设备已明确**：ADALM-Pluto（AD9363，libiio，USB）。据此新增 `pluto::PlutoIqSource`
  接口层（可选编译）与 `iio::MockBackend` 离线验证（见 P），**未臆造任何设备实测值**。
- 仍 **TBD**（到货后非盲重放确定，本层不猜）：
  1. 实际 **URI / 中心频率 / 采样率 / RF 带宽 / 增益模式 / 增益 / 缓冲长度 / 超时**
     —— 均由 `pluto::Config` / `cfg::Config` 的 `pluto_*` 字段**运行时承载**（默认 0/""）；
  2. 原始采样率是否需重采样到 128 ksps（及重采样算法，只落在 SDR 适配层）；
  3. `receiver_scale` 的**非盲重放标定值**（冻结前）；
  4. SDR 硬件计数器位宽（决定 frame_id 回绕；当前适配层用自身单调计数器，不依赖硬件回绕）。

## P. 本批系统集成补充（SDR 到货前离线可完成项）

**P1 — 类别契约（三层，不写死 8 类）**：`cat::Contract`（`sdr_adapter/categories.hpp`）
携带分类宽度（合法 `[8,16]`），三层 `frozen_8` / `current_10` / `target_12` 各带
provenance；分类接口 `classify::Classifier` 按契约宽度输出 N 类，`MockClassifier`
离线以 **MOCK logits**（`mock=true`、`source="mock"`）占位，**不冒充真实推理**。

**P2 — Pluto 接口层（可选编译）**：`pluto::Config` 承载 8 项运行时参数
（URI/中心频率/采样率/RF 带宽/增益模式/增益/缓冲长度/超时），默认 0/""=未指定；
`pluto::PlutoIqSource` 从 `iio::Backend` 帧化 1024 复采样、分配单调 frame_id、
透传 overflow/discontinuity/dropped、EOS 半帧标记 short_frame、超时重试后中止、
断流 reopen 恢复并标记 discontinuity。默认无 libiio 走 mock 后端；定义
`SDR_ADAPTER_HAVE_LIBIIO` 才链接真实 libiio 后端。

**P3 — mock IIO 后端（无 Pluto 离线验证）**：`iio::MockBackend`（`mock_iio.hpp`）
确定性复音 + 有界环形缓冲 + 故障注入，单测覆盖：连续缓冲、短读、超时、overflow、
discontinuity、frame_id 连续性、断流恢复、背压（环形溢流丢样本计数）。

**P4 — 离线 File IQ 端到端链**：`chain::run`（`offline_chain.hpp`）串起
`FileIqSource → 1024 复采样帧 → 部署预处理（physical 前端，float 参考）→
分类接口（MockClassifier）→ ResultFrame → HDMI JSONL/UnixSocket 适配器`。
`ui::result_frame_line` 序列化 `rf::ResultFrame`（含 `mock` 字段）；`ui::UnixSocketSink`
经 Unix 域套接字输出 JSONL。可运行 demo `offline_e2e_main.cpp`。

## Q. 交付状态（四类分别汇报）

| 状态 | 内容 | 判据 |
|------|------|------|
| **已离线验证** | 类别契约 / 预处理 / 分类接口 / ResultFrame / mock IIO / PlutoIqSource / 离线端到端链 / Unix 套接字适配器 / `pluto_*` 配置解析 | WSL g++ 15.2.0 `-Wall -Wextra -O2` **零告警**，`pass=212 fail=0`；demo 逐帧输出 JSONL（含 `"mock":true`） |
| **待上板** | `board_package` 连续联合压测（FPGA↔NPU 单 Device） | 板卡到位后 `run_smoke→run_basic→run_stress`，`STRESS_RESULT=PASS/FAIL` |
| **待 Pluto** | 真实 libiio 后端 `pluto_libiio.cpp` **已实现**（编译+链接+无设备快速失败已离线验证）；URI/频率/增益等 8 项运行时参数**实值**；`receiver_scale` 标定 | SDR 到货 + `-DSDR_ADAPTER_HAVE_LIBIIO` + 非盲重放标定（**真采集不 PASS**，见 R） |
| **待最终模型** | 10/12 类真实 logits（替换 MOCK）；分类宽度从 `frozen_8` 切换到 `current_10`/`target_12` | 模型冻结 + NPU 路径就绪后，用 `cat::Contract` 切换，**当前一律 MOCK** |

## R. libiio 构建门（Task 3，SDR 到货前最后的构建门）

**结论（2026-10-04，WSL 主机，`sdr_adapter/build_libiio_gate.sh`）：** 分别实编译
`SDR_ADAPTER_HAVE_LIBIIO=0` 与 `=1` 两种配置，**均编译通过**；`=1` 链接 libiio 成功，
无 Pluto 设备时实际运行**快速、明确**返回 `device not found`（约 4ms，exit 2），
**不崩溃 / 不卡死 / 不回退 MOCK**。

| 配置 | 编译 | 链接 | 运行（无设备） |
|------|------|------|----------------|
| `=0`（默认，mock） | 通过 | —（header-only） | mock 后端离线读 4 帧，exit 0 |
| `=1`（libiio） | 通过 | 通过（`-liio` + `-Wl,-rpath-link`） | `GATE: pluto: device not found (no ADALM-Pluto on USB)`，exit 2，约 4ms |

**记录的环境与依赖：**
- 编译器：g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0，`-std=gnu++17 -Wall -Wextra -O2`（零告警）。
- libiio 版本：**0.26**（`0.26-2build2`，Ubuntu 25.04 "resolute" universe）。
- `libiio.so.0.26` 依赖（DT_NEEDED）：libusb-1.0.so.0、libserialport.so.0、
  libavahi-client.so.3、libavahi-common.so.3、libxml2.so.16、libc.so.6。

**实现：**
- `sdr_adapter/pluto_libiio.cpp`：真实 `iio::LibiioBackend`。`open()` 空 URI 时只扫 USB
  后端（`iio_create_scan_context("usb",0)`），无设备立即抛 `device not found`；显式
  `ip:` URI 走 libiio 自身网络超时。AD9361 RX 缓冲读取按 ADI `ad9361-iiostream` 规范，
  但**未经板卡验证**（真采集不 PASS）。
- `sdr_adapter/pluto.hpp`：`make_backend()` 按宏门控 —— 无 libiio 返 mock；有 libiio
  由 `pluto_libiio.cpp` 定义（**无设备时抛异常，绝不回退 mock**）。
- `sdr_adapter/libiio_gate.cpp` + `build_libiio_gate.sh`：两配置构建+运行+判 exit code。

**AArch64 部署与离线/静态链接方案**（详见 `sdr_adapter/libiio_offline/README.md`）：
- 离线资产：6 个 amd64 debs（**仅主机验证，不上板**）+ `libiio-0.26.tar.gz`（可交叉编译）。
- 方案 A：离线 .deb（板卡 OS 为 Debian/Ubuntu 系时，从 `ports.ubuntu.com` 取 arm64 包）；
- 方案 B：源码交叉编译（`aarch64-linux-gnu` + CMake）；
- 方案 C：**静态链接最小化**（推荐）——禁用网络/本地/串口后端，libiio 只剩 libusb-1.0，
  静态链出自包含板卡二进制（无 .so 运行时依赖）。

**边界：** 只验证「编译+链接+无设备快速失败」；**不声称真实采集 PASS**。真实采集、
8 项参数实值、`receiver_scale` 标定仍属「待 Pluto 到货后非盲复测」。

---

## 约束核对（不变）

未修改任何冻结文件/数值；未上板；未装 SDR 驱动；未接 SDR；未重训模型；未进入真实
驱动安装；未覆盖任何既有基线目录。如需上板 / 烧录 / 改已验证工程，会先停下确认。
