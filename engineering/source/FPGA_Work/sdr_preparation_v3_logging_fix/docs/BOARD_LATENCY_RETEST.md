# 板端延迟复测指南（非侵入式日志版）

> 复测人：用户本人（我禁碰板、不写 Flash）。上板前请先构建三个程序。
> 本指南顺序**不可调换**；所有脚本都已改为**非侵入式日志**（运行期间串口安静，
> 退出后打印简短摘要，真实退出码原样透传）。

---

## 0. 上板前准备

```sh
cd board_package
sha256sum -c sha256_manifest.txt     # 校验交付文件（全 OK 再继续）
./build_on_board.sh                  # cmake + make 三个程序（gnu++17，iCraft 3.39）
```

`build_on_board.sh` 会构建三个可执行文件：

- `./build/continuous_joint_stress`（v1 等价，回滚对照用）
- `./build/continuous_joint_stress_baseline_diag`
- `./build/continuous_joint_stress_fixed`

---

## 非侵入式日志：每个脚本都在做什么

每个 `run_*.sh` 都会：

1. 把程序**完整输出**重定向到带时间戳的日志文件 `logs/<name>_<时间戳>.log`；
2. 运行期间**串口保持安静**（禁止 `| tee` 与测量期间 `tail -f`）；
3. 程序退出后，从日志文件 grep 出**简短摘要**打印到串口；
4. 打印 `LOG_FILE=...` 与 `EXIT_CODE=...`；
5. `exit "$rc"` **真实退出码原样透传**。

因此：**看脚本的退出码（`echo $?`）即可判 PASS/FAIL**；要看完整细节再 `cat logs/*.log`。

---

## 判据总览：退出码已自动化

| 程序 | 输出结果行 | 返回 0 的条件 |
|------|-----------|--------------|
| `baseline_diag` | `BASELINE_SPIKE_REPRODUCED=YES\|NO`、`BASELINE_CORRECTNESS_RESULT`、`BASELINE_LATENCY_RESULT`、`BASELINE_FINAL_RESULT` | 正确性门 **AND** 非侵入式延迟门均 PASS（`BASELINE_FINAL_RESULT=PASS`） |
| `fixed` | `CORRECTNESS_RESULT` / `LATENCY_RESULT` / `RESOURCE_RESULT` / `FINAL_RESULT` | 三门全 PASS（`FINAL_RESULT=PASS`） |

> **重要变化**：`BASELINE_SPIKE_REPRODUCED=NO` 现在是**正常且正确**的结果（非侵入式日志下
> 不应再有 >100ms 尖峰），**不再决定退出码、不再禁止继续 fixed**。它只是诊断参考。

---

## 第 1 步 — baseline_diag 100 循环（诊断参考）

```sh
./run_baseline_diag_100.sh; echo "EXIT=$?"
```

**判据**：`BASELINE_FINAL_RESULT=PASS`（脚本退出码 0）。
`BASELINE_SPIKE_REPRODUCED=NO` 与 `BASELINE_CORRECTNESS_RESULT=PASS`、
`BASELINE_LATENCY_RESULT=PASS` 一起说明：非侵入式日志下正确性通过、且无 >100ms 尖峰。

`BASELINE_SPIKE_FRAME`（若有）会逐行列出慢帧 `cycle/frame`，仅作参考；`LATENCY_PHASE` 各阶段统计
用于核对尖峰已消失。**不再要求「必须先复现尖峰」。**

---

## 第 2 步 — fixed Smoke（1 循环）

```sh
./run_fixed_smoke.sh; echo "EXIT=$?"
```

**判据**：`CORRECTNESS_RESULT=PASS`、`LATENCY_RESULT=PASS`、`RESOURCE_RESULT=PASS`、
`FINAL_RESULT=PASS`（退出码 0）。`RESOURCE_RESULT=PASS` 同时确认 `input_allocations=2`
（输入复用生效）与循环/帧数完整。

---

## 第 3 步 — fixed Basic（10 循环）

```sh
./run_fixed_basic.sh; echo "EXIT=$?"
```

**判据**：`FINAL_RESULT=PASS`（退出码 0）。

---

## 第 4 步 — fixed Stress（100 循环）

```sh
./run_fixed_stress_100.sh; echo "EXIT=$?"
```

**判据**：`FINAL_RESULT=PASS`（退出码 0）。程序已对 `total_inference` 执行延迟硬门（见下）。
请把 `total_inference` 的 `gt_100ms / p99 / max / gt_10ms` 四值回传给我。

---

## 第 5 步 — fixed Stress（1000 循环）

```sh
./run_fixed_stress_1000.sh; echo "EXIT=$?"
```

**判据**：`FINAL_RESULT=PASS`（退出码 0），且越过原始尖峰 onset（cycle 58）后仍无尖峰。

---

## 延迟硬门（不可放宽，程序已自动执行）

对 `total_inference`：

| 门 | 要求 |
|----|------|
| `gt_100ms` | **= 0** |
| `p99` | **≤ 5 ms** |
| `max` | **≤ 10 ms** |
| `gt_10ms` | **= 0** |

资源门（fixed 额外要求）：`input_allocations == 2`、`completed_cycles == opt.cycles`、
`frame_timings.size() == opt.cycles × npu_frames_per_cycle`。

**任一 FAIL = NO_GO，保留证据，不得放宽。** 程序对失败门返回非零退出码。

---

## 结果回填（供我更新状态）

复测完成后，请回传：

1. 第 1 步 `BASELINE_FINAL_RESULT` 与 `BASELINE_SPIKE_REPRODUCED`、`LATENCY_PHASE` 各阶段统计；
2. 第 2~5 步的 `CORRECTNESS_RESULT` / `LATENCY_RESULT` / `RESOURCE_RESULT` / `FINAL_RESULT`
   与 `LATENCY_SUMMARY`（`input_allocations`、RSS）；
3. 第 4/5 步 `total_inference` 的 `gt_100ms / p99 / max / gt_10ms` 四值。

全部 PASS（退出码 0）才把状态记为 `FPGA_NPU_CONTINUOUS_HARDWARE_PASS` +
`REALTIME_LATENCY_PASS_NONINTRUSIVE_LOGGING`；否则维持 NO_GO / RETEST 并保留证据。
