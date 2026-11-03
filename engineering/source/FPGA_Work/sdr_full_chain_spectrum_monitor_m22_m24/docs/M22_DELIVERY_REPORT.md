# M22 交付报告（§二十二）

任务 39e5 M22「运行时性能修复」。本报告按 §二十二 逐项给出 M22 两个交付物的完整信息。
基线 = M19 全量包（`sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz`，SHA
`3d6d793c5a89ab983dfd6c381032192401bc3678dc43ae1b3e7139e3e76a31cd`）。

> **诚实声明**：M22 离线阶段交付的是**可重复的板端测量/修复工具**，真实延迟/资源数值只能由
> 板端采集（我禁碰板）。`reopen==0` / 逐帧零分配 / `spike_free==1` 目前是**代码级推导 + 假设**，
> 待板端 `M22_RUNTIME_RESULT result=PASS` 到手后才转**实测**。绝不把理论值写成实测值。

---

## 1. 交付物一览

| 交付物 | Windows 完整路径 | 字节 | SHA256 |
|---|---|---|---|
| M22 全量包 | `F:\FPGA_Work\sdr_full_chain_spectrum_monitor_m22_m24\dist\sdr_full_chain_spectrum_monitor_m22_m24_m22_board_package.tar.gz` | **3,338,569** | `f07bd09169f76f172b326e956b6e1793928dad5f7805a1f33c3813c904e15b91` |
| M22 补丁 | `F:\FPGA_Work\sdr_full_chain_spectrum_monitor_m22_m24\dist\m22_runtime_fix_patch.tar.gz` | **106,509** | `697647f903d0be8fe3f42e15fd19d1c1492881a2970aebd2b88cdbe9d3abd01e` |

| 指标 | 全量包 | 补丁 |
|---|---|---|
| 文件数（含 `SHA256SUMS.txt`） | **463** | **23** |
| `SHA256SUMS.txt` 行数（manifest，排除自身） | **462** | 462（与全量包逐字节一致） |
| 确定性打包 | `GZIP=-n` + `--mtime='UTC 2026-10-09'` + `--owner=0 --group=0 --numeric-owner` | 同左 |

## 2. 独立解包校验

- 全量包：解包到独立临时目录 → `sha256sum -c SHA256SUMS.txt` → **463/463 全 OK**。
- 补丁：解包 23 文件 → 其 `SHA256SUMS.txt` 与全量包 manifest 逐字节一致（diff 零）。

## 3. 补丁叠加一致性

`M19 全量包解包 + 叠加 m22_runtime_fix_patch.tar.gz` 与 M22 全量包解包做 `diff -rq`：

**ZERO differences（0 差异）** —— M22 全量包 ≡「M19 全量包 + M22 补丁」。

## 4. 精确 diff 清单（补丁 23 文件 = 10 改 + 10 增 + 2 文档 + 1 清单）

### 4.1 改动（10，相对 M19）

| 文件 | 改动要点 |
|---|---|
| `board_package/board_gate9_full_chain_12class.cpp` | M22 九阶段 `m22::StageTiming` 打点 + `NullSink` 默认 + `finish_m22_runtime()` 输出唯一 `M22_RUNTIME_RESULT` + `--perf-file`/`--summary-interval` + 资源采样 |
| `board_package/npu_classifier.hpp` | Device 构造器 Open 一次/析构 Close 一次、Session 持久 apply 一次、per-frame `Device::reset(1)` 从第 2 帧、`NpuLifecycleState` 状态机、`inputs_.reserve(1)`/`read_buf_` 复用 |
| `board_package/producer_12class.hpp` | 预分配成员 `cf_`/`scaled_`/`dsp_scratch_`，`measure_into`/`classify` 原地复用 |
| `board_package/chain_common.hpp` | `classify::softmax(logits)` → `classify::softmax_into(logits, r.probabilities)` 复用安全 |
| `sdr_adapter/classify.hpp` | 新增 `softmax_into(x,out)` 原地复用，`softmax` 委托（定义顺序修正） |
| `sdr_adapter/dsp_measure.hpp` | 新增 `MeasureScratch` 复用 FFT/power/sorted 临时缓冲 + `measure_into` 原地测量 |
| `sdr_adapter/ui_report.hpp` | 新增 `NullSink`（M22 默认逐帧不写串口） |
| `sdr_adapter/unix_socket_sink.hpp` | 非阻塞写（`O_NONBLOCK` + EAGAIN 丢帧 + 对端消失重连），绝不阻塞推理循环 |
| `host_tests/build_host_tests.sh` | 追加 `test_m22_runtime` |
| `host_tests/run_tests.sh` | 追加 `test_m22_runtime` |

### 4.2 新增（10）

| 文件 | 内容 |
|---|---|
| `sdr_adapter/latency_stats.hpp` | `StageId` 九阶段 + `PercentileStats`（65536 环形，`record()` 零分配）+ `StageTiming` RAII + `json()` |
| `sdr_adapter/npu_lifecycle_state.hpp` | 纯逻辑 NPU 生命周期状态机（Uninit→Opened→SessionApplied→Ready/Recovering/Failed） |
| `sdr_adapter/resource_snapshot.hpp` | `ResourceSample` + `read_resources()`（/proc + getrusage，Linux 专用） |
| `host_tests/test_m22_runtime.cpp` | 346 断言（分阶段统计/生命周期/资源采样/软硬门限/JSON） |
| `scripts/m22_harness.sh` | M22 共享助手（run_id/后台启动/唯一 verdict 提取/PASS 判定/perf 非空） |
| `scripts/run_m22_runtime_baseline.sh` | RX-only ambient 10000 帧运行时基线采集 + 唯一 `M22_RUNTIME_BASELINE result=` |
| `scripts/run_m22_runtime_regression.sh` | 离线重放 240 帧回归 + 唯一 `M22_RUNTIME_REGRESSION result=` |
| `scripts/test_m22_m24.sh` | M22/M24 脚本层主机测试，45 断言 |
| `docs/M22_RUNTIME_BASELINE.md` | §三 13 项测量清单 + 标签 + JSON schema + 板端采集步骤 + 验收行 |
| `docs/M22_LATENCY_ROOT_CAUSE.md` | §四 候选位置分析 + 主假设（串口观察者效应）+ 板端确认流程 |

### 4.3 文档（2）+ 清单（1）

- `README.md`：状态行 → `READY-FOR-M22-RUNTIME-HARDWARE-PROFILING` + M22 里程碑行。
- `PROVENANCE.md`：§3 增记 M22 20 行（每文件 SHA256）+ §12 交付物节。
- `SHA256SUMS.txt`：重生成（462 行，排除自身）。

> 排除项（非交付物，不进入任何包）：`host_tests/bin/*`（x86 WSL 编译产物，31 个二进制，其中含
> 新增 `test_m22_runtime`；板端自行 `./build_host_tests.sh` 重编）、`work/pkg` 内构建缓存。

## 5. 主机测试结果（WSL g++ 15.2.0，本轮复跑全绿）

| 项 | 结果 |
|---|---|
| `host_tests/build_host_tests.sh`（`-std=gnu++17 -O2 -Wall -Wextra -Werror`） | **OK，30 个二进制全部编译通过** |
| `host_tests/run_tests.sh` | **ALL HOST TESTS PASSED**（30 套） |
| `test_m22_runtime`（C++） | **346 pass / 0 fail** |
| `test_m22_runtime`（ASan/UBSan `-fsanitize=address,undefined` + `detect_leaks=1`） | **346 pass / 0 fail，无 sanitizer 报错** |
| `scripts/test_m22_m24.sh` | **45 pass / 0 fail** |
| `scripts/test_board_build.sh` | **24 passed / 0 failed** |
| `scripts/test_cli_override.sh` | **PASSED** |
| `bash -n`（build_host_tests/run_tests/m22_harness/run_m22_runtime_baseline/run_m22_runtime_regression/test_m22_m24） | 全通过 |
| 板端 iCraft 路径 `board_gate9_full_chain_12class` `-fsyntax-only`（`-isystem $ICRAFT_INCLUDE`） | 语法通过（板端链接/运行仍待上板） |

## 6. 未完成事项（须板端完成，离线无法替代）

1. **真实 13 项运行时数值**：`runs/m22_runtime_baseline/*.json` 的逐阶段 mean/P50/P95/P99/max、RSS/FD/线程、
   CPU 秒等仍为 `UNKNOWN`，须用户本人上板跑 `run_m22_runtime_baseline.sh --frames=10000` 采集回填。
2. **`reopen==0` / 逐帧零分配 / `spike_free==1` 的实测确认**：当前为代码级推导 + 假设，板端
   `M22_RUNTIME_RESULT result=PASS` 到手才转**实测**。
3. **425–937 ms 尖峰根因确认**：主假设 = 串口观察者效应（`M22_LATENCY_ROOT_CAUSE.md` §2），须板端
   `spike_free==1` 且唯一改动吻合才由「假设」升级为「确认根因」；若仍 `spike_free==0` 则按 §5 用逐阶段
   `max_us` 定位真正尖峰阶段（§四「禁止在未确认根因前直接修改多个模块」）。
4. **板端真实链接/运行**：iCraft SDK 仅板端可链接，`-fsyntax-only` 已过，正式运行待上板。
5. **M23/M24 尚未开始**（§二 阶段门禁：M22 未通过不得开始 M23）。

## 7. 状态红线

- 当前最高：**`READY-FOR-M22-RUNTIME-HARDWARE-PROFILING`**（离线交付完成，未上板）。
- 板端 `run_m22_runtime_regression.sh` + `run_m22_runtime_baseline.sh` 均 `result=PASS` 后，方可标
  **`M22_RUNTIME_HARDWARE_PASS`**。
- **绝不提前写**：`PERFORMANCE_PASS` / `M22_RUNTIME_HARDWARE_PASS` / `OOD_U_PASS` / `24CLASS_PASS` /
  `PROJECT_COMPLETE`。
- 12 类正式模型冻结 `model_sha256 = 2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c`，
  未改 NPU 权重/标签序/输入预处理/稳定 RTL/XDC/位流/framebuffer 地址与显示时序/触摸语义。

## 8. 上板最短步骤（用户本人执行，我禁碰板/禁写 Flash）

```bash
# 前提：板端 -O2 构建（./board_package/build_npu_on_board.sh）并把产物装入 bin/。
./scripts/run_m22_runtime_regression.sh          # 期望 M22_RUNTIME_REGRESSION result=PASS
./scripts/run_m22_runtime_baseline.sh            # 期望 M22_RUNTIME_BASELINE result=PASS 且 spike_free=1
# 落点：runs/m22_runtime_baseline/<run_id>/m22_runtime_baseline.json + gate9_ambient.log
```

## 9. M22 回答 §二十三 前 3 问（当前状态）

1. **263 ms Device reopen 是否彻底消除**：代码级推导 = 是（Device 仅在构造器 Open 一次、析构 Close 一次，
   `NpuLifecycleState::discipline_ok()` 要求 `open_count==1 && apply_count==1`）；板端 `reopen==0` 确认后转**实测**。
2. **425–937 ms 尖峰的确认根因**：主假设 = 串口观察者效应（逐帧 stdout JSONL + `fflush`，默认已改 `NullSink`），
   板端 `spike_free==1` 确认后转**确认根因**。
3. **稳态是否还有逐帧内存分配**：代码级推导 = 否（热路径缓冲全预分配复用，`record()` 零分配；唯一保留的
   iCraft `Tensor.mallocOn` 有界 ~8KB 非泄漏）；板端 RSS 平稳确认后转**实测**。
