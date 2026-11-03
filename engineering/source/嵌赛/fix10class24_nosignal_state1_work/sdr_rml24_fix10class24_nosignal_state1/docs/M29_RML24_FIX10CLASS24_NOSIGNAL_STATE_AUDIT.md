# M29 RML24 fix10class24-nosignal-state1 — 无信号状态机 + UI 状态映射修复审计

**状态**：`M29-RML24-FIX10CLASS24-NOSIGNAL-STATE-READY-FOR-BOARD-TEST`（最高允许；禁写 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / STANDALONE_PASS / 24CLASS_PASS / NEW_PRODUCTION_THRESHOLD）
**日期**：2026-10-18
**范围**：状态机 + UI 映射（与类别数无关的共享逻辑）。不碰 BF16 模型 / 标签序 / 24→23 合同 / canonical 资产 / 双 SDR 恢复器 / 0.10 门 / TX 上限 / 训练量化资产；不碰板、不开 SDR。

---

## 1. 背景：两个确定 bug

真实 RX 链路信号存在状态机（`sdr_adapter/signal_presence.hpp`）与 UI 状态映射（`board_package/ui_state_map.hpp`）各有一个确定缺陷：

| # | 位置 | 缺陷 | 后果 |
|---|------|------|------|
| B1 | `signal_presence.hpp::update()` no-hint 分支 | `case SignalLost / NoSignal / Invalid: break; // stay` 三者合并为「永久停留」 | SIGNAL_PRESENT 掉 5 帧进 SIGNAL_LOST 后，后续无信号帧**永远停在 SIGNAL_LOST**，无法回 NO_SIGNAL；INVALID 故障清除后遇到正常无信号帧**永远停在 INVALID** |
| B2 | `ui_state_map.hpp::map_to_state()` + 进程级优先级块 | 只特判 `presence_state == "NO_SIGNAL"`，SIGNAL_LOST / INVALID / ACQUIRING 全落 `else → Live`，且 `top1/conf/dist` 无条件填旧分类 | 无信号时**旧的类别/置信度/Top-N 仍显示为 LIVE** |

（INVALID + 有信号 → ACQUIRING 重新确认、SIGNAL_PRESENT → SIGNAL_LOST 这两条**已正确**，未改。）

---

## 2. 状态机修复（`sdr_adapter/signal_presence.hpp`）

`update()` 的 no-hint 分支由「三态合并 stay」拆成三个独立 case：

```cpp
case PresenceState::SignalLost:
    // 下一帧仍无信号即回 NO_SIGNAL（绝不永久停留 SIGNAL_LOST）；
    // 再次有信号仍从 ACQUIRING 重新确认（hint 分支不变）。
    lost_ = 0;
    state_ = PresenceState::NoSignal;
    break;
case PresenceState::NoSignal:
    break;  // stay
case PresenceState::Invalid:
    // 故障清除后的正常无信号帧恢复到 NO_SIGNAL；
    // 故障清除后的有信号帧仍从 ACQUIRING 重新确认（hint 分支不变）。
    lost_ = 0;
    state_ = PresenceState::NoSignal;
    break;
```

### 修复后状态机转换表

| 当前态 | 输入：正常无信号帧 | 输入：正常有信号帧 | 输入：clip/NaN/捕获错误 |
|--------|------------------|------------------|------------------------|
| NO_SIGNAL | stay NO_SIGNAL | → ACQUIRING（confirm=1） | → INVALID |
| ACQUIRING | → NO_SIGNAL（confirm 复位） | 累计到 N=3 → SIGNAL_PRESENT | → INVALID |
| SIGNAL_PRESENT | 累计到 M=5 → SIGNAL_LOST | stay | → INVALID |
| SIGNAL_LOST | **→ NO_SIGNAL（修复 B1）** | → ACQUIRING（重新确认） | → INVALID |
| INVALID | **→ NO_SIGNAL（修复 B1）** | → ACQUIRING（重新确认，已正确） | stay |

---

## 3. UI 映射修复

### 3.1 `ui_sw/ui_render.hpp` — `Status` 枚举新增两值

```cpp
SignalLost,   // RUNNING + SIGNAL_LOST，心跳新鲜（曾 present 后掉信号，瞬态）
Invalid,      // RUNNING + INVALID（RX 硬故障：clip/NaN/捕获错误），心跳新鲜
```

### 3.2 `board_package/ui_state_map.hpp` — 状态决策 + 分类隐藏

`map_to_state()` 决策链（优先级从高到低）：
`Mock → Error(overflow/dropped/discontinuity/short_frame) → NoSignal → SignalLost → Invalid → Acquiring → else Live`

并对**四个 presence 状态**清空旧分类字段（Mock/Error/Live 不变）：

```cpp
const bool hide = st.status == ui::Status::NoSignal ||
                  st.status == ui::Status::SignalLost ||
                  st.status == ui::Status::Invalid ||
                  st.status == ui::Status::Acquiring;
if (hide) { st.top1.clear(); st.conf = 0.0f; st.dist.clear(); }
else      { st.top1 = r.argmax_class; st.conf = r.confidence; st.dist = r.probabilities; }
```

`apply_state_event()`：presence 映射从只认 NO_SIGNAL 扩到四态（NO_SIGNAL→NoSignal、SIGNAL_LOST→SignalLost、INVALID→Invalid、ACQUIRING→Acquiring），四态同样清空 `top1/conf/dist`；SIGNAL_PRESENT 仍**不伪造 Live**、不覆盖既有分类。

### 3.3 `ui_sw/ui_render.cpp` — 标签/颜色/形状/hero 分支

| 项 | SignalLost | Invalid |
|----|-----------|---------|
| `status_label()` | `"SIGNAL LOST"` | `"RX ERROR"` |
| `status_color()` | `th.warning`（琥珀，瞬态） | `th.error`（红，硬故障） |
| `draw_status_badge()` | `outline_circle(8)` | `fill_triangle(9)`（与 Error 同形同色） |
| `status_badge_shape_cx()` | `r = (Error||Invalid)?9:8` → 8 | → 9 |

`render_main()` 在 NoSignal hero 分支之后、默认分类路径之前，新增三个独立 hero 分支，各自 `draw_text` hero 标题 + `draw_info_strip` + `draw_nav` + **立即 `return`**，绝不落入默认分类渲染（不画置信度条、不画 TOP CLASSES、不画 "no probability data"）：

- `Status::Acquiring` → "ACQUIRING" / "Locking onto signal"（琥珀）
- `Status::SignalLost` → "SIGNAL LOST" / "Signal dropped - reacquiring"（琥珀）
- `Status::Invalid` → "RX ERROR" / "RX capture fault"（红）

### 3.4 `board_package/board_ui_live_rml23.cpp` — 进程级优先级块 + 日志名

- `status_log_name()`：加 `SignalLost → "SIGNAL_LOST"` / `Invalid → "INVALID"`。
- 优先级块在 ACQUIRING 之后、SIGNAL_PRESENT 之前加：
  ```cpp
  else if (display.presence == "SIGNAL_LOST") { display.status = ui::Status::SignalLost; ... }
  else if (display.presence == "INVALID")     { display.status = ui::Status::Invalid; ... }
  ```
  （STALE 超时/断开仍最高优先。）

---

## 4. 测试

### 4.1 扩展 `host_tests/test_signal_presence.cpp`（+3 测试，共 49 断言 / 0 失败）
- `test_signal_lost_resolves_to_no_signal`：present → 5 连损 → SIGNAL_LOST → 再 1 帧无信号 → NO_SIGNAL（不永久停留）。
- `test_invalid_resolves_to_no_signal`：nan_inf 触发 INVALID → 故障清除 + 无信号帧 → NO_SIGNAL。
- `test_full_cycle`：NO_SIGNAL →(信号×3)→ SIGNAL_PRESENT →(无信号×5)→ SIGNAL_LOST →(无信号×1)→ NO_SIGNAL。

### 4.2 新增 `host_tests/test_ui_nosignal_state.cpp`（54 断言 / 0 失败）
- `map_to_state` 四态映射（NO_SIGNAL/SIGNAL_LOST/INVALID/ACQUIRING + SIGNAL_PRESENT→Live）。
- 隐藏旧分类：四态 `top1 空 && conf==0 && dist 空`；SIGNAL_PRESENT 保留分类；Mock/Error 分类不变（回归）。
- `apply_state_event` 四态映射 + 隐藏旧分类；SIGNAL_PRESENT 不伪造 Live（回归）。
- `status_label`：`"SIGNAL LOST"` / `"RX ERROR"` / `"ACQUIRING"` / `"NO SIGNAL"`。
- `status_badge_shape_cx`：Invalid r=9（与 Error 同）、SignalLost r=8。
- **合成 24 维**：构造 24 维 `probabilities` 的 `ResultFrame`，证明映射与分类隐藏**与类别数无关**（SIGNAL_PRESENT 保 24 维 dist、NO_SIGNAL 清空 dist）。
- **hero 分支像素/文本渲染**：三态各 `render_main`，断言不进入默认分类路径（内容区 `accent_bar_bg` 计数为 0，即不画置信度条/Top-N）；Acquiring/SignalLost 画琥珀（无红）、Invalid 画红；对照 SIGNAL_PRESENT 帧画置信度条。

### 4.3 已覆盖、无需新增（既有测试证明）
- 「仅 SIGNAL_PRESENT 跑 NPU」→ `test_live_rx_gating.cpp::test_classify_now_gate`。
- 「10s NO_SIGNAL 不 STALE」/「>stale_ms→STALE」→ `test_heartbeat_socket.cpp`。

### 4.4 注册
- `build_host_tests.sh`：加 `test_ui_nosignal_state.cpp` 构建行（链接 font_atlas + ui_render）。
- `run_tests.sh`：加 `./bin/test_ui_nosignal_state || rc=1`。

---

## 5. 红线核验（已通过）

`diff -rq baseline nosignal --exclude=bin --exclude=board_capture --exclude=board_capture_extracted` 结果：**仅 9 处差异，全部为本任务列明的改动**：

| 差异 | 类型 |
|------|------|
| `sdr_adapter/signal_presence.hpp` | 修改（本任务） |
| `board_package/ui_state_map.hpp` | 修改（本任务） |
| `board_package/board_ui_live_rml23.cpp` | 修改（本任务） |
| `ui_sw/ui_render.hpp` | 修改（本任务） |
| `ui_sw/ui_render.cpp` | 修改（本任务） |
| `host_tests/test_signal_presence.cpp` | 修改（本任务） |
| `host_tests/build_host_tests.sh` | 修改（本任务） |
| `host_tests/run_tests.sh` | 修改（本任务） |
| `host_tests/test_ui_nosignal_state.cpp` | 新增（本任务） |

**未改动**（逐字节一致）：模型 json `28272abc…` / raw `c1781aec…`、24 类标签序、24→23 合同、canonical 三组件、`board_package/iq_rf_sync_recovery.hpp`（双 SDR 恢复器）、`iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（双 SDR runner）、0.10 残差门、`clean24_smoke`、TX −40 dB 上限。

---

## 6. 全量回归（通过）

```
BUILD_RC=0
RUN_RC=0
run_tests.sh: ALL HOST TESTS PASSED
```

`bash host_tests/build_host_tests.sh && bash host_tests/run_tests.sh` 全量通过。新增 `test_ui_nosignal_state`（54/0）+ `test_signal_presence`（49/0，含 3 个新测试）与全套回归无一失败：全部 C++ 测试 + Python 测试 + `test_board_build.sh: 24 passed` + `test_cli_override.sh: PASSED` + `test_rml23_build.sh: 7 passed`。真实板捕获数据（`board_capture` / `board_capture_extracted`）已就位，`test_fix10class24_replay_canonical`（canonical BPSK dump 逐字段复现）与 `test_fix10class24_failed_rx_force_classify`（残差分解）均**实际运行并通过**（非 SKIP）。

---

## 7. 如实报告：无 raw24 live-rx UI 入口

- 不存在 `map_to_state_rml24` 或 24 类 UI phase（那是 standalone 任务 B 的范围）。
- 状态机 + UI 映射是**类别数无关的共享逻辑**，本任务用**合成 24 维 `ResultFrame`** 直接验证（`test_ui_nosignal_state.cpp` 构造 24 维 `probabilities`，证明映射与分类隐藏与类别数无关）。
- 真实 raw24 live-rx UI 的运行时集成待 standalone-rx-prep1（任务 B）之后进行。

---

## 8. 板端测试步骤（用户执行，本任务不碰板）

1. 上板部署本工作树，启动 `board_ui_live_rml23`。
2. 无输入信号：确认 UI 显示 "NO SIGNAL"（无旧类别/置信度/Top-N）。
3. 注入强信号再撤掉：确认 "ACQUIRING" → 类别显示 → 撤信号 5 帧后 "SIGNAL LOST" → 再 1 帧后回到 "NO SIGNAL"（不永久停留 SIGNAL LOST）。
4. 制造 RX 故障（clip/NaN）：确认 "RX ERROR"，故障清除后回到 "ACQUIRING"（有信号）或 "NO SIGNAL"（无信号）。
5. 观察 10s 无信号：确认不误判 STALE；仅心跳超时/断开才 STALE。
6. 确认无信号期间 NPU 不推理（无分类刷新）。

---

## 9. 补记

全量回归结果见 §6：`BUILD_RC=0`、`RUN_RC=0`、`ALL HOST TESTS PASSED`。
