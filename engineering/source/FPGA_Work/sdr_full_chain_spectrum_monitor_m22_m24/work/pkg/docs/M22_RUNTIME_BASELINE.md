# M22 运行时性能基线（Runtime Baseline）

任务 39e5 M22 §三。本文档定义**13 项必须测量**的运行时指标、每项的测量方法、数据落点，
以及每个数字的**来源标签**（实测 / 编译报告 / 推导 / UNKNOWN）。

> **关键诚实声明**：M22 离线阶段（本工程当前状态）交付的是**可重复的板端测量工具**——
> 分阶段打点已写入 `board_gate9_full_chain_12class`（`m22::StageTiming` / `m22::PercentileStats` /
> `m22::ResourceSample` / `finish_m22_runtime()`），一键脚本 `run_m22_runtime_baseline.sh` 已就绪。
> 但**真实延迟/资源数值只能由板端采集**（我禁碰板）。因此：本文档中所有「数值」列的当前状态是
> **待板端采集**，采集命令与落点见 §4；只有「工具已接线并编译验证」与「代码级生命周期/分配保证」
> 这两类事实在离线阶段即已完成（见 §3，标 `编译报告` / `推导`）。**绝不把理论峰值写成实际利用率，
> 绝不在未上板前填任何伪造的实测数值。**

---

## 1. 标签说明（§三「每个数字必须标记」）

| 标签 | 含义 |
|---|---|
| **实测** | 板端真实运行采集得到的数值（来源：`runs/m22_runtime_baseline/*/m22_runtime_baseline.json` 与运行日志）。 |
| **编译报告** | 离线即可确认的编译/静态事实（`-O2 -Wall -Wextra -Werror` 通过、`bash -n` 通过、主机单测通过、打点已接线）。 |
| **推导** | 由代码结构必然推出的性质（如「设备只在构造器打开一次」→ reopen 恒为 0）。 |
| **UNKNOWN** | 尚无数据，且离线无法推出（需板端实测后才能转为 `实测`）。 |

---

## 2. 13 项测量清单（§三.1–§三.13）

| # | 测量项 | 定义 / 单位 | 测量位置（打点） | 数据落点 | 标签 |
|---|---|---|---|---|---|
| 1 | Device 打开耗时 | NPU `Device::Open(axi://zg330aiu?…)` 一次性开销，微秒 | `StageId::DeviceOpen`（`npu_classifier.hpp` 构造器，启动期一次） | perf JSON `stages.device_open` | **实测**（启动期；当前 UNKNOWN 待采集） |
| 2 | 模型加载耗时 | `lazyLoadParamsFromFile(model_raw)` + 契约校验，微秒 | `StageId::ModelLoad`（同上） | `stages.model_load` | **实测**（启动期；当前 UNKNOWN） |
| 3 | RF 配置耗时 | `set_rx_gain_mode/set_rx_gain/set_loopback`，微秒 | `StageId::RfConfig`（`run_ambient_phase` 启动期） | `stages.rf_config` | **实测**（启动期；当前 UNKNOWN） |
| 4 | RX refill 耗时 | `capture_contiguous` 单批连续采集，微秒/批 | `StageId::RxRefill`（批循环，`board_gate9…:1106`） | `stages.rx_refill` | **实测**（当前 UNKNOWN） |
| 5 | 输入预处理耗时 | `chain.push_int16`（重采样/定标/组帧），微秒/批 | `StageId::Preprocess`（`board_gate9…:1115`） | `stages.preprocess` | **实测**（当前 UNKNOWN） |
| 6 | NPU 推理耗时 | `npu.infer` 单帧（含 reset(1)+forward+waitForReady+read），微秒 | `StageId::NpuInfer`（分类 lambda，`board_gate9…:1149`） | `stages.npu_infer` | **实测**（当前 UNKNOWN） |
| 7 | 后处理耗时 | `chain::fill_result` + 发布门控 + 测量填充，微秒/帧 | `StageId::Postprocess`（`board_gate9…:1208`） | `stages.postprocess` | **实测**（当前 UNKNOWN） |
| 8 | UI 提交耗时 | `emit_frame_v3`（socket 非阻塞写 + 可选 stdout），微秒/帧 | `StageId::UiSubmit`（`board_gate9…:1214`） | `stages.ui_submit` | **实测**（当前 UNKNOWN） |
| 9 | 完整帧周期 | 单帧 `ft0 → 帧结束` 端到端，微秒/帧 | `StageId::FrameTotal`（`board_gate9…:1219`） | `stages.frame_total` | **实测**（当前 UNKNOWN） |
| 10 | 平均 / P50 / P95 / P99 / 最大 | 每阶段统计量（§三.10） | `m22::PercentileStats`（固定 65536 容量环形缓冲，`record()` 零分配） | 每阶段 `mean_us / p50_us / p95_us / p99_us / max_us / min_us` | **实测**（当前 UNKNOWN） |
| 11 | 连续 ≥10000 帧 | 累计处理帧数 | `total_processed`（默认 `--frames=10000`） | 日志 `frames=N/N` + JSON `stages.*.count` | **实测**（工具已就绪，默认 10000） |
| 12 | CPU / 内存 / 线程 / FD | RSS(kB)、VM(kB)、FD 数、线程数、CPU 秒 | `m22::read_resources()`（`/proc/self/status` + `/proc/self/fd` + `getrusage`） | JSON `resource_first / resource_last / resource_peak` | **实测**（当前 UNKNOWN） |
| 13 | 内存增长 / FD 泄漏 / 设备重复打开 | `rss_growth_kb`、`fd_growth`、`device_reopen_count` | `finish_m22_runtime()` 由 first/last/peak 差值与 `npu.lifecycle()` 计算 | JSON 顶层字段 + `M22_RUNTIME_RESULT` 行 | **推导**（代码保证，见 §3.3）+ **实测**（板端确认） |

> §三.11 要求「连续运行至少 10000 帧」：`run_m22_runtime_baseline.sh` 默认 `--frames=10000`，
> 且 `--summary-interval=1000` 每 1000 帧打印一行 `M22_SUMMARY`（RSS/FD/线程 + NPU 与帧周期 P50/P99/max），
> 使长运行过程可观察、可中断（Ctrl-C 可靠退出，`trap INT/TERM/EXIT`）。

---

## 3. 离线阶段已确认的事实（`编译报告` / `推导`）

### 3.1 测量工具已接线并编译验证（`编译报告`）

- 九阶段打点全部接线：`DeviceOpen / ModelLoad / RfConfig / RxRefill / Preprocess / NpuInfer / Postprocess / UiSubmit / FrameTotal`
  （`sdr_adapter/latency_stats.hpp` 的 `StageId` 枚举 + `StageTiming::Timer` RAII）。
- 热路径 `record()` 零堆分配（写固定容量环形缓冲 + 就地更新 min/max/sum），分位数只在摘要时算一次（拷贝 + 排序，在帧循环之外）。
- 资源采样 `m22::read_resources()` Linux 专用（`/proc` + `getrusage`），非 Linux 主机字段为 0 且 `is_supported()==false`（主机单测仍可测 JSON 与泄漏判定逻辑）。
- 主机单测 `host_tests/test_m22_runtime.cpp`：**346 断言 0 失败**，`-O2 -Wall -Wextra -Werror` 编译通过，ASan/UBSan（`-fsanitize=address,undefined` + `detect_leaks=1`）零失败。
- 脚本层：`bash -n` 全通过；`test_m22_m24.sh` 45/45 PASS（含唯一 verdict、旧日志假 PASS 防护、`stop_pid_if_matches` 身份重验、库守卫短路等）。

### 3.2 构建门禁（`编译报告`）

- 主机全量 `build_host_tests.sh` + `run_tests.sh`：**ALL HOST TESTS PASSED**（含 `test_m22_runtime`）。
- `test_board_build.sh` 24/0、`test_cli_override.sh` PASS、`syntax_check.sh` gate7/gate9/gate10 全「syntax OK」。
- 板端二进制 `board_gate9_full_chain_12class` 的 iCraft 路径以 `-fsyntax-only`（`-isystem $ICRAFT_INCLUDE`）语法验证通过；**板端真实链接/运行仍待上板**（iCraft SDK 仅在板端可链接）。

### 3.3 生命周期与分配保证（`推导`，板端确认后转为 `实测`）

| 性质 | 依据 | 状态 |
|---|---|---|
| 稳态 `reopen == 0` | `NpuClassifier12` 仅在构造器 `Device::Open` 一次、析构器 `Device::Close` 一次；帧循环无任何 reopen 路径；`NpuLifecycleState::discipline_ok()` 要求 `open_count==1 && apply_count==1` | 推导（代码结构） |
| 稳态逐帧堆分配 == 0 | 热路径缓冲全部预分配复用：producer `cf_/scaled_/dsp_scratch_`（成员）、`npu` 的 `inputs_.reserve(1)`/`read_buf_` 复用、`softmax_into`/`measure_into` 原地写入；`record()` 零分配。主机单测以 `softmax_into==softmax`、`measure_into==measure` 逐位一致证明复用路径不改变结果 | 推导 + 编译报告 |
| FD 不随帧数增长 | 帧循环不打开任何 fd（socket 连接复用、日志不逐帧写文件） | 推导 |
| RSS 无持续增长 | 无逐帧 `malloc/new`；唯一保留的逐帧分配是 iCraft `Tensor.mallocOn`（有界 ~8KB 主机内存，非泄漏，见 `npu_classifier.hpp` 头注，复用留待板端验证的后续） | 推导 |
| 无 425–937ms 尖峰 | 逐帧 stdout JSONL + `fflush` 已默认关闭（`NullSink` 默认，`--verbose` 才开），见 `M22_LATENCY_ROOT_CAUSE.md` | 假设，待板端 `spike_free=1` 确认 |

---

## 4. 板端采集步骤（用户本人执行，我禁碰板）

```bash
# 前提：已在板端完成 -O2 构建（./board_package/build_npu_on_board.sh）并把产物装入 bin/。

# (A) 快速回归（离线重放 240 帧）：证明 NPU 输出与 golden 一致 + 生命周期 reopen==0/apply==1
./scripts/run_m22_runtime_regression.sh          # 期望 M22_RUNTIME_REGRESSION result=PASS

# (B) 运行时基线（RX-only ambient，10000 帧，接好外部天线，无 TX）
./scripts/run_m22_runtime_baseline.sh             # 期望 M22_RUNTIME_BASELINE result=PASS
./scripts/run_m22_runtime_baseline.sh --frames=20000 --summary-interval=1000

# 落点：
#   runs/m22_runtime_baseline/<run_id>/m22_runtime_baseline.json   <- 13 项数值（stages + resource）
#   runs/m22_runtime_baseline/<run_id>/gate9_ambient.log            <- M22_SUMMARY / M22_RUNTIME_RESULT
```

采集完成后，把 `*.json` 的数值回填到本文档 §2 各行的「数据落点」对应值，并把标签由
`UNKNOWN/待采集` 改为 `实测`。

### JSON schema（`--perf-file` 产物）

```jsonc
{
  "phase": "ambient",
  "model_sha": "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c",
  "stages": {
    "device_open": {"count":1,"mean_us":…,"p50_us":…,"p95_us":…,"p99_us":…,"max_us":…,"min_us":…},
    "model_load":  { … }, "rf_config": { … }, "rx_refill": { … },
    "preprocess":  { … }, "npu_infer": { … }, "postprocess": { … },
    "ui_submit":   { … }, "frame_total": { … }
  },
  "resource_first": {"rss_kb":…,"vm_kb":…,"fd_count":…,"thread_count":…,"cpu_seconds":…},
  "resource_last":  { … },
  "resource_peak":  { … },
  "device_reopen_count": 0,
  "session_apply_count": 1,
  "npv_discipline_ok": true,
  "rss_growth_kb": …,
  "fd_growth": …,
  "spike_free": true,
  "result": "PASS"
}
```

### §六 验收行（由二进制 `finish_m22_runtime()` 输出，唯一权威）

```
M22_RUNTIME_RESULT result=PASS|FAIL phase=ambient reopen=… apply=… discipline=… \
  fd_growth=… rss_growth_kb=… rss_ok=… fd_ok=… spike_free=… frame_total_p99_us=… frame_total_max_us=…
```

`result=PASS` 当且仅当 `reopen==0 && apply==1 && discipline==OK && fd_growth<=0 && rss_growth<=32768 && spike_free(frame_total_max<=100ms)`。

---

## 5. 状态红线

- 当前最高：**`READY-FOR-M22-RUNTIME-HARDWARE-PROFILING`**（离线测量工具已交付，未上板）。
- 板端 `run_m22_runtime_regression.sh` + `run_m22_runtime_baseline.sh` 均 `result=PASS` 后，方可标
  **`M22_RUNTIME_HARDWARE_PASS`**。
- 未上板前**绝不写** `PERFORMANCE_PASS` / `M22_RUNTIME_HARDWARE_PASS`，绝不用理论峰值冒充实测。
