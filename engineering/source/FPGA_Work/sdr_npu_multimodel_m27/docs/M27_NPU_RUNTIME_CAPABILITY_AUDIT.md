# M27 NPU 运行时能力审计（Runtime Capability Audit）

任务 id="39e5" · M27 · 只读审计，未修改任何工程/代码/位流/模型/交付包。

**来源类别图例**（全文统一）：
`实测`＝板端日志/用户转录实测值；`官方头文件`＝iCraft 3.39.0 SDK 头文件与设备文档（`C:/Icraft/CLI v3.39.0/`）；
`代码常数`＝板端源码 .cpp/.hpp 常量；`契约文档`＝工程内 .md/.json 契约；`无证据`＝审计范围内无该证据，不猜测（标 UNKNOWN）。

**审计对象**：ZG330 iCore（iCraft 3.39 运行时），板端证据来自 `npu_realtime_v1/`（`npu_realtime.cpp` + `REPORT.md` + `BOARD_RESULTS_2026-10-01.md`）、`npu_stage_v1/`、`fpga_npu_joint_v1/`、`sdr_m21_0_board_audit/`。

---

## 0. 结论摘要（TL;DR）

| # | 审计项 | 结论 |
|---|---|---|
| 1 | 多模型同时加载 | **UNKNOWN（无证据）**，现有代码仅单模型单持久 Session |
| 2 | 多模型上下文 | **UNKNOWN（无证据）** |
| 3 | 异步队列 | 仅单推理异步完成（`waitForReady`），**无多请求队列 API** |
| 4 | 并行 / 仅串行 | **UNKNOWN（无证据）**，现链为软件串行流水线 |
| 5 | NPU 可用模型内存 | **UNKNOWN（无证据）**；模型 raw 2,851,472 B（lazyLoad） |
| 6 | 单模型加载时间 | **UNKNOWN（无证据）**；未与 reopen 解耦隔离 |
| 7 | 上下文创建/销毁时间 | **UNKNOWN**；Device::Open 是 reopen 主要开销 |
| 8 | 模型切换时间 | **UNKNOWN（无证据）**；无多模型切换代码 |
| 9 | DMA 输入输出耗时 | per-frame setup avg **0.045ms** / max 0.116–0.123ms（实测） |
| 10 | 硬件利用率/busy-time 计数器 | **无**；仅 `layerCount()` 只读观测 |
| 11 | 批量输入 | **UNKNOWN（无证据）**；现有输入 batch=1 |
| 12 | 输出真实 raw logits | **是**：直接 memcpy float，无 softmax/argmax 后处理 |
| 13 | 263ms reopen 调用链 | **已定位**：Device::Open 主导；根因=异步完成缓存单调不回零 |

**总体判定（关键）**：

```
MULTI_MODEL_RESIDENCY_UNSUPPORTED
```

现有 ZG330/iCraft 3.39 运行时**无任何证据表明支持多模型同时常驻**：代码只有单一 `Device` + 单一 `Session` + 单一 `Network` + 一次 `apply()`；官方头文件审计也未见多上下文/多模型常驻 API（`npn_realtime_v1/REPORT.md` 的 API 盘点只列出 `forward/waitForReady/isReady/setReady/setCheckFunc/reset/check/layerCount`）。因此 M27 的注册表/路由/融合框架**必须假设单模型常驻**，采用 spec §七 指定的替代方案（见 §8），**不得假装并发运行**，不得为「提升利用率」而无条件重复推理。

---

## 1. 是否支持多个模型同时加载（审计项 1）

**UNKNOWN（无证据）。** 现有板端代码（`npu_realtime.cpp`、`fpga_npu_joint_smoke.cpp`）均为**单模型**：一个 `Network::CreateFromJsonFile(model.json)` + `lazyLoadParamsFromFile(model.raw)` + 一个持久 `Device` + 一个 `Session` + 一次 `apply()`。无任何多 `Network`/多 `Session` 并存的代码路径或 API 证据。

---

## 2. 是否支持多个模型上下文（审计项 2）

**UNKNOWN（无证据）。** 官方头文件盘点（`npu_realtime_v1/REPORT.md` §B）列出的完成等待/重 arm 接口为 `waitForReady / isReady / setReady / setCheckFunc / reset / check / layerCount`，无「多上下文 / 多 Session 绑定 / context switch」类 API。单上下文（1 Device + 1 Session + 1 applied Network）是唯一被验证的形态。

---

## 3. 是否支持异步队列（审计项 3）

**部分（仅单推理异步完成，无队列）。** `Session::forward()` 对 ZG330 后端是**异步**的：返回输出 `Tensor`，其完成状态由「软件 `ready_` 缓存 + 硬件 `check_func_`」编码（`icraft-xrt/core/tensor.h`）。`Tensor::waitForReady(timeout)` 是唯一的官方完成等待接口。但这是**单次推理的异步完成握手**，不是多请求排队/乱序完成/异步提交队列。**无** `finish/synchronize/release/rebind/flush/barrier` 等官方同步接口（全 SDK 头文件 grep 仅 `serialize.h` 有一个无关 `finish`）。

---

## 4. 是否支持并行或仅串行执行（审计项 4）

**UNKNOWN（无证据）。** 现有端到端链为软件层串行流水线 `Capture→Fpga→Npu→Result`；无多 Session 并行、无流水推理、无并行推理证据。M21-0 审计同样结论：并行/流水推理 = UNKNOWN。

---

## 5. NPU 可用模型内存（审计项 5）

**UNKNOWN（无证据）。** NPU 片上 SRAM/cache 容量无官方文档（M21-0 结论：9.3Mb Block RAM 是 PL/FPGA 侧资源，非 NPU 片上 SRAM）。已知模型体量：12 类 `model.raw` **2,851,472 字节**，经 `lazyLoadParamsFromFile` 加载；12 类 279,036 参数 / 46,544,384 MAC，24 类 280,584 参数 / 46,545,920 MAC。模型驻留内存上限无法从审计源确定。

---

## 6. 单模型加载时间（审计项 6）

**UNKNOWN（无证据，未隔离）。** 加载经 `lazyLoadParamsFromFile`，无独立隔离测量。reopen 基线（~263ms/帧）**包含** `Device::Open` + `Network` 构建 + `Session::Create` + `apply()` 全链，无法从该数字拆出「纯模型加载时间」。

---

## 7. 上下文创建与销毁时间（审计项 7）

**UNKNOWN（未单独隔离），但已知为 reopen 主导开销。** 每帧 `Device::Close/Open` 是 ~263ms 的主要来源（`BOARD_RESULTS_2026-10-01.md`：「reopen 12/12 correctness control, PASS, but about 263 ms per frame」）。持久 Device + 每帧 `reset(1)` 后 forward 降至毫秒级（见 §9），说明**上下文生命周期**（而非计算）是开销主体。上下文创建/销毁的精确分段耗时**无落盘值**。

---

## 8. 模型切换时间（审计项 8）

**UNKNOWN（无证据）。** 无多模型切换代码；无「卸载模型 A 加载模型 B」的实测。因运行时不支持多模型常驻（§0），模型切换等价于「重开上下文 + 重载模型」，其下限即 reopen 量级（~263ms 量级，含 Device 重建），**逐帧切换不可行**。

---

## 9. DMA 输入输出耗时（审计项 9）

| 项 | 数值 | 来源 |
|---|---|---|
| per-frame setup（张量分配 + 写入 + reset） | avg **0.045ms** / max 0.116–0.123ms | 实测（8 类 100 帧 ×3 轮） |
| forward（含 waitForReady + read） | avg 0.666–0.673ms / max 1.052–1.059ms | 实测（8 类 100 帧 ×3 轮） |
| NPU 输入带宽 | 2048 float ×4B = 8KB/帧；@1000fps ≈ 8MB/s | 推导（M21-0） |
| NPU DMA 通道 | PL DDR 64-bit MIG（`dma=0x80000000`） | 代码常数 |

**审计结论**：DMA/张量搬运本身毫秒级以下（setup ~0.045ms），不是瓶颈；瓶颈在上下文生命周期与周期性尖峰（见 §13）。

---

## 10. 是否存在硬件利用率或 busy-time 计数器（审计项 10）

**无。** 唯一可读观测是 `ZG330Device::layerCount()`（`zg330_device.h:209`，只读层计数，用于观测 `layer_b/layer_a`）。**无**利用率 / busy-time / 性能计数器暴露于官方 API。因此 spec §九要求：无硬件计数器时只能写「估算利用率」，**不得写「真实 NPU 利用率」**。

---

## 11. 是否支持批量输入（审计项 11）

**UNKNOWN（无证据）。** 现有模型输入为 `[1,2,1024]` + `[1,3,1024]`（batch=1，`npu_realtime.cpp` `same_shape(shape, {1,2,1024})` 强制校验）。无 batch>1 的编译或运行证据。M27 框架默认按 batch=1 设计，批量支持作为待上板验证项。

---

## 12. 输出是否为真实 raw logits（审计项 12）

**是。** `read_fp32_logits()`（`npu_realtime.cpp`）读 `tensor.dtype().bytes()`（8 类 = 32 字节）→ `to(HostDevice::MemRegion())` → `read` → `memcpy` 成 `std::vector<float>`（8 个 float）。无 softmax、无 argmax 后处理、无归一化。8 类 raw logits = 8×float；12 类 = 12×float。**输出即真实 raw logits**，可直接作为融合/路由/OOD 评分的输入。

---

## 13. 约 263ms reopen 问题的实际调用链（审计项 13）

**调用链（`npu_realtime.cpp::forward_read_reopen`）**：

```
Device::Open(kDeviceUrl)                    // axi://zg330aiu?npu=0x40000000&dma=0x80000000
  → Session::Create<ZG330Backend, HostBackend>(network, {device, HostDevice::Default()})
  → session.apply()
  → make_inputs(...)                        // 反量化 + 建输入 Tensor
  → session.forward(inputs)                 // 异步返回
  → outputs[0].waitForReady(kReadyTimeout)  // 完成等待
  → read_fp32_logits(outputs[0])            // memcpy 输出
  → Device::Close(device)
```

**根因（`npu_realtime_v1/REPORT.md` 只读审计，7 组真板实验验证）**：

1. `Session::forward()` 对 ZG330 是**异步**的，输出 Tensor 完成由 `TensorNode::ready_`（软件缓存，默认 true）+ `check_func_`（硬件完成轮询）编码。
2. `waitForReady()` 在 `ready_==true` 时**短路**，不查硬件；只有 `ready_==false` 才轮询 `check_func_`。
3. 复用 Session 时，`forward()` 从 `SessionNode::tmap_` 返回**同一** `TensorNode`，上一帧 `waitForReady()` 已置 `ready_=true` → 下一帧读旧输出。
4. 硬件完成态（`FPGA_LAYER_CNT_REG=0x0C` / `FPGA_STATE_REG=0x08`）在**同一 Device 生命周期内单调递增、不回零**，只有 `Device::Open`（初始化）或 `Device::reset` 才清除。

**结果**：保持 Device 常驻的方案（exp0/1/2/3/5/6）都是 1~5/12（一帧陈旧输出）；只有每帧 `Device::Close/Open`（exp4）重建硬件完成态 → 12/12，代价 **~263ms/帧**。

**修复（已真板 PASS）**：持久 Device + **每帧 `Device::reset(1)`**（官方文档化「只复位 FPGA 状态」）在 forward 之前重 arm 完成态（首帧除外）。结果：3 轮 ×100 帧全部 100/100，delay_shift=0，timeout=0，error=0，forward avg **0.666–0.673ms** / max 1.052–1.059ms，setup avg 0.045ms；24 次交替帧完整 logits 校验 worst diff = 0.0（stale=0）。

**审计结论**：263ms reopen 根因已定位并已有官方 API 修复（reset1），**生产链已无逐帧 reopen**；M27 框架必须沿用「Device 只 Open 一次 + 每帧 reset(1)」，**禁止逐帧 open/close 设备、禁止逐帧加载/卸载模型**。

---

## 附：M27 框架落地约束（源自本审计）

1. **`MULTI_MODEL_RESIDENCY_UNSUPPORTED`**：运行时无多模型常驻证据 → 采用替代方案（见下），不假装并发。
2. **替代方案 A（启动时选择模型）**：注册表 A–E 槽位，启动时只加载 1 个正式模型；其它模型为 stub/默认关闭，`enabled=false` 时不加载。当前 12 类模型默认行为保持不变。
3. **替代方案 B（共享骨干多输出头）**：24 类 / 专家 / OOD 若需共存，优先合并为单一 `Network` 的多输出头，而非多模型驻留。
4. **禁止**：逐帧 open/close 设备、逐帧加载/卸载模型、逐帧串口打印、为提升利用率无条件重复推理。
5. **状态红线**：最高 `M27-NPU-MULTIMODEL-OFFLINE-FRAMEWORK-READY`；不得写 `NPU_MULTIMODEL_PASS / 24CLASS_PASS / OOD_PASS / HARDWARE_PASS / PERFORMANCE_PASS / PROJECT_COMPLETE`；无硬件计数器时只能写「估算利用率」。
6. **时间预算基线**（供调度器参考）：单帧 forward ~0.67ms、setup ~0.045ms、reopen ~263ms（禁止路径）。
