# 集成补丁（待主线程合入，本线不就地改 A/B 树）

本目录是 C 线「多目标真实入口集成 + 收口实施」的交付物。C1→C5 已实际修完：
多候选检测/跟踪/去重/老化（tracker）与公平调度（MultiSignalScanLoop）已接入
**可注入真实入口** `receiver_entry.ReceiverEntry`，离线测试直接驱动该入口（不是
复刻逻辑），板端只需在构造函数里接真 radio/NPU/controller/transport。全部离线，
由主线程审阅后合入；本线不修改 A/B 树就地。

## 文件

| 文件 | 说明 |
|------|------|
| `receiver_entry.py` | **可注入真实入口**（C3 调度 + C5 可注入循环）。板端与离线测试执行的是同一份循环。部署为 `multisignal_receiver_entry.py` |
| `standalone_receiver.multisignal.py` | 合入后的**完整参考文件**：A 线 `standalone_receiver.py` 的手写循环整体替换为 `ReceiverEntry` 接线，供主线程对照 |
| `patch_standalone_receiver.diff` | 统一 diff（`a/standalone_receiver.py` → `b/standalone_receiver.py`），逐行可审 |
| `../cpp/target_list_rml24_parse.hpp` | 板端 C++ `rml24_targets` 事件**严格解析器**（手写递归下降 JSON，无外部依赖，host 可测） |
| `../cpp/target_list_state.hpp` | 板端 C++ 列表页状态模型（排序/分页/选择/切目标清旧 IQ/「未分类」） |
| `../cpp/test_target_list.cpp` | C++ host 测试（g++ 15.2.0 编译通过，**未 aarch64 编译**） |
| `../scripts/probe_flat_deploy.py` | C1 证据：干净临时目录 flat 部署 import + 入口启动探测 |
| `../scripts/build_flat_deploy.py` | flat 部署生成器（含 `receiver_entry` → `multisignal_receiver_entry`） |
| `../deploy/` | 生成的 flat 部署树（10 个模块 + `SHA256SUMS` + `manifest.json`） |

## C1→C5 收口状态（如实）

- **C1 部署依赖（已修）**：`src/tracker.py` 的 `from . import contracts` 在单文件
  部署 `multisignal_tracker.py` 下会 ImportError。`build_flat_deploy.py` 把相对导入
  改写为 `import multisignal_contracts`；`scripts/probe_flat_deploy.py` 在**干净临时
  目录**（仅 flat 模块，`python -I`）跑 `PROBE_OK flat_imports=clean entry_startup=ok`。
- **C2 真实 C++ 事件/列表/选择/反馈（已修）**：`target_list_rml24_parse.hpp` 严格
  fail-closed 解析 9 字段记录（power_valid null-or-finite、top3≤3、未分类须 conf=0、
  status/backend 枚举）；`target_list_state.hpp` 排序/分页/选择/清旧 IQ/「未分类」。
  `cpp/test_target_list.cpp` 经 WSL g++ 15.2.0 编译 + 运行 **ALL CHECKS PASSED**；
  **未 aarch64 编译**（无交叉工具链，如实标注）。
- **C3 逐目标分类调度（已修）**：`receiver_entry.ReceiverEntry` 直接驱动
  `MultiSignalScanLoop`（候选队列/分类预算/公平重访/全频段周期重扫/
  last_seen vs last_classified/过期清理/apply_range 换带清理迁移）。板端参考接线见
  `standalone_receiver.multisignal.py`。
- **C4 同一捕获多信号（已修 + 口径收紧）**：`tests/test_same_capture_multisignal.py`
  + `results/public_bw_verification.json` 审计证明**真实公共前导/尾是满带宽 QPSK
  （占用 ~1.00×fs，不是 ≤10kHz）**，因此相关原语单捕获只返回一个命中，不再承诺
  单 dwell 同时多信号；软件 PSD 多候选通路（`psd.pick_peaks`→`sweep_psd`）对**窄带
  替身** 0/1/2/3 峰、重叠不可分辨、强弱、带边均有测试；12.5kHz 仍为待板测目标，
  不沿用 10kHz 假设。`home_map` 回放保留并明确标注为「受控调度 fixture」。
- **C5 补丁后完整入口测试（已修）**：`tests/test_entry_integration.py`（12 项）直接
  驱动最终补丁后的 `ReceiverEntry`（注入 radio/infer/clock/transport），覆盖全链、
  UI 选择/清旧 IQ、同捕获 PSD 多候选、未分类、跨 LO 去重、无信号、短帧、断连恢复、
  推理异常恢复、换带清理、取消命令、弱目标公平、FIXED 原行为。NPU 离线 stub
  label-blind，不读真值。

## 诚实边界（合入前必读）

1. **逐 dwell 单检测**：`detect_public_training` 每 capture 只返回一个命中；多目标
   来自跨 LO dwell 的顺序扫描 + PSD 多候选。真实公共帧满带宽，单 dwell 内多个
   真实帧在频域几乎完全重叠，相关原语不承诺同 dwell 多信号。
2. **ReceiverEntry 与 A 线循环的 fidelity 差异**（主线程合入时对账）：
   `lock_policy` 迟滞/`locked-rescan-hold` 由调度器公平重访 + 周期全扫替代；
   逐 dwell `ACQUIRING` 状态与 RMS/peak/energy 特征测量未在 ReceiverEntry 复刻
   （其 state 事件只带 presence）；`--save-captures` 原始落盘与
   records/status/final.json schema 被简化为紧凑 records.jsonl。需字节兼容则主线程
   补回。
3. **power_valid 数值契约**：相关检测器无 PSD 功率 → `observe(power_db=None)` 记录
   `power_valid=NaN`（未测），**上线路序列化为 `null`**（NaN 不是标准 JSON，C++ 解析
   器拒绝 NaN）；PSD 后端才填数值（相对中位噪声底 dB，不是 dBm）。
4. **`rml24_targets` 是新事件 schema**：C++ 列表页在本线 `cpp/` 交付，板端合入后
   才消费。这不是把离线模块 PASS 写成整机完成。
5. **部署**：`multisignal_tracker.py`/`multisignal_scan_adapter.py`/
   `multisignal_receiver_entry.py` 必须与 `standalone_receiver.py` 同级（板端 runtime），
   保持 `src/contracts.py` 冻结常量一致。

## 离线验证（已过）

- `tests/test_entry_integration.py`（12 项）：最终补丁后入口端到端。
- `tests/test_same_capture_multisignal.py`（6 项）：真实帧满带宽审计 + PSD 多候选。
- `tests/test_real_entry_replay.py`（11 项）：真实入口模块离线回放（home_map 受控 fixture）。
- C++ `cpp/test_target_list.cpp`：WSL g++ 15.2.0 编译 + 运行 ALL CHECKS PASSED。
- C1 探测 `scripts/probe_flat_deploy.py`：干净临时目录 `PROBE_OK`。
- 全树 `pytest`：见最终报告逐项计数。
