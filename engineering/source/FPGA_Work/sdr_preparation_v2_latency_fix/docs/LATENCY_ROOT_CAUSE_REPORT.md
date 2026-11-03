# FPGA↔NPU 周期性延迟尖峰 — 根因诊断报告

> 日期：2026-10-05。范围：`continuous_joint_stress` 周期性延迟尖峰的**离线诊断与修复准备**。
> 目录：`F:/FPGA_Work/sdr_preparation_v2_latency_fix/`（独立复制自 v1，v1 完全未动）。
> 状态：**`READY-FOR-HARDWARE-LATENCY-RETEST`** —— 离线阶段只完成了诊断代码、主机纯逻辑测试、
> 主机语法校验与交付打包；**根因尚未确认、延迟尚未证明修复、未上板**。

---

## 1. 原始异常数据（来源：用户板端日志转录）

> ⚠️ 以下两次板测数据来自**用户板端日志转录**，本离线阶段**未取得原始日志文件**，
> 未做逐行核对，仅作为根因假设与复测门槛的依据，不构成已确认测量。

| 项 | 值 |
|----|----|
| 程序 | `continuous_joint_stress`（100 循环 Stress） |
| 正确性 | 两次运行均 `match 1200/1200`（argmax 全对） |
| 尖峰形态 | 从 **cycle 58** 起，**每 6 个 cycle**，固定落在每轮**第一个 NPU 帧 `frame=7`** |
| 尖峰耗时 | forward ≈ **425 / 604 / 937 ms** |
| 正常耗时 | forward ≈ **0.65 ~ 1.0 ms** |
| 两次运行一致性 | 位置完全一致（已排除随机调度抖动与串口打印干扰） |

`frame=7` 是每轮（cycle）12 个 NPU 帧（7..18）中的第一帧，即每次 `reset(1)` re-arm 序列的起点。

---

## 2. 根因假设（**未确认**）

> 此节为**假设**，不是结论。只有真实上板分段计时定位到具体阶段，并且 fixed 版本
> 消除尖峰后，才能把假设升级为「已确认根因」。

**假设**：NPU 热路径每帧都在分配/释放资源，触发 iCraft 运行时内存池的**周期性回收（GC）**。

每 cycle 12 帧 × 6 cycle = 72 次推理出现一次尖峰，强烈指向「每 N 次分配触发一次回收」。
当前定位到的三个热路径分配点（均在 `continuous_joint_stress.cpp` 内）：

1. `make_inputs()` → 每帧 `Tensor(value).mallocOn(host)` × 2；
2. `read_fp32_logits()` → 每帧 `std::vector<char> bytes` + `tensor.to(HostDevice)` 新 host Tensor + `std::vector<float> logits(8)`；
3. `make_inputs()` 内 `std::vector<Tensor> inputs` 每帧构造/析构。

**待证实**：尖峰具体落在哪一个阶段（`forward_submit` / `wait_ready` / `output_to_host` /
`output_read` 之一，还是输入分配阶段 `input_prepare`）。

---

## 3. 分段计时方案

新增 9 个阶段的独立计时（`std::chrono::steady_clock`，毫秒），每个阶段独立输出统计：

| 阶段 | 定义 |
|------|------|
| `reset` | `Device::reset(1)` + 前后只读 `VERSION` 体检 |
| `dequantize` | int8 → float 反量化 |
| `input_prepare` | 输入 Tensor 构造/写入 |
| `forward_submit` | `Session::forward(inputs)` 提交 |
| `wait_ready` | `waitForReady(kReadyTimeout)` 等待就绪 |
| `output_to_host` | `Tensor::to(HostDevice::MemRegion())` 输出搬移 |
| `output_read` | `host.read(...)` 读回 logits |
| `forward_legacy` | **= submit + wait + to_host + read**，与板测 forward 一一对应 |
| `total_inference` | 从帧开始到 read 完成的整帧耗时 |

每个阶段输出 `count / p50 / p95 / p99 / max / gt_5ms / gt_10ms / gt_100ms`。
**所有帧都进入统计**，不排除 warm-up、frame 7、前若干轮或任何慢帧；不加 sleep、不提高超时、不跳帧、不改 `reset(1)` 频率。

---

## 4. 是否已确认根因

**未确认。** 离线阶段只能证明「诊断代码已就绪、纯逻辑正确、语法通过」，不能证明尖峰发生在
哪个阶段。确认需要两步，且缺一不可：

1. `baseline_diag` 上板 100 循环，`LATENCY_PHASE_*` 显示出尖峰集中在某几个阶段；
2. `fixed` 上板（Smoke→Basic→Stress 100→Stress 1000），同样的阶段不再出现尖峰。

只有当 (1)(2) 都满足，本报告才可把 §2 的假设标注为「已确认根因」。

---

## 5. 生命周期与内存池假设示意

```
每帧热路径（v1 / baseline_diag 行为等价）：
  dequantize ──> make_inputs: mallocOn(host) ×2  ──> reset(1)  ──> forward ──> waitForReady
        ──> to(HostDevice) 新 host Tensor  ──> read ──> 比较/打印

假设的尖峰机制：
  每帧 2 次 mallocOn + 1 次 to() 新 host Tensor + 2 个 vector 分配
        ──> iCraft 运行时内存池累加 ──> 每约 72 次推理触发一次 GC ──> 尖峰
```

`fixed` 版将输入 `mallocOn` 降为一次（`input_allocations == 2`），消除每帧 `vector<Tensor>`
与 `vector<char>/vector<float>` 构造；输出转换 `to(HostDevice)` **保留**（无复用目标 API）。

---

## 6. 修改清单

| 文件 | 说明 |
|------|------|
| `board_package/latency_diag.hpp` | **新增**。纯逻辑：9 阶段统计（`compute_phase_stats`）、百分位、RSS 解析、序号映射、资源计数，以及三个门禁判定 `evaluate_latency`（延迟硬门）、`evaluate_resource`（资源门）、`detect_spikes`（尖峰复现检测）。iCraft-free。 |
| `board_package/continuous_joint_stress_baseline_diag.cpp` | **新增**。v1 行为等价 + 分段计时 + RSS + 资源计数，外加**自动复现门**：`BASELINE_SPIKE_REPRODUCED=YES/NO`，NO 即非零退出并禁止继续 fixed。 |
| `board_package/continuous_joint_stress_fixed.cpp` | **新增**。输入 Tensor 一次分配循环复用 + logit 缓冲预分配 + 同款诊断，外加**三门判定**（正确性/延迟/资源）+ 四结果行（`CORRECTNESS_RESULT`/`LATENCY_RESULT`/`RESOURCE_RESULT`/`FINAL_RESULT`），三门全 PASS 才返回 0。 |
| `board_package/CMakeLists.txt` | 增两个 target（`baseline_diag`、`fixed`），原 target 不变。 |
| `board_package/build_on_board.sh` | 三个程序一起 make。 |
| `board_package/run_baseline_diag_100.sh` 等 5 个脚本 | **新增**。复测顺序脚本，`exec` 透传程序退出码。 |
| `host_tests/test_latency_diag.cpp` + `build_and_run.sh` + `syntax_check.sh` | **新增**。主机纯逻辑测试（含 5/10/100ms 门限边界、超限、循环不完整、`input_allocations!=2`）+ iCraft 头文件语法校验。 |
| `docs/baseline_diag_vs_v1.diff` | **新增**。行为等价 diff 证据。 |

**未修改**：v1 的 `continuous_joint_stress.cpp`、`pl_ddr_register_map.hpp`、`iq_source.*`、
`file_iq_source.cpp`、冻结数据、CMake 原 target、RTL/XDC/位流/PS7-DDR/FMSH patch/模型/IQ/Golden/reference。

---

## 7. 冻结文件一致证据

v2 目录内 9 个冻结/复用文件与 v1 **逐字节一致**（`sha256sum`）：

`iq_input.bin`、`expected_tensor_plddr.bin`、`model.json`、`model.raw`、
`reference_argmax.txt`、`pl_ddr_register_map.hpp`、`iq_source.hpp`、`iq_source.cpp`、
`file_iq_source.cpp`。

---

## 8. 主机验证结果

**8.1 纯逻辑测试（`host_tests`）**：WSL Ubuntu g++ 15.2.0，`-std=c++17 -O2 -Wall -Wextra -Werror`，
plain 与 ASan/UBSan 两种构建均 **ALL PASS**（零告警、零失败）。覆盖：百分位（nearest-rank）、
9 阶段独立统计、`forward_legacy` 求和、RSS 解析、序号→(cycle,frame) 映射，以及**门禁边界**：
延迟硬门四条件（`gt_100ms==0`、`p99<=5ms`、`max<=10ms`、`gt_10ms==0`）各自独立失败、5ms/10ms/100ms
精确边界（`==` 通过、`+0.0001` 失败、`gt_*` 计数严格 `>`）、资源门（`input_allocations!=2`、
循环不完整、帧数不匹配）、尖峰复现检测（慢帧坐标、`==100ms` 不算尖峰）。

**8.2 板端源码语法校验（`-fsyntax-only`）**：用 iCraft 3.39 头文件
（`F:\嵌赛\audit\icraft_3_39\usr\include\`，`-isystem` 隔离第三方告警）对两个板端源码执行
`-fsyntax-only -Wall -Wextra -Werror`，**均 `syntax OK`**。

**结论措辞**：**host syntax verified；board link pending hardware retest。**
离线无法链接 iCraft 运行时库，**不冒充板端编译通过**。板端 `build_on_board.sh` 需在上板时执行。

**RSS 证据定位**：`read_vm_rss_kb()` 仅作为**辅助证据**。iCraft 设备内存池可能不反映在
Linux `VmRSS` 中，**不得用「RSS 稳定」单独证明没有运行时资源回收**。判定以 `LATENCY_PHASE_*`
分段计时为准。

---

## 9. 板端复测命令（固定顺序，见 `BOARD_LATENCY_RETEST.md`）

1. `baseline_diag` 100 循环 —— **必须先复现原周期尖峰**；
2. `fixed` Smoke（1 循环）；
3. `fixed` Basic（10 循环）；
4. `fixed` Stress（100 循环）；
5. `fixed` Stress（1000 循环）。

退出码已自动化，**无需人工读日志判 PASS/FAIL**：

- `baseline_diag`：输出 `BASELINE_SPIKE_REPRODUCED=YES|NO`。只有复现 ≥1 个
  `forward_legacy>100ms` 尖峰 **且** 正确性门通过才返回 0；`NO` 返回非零并打印
  `BASELINE_NO_SPIKE`，明确禁止继续 fixed 测试。
- `fixed`：输出 `CORRECTNESS_RESULT` / `LATENCY_RESULT` / `RESOURCE_RESULT` /
  `FINAL_RESULT`，三门全 PASS 才返回 0（任一 FAIL 即非零）。

若 `baseline_diag` **不能复现**原尖峰，立即停止，**不得**用 `fixed` 结果宣称修复。

---

## 10. 板端延迟硬门（不可放宽，已由程序自动执行）

对 `total_inference`（及任何阶段）的判定门槛：

| 门 | 要求 |
|----|------|
| `gt_100ms` | **= 0** |
| `p99` | **≤ 5 ms** |
| `max` | **≤ 10 ms** |
| `gt_10ms` | **= 0** |

`continuous_joint_stress_fixed` 对 `ps.total_inference` **在程序内执行此硬门**（`evaluate_latency`），
连同资源门（`input_allocations==2`、`completed_cycles==opt.cycles`、
`frame_timings.size()==opt.cycles*npu_frames_per_cycle`）一起接入退出码。**无法达到即 NO_GO，
并给出证据；不得放宽门槛。**

---

## 11. 回滚

v1（`sdr_preparation_v1`）**完全未动**，是回滚基线。v2 的 `baseline_diag` / `fixed` 均为新增文件，
不影响 v1 程序、CMake 原 target 或任何冻结工程。任何一步需要回滚，删除 v2 目录即回到 v1。

---

## 12. 交付状态

**`READY-FOR-HARDWARE-LATENCY-RETEST`**。

- 根因：**假设**（未确认）。
- 延迟：**未证明修复**。
- 板测数据：**用户板端日志转录**（未取得原始日志）。
- 编译：**host syntax verified；board link pending hardware retest**。
- 硬件 PASS：**不写**。

待用户本人上板按 `BOARD_LATENCY_RETEST.md` 顺序复测，我禁碰板、不写 Flash。
