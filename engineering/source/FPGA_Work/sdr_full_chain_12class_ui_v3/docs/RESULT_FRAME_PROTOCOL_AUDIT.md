# ResultFrame 协议审计与 v3 扩展契约（任务 39e5 UI v3 · M4）

> 状态：**生产者接线完成（READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST 的软件里程碑）**。
> 生产者：`sdr_adapter/ui_report.hpp`（`result_frame_v2_line` / 新增 `result_frame_v3_line`）。
> 消费者：`board_package/result_frame_v2_parse.hpp`（`parse_result_frame_v2` / 新增 `parse_result_frame_v3`）。
> 数据载体：`sdr_adapter/result_frame.hpp`（`rf::ResultFrame`，新增 v3 扩展字段）。
> 主机测试 `host_tests/test_result_frame_v3.cpp`（35 断言，ASan/UBSan 零失败）。

## 1. 目的

ResultFrame 是 SDR→NPU→UI 链路的**逐帧结果协议**，从板端分类器经 AF_UNIX 行流传给
UI 服务端。M4 做两件事：

1. **v2 审计**：确认既有 schema `12class-chain-v1` 的字段与严格校验契约（§二.5）完整、无歧义。
2. **v3 扩展**：新增 schema `12class-chain-v2`，在 v2 之上携带 M1/M2/M3 的运行时状态与 DSP
   测量值，供 PARAMETERS 页(M5)、模式控制(M6)与诊断展示消费，**不改变 v2 字段语义**。

## 2. v2 现状审计（schema `12class-chain-v1`，冻结兼容）

| 字段 | 类型 | 校验（严格 fail-closed） |
|------|------|--------------------------|
| `type` | string | 必须 `"result"` |
| `version` | string | 必须 `"12class-chain-v1"` 或 `"12class-chain-v2"` |
| `frame_id` / `timestamp_us` | uint64 | 有限 |
| `argmax_idx` | int | ∈[0,11] |
| `argmax_class` | string | == `cat::label(target_12(), argmax_idx)`（冻结序） |
| `confidence` | float | ∈[0,1] 且 == `probabilities[argmax_idx]`（tol 1e-4） |
| `class_count` | int | == 12 |
| `probabilities` | array[12] | 逐项 ∈[0,1] 有限，`|sum-1|≤1e-3` |
| `snr_db` | float\|null | null 允许，否则有限 |
| `quality` | float | ∈[0,1] |
| `model_sha` | string | 非空 |
| `mock` / `overflow` / `dropped` / `discontinuity` / `short_frame` | bool | — |
| `source` / `e2e_us` / `preprocess_us` / `classify_us` | string/float | 数值须有限 |

- 全量 logits **不序列化**（argmax + confidence 足够 HDMI 显示；logits 仅在
  `rf::ResultFrame::logits` 供程序化使用）。
- 手写递归下降 JSON 解析器（`ui::detail::JsonReader`），无外部 JSON 依赖，支持
  `\" \\ \n \r \t \uXXXX` 转义；拒绝截断/垃圾/尾随内容/未知版本。

## 3. v3 扩展（schema `12class-chain-v2`）

v3 = v2 全部字段 **+** 下面 4 个顶层字段 **+** 嵌套 `measurements` 对象。v2 字段语义不变；
v1 记录仍被接受（向后兼容），其 v3 扩展字段留默认值。

### 3.1 顶层扩展字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `presence_state` | string | M1 `signal_presence` | 五态之一：`NO_SIGNAL`/`ACQUIRING`/`SIGNAL_PRESENT`/`SIGNAL_LOST`/`INVALID` |
| `level_mode` | string | M2 `auto_level_control` | `FIXED` / `AUTO` |
| `model_scale` | float | M2 | 数字标量（恒等默认 1.0） |
| `rf_gain_db` | float | M2 | RF 增益（dB） |
| `measurements` | object\|null | M3 `dsp_measure` | 见 §3.2；`has_measurements==false` 时为 `null` |

### 3.2 `measurements` 对象（12 个标量，全部数值）

| 键 | 类型 | 键 | 类型 |
|----|------|----|------|
| `rms_counts` | float | `psd_peak_prominence_db` | float |
| `peak_counts` | float | `snr_est_db` | float |
| `papr_db` | float | `occupied_bins` | int |
| `clip_ratio` | float | `spectral_centroid_hz` | float |
| `power_dbfs` | float | `occupied_bw_hz` | float |
| `noise_floor_dbfs` | float | `model_rms` | float |

- `nan_inf` / `valid`（M3 安全标志）**不序列化**，解析侧置默认（false/true）；它们是进程内
  安全旗标，不属于协议载荷。
- 解析时每个数值须有限；`occupied_bins` 须为整数；未知键跳过（前向兼容）。

## 4. 严格校验（v3 新增规则）

- schema `12class-chain-v2` 的 4 个顶层扩展字段 + `measurements` 键**均为必需**；缺失即拒绝
  （错误含 `"extension"`），防止「改了版本号却忘了填扩展」的半吊子记录冒充 v3。
- `model_scale` / `rf_gain_db` 须有限；`measurements` 为 `null` 时 `has_measurements==false`。

## 5. 主机测试（`test_result_frame_v3.cpp`，5 组 / 35 断言）

1. **v3 全量往返**：生产者 `result_frame_v3_line` → 消费者 `parse_result_frame_v3`，校验全部
   扩展字段与 12 个测量标量逐项往返一致（按 `%.3f`/`%.6f` 容差）。
2. **null 测量**：`has_measurements==false` → 序列化 `measurements:null` → 解析回 false。
3. **v1 向后兼容**：v1 记录经 `parse_result_frame_v2` 与 `parse_result_frame_v3` 均接受；
   v1 记录不残留伪造 v3 扩展（presence_state 空、has_measurements false）。
4. **v2 必需扩展**：v1 行改版本号为 v2（缺扩展）→ 拒绝，且错误点明 `extension`。
5. **坏测量**：`occupied_bins` 改成非整数 `5.5` → 拒绝。

ASan/UBSan 对 `test_result_frame_v3` 与 `test_result_frame_parse`（改动后的解析器）均零失败。

## 6. 与其它里程碑的关系

| 消费方 | 用到 |
|--------|------|
| UI 服务端(M5) | `parse_result_frame_v3` 接受 v2/v3，渲染时可用 `measurements` 填 PARAMETERS 页 |
| 模式控制(M6) | `presence_state` / `level_mode` / `model_scale` / `rf_gain_db` 供状态机决策 |
| 诊断 | `measurements` + `presence_state` 逐帧落盘可追溯 |

## 7. 红线

- v2 字段语义**冻结**，v3 只增不改；`result_frame_v2_line`（v1）原样保留，向后兼容。
- 全量 logits 仍不序列化。
- 数值 NaN/Inf/非整数在协议边界一律 fail-closed，绝不产出虚假测量。
- 未经实机验证只标 `READY-FOR-UI-V3-PRODUCER-INTEGRATION-HARDWARE-TEST`。
