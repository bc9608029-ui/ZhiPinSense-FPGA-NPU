# 板端延迟复测指南（固定顺序）

> 复测人：用户本人（我禁碰板、不写 Flash）。上板前请先构建三个程序。
> 本指南的顺序**不可调换**，任何一步不满足就停止，不得跳到下一步。

---

## 0. 上板前准备

```sh
cd board_package
sha256sum -c sha256_manifest.txt     # 校验交付文件（全 OK 再继续）
./build_on_board.sh                  # cmake + make 三个程序（gnu++17，iCraft 3.39）
```

`build_on_board.sh` 会构建三个可执行文件：

- `./build/continuous_joint_stress`（v1 等价，回滚对照用，本指南不用它复测尖峰）
- `./build/continuous_joint_stress_baseline_diag`
- `./build/continuous_joint_stress_fixed`

---

## 判据总览：退出码已自动化，无需人工读日志判 PASS/FAIL

| 程序 | 输出结果行 | 返回 0 的条件 |
|------|-----------|--------------|
| `baseline_diag` | `STRESS_RESULT`（正确性）、`BASELINE_SPIKE_FRAME`×N、`BASELINE_SPIKE_REPRODUCED=YES\|NO` | 复现 ≥1 个 `forward_legacy>100ms` 尖峰 **且** 正确性门通过；`NO` 返回非零并打印 `BASELINE_NO_SPIKE`（禁止继续 fixed） |
| `fixed` | `CORRECTNESS_RESULT` / `LATENCY_RESULT` / `RESOURCE_RESULT` / `FINAL_RESULT`（各 `PASS\|FAIL`） | 三门全 PASS：正确性 AND 延迟硬门 AND 资源门 |

5 个 `run_*.sh` 都 `exec` 程序本体，**真实退出码原样透传**（`$?` 即程序退出码）。

---

## 第 1 步 — baseline_diag 100 循环（必须先复现尖峰）

```sh
./run_baseline_diag_100.sh
```

**判据**：看输出末尾 `BASELINE_SPIKE_REPRODUCED=YES` 且 `STRESS_RESULT=PASS`（即脚本退出码 0）。

`BASELINE_SPIKE_FRAME` 会逐行列出每个慢帧的 `cycle/frame`，用于核对是否仍是原形态
（`frame=7`，每 6 个 cycle 一次，forward_legacy ≈ 400~937 ms）。同时记录 `LATENCY_PHASE`
里**哪一个阶段**承载了尖峰（这是根因定位的关键证据）。

> ⚠️ **若输出 `BASELINE_SPIKE_REPRODUCED=NO`（脚本退出码非零）：立即停止。**
> 不得用 fixed 结果宣称修复——无法复现意味着诊断条件不成立，后续任何结果都不可信。

---

## 第 2 步 — fixed Smoke（1 循环）

```sh
./run_fixed_smoke.sh
```

**判据**：`CORRECTNESS_RESULT=PASS`、`LATENCY_RESULT=PASS`、`RESOURCE_RESULT=PASS`、
`FINAL_RESULT=PASS`（脚本退出码 0）。`RESOURCE_RESULT=PASS` 同时确认 `input_allocations=2`
（输入 Tensor 复用生效）与循环/帧数完整。

---

## 第 3 步 — fixed Basic（10 循环）

```sh
./run_fixed_basic.sh
```

**判据**：同上，`FINAL_RESULT=PASS`（脚本退出码 0）。

---

## 第 4 步 — fixed Stress（100 循环）

```sh
./run_fixed_stress_100.sh
```

**判据**：`FINAL_RESULT=PASS`（脚本退出码 0）。程序已对 `total_inference` 执行延迟硬门
（见下），无需人工对照 `LATENCY_PHASE`；但请仍把 `total_inference` 的
`gt_100ms / p99 / max / gt_10ms` 四值回传给我。

---

## 第 5 步 — fixed Stress（1000 循环）

```sh
./run_fixed_stress_1000.sh
```

**判据**：`FINAL_RESULT=PASS`（脚本退出码 0），且越过原始尖峰 onset（cycle 58）后尖峰仍不出现。

---

## 延迟硬门（不可放宽，程序已自动执行）

对 `total_inference` 阶段（以及任何其它阶段）：

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

1. 第 1 步 `BASELINE_SPIKE_REPRODUCED` 与 `LATENCY_PHASE` 各阶段统计（确认尖峰落在哪个阶段）；
2. 第 2~5 步的 `CORRECTNESS_RESULT` / `LATENCY_RESULT` / `RESOURCE_RESULT` / `FINAL_RESULT`
   与 `LATENCY_SUMMARY`（`input_allocations`、RSS）；
3. 第 4/5 步 `total_inference` 的 `gt_100ms / p99 / max / gt_10ms` 四值。

只有第 1 步复现尖峰、且第 4/5 步满足硬门，才会把根因从「假设」升级为「已确认」，
并把状态从 `READY-FOR-HARDWARE-LATENCY-RETEST` 改为硬件 PASS。否则维持 NO_GO / RETEST。
