# 竞赛资源/延迟/吞吐/稳定性/功耗 记录模板

> 用途：SDR 到货并上板后，按此模板统一记录，避免数据口径不一致。
> 本文件只定义「记什么、怎么记」，不改变任何工程/数值。

## 0. 一次运行的固定信息

| 字段 | 值 |
|------|----|
| 日期 / 板卡 / 位流版本 | |
| 模型 (model.json / model.raw SHA) | |
| IQ/Tensor/Golden SHA | |
| SDR 型号 / 接口 / 原始采样率 | |
| 目标采样率 | 128000 Hz（冻结） |
| 运行模式 | smoke / basic / stress（1 / 10 / 100 轮） |
| 室温 / 供电 | |

## 1. 资源（Resource）

| 指标 | 单位 | 采集方式 |
|------|------|----------|
| PS DDR 占用（MemChunk 分配） | bytes | `STRESS_SETUP` 的 chunk 大小（175104 B） |
| PL 资源（LUT/FF/DSP/BRAM/URAM） | % | Vivado 综合/实现报告（不重新综合，读已有报告） |
| NPU 占用（HardOp 数 / 计算核） | count | iCraft 报告（85 HardOps @zhuget(330)） |
| CPU 使用率（每阶段） | % | `top`/`pidstat` 采样 |
| 内存占用峰值 | MB | `/proc/<pid>/status VmRSS` |

## 2. 分阶段延迟（Latency，来自 `perf_stats.hpp`）

| 阶段 | key | 单位 |
|------|-----|------|
| SDR 采集 | `sdr_capture` | µs |
| 重采样/帧化 | `resample_frame` | µs |
| PL-DDR 传输 | `plddr_transfer` | µs |
| FPGA 处理 | `fpga_process` | µs |
| NPU 推理 | `npu_infer` | µs |
| 端到端 | `end_to_end` | µs |

每个阶段记录：count / avg / min / max（`perf_stats.hpp` 的 `summary()`）。

## 3. 吞吐（Throughput）

| 指标 | 单位 | 公式 |
|------|------|------|
| 轮速率 | cycles/s | `cycles_done * 1000 / total_ms` |
| NPU 帧速率 | frames/s | `npu_frames_done * 1000 / total_ms` |
| IQ 样本速率 | samples/s | `cycles_done * 19 * 1024 * 1000 / total_ms` |

对应 `continuous_joint_stress` 的 `STRESS_THROUGHPUT` 行。

## 4. 稳定性（Stability）

| 指标 | 阈值（PASS） |
|------|------|
| tensor 逐字节 mismatch | = 0 |
| NPU match | 全部 match |
| delay_shift（stale 迹象） | = 0 |
| timeout / error | = 0 |
| drop / overflow / duplicate / reorder / discontinuity | = 0（`sequence_monitor`） |
| VERSION 一致性 | 恒 = 0x20260929 |
| 连续运行时长（无退化） | 记录实际时长 |

异常时记录：`FailureClass`、`RecoveryAction`、发生轮次、恢复结果。

## 5. 功耗（Power，若可测）

| 指标 | 单位 | 采集方式 |
|------|------|----------|
| 板级总功耗 | W | 电源端功率计（如有） |
| PS/PL 分区功耗 | mW | Vivado Power 报告（读已有，不重新综合） |
| NPU 推理期 vs 空闲期功耗差 | mW | 对比采样 |

> 若现场无功率计，注明「未测」，**不编造数值**。

## 6. 记录口径（统一）

- 所有延迟/吞吐来自 `perf_stats.hpp` 与 `STRESS_*` 行，**不手工拼数**；
- 一次运行一份记录，附原始 log 的 SHA；
- 稳定性以「长时间连续运行 + 0 异常」为准，不以单次通过为准。
