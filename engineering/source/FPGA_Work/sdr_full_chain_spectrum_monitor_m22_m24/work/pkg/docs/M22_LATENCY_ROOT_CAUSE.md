# M22 延迟尖峰根因定位（Latency Root Cause）

任务 39e5 M22 §四。目标：**定位而不是猜测** 425–937ms 周期尖峰的来源，并给出可重复的板端确认手段。

> **诚实声明**：离线阶段只能做**代码级分析（推导）**，无法采集板端时间戳。本文档：
> (1) 逐项列出 §四 的候选位置并给出代码证据；(2) 给出**主假设**（串口观察者效应）及其依据；
> (3) 给出把「假设」升级为「确认根因」的**板端打点流程**。**在板端 `spike_free=1` 与逐阶段
> `max_us` 时间戳到手前，本文档只称「假设」，不称「已确认根因」。**

---

## 1. M21-0 发现的三个现象（引用基线，不重复猜测）

| 现象 | M21-0 报告值 | 本文档处理 |
|---|---|---|
| Device reopen | 约 **263 ms** | M22 以「open-once/close-once + 状态机」消除（见 §3.1），板端 `reopen==0` 确认 |
| 周期性尖峰 | 约 **425–937 ms** | 本文档定位对象 |
| 逐帧 fresh 分配 | 每帧存在 | M22 以「全预分配复用」消除（见 §3.2） |

---

## 2. §四 候选位置逐一分析

| # | 候选位置 | 代码证据 | 判断 |
|---|---|---|---|
| 1 | 设备 open/close | M21-0 的 263ms reopen 是**一次性**、非周期性；且帧循环内无 open/close 路径 | **排除为「周期」尖峰源**（但仍需 `reopen==0` 消除一次性开销） |
| 2 | libiio | 采集走 `capture_contiguous` 单次大 refill；无逐帧属性读写（Gate 3 已修复属性路由） | 非主因；由 `StageId::RxRefill` 打点覆盖 |
| 3 | RX refill | 单批 16 帧连续采集，非逐帧 | 由 `rx_refill` 打点观察 |
| 4 | DMA/cache sync | iCraft 侧 `Tensor.write/read` 与 `Device::reset(1)` | 由 `npu_infer` 打点覆盖（reset+forward+wait 全在 `npu_infer` 计时内） |
| 5 | NPU 运行时 | `forward + waitForReady` 异步；旧每帧新建 Session 不重武装 → 读回上一帧（已修） | 由 `npu_infer` 打点观察 |
| 6 | 内存分配 | 已全预分配复用（`cf_/scaled_/dsp_scratch_/inputs_/read_buf_`） | **代码级消除**；保留的 iCraft `Tensor.mallocOn` 有界 ~8KB 非泄漏 |
| 7 | **日志 flush** | 旧路径逐帧 stdout JSONL + `fflush(stdout)`，串口 115200 下每帧 ~1KB 记录 → 毫秒级阻塞，累积为周期尖峰 | **主假设** |
| 8 | framebuffer | UI 侧 vblank 只读审计（M17 Task D）已确认不阻塞生产者；生产者→UI 走 AF_UNIX socket 非阻塞写 | 非主因 |
| 9 | 调度抢占 | 4×A53 @~1GHz；控制线程与采集线程并存 | 由 `frame_total max_us` 与逐阶段 `max_us` 对照排除 |

### 主假设：串口观察者效应（`推导`，待板端确认）

- **机理**：旧代码对每一帧 `result_frame_v3_line()` 生成 ~1KB JSON 字符串后 `std::fputs + fputc('\n') + fflush(stdout)`。
  串口波特率下 `fflush` 会阻塞等待写空；逐帧 flush 使串口成为吞吐瓶颈，导致周期性 425–937ms 尖峰。
- **既往证据**：任务 39e5d-v3（`sdr_preparation_v3_logging_fix`）已把「输入分配」根因**反转为串口观察者效应**；
  M21-0 报告的三现象中「逐帧 fresh 分配」单独无法解释 425–937ms 的量级，而串口阻塞可以。
- **M22 的处理**：逐帧结果路由默认改为 `NullSink`（`--verbose` 才开 stdout）；性能明细写 `--perf-file` 文件；
  串口只打印启动/状态变化/`M22_SUMMARY` 周期摘要/最终结果（§五.3 日志要求）。
- **验证逻辑**：若板端 `spike_free==1`（`frame_total max_us <= 100ms`），则尖峰消失 → 与「移除逐帧 flush」
  这一唯一改动吻合，从而**确认**根因为串口观察者效应；若仍 `spike_free==0`，则按 §5 用逐阶段 `max_us`
  定位真正尖峰所在阶段。

---

## 3. M22 已做的修复（对应 §五）

### 3.1 Device 生命周期（§五.1）

- `NpuClassifier12` 只在构造器 `Device::Open` 一次、析构器 `Device::Close` 一次；连续帧间零 reopen。
- 显式状态机 `NpuLifecycleState`：`Uninit→Opened→SessionApplied→Ready`；瞬态 per-frame 失败进 `Recovering`
  并按预算重试**同一帧**；`Device::reset` 失败为**致命**（fail-closed，RAII 关闭一次）；**永不**以泄漏规避 close。
- `NpuReArmState` 保证首帧不 reset、第 2 帧起每帧恰一次 `Device::reset(1)` 且不 re-apply（`reset_count==frames-1`）。

### 3.2 缓冲区生命周期（§五.2）

- 预分配并复用：RX IQ（`iq`）、预处理输入（`chain` 内部）、NPU 输入（`scaled_`）、NPU 输出（`out`/`d.logits`）、
  分类后处理（`softmax_into` 原地）、UI 消息序列化（`result_frame_v3_line` 复用 `rf::ResultFrame`）。
- 稳定运行阶段无逐帧 `malloc/new/free`；主机单测以 `softmax_into==softmax`、`measure_into==measure` 逐位一致证明。

### 3.3 日志（§五.3）

- 默认不逐帧写串口（`NullSink`）；性能明细写 `--perf-file`；串口只打启动/状态/周期摘要/最终结果；`--verbose` 显式开启逐帧。

### 3.4 线程与同步（§五.4）

- 无忙等；控制队列 `CommandQueue(32)` 有界；生产者→UI 走 `UnixSocketSink` 非阻塞写，满则丢帧/对端消失则重连，
  **绝不阻塞推理循环**；UI 只渲染最新帧（既有 M17 事件驱动调度）。

---

## 4. 板端确认流程（把「假设」升级为「确认根因」）

```bash
# (1) 先证 NPU 输出一致 + 生命周期纪律（reopen==0/apply==1）
./scripts/run_m22_runtime_regression.sh
#   期望：M22_RUNTIME_REGRESSION result=PASS

# (2) 长运行基线，抓逐阶段时间戳
./scripts/run_m22_runtime_baseline.sh --frames=10000 --summary-interval=1000
#   期望：M22_RUNTIME_BASELINE result=PASS 且 spike_free=1

# 判定：
#   spike_free=1  => 425–937ms 尖峰消除，且唯一改动是「移除逐帧 stdout flush」→ 确认根因 = 串口观察者效应
#   spike_free=0  => 打开 runs/m22_runtime_baseline/<run_id>/m22_runtime_baseline.json，
#                    看哪个阶段 max_us 最大（npu_infer / rx_refill / frame_total / …），定位真正尖峰阶段，
#                    再针对性排查（不得未确认就改多模块）
```

---

## 5. 未确认前不得做的事（§四「禁止在未确认根因前直接修改多个模块」）

- 在 `spike_free` 与逐阶段 `max_us` 到手前，**不**进一步改动采集/NPU/UI 的多个模块；
- 不把「主假设」写成「已确认根因」；
- 不以「减少测试帧数」或「关闭功能」掩盖尖峰（§六）。

## 6. 状态

- 根因状态：**假设（串口观察者效应），待板端时间戳确认**。
- 与 `docs/M22_RUNTIME_BASELINE.md` §3.3 一致：`spike_free` 的 `frame_total_max_us<=100ms` 门限即尖峰确认开关。
