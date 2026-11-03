# RECOVERY_FIX2 B 线 — 同步效率 / 资源生命周期 / 计时拆分

任务书映射：fix1v2-independent-rx-recovery-fix2 三并行线中的 **B 线**（同步效率 + 资源
计量 + 计时拆分）。纯离线，不改恢复算法 / 分类门限 / 输出列，不碰板 / 不发射 / 不训练。
只改 `board_package/radioml_independent_rx_runner.hpp`（sync + 资源 + 计时区域）、新增
`board_package/radioml_independent_rx_fft.hpp`、在 `sdr_adapter/latency_stats.hpp` 追加
3 个计时阶段。红线内函数 `recover_and_classify_one` / `independent_rx_result_header` /
门限 / 输出列 **未改动**。

---

## 1. 同步搜索优化（`locate_preamble` / `preamble_sync_score`）

### 根因
原 `locate_preamble` 对 `[0, 76288]` 每个 offset 调 `preamble_sync_score`，后者在函数体
内每次调用都重新执行 `preamble_ref()`（= `iqrftrain::preamble()` → 1024 次 `zadoff_chu`
→ 1024×cos + 1024×sin，再 `deinterleave`）并重算前导能量 `p_energy`（常量）。因此每帧：

| 成本项 | 原实现 | 数量 |
|---|---|---|
| 前导再生成（cos+sin） | 76289 × 2048 | **≈156.2M 次超越函数 / 帧** |
| 互相关 + 能量（vdot 1024 + norm 2048） | 76289 × ~3072 | ≈234M 复运算 / 帧 |

设备捕获为 2×burst+2×margin = 136192 复样本，`max_off = 136192 − 59904 = 76288`，所以
单帧就是 76289 次偏移扫描。前导再生成的 156.2M 次 sin/cos 在板端 ARM（软件双精度超越
函数、无 fast-math）是 M22 实测单帧 ~27.7s 的主导项。

### 修复
1. **前导 + 前导能量提为不变量**：`locate_preamble` 每调用一次只生成一次 `pre`、只算
   一次 `p_energy`，新增 4 参 `preamble_sync_score(rx, off, pre, p_energy)`；保留 2 参
   重载（委托）兼容任何外部调用方。
2. **O(N·K) → O(N log N) 互相关**：新增自包含 radix-2 复 FFT
   （`radioml_independent_rx_fft.hpp`，header-only、无 iCraft / libiio、主机板端同源）。
   用线性卷积算 `R[m] = Σ_k rx[m+k]·conj(pre[k])`（零填充到 `N = next_pow2(limit+2K−1)`
   = 131072，三次 FFT）。
3. **top-K 候选峰 + 精确回退**（关键正确性设计）：TX 是循环的（capture ≥ 2 burst），
   ZC 前导可在两个 offset（相距 59904）出现；且归一化分数 `|R|/√(p_energy·r_energy)`
   还要除以随窗口缓慢变化的 `r_energy`，故「原始 |R| 的 argmax」**不一定等于**「归一化
   分数的 argmax」。因此：收集 |R[m]| 的局部极大值 → 按幅值取 top-8 → 按 offset 升序对
   每个候选峰 ±64 用**精确公式**重算归一化分数 → 取全局最大（`>` 保持最小 offset 打平
   优先）。返回的 offset/score 与全量 O(N·K) 暴力**逐位一致**。

### 正确性核验（真实 24 帧捕获，`host_tests/test_sync_fft_invariant.cpp`）
读 `rml24_independent_v2_dual_1773374217_210/*.raw.i16`，逐帧比对「精确暴力」vs「FFT」：

```
SYNC_FFT_INVARIANT offset=24/24 no_sync=24/24 max_score_err=0.000e+00
```

24/24 offset 一致、24/24 no_sync 判定一致、最大 score 误差 = 0（返回分数逐位一致）。
（首版只对单 argmax 回退时 sid=14/18 翻转 —— 正是循环帧双前导 + r_energy 归一化导致，
top-8 候选回退修复后归零。）

### 耗时（`host_tests/test_sync_bench.cpp`，sid=1，主机 x86，-O2）
```
brute_force(hoisted): 114.4 ms
fft                 :  22.5 ms    -> 5.1x（主机；这是「已提升前导」下界）
```
真实原实现还叠加 156.2M 次 sin/cos（x86 约 +1~2s，板端 ARM 为主导项）。**板端投影**：
sync 从 ~20s 量级降为三次 131072 点 FFT + ≤8×129 点精确回退 ≈ ~1s；`FrameTotal` 的 27.7s
塌缩到 RF 捕获(~53ms)+控制往返+2×NPU 推理+落盘 ≈ ~1–2s。板端绝对值为板上实测，此处不
宣称（只给主机实测相对数与板端量级投影）。

---

## 2. 资源采样生命周期 + fd_growth=7

### 根因（非每帧泄漏，是采样点错位）
`rep.first_res = m22::read_resources()` 原先在 `results_out` 打开之后、**设备初始化之前**
采样。设备模式下，此后才打开的是**常驻 init 期 FD**：libiio 设备上下文（`pluto::make_device`
→ `LibiioDevice::open()`，网络/本地后端持有数个 sysfs/socket FD）+ TCP 控制通道
`client.connect()`（1 个 socket）。这些 FD 在整个 run 期间常驻，却落在 first_res 之后 →
被 `finish_m22_runtime` 的 `fd_growth = last − first` 误报为「泄漏」。fd_growth=7 与
「libiio 上下文(≈4–6 FD) + 控制 socket(1 FD)」数量吻合。

### 审计结论（runner 自身文件 I/O 全部成对、零每帧增长）
`read_i16_file` / `manifest_file_sha256`（`std::ifstream` RAII）、`persist_raw_rx` /
`persist_logits` / `.recovered.tensor.bin` / `.capture.diag.tsv`（全部块作用域
`std::ofstream` RAII）、`results_out` / `summary`（run 级单句柄）—— 逐项核对均成对关闭。
`recreate_rx_buffer()`（`pluto_device_libiio.cpp`）先 `iio_buffer_destroy` 再置空
（destroy-before-create，平衡），亦非每帧泄漏源。

### 修复
把 `first_res` 采样点**后移**到设备/NPU/TCP 初始化完成、帧循环之前（`capture` 定义后、
`for (frames)` 前），使 `first_res` 捕获完整常驻 FD 集。此后 `fd_growth = last − first`
才是**真正的每帧增长**；常驻 init FD 不再被误报。runner 层无每帧 FD 泄漏，故修复后
预期 `fd_growth ≤ 0`（`fd_ok` 判定通过）。此修复对 file 模式无影响（file 模式本就无
设备/控制 FD，first_res 采样点等价）。

---

## 3. 计时拆分（六段）

`latency_stats.hpp` `StageId` 追加 3 阶段（插在 `FrameTotal` 后、`Count` 前，索引与既有
语义不变，`kStageCount`/`json()` 自动纳入）：

| 任务书六段 | 对应阶段 | 说明 |
|---|---|---|
| control-wait | **ControlWait**（新） | `capture_device_frame` 内 PREPARE→START→READY 与 CAPTURED→STOPPED 两段控制往返 |
| SDR-capture | **RxRefill**（既有） | `capture_contiguous` 实际 RF 采样 |
| sync | **Sync**（新） | `locate_preamble` 前导搜索 |
| reference-estimate-recovery | **RecoveryClassify**（新） | `recover_and_classify_one` 整体 |
| 2×NPU-inference | *并入 RecoveryClassify* | `recover_and_classify_one` 为冻结函数，`npu.infer×2` 在其内部，无法单独计时 |
| diagnostic-save | *并入 RecoveryClassify* | 同上（raw/logits/tensor 落盘在其内部） |

诚实边界：`recover_and_classify_one` 是红线冻结函数，不能拆成 estimate / infer / save
三个独立计时；因此「恢复 + 2×推理 + 落盘」合并为一个 `RecoveryClassify` 阶段。既有
`NpuInfer` 阶段在本 phase 本就从未被该函数填充（非本次引入）。六段中三段可独立归因，
三段折叠为一段，报告据此说明 27.7s → 修复后的时间去向（sync 不再占主导）。

---

## 4. 交付物与验证

- `board_package/radioml_independent_rx_fft.hpp`（新）：自包含 radix-2 FFT + `next_pow2` + `cross_correlate`。
- `board_package/radioml_independent_rx_runner.hpp`（改）：sync 优化 + first_res 采样点后移 + ControlWait/Sync/RecoveryClassify 计时。**未改** `recover_and_classify_one` / 结果表头 / 门限 / 输出列。
- `sdr_adapter/latency_stats.hpp`（改）：追加 3 个 `StageId` + `stage_name`。
- `host_tests/test_sync_fft_invariant.cpp`（新）：24 帧 offset/no_sync 不变量核验（**24/24，score_err=0**）。
- `host_tests/test_sync_bench.cpp`（新）：sync 前后耗时（主机 5.1×，板端量级投影见 §1）。
- `host_tests/syntax_runner_template.cpp`（新）：`-fsyntax-only` 显式实例化 `run_radioml_independent_rx`（**SYNTAX_OK**），确认模板体改动可编译。
- 编译：`g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter`，`test_sync_fft_invariant`、
  `test_radioml_independent_rx`（既有 host 链测）均编译通过；`-fsyntax-only` 实例化通过。

红线遵守：未碰 A 线 `radioml_independent_rx_public_recovery.hpp` / C 线回归判读、未改
`recover_and_classify_one` / 表头 / 门限 / 输出列、纯离线、不碰板。
