# M27.1 板端探针计划与结论分类（Probe Plan & Conclusion Classification）

任务 id="39e5" · M27.1 · 本节定义 5 个探针、测量指标、安全边界与 A/B/C/D/E 结论分类。

**离线阶段最高状态**：`M27_1-MULTI-MODEL-PROBE-READY`。只有完成真实板端探针后，才允许把结论推进为 A/B/C/D 之一。

---

## 1. 探针清单（5 个，独立版本目录，不触碰 Gate 9/10）

所有探针位于 `probes/`，共用 `probe_common.hpp`（设备/网络/会话/输入反量化/日志/计时/结果输出），每个探针一个 `.cpp`。全部**失败即非零退出**（fail-closed），输出一行 `PROBE_RESULT=...` 尾标 + 结构化 JSON。

| 探针 | 目的 | 回答的能力问项 |
|---|---|---|
| `probe_single_model` | 基线：单模型单 Session 1000 帧稳定推理（对照） | 单模型驻留正确性/延迟基线 |
| `probe_two_networks` | 单 Device 上同时建 2 个 Network + 2 个 Session + 2 个 ZG330Backend，分别 `apply()` 后交替 `forward` | **能否多模型同时驻留**（A/B） |
| `probe_sequential_inference` | 同一 Device **不重开**，串行 A→B→A 各 1000 帧 | **能否多模型串行调度**（无逐帧 Device::Open） |
| `probe_concurrent_inference` | 仅当 SDK 允许：多线程各持 `Backend::fork()` 副本，观察是否真正并行（吞吐 vs 串行对照） | **能否真正并发** |
| `probe_unload_reload` | 卸载 A（Session 析构 + deinit）→ 装载 B → 卸载 B → 重装 A，测切换延迟 | **模型切换 / 卸载重载延迟** |

> `probe_concurrent_inference` 若 SDK 无法构造并发（无异步提交 API，见审计 §7），则**输出 `CONCURRENT_UNSUPPORTED_BY_API` 并跳过**，**不得**用假线程伪造并行结论。

---

## 2. 测量指标（§四）

### 2.1 统一采样协议

- 每个模型每轮：**100 帧 warmup**（丢弃，不计入指标）+ **1000 帧**有效采样。
- 串行切换 `probe_sequential_inference`：A 1000 → B 1000 → A 1000（A/B/A 各 warmup 100）。
- 可选 `probe_concurrent_inference`：双模型并发 1000 帧吞吐 vs 串行 1000 帧吞吐对照。

### 2.2 逐探针记录字段（结果 JSON 见 `results/M27_1_RESULT_TEMPLATE.json`）

| 字段 | 含义 |
|---|---|
| `device_open_us` | `Device::Open` 耗时（一次性） |
| `model_load_us` | `CreateFromJsonFile`+`lazyLoadParamsFromFile` 耗时（每模型） |
| `session_apply_us` | `Session::Create`+`apply()` 耗时（每模型） |
| `forward_us_mean/max/p99` | 单模型有效帧 forward+waitForReady 耗时 |
| `switch_us` | A↔B 切换（卸载+重装+apply）耗时 |
| `concurrent_throughput_fps` | 并发吞吐（仅并发探针） |
| `serial_throughput_fps` | 串行吞吐（对照） |
| `correctness_pass` | 输出与冻结 reference 一致（A 12 类 / B 8 类） |
| `repeatability_pass` | 多轮结果稳定 |
| `error_count / timeout_count` | 失败帧数 |
| `return_code` | 各 API 返回码 |
| `mem_etm_used_bytes / ocm_used_bytes` | 若 SDK 暴露段表可读（否则 UNKNOWN） |
| `cpu_usage` | 采样期间 CPU 占用 |

### 2.3 稳定性与正确性判据

- **正确性**：A 输出 12 维、B 输出 8 维，与各自冻结 reference 逐帧比对（B 用 `npu_realtime_v1/board_package/reference_argmax.txt` 的 argmax 序列）。
- **重复性**：每探针至少跑 2 轮，轮间 `forward_us_mean` 相对偏差 ≤ 一定阈值（默认 20%，超阈值记 `repeatability_pass=false`）。
- **不掩盖错误**：任何 `apply()`/`forward()` 异常都记录 `return_code` + `error_count`，**不允许**静默降级为 HostBackend。

---

## 3. 安全边界（§五，红线）

探针必须满足以下全部约束（`probe_common.hpp` 与一键脚本共同保证）：

1. **不写 Flash**：不调用任何 Flash 写入接口。
2. **不碰 RTL/XDC/位流**：纯运行时推理探针，不生成/修改任何 FPGA 工程。
3. **不覆盖历史模型**：A/B 只读加载，`sha256sum -c` 冻结校验先行。
4. **不接生产链 / Gate 9/10**：探针是独立进程，不链接 `board_ui_live_12class`、不读写生产链的共享内存/UNIX socket。
5. **不逐帧串口打印**：探针只在结束时汇总打印，采样期静默。
6. **不逐帧 `Device::Open`**：探针一次 Open、一次 Close（`probe_unload_reload` 除外，它测的正是卸载/重装延迟，但仍不逐帧 Open）。
7. **禁止 263ms/帧重开路径**：持久 Device + 每帧 `reset(1)`（首帧除外），沿用 `npu_classifier.hpp` 已板证纪律。
8. **fail-closed**：任一前置校验（SHA 不匹配、参数非法、模型契约不符）→ 非零退出，不继续。

---

## 4. 结论分类（§六，只能选其一，且须有板端实测证据）

| 结论 | 状态串 | 触发条件 |
|---|---|---|
| **A** | `MULTI_MODEL_RESIDENT_SUPPORTED` | `probe_two_networks` 证明 A+B 同时驻留且稳定串行调用 |
| **B** | `MULTI_MODEL_CONCURRENT_SUPPORTED` | 在 A 基础上，`probe_concurrent_inference` 有证据证明真正并发执行 |
| **C** | `MULTI_MODEL_SWITCH_ONLY` | 不能同时驻留，但 `probe_unload_reload` 证明可卸载/加载交替运行 |
| **D** | `SINGLE_MODEL_ONLY_CONFIRMED` | SDK 文档**和**实测都证明只能维持一个模型 |
| **E** | `MULTI_MODEL_CAPABILITY_UNRESOLVED` | 证据不足，或缺少第二个合法模型，不能下结论 |

**判定纪律**：
- 探针**跑完前**只能写 `UNVERIFIED`，不得预判 A/B/C/D。
- **不得**把"当前代码只有一个 Session"当作"硬件只支持一个模型"（任务红线）。
- `probe_two_networks` 若因 etm 不足在 `apply()` 阶段失败 → 记录 `return_code`，此时**不能**直接判 D（可能是容量问题而非"只支持单模型"），应判 **C**（可卸载/加载）或 **E**（需更多证据），以实测卸载/重载探针为准。

---

## 5. 状态

```
M27_1-MULTI-MODEL-PROBE-READY
```
