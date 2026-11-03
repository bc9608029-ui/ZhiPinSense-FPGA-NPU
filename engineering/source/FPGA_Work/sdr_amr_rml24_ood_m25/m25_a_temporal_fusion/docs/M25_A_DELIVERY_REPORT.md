# M25-A 通用多帧时序融合 — 离线交付报告

## 状态

- **模块**：`M25-A-OFFLINE-MODULES-READY`
- **硬件对齐**：**未做**（真实 NPU logits 未取，融合参数未在板上校准）。**严禁**书写
  `TEMPORAL_FUSION_HARDWARE_PASS` / `PERFORMANCE_PASS` / `PROJECT_COMPLETE`。

## 交付物

| 路径 | 说明 |
|---|---|
| `sdr_adapter/m25_temporal_fusion_config.hpp` | `FusionConfig` / `FusionAlgorithm` / `config_valid` / `algorithm_name` |
| `sdr_adapter/m25_temporal_fusion_state.hpp` | `ResetReason` / `FusionStats` / `FusionState`（预分配缓冲） |
| `sdr_adapter/m25_temporal_fusion.hpp` | 公开 API：`TemporalFusionInput` / `TemporalFusionResult` / `TemporalFusion` |
| `sdr_adapter/m25_temporal_fusion.cpp` | 5 算法 + 复位检测表 + 特殊处理实现（非 inline） |
| `host_tests/test_m25_a.cpp` | 67/66 断言主机测试 |
| `host_tests/{build,run}_m25_a*.sh` | release / ASan / UBSan 三套构建运行 |
| `host_tools/m25_temporal_fusion_replay.cpp` | JSONL logits 回放（含内置 demo 流） |
| `host_tools/m25_temporal_fusion_bench.cpp` | 统一基准 + 稳态零分配断言 |
| `scripts/` | replay / test / package 三个编排脚本 |
| `docs/` | 本报告 + 集成接口 |

## 模块行为摘要

- **默认关闭**：未 `configure` 或 `enabled=false` 时，输出与单帧 argmax 字节一致
  （`raw_class_index == fused_class_index`、`raw_margin == fused_margin`、`class_changed=false`）。
- **原始 logits 域**：argmax 严格 `>`（并列取小下标），margin = top1 − top2；除 EMA 逐维
  滑动均值外不引入 Softmax。
- **5 算法**：`MajorityVote` / `LogitsMean` / `LogitsEMA` / `EMA_KFrameConfirm`（默认）/
  `EMA_MarginHysteresis`。
- **12 类复位条件**（按 `ResetReason` 独立计数）：model_sha 变化（含 nullptr↔非空）、
  维度 12↔24、mode_id、lo_freq_hz、tuning_generation、START、STOP、NO_SIGNAL、
  frame_id 回退/重复/跳号、timestamp 回退/超间隔、NaN/Inf fail-closed、显式 `reset()`。
- **特殊处理**：NO_SIGNAL 清融合历史；UNKNOWN（OOD-U 已拒识）不被投票覆盖；ERROR 立即
  直通；OOD 分数走独立 EWMA+滞回，绝不混入类 logits。
- **有界窗口 + 稳态零堆分配**：`max_window=32`，缓冲在首帧/复位一次性预留，process() 只
  按下标读写，无 push_back/erase。

## 测试计数（主机，g++ 15.2.0 / WSL）

| 套件 | 断言 | 通过 | 失败 |
|---|---|---|---|
| release（`run_m25_a.sh`） | 67 | 67 | 0 |
| ASan（`run_m25_a_asan.sh`，`-DM25_SKIP_ALLOC_TEST`） | 66 | 66 | 0 |
| UBSan（`run_m25_a_ubsan.sh`，`-DM25_SKIP_ALLOC_TEST`） | 66 | 66 | 0 |

覆盖项：①配置校验（alpha 区间/confirm≤latency/window≥confirm/算法名）②默认关闭直通
③fail-closed（非法维度/null/NaN/Inf）④5 算法各 ≥2 断言（多数票收敛+翻转、均值、EMA、
fast_switch+confirm 门控、margin 滞回）⑤12 类复位各 1 断言（每类用全新实例隔离）
⑥NO_SIGNAL 清史 ⑦UNKNOWN 不被覆盖 ⑧ERROR 直通 ⑨OOD 独立 EWMA 不扰动类融合
⑩有界窗口 1000 帧无泄漏/无伪复位 + 12↔24 维度切换 ⑪稳态零堆分配（release only）。

## 性能基准（`m25_temporal_fusion_bench`，24 类，N=200000）

| 阶段 | 耗时 |
|---|---|
| disabled passthrough | 0.01 µs/帧 |
| EMA_KFrameConfirm（默认） | 0.08 µs/帧 |
| 融合开销 | 0.06 µs/帧（约 5.3×） |
| 稳态零逐帧堆分配 | PASS |

回放 demo（60 帧：类5 → 单帧毛刺类17 → 类5 → 真实换模类9）：
`raw 换模 3 次 → fused 换模 1 次`，毛刺帧被覆盖（fus≠raw），真实换模在下一帧经
`fast_switch` 翻转；均值 0.17 µs/帧。

> 以上为 CPU 参考数，**不代表板上 NPU 链路的实际延迟/吞吐**。

## 12 问（真实 NPU 对齐前必须回答）

1. 真实 NPU 输出的 12/24 维 raw logits 量级与分布，是否落在 `alpha`/`margin_hysteresis`
   默认值的合理区间？
2. 单帧误判（瞬时毛刺）在真实链路上出现的概率与模式，能否支撑"clear-failure 快速翻转"
   的假设？
3. 真实换模的帧级延迟（平均/最大）是多少，`max_latency_frames=4` 预算是否够？
4. 独立 OOD EWMA 通道与主链已有 OOD-U 判定（logit_margin / id_accept_99）是否重复或冲突？
5. 融合引入的确认帧延迟，是否与 Gate9/10 的实时 UI 刷新节奏兼容？
6. `frame_id`/`timestamp_ns` 在真实数据通路上是否单调且无跳号；若存在跳号，`max_frame_gap`/
   `max_timestamp_gap_ns` 如何设置？
7. NO_SIGNAL / UNKNOWN / ERROR 三态在真实 NPU 数据通路上的触发频率与语义是否与本模块一致？
8. 24 类正式 baseline 冻结后，融合默认算法/参数是否需要针对 24 类 logits 重新标定？
9. 板上（A53 + 可能的 NPU 旁路 CPU）运行本模块的单帧成本是否满足实时预算？
10. 融合是否应与 OOD-U 拒识共用同一"UNKNOWN 不被覆盖"语义，还是需要独立 OOD 门控？
11. 12 类正式模型与 24 类模型之间的换模（model_sha 变化触发复位）在真实调度中是否可见？
12. 融合后的稳定性（stability）能否作为 UI/巡检的置信度展示，而非仅内部计数？

## 红线自检

- 未修改/覆盖 12 类正式模型、24 类 pilot、M22/M23/M24 交付物、RTL/XDC/位流、FPGA 数据
  通路、标签顺序与输入预处理、历史工程与历史包。
- 未启动 Vivado、未接 Gate 9/10 主链、未写 Flash、未碰板。
- 未书写任何 `*_PASS` 禁词（`TEMPORAL_FUSION_HARDWARE_PASS` / `OOD_PASS` /
  `PERFORMANCE_PASS` / `PROJECT_COMPLETE` / FINAL_* 族）。
