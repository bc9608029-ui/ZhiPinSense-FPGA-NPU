# FPGA↔NPU 周期性延迟尖峰 — 根因诊断报告（最终版）

> 日期：2026-10-05。目录：`F:/FPGA_Work/sdr_preparation_v3_logging_fix/`（独立复制自 v2，**v2/v1 均未动**）。
> 状态：**`READY-FOR-HARDWARE-LATENCY-RETEST`**（非侵入式日志版）。
> 本版结论与 v2 相反：**根因不是输入 Tensor 分配，而是 115200 串口实时逐帧打印的观察者效应**。

---

## 1. 原始异常数据（来源：用户板端日志转录）

> ⚠️ 以下数据来自**用户板端日志转录**，本离线阶段未取得原始日志文件，未做逐行核对，
> 仅作为根因分析与复测门槛的依据，不构成本阶段独立完成的测量。

| 项 | 值 |
|----|----|
| 程序 | `continuous_joint_stress`（100 循环 Stress） |
| 正确性 | 两次运行均 `match 1200/1200`（argmax 全对） |
| 尖峰形态 | 从 **cycle 58** 起，**每 6 个 cycle**，固定落在每轮**第一个 NPU 帧 `frame=7`** |
| 尖峰耗时 | forward ≈ **425 / 604 / 937 ms** |
| 正常耗时 | forward ≈ **0.65 ~ 1.0 ms** |
| 两次运行一致性 | 位置完全一致 |

`frame=7` 是每轮（cycle）12 个 NPU 帧（7..18）中的第一帧，即每次 `reset(1)` re-arm 序列的起点。

---

## 2. 根因反转：真实板测结论（**用户板端实测**）

> 本节的结论来自**用户本人上板实测**，本 API 未操作板卡、未写 Flash。板测数据标注为
> 「用户板端实测 / 用户板端日志转录」。

板测逐步排除，最终把根因反转：

1. **输入复用版（`fixed`）上板仍出现尖峰** —— v2 的 `fixed` 已把输入 Tensor 复用
   （`input_allocations == 2`）并预分配 logit 缓冲，但**尖峰仍在**（同为 cycle 58 起每 6 cycle、
   frame=7、数百 ms）。这证明**输入 Tensor 分配不是尖峰根因**。
2. **改为非侵入式日志后尖峰消失** —— 把逐帧实时打印从 115200 串口重定向到文件、运行时串口保持安静，
   同样的负载下**尖峰不再出现**。
3. 结论：**慢速 115200 串口上的实时逐帧打印 = 观察者效应**，串口背压 + 调度扰动制造了
   425~978 ms 的**虚假尖峰**；它与 NPU 推理本身、输入分配、GC 都无关。

> 这是对 v2 报告 §2 假设的**否定**：v2 假设「iCraft 内存池每 72 次分配触发一次 GC」未被证实，
> 且与其配套的「必须复现尖峰才允许继续 fixed」门禁在真实板测下被证伪（见 §3 修正）。

---

## 3. 最终根因结论

**已确认根因：慢速 115200 串口上的实时逐帧日志输出（观察者效应）制造了 425~978 ms 的虚假延迟尖峰。**

- 输入 Tensor 分配：**不是根因**（假设已否决）。
- 资源复用（`input_allocations == 2`、logit 预分配）：**可保留**（降低 `input_prepare` 开销），
  但**不得声称它消除了尖峰**——尖峰消除归因于「非侵入式日志」，而非资源复用。
- 判定依据以 `LATENCY_PHASE` 分段计时为准，`VmRSS` 仅作辅助证据。

---

## 4. v3 修改内容

| # | 改动 | 说明 |
|---|------|------|
| 1 | 所有性能脚本 → 非侵入式日志 | 完整输出写带时间戳的日志文件；运行期间串口保持安静；退出后只打印简短摘要；真实退出码原样透传。**禁止 `\| tee` 与测量期间 `tail -f`。** |
| 2 | 修正 baseline 门禁 | `BASELINE_SPIKE_REPRODUCED` 降为**仅诊断**，不再决定退出码；baseline 退出码 = 正确性门 + 非侵入式延迟门；输出 `BASELINE_CORRECTNESS_RESULT` / `BASELINE_LATENCY_RESULT` / `BASELINE_FINAL_RESULT`；**不再打印「没有尖峰所以禁止继续 fixed」**。 |
| 3 | 保留延迟硬门 | `gt_100ms==0`、`p99≤5ms`、`max≤10ms`、`gt_10ms==0`（允许个别 `gt_5ms=1`、max 6.263ms 之类）。 |
| 4 | 增加防误用提示 | 当 stdout 连接到慢速 TTY 时打印 `WARNING: live per-frame serial output invalidates latency measurements`。 |

脚本非侵入式模板（核心）：

```sh
set +e
"$BIN" ... --cycles N > "$LOG_FILE" 2>&1
rc=$?
set -e
grep -E '...' "$LOG_FILE" || true
echo "LOG_FILE=$LOG_FILE"
echo "EXIT_CODE=$rc"
exit "$rc"
```

---

## 5. 修改清单

| 文件 | 说明 |
|------|------|
| `board_package/continuous_joint_stress_fixed.cpp` | **仅**加 `#include <unistd.h>` + 启动时 isatty 防误用检查。**推理热路径一字未改。** |
| `board_package/continuous_joint_stress_baseline_diag.cpp` | 加 isatty 检查；结尾重写：删除「必须复现尖峰」门，改为正确性门 + 非侵入式延迟门 + `BASELINE_*` 三结果行 + `baseline_final_pass` 决定退出码。**推理热路径未改。** |
| `board_package/latency_diag.hpp` | 新增 `baseline_final_pass(correctness, latency_gate)` 纯函数；`SpikeDetection` 注释更新为「仅诊断」。 |
| 8 个 `run_*.sh` | 全部改为非侵入式（日志只写文件、结束后打印摘要、真实退出码透传）。 |
| `host_tests/test_latency_diag.cpp` | 新增 `baseline_final_pass` 边界测试（无尖峰+好延迟 PASS / 正确性 false FAIL / 延迟门 fail FAIL）。 |
| `host_tests/test_script_behavior.sh` | **新增**。脚本行为测试：`bash -n` 语法、退出码透传、日志只写文件/结束后摘要。 |
| `docs/LATENCY_ROOT_CAUSE_REPORT.md`、`docs/BOARD_LATENCY_RETEST.md` | 结论改写 + 复测指南改写。 |
| `board_package/README.md` | 增补 baseline_diag/fixed 与非侵入式脚本说明。 |

**未修改**：v1 `continuous_joint_stress.cpp`、`pl_ddr_register_map.hpp`、`iq_source.*`、`file_iq_source.cpp`、
冻结数据、CMake 原 target、RTL/XDC/位流/PS7-DDR/FMSH patch/模型/IQ/Golden/reference。
**fixed 的 C++ 推理热路径未改**（仅启动时 isatty 检查），故无需重跑 100/1000 循环的额外理由
——但 100/1000 循环本就是复测流程一部分，照常执行。

---

## 6. 冻结文件一致证据

v3 目录内 9 个冻结/复用文件与 v1 **逐字节一致**（`sha256sum`）：

`iq_input.bin`、`expected_tensor_plddr.bin`、`model.json`、`model.raw`、
`reference_argmax.txt`、`pl_ddr_register_map.hpp`、`iq_source.hpp`、`iq_source.cpp`、
`file_iq_source.cpp`。

---

## 7. 主机验证结果

- **7.1 纯逻辑测试（`host_tests/build_and_run.sh`）**：WSL Ubuntu g++ 15.2.0
  `-std=c++17 -O2 -Wall -Wextra -Werror`，plain 与 ASan/UBSan 均 **ALL PASS**（零告警、零失败）。
  覆盖：百分位（nearest-rank）、9 阶段统计、`forward_legacy` 求和、RSS 解析、序号↔(cycle,frame) 映射、
  延迟硬门边界（5/10/100ms 精确边界）、资源门、尖峰检测，以及新增的 `baseline_final_pass` 边界。
- **7.2 脚本行为测试（`host_tests/test_script_behavior.sh`）**：8 个 `run_*.sh` `bash -n` 全过；
  用 mock 二进制验证退出码透传（0 与 3）、逐帧输出只进日志文件（不泄漏到 stdout）、
  结束后打印摘要与 `LOG_FILE`/`EXIT_CODE`。**ALL SCRIPT TESTS PASSED**。
- **7.3 板端源码语法校验（`host_tests/syntax_check.sh`）**：用 iCraft 3.39 头文件
  （`-isystem` 隔离第三方告警）对两个板端源码 `-fsyntax-only -Wall -Wextra -Werror`，
  **baseline_diag / fixed 均 syntax OK**。

**结论措辞**：**host syntax verified；board link pending hardware retest。**
离线无法链接 iCraft 运行时库，**不冒充板端编译通过**。

---

## 8. 板端复测命令（非侵入式，见 `BOARD_LATENCY_RETEST.md`）

1. `baseline_diag` 100 循环（**诊断参考**，退出码由正确性门 + 延迟门决定，不再要求「复现尖峰」）；
2. `fixed` Smoke（1 循环）；
3. `fixed` Basic（10 循环）；
4. `fixed` Stress（100 循环）；
5. `fixed` Stress（1000 循环）。

退出码已自动化，无需人工读日志判 PASS/FAIL。日志完整内容在 `logs/*.log`，摘要打印在退出后。

---

## 9. 板端延迟硬门（不可放宽，程序已自动执行）

对 `total_inference`：

| 门 | 要求 |
|----|------|
| `gt_100ms` | **= 0** |
| `p99` | **≤ 5 ms** |
| `max` | **≤ 10 ms** |
| `gt_10ms` | **= 0** |

资源门（fixed 额外要求）：`input_allocations == 2`、`completed_cycles == opt.cycles`、
`frame_timings.size() == opt.cycles × npu_frames_per_cycle`。

**任一 FAIL = NO_GO，保留证据，不得放宽。**

---

## 10. 回滚

v1（`sdr_preparation_v1`）与 v2（`sdr_preparation_v2_latency_fix`）**均完全未动**，是回滚基线。
v3 的改动仅涉及脚本、baseline 判定语义、日志输出方式、文档/测试/打包。任何一步需要回滚，
删除 v3 目录即回到 v2/v1。

---

## 11. 交付状态

**`READY-FOR-HARDWARE-LATENCY-RETEST`**（非侵入式日志版）。

- 根因：**已确认 = 慢速串口实时逐帧日志的观察者效应**（用户板端实测）。
- 输入分配假设：**已否决**（用户板端实测：输入复用后尖峰仍在）。
- 资源复用：**保留但不得声称消除尖峰**。
- 板测数据：**用户板端实测 / 用户板端日志转录**（本 API 未操作板卡）。
- 编译：**host syntax verified；board link pending hardware retest**。

待用户本人按 `BOARD_LATENCY_RETEST.md` 用 v3 非侵入式脚本复测（baseline_diag 100 → fixed
smoke/basic/100/1000），确认无尖峰 + 延迟硬门全 PASS 后，才正式记录
`FPGA_NPU_CONTINUOUS_HARDWARE_PASS` 与 `REALTIME_LATENCY_PASS_NONINTRUSIVE_LOGGING`。

已可记录（用户板端实测确立）：`SERIAL_LOGGING_OBSERVER_EFFECT_CONFIRMED`、
`INPUT_ALLOCATION_ROOT_CAUSE_HYPOTHESIS_REJECTED`。

整个系统**尚未最终**（等待 10/12 类模型 + Pluto 实机级联）。
