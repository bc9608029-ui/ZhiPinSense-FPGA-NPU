# M27.1 SDK 多模型能力只读审计（iCraft 3.39.0 / ZG330）

任务 id="39e5" · M27.1 — FMQL30TAI/ZG330 NPU 多模型能力核验 · **只读审计，未修改任何工程/代码/位流/模型/交付包。**

**证据来源图例（全文统一）**：
- `官方头文件`＝iCraft 3.39.0 运行时头文件（`/f/嵌赛/tmp_icraft_deb_audit/data/usr/include/`，从 deb 解包，只读）
- `官方文档`＝iCraft 3.39.0 安装文档（`C:/Icraft/CLI v3.39.0/docs/`，HTML）
- `板端源码`＝当前生产链板端 NPU 封装（`sdr_full_chain_spectrum_monitor_m22_m24/work/pkg/board_package/npu_classifier.hpp`）
- `实测`＝板端日志/用户转录实测值（已发生、可溯源）
- `无证据`＝审计范围内无该证据，不猜测（标 UNKNOWN / UNVERIFIED）

---

## 0. 结论摘要（TL;DR）

**关键勘误（对 M27 审计结论的更正）**：

M27 审计（`sdr_npu_multimodel_m27/docs/M27_NPU_RUNTIME_CAPABILITY_AUDIT.md`）曾下结论 `MULTI_MODEL_RESIDENCY_UNSUPPORTED`，依据是"现有代码只有单一 Device/Session/Network + 官方头文件未见多上下文/多模型常驻 API"。**本次 M27.1 更深层的 SDK 审计否定了后一条依据**：iCraft 3.39 运行时**确实存在**多实例 API 与官方多网络部署机制（见 §5/§6）。因此：

```
CURRENT_PROJECT_VERIFIED_MODE=SINGLE_MODEL_RESIDENT
MULTI_MODEL_RESIDENCY=UNVERIFIED
CONCURRENT_MULTI_MODEL_EXECUTION=UNVERIFIED
MODEL_SWITCHING_LATENCY=UNVERIFIED
```

**上述四个状态标记必须逐字保留**，直到完成真实板端探针（见 `M27_1_PROBE_PLAN.md`）后，才允许把结论推进为 §六 的 A/B/C/D 之一。**禁止**把"当前代码只有一个 Session"当成"硬件只支持一个模型"。

| # | 能力问项 | SDK 层结论 | 板端结论 |
|---|---|---|---|
| 1 | 多 Device 并存 | **支持**（API 无单例） | 单个已实测；多 Device 未实测 |
| 2 | 多 Network 并存 | **支持**（对象级，无全局单例） | UNVERIFIED |
| 3 | 多 Session 并存 | **支持**（`Session::sub`/`CreateWithBackends`/`CreateWithSnapshot`） | UNVERIFIED |
| 4 | 多 ZG330Backend 并存 | **支持**（`zg330backend_sid` 计数 + 每 backend 独立段表） | UNVERIFIED |
| 5 | 多网络部署（官方机制） | **有**（`userReuseSegment` / `userConnectNetwork`） | UNVERIFIED |
| 6 | 模型卸载/切换 API | **无独立 unload/release**（切换＝`Backend::deinit` + 重建 Network/Session） | UNVERIFIED |
| 7 | 真正并发执行 API | **无**（无 Job / 无异步提交队列；仅 `Backend::fork` 多线程复制 + 异步 `forward`） | UNVERIFIED |

**一句话**：SDK 的**对象模型**允许多 Device/多 Network/多 Session/多 Backend 并存，且官方文档明确支持"多网络部署/多网络连接"；但**是否能在同一芯片上同时驻留两个模型、能否真正并发、切换延迟几何**，SDK 层只给到"有机制、无上限/下限证据"，必须靠板端探针实测（当前均 UNVERIFIED）。

---

## 1. 术语分层（任务书强制区分）

| 层 | 含义 | SDK 证据 | 状态 |
|---|---|---|---|
| **文件存储** file-storage | 磁盘上可同时存在多个编译模型（.json+.raw） | 现有 A/B 两模型已同时存在于盘上 | CONFIRMED |
| **部署** deployment | 把模型装载为 `Network` 对象 + 权重 `loadParams` | `Network::CreateFromJsonFile` + `lazyLoadParamsFromFile` | CONFIRMED（单模型） |
| **驻留** residency | 多个已 `apply()` 的 Session/Backend 同时在设备内存中存活 | 多实例 API + 每模型独立 weight/instr 段 | **UNVERIFIED** |
| **串行** serial | 多个驻留模型依次调用，无时间重叠 | `Session::forward` 同步/异步单次完成握手 | **UNVERIFIED** |
| **并行** parallel | 多个模型真正同时执行 | **无 Job/队列/异步提交 API** | **UNVERIFIED** |

> 判断归属时，任何结论都须落到上表某一行；"能同时建多个 Network 对象"只证明"部署/驻留"的 API 允许，**不证明**"并行执行"。

---

## 2. 多 Device：API 层支持（无单例）

**依据**（`icraft-xrt/core/device.h`，官方头文件）：

- `Device::Open(const std::string& url)` 是 **static 工厂**，每次调用创建一个新 Device 句柄，**非单例**。
- `DeviceRegistry::Register / ListNames / Get`（name→creator 注册表）：运行时按 url scheme 注册多个设备后端（`axi://zg330aiu`、host、buyi 等），**不存在"全局唯一 Device"约束**。
- `Device::Close(device)` 显式关闭句柄；`Device::deinit()`（device.h:305/528/779）释放设备资源。

**判断**：SDK 允许同一进程持有多个 `Device` 句柄。当前板端链只用**一个**（`npu_classifier.hpp:90` `Device::Open(kNpuDeviceUrl)`），故"多 Device 并存"是**未实测**（UNVERIFIED），但 API 层不禁止。

---

## 3. 多 Network：对象级并存（无全局单例）

**依据**（`icraft-xir/core/network.h`，官方头文件）：

- `Network::CreateFromJsonFile(file_path)`（network.h:611）、`CreateFromFlatFile`（629）返回独立 `Network` 对象。
- 每个 `NetworkNode` 持独立 `ops_id_` / `mapped_addr_` / `params_md5`（对象级，非全局）。
- 权重装载：`loadParamsFromFile`（650）、`lazyLoadParamsFromFile`（671）、`lazyLoadParamsFromDir`（681）、`autoLoadParams`（692）。

**判断**：可同时构造多个 `Network` 对象并各自 `lazyLoadParams`。这是"多模型部署"的 API 基础，**已确认 SDK 允许**；但两个已装载权重的 Network **同时 apply 到同一 ZG330 芯片**是否成功，属驻留问题（UNVERIFIED，见 §6）。

---

## 4. 多 Session：API 层支持

**依据**（`icraft-xrt/core/session.h`，官方头文件）：

- `Session::Create<BackendType...>(network, devices)`（session.h:83）— 模板，绑定一个 NetworkView 到一组 backend+device。
- `Session::CreateByOrder`（98）、`CreateWithBackends`（111）、`CreateWithSnapshot`（250）。
- `Session::sub(start, end)`（119/126）— 从同一 Session 派生**新 Session**（共享 backend，不同 network_view 子区间）。
- 每个 `SessionNode` 持有独立 `backends` / `network_view` / `forwards_` / `tmap_`（对象级）。

**判断**：一个 `Device` 上可创建多个 `Session`（各绑定不同 Network/Backend）；`sub()` 明确支持"一个 Session 拆出多个"。API 层**支持多 Session**。板端是否可同时 hold 两个已 `apply()` 的 Session 并正确 `forward`，UNVERIFIED。

---

## 5. 多 ZG330Backend + 官方多网络部署机制（本次审计的关键新证据）

### 5.1 多 Backend 实例计数

**依据**（`icraft-backends/zg330backend/zg330backend.h`，官方头文件）：

- `static int zg330backend_sid`（zg330backend.h:357）— 注释"计算当前程序下 zg330backend 的个数"，即**运行时为多个 ZG330Backend 实例编号**。
- `int zg330backend_id`（358）— 每个 backend 的编号。
- 每个 `ZG330BackendNode` 持独立 `logic_segment_map` / `phy_segment_map`（345-346）、`map_table` / `map_table_chunk`（353-354）、`alloc_mode`（362，默认 BYPASS）、`ocmopt`（363，默认 BEST_SCORE）。

**判断**：运行时有意识地**支持多个 ZG330Backend 实例**（否则无需全局计数 `sid`）。这是"多模型驻留"最直接的 API 证据。

### 5.2 官方多网络部署接口

**依据**（`zg330backend.h:399/407` + `docs/zg330backend/index.html` §2.3）：

- `userReuseSegment(MemChunk&, SegmentType)`（399）— 注释"用户配置网络权重/指令/中间层数据段的 memchunk，用于复用数据或内存空间，**减少多网络部署对 etm 的使用量**"。
- `userConnectNetwork(MemChunk&, int64_t v_id)`（407）— 注释"用户配置网络输入/输出数据段的 memchunk，用于**连接多网络在 etm 上的输入和输出**"。
- 官方文档 `zg330backend/index.html`：
  - §1.1 多网络输入输出连接："BuyiBackend 中多网络多输入/输出连接要求两个网络的输入/输出顺序一致，**在 ZG330Backend 中没有该约束**，可指定任意输入/输出进行内存复用。"
  - §2.3.1 userReuseSegment："**相同网络可以复用权重/指令/中间层数据段，不同网络只能复用中间层数据段。**"
  - §2.3.2 userConnectNetwork："复用多个网络在 PL DDR 上的数据结果，减少 PL 和 PS 之间拷贝的耗时。"

### 5.3 内存分段模型（驻留容量的判据）

**依据**（`zg330backend.h:25-31` SegmentType 枚举）：

```
WEIGHT   权重分段（etm 上 hardop 权重数据）
INSTR    指令分段（etm 上 hardop 指令数据）
FTMP     中间层分段（etm/ocm 上可优化的中间 Value）
INPUT    输入分段（etm）
OUTPUT   输出分段（etm）
```

`AllocMode`（37-40）：`MMU` / `BYPASS`（默认）/ `RECODE`。

**推论（驻留判据）**：两个**不同**模型若要同时驻留，各自需要独立的 WEIGHT + INSTR 段（只能复用 FTMP）。因此同时驻留的可行性 = **etm 可用容量 vs（模型 A 的 weight+instr+ftmp）+（模型 B 的 weight+instr+ftmp）**，是**容量依赖**而非 API 禁止。该容量在官方文档中**未给出上限** → 驻留可行性 UNVERIFIED，待板端探针实测（`probe_two_networks`）。

---

## 6. 模型卸载 / 切换：无独立 unload/release，切换＝重建

**依据**（全文检索 release/unload/destroy）：

- `Network` / `Session` **没有** `unload()` / `release()` / `destroy()` 方法。
- 唯一的资源释放路径：`Backend::deinit()`（backend.h:83/175；zg330backend.h:337）、`Device::deinit()`（device.h:305/528/779）、`Device::Close`、`MemChunk::free` / `Device::free`（device.h:162/183/319/478）。
- `SessionNode::backends_need_deinit`（session.h:41/261）— Session 析构时可级联 deinit 其 backend。

**判断**：
- **不存在**"卸载模型 A、保留设备、轻量装载模型 B"的独立 API。
- 模型切换等价于：销毁旧 Session（触发 `backends_need_deinit` 级联 `Backend::deinit`）+ 销毁旧 Network + 新建 Network（`CreateFromJsonFile` + `lazyLoadParamsFromFile`）+ 新建 Session + `apply()`。**切换延迟下限 ≈ 单模型加载+apply 全链**，无官方分段耗时，故 `MODEL_SWITCHING_LATENCY=UNVERIFIED`（待 `probe_unload_reload` 实测）。

**附带发现（内存交换）**：`NetworkNode::swap_mode`（network.h:286，"内存交换模式"）+ `llm_mode`（287，"大模型标记"）+ `dumpSwapParamsToDir(dest, move)`（559，"swap_mode 下是否移动参数缓存文件（移动会导致网络不可访问）"）。这是**面向大模型（llm）的参数换页机制**，**不是**面向 12/24 类小模型的多模型快速切换 API；其对 12/24 类模型的适用性 UNKNOWN。

---

## 7. 并发 / 异步执行：无 Job，无异步提交队列

**依据**（全文检索 Job/async/concurrent/线程）：

- **不存在** `Job` 类、异步提交队列、乱序完成、`finish/synchronize/barrier` 等并发执行 API（grep 仅命中 spdlog 异步日志，与推理无关）。
- 唯一的"异步"是 `Session::forward()` 对 ZG330 的**单次推理异步完成握手**：返回输出 `Tensor`，`waitForReady(timeout)` 等完成（详见 M27 审计 §3）。
- 唯一的多线程线索：`Backend::fork()`（backend.h:115/183，注释"复制一个 Backend 用于多线程"）— 复制 backend 以支持多线程，**非**"多模型并行执行"的声明。

**判断**：SDK 未提供真正并发执行（多模型同时计算）的 API。`CONCURRENT_MULTI_MODEL_EXECUTION=UNVERIFIED`，且**倾向不可达**——但受任务红线约束，在板端探针（`probe_concurrent_inference`，仅当 SDK 允许时）前不下确定结论。

**"context" 检索结果（任务书全文检索词之一）**：`icraft-xir/core/context.h` 中的 `Context` / `CloneContext` / `EqualContext` 是**图 reduce/clone 的等价性判定上下文**（用于网络克隆/覆盖的 override 函数），**不是**多模型运行时上下文/上下文切换 API。全 SDK 头文件**无**"多模型 runtime context / context switch" 接口。故"多模型上下文"能力 = UNKNOWN（无证据），不能据此推断支持或拒绝。

---

## 8. 当前板端实际使用模式（单模型常驻，已板证）

**依据**（`npu_classifier.hpp`，板端源码，只读引用）：

- `Device::Open(kNpuDeviceUrl)`（:90）— **一次**，URL `axi://zg330aiu?npu=0x40000000&dma=0x80000000`。
- `Network::CreateFromJsonFile(model_json)` + `lazyLoadParamsFromFile(model_raw)`（:73/:78）— **一个** Network，权重 lazy 装载。
- `Session::Create<ZG330Backend, HostBackend>(network_, {device_, HostDevice::Default()})` + `session_.apply()`（:97-100）— **一个** Session，apply **一次**。
- 每帧 `device_.reset(1)`（:168）后 `session_.forward`（:172），**不**每帧 open/close、**不**每帧 apply（M27/39e5 已板证的持久 Device + reset1 纪律）。

**确认**：当前生产链 = `SINGLE_MODEL_RESIDENT`（单 Device + 单 Network + 单 Session + 单 ZG330Backend）。**这是唯一已实测形态**，其余形态 UNVERIFIED。

---

## 9. 逐项判断表（每个判断附证据，无证据写 UNKNOWN/UNVERIFIED）

| 问项 | SDK 证据（文件:行） | 结论 |
|---|---|---|
| 能否同一芯片上放多模型 | `zg330backend_sid`(zg330backend.h:357) + `userReuseSegment`(399)/`userConnectNetwork`(407) + 官方 §2.3 | **机制存在**；板端 UNVERIFIED |
| 能否多模型同时驻留 | 不同网络只能复用 FTMP（官方 §2.3.1）；etm 上限无文档 | **UNVERIFIED（容量依赖）** |
| 能否单 Device 多 Network/Session | `Session::Create`(session.h:83)/`CreateWithBackends`(111)/`sub`(119) | API 允许；板端 UNVERIFIED |
| 能否多模型串行不重开 Device | 多 Session/Backend + 多 Network 并存（§2-§5） | API 允许；板端 UNVERIFIED |
| 能否真正并发执行 | 无 Job/异步队列；仅 `Backend::fork`(backend.h:115) | **UNVERIFIED** |
| 模型切换 API | 无 unload/release；`Backend::deinit`(backend.h:83)+重建 | 切换＝重建；延迟 UNVERIFIED |
| 模型切换延迟 | 无官方分段耗时 | **UNVERIFIED** |
| 卸载模型 | `Backend::deinit` / `Device::deinit` / `Device::Close` / `free` | 有释放路径；"轻量换模"无 |
| 内存上限（etm/ocm） | `SegmentType`(25-31)/`AllocMode`(37-40)；容量无文档 | **UNKNOWN** |
| 批处理 batch>1 | 现有模型编译为 batch=1；无 batch>1 证据 | **UNKNOWN** |

---

## 10. 与 M27 审计的差异（必须记录）

| | M27 审计 | M27.1 审计 |
|---|---|---|
| 多模型常驻 | `MULTI_MODEL_RESIDENCY_UNSUPPORTED` | **`MULTI_MODEL_RESIDENCY=UNVERIFIED`** |
| 依据 | 代码单 Session + 浅层头文件盘点未见多上下文 API | 深读 `zg330backend.h`/`session.h`/`network.h` + 官方 `zg330backend/index.html` 找到 `userReuseSegment`/`userConnectNetwork`/`zg330backend_sid` |
| 性质 | 把"无证据"写成"不支持" | 把"无实测"写成"未验证"，符合任务红线 |

**结论**：M27 的 `UNSUPPORTED` 判定过强（浅层审计 + 误把"代码单 Session"当作"硬件只支持单模型"）。M27.1 更正为：**SDK API 明确支持多实例与多网络部署，真实能力待板端探针**。

---

## 11. 状态

```
M27_1_SDK_MULTI_MODEL_AUDIT result=SDK_SUPPORTS_MULTI_INSTANCE_AND_MULTI_NETWORK_DEPLOYMENT_API
CURRENT_PROJECT_VERIFIED_MODE=SINGLE_MODEL_RESIDENT
MULTI_MODEL_RESIDENCY=UNVERIFIED
CONCURRENT_MULTI_MODEL_EXECUTION=UNVERIFIED
MODEL_SWITCHING_LATENCY=UNVERIFIED
```

板端探针设计、模型选择（A=12 类冻结 / B=8 类板证模型）、测量指标、安全边界与 A/B/C/D/E 结论分类，见：
- `M27_1_MODEL_SELECTION.md`
- `M27_1_PROBE_PLAN.md`
