# UI_RML24_TARGETS_INTEGRATION — C 线多目标列表页接入说明

状态：**host 编译 + 关键解析单测 PASS，待板端 aarch64 编译 + 实屏验证**（未烧 Flash、未加载位流、未碰板、未发射）。

## 1. 目标

把 `type:"rml24_targets"` 事件接入板端 UI 事件分发，使其不再落入 `rejected`/`state_rejected` 分支；BAND SCAN 模式下 CLASSIFY 页渲染多目标列表，选中目标的 Top3/params/constellation 只来自该目标身份 + 该目标的数据时间，切换/过期/未分类时清除旧 IQ/params。FIXED 页面与 result/state 行为逐字节不变。

## 2. 改动文件清单

| 文件 | 改动 |
|---|---|
| `overlay/board_package/target_list_dispatch.hpp` | **新增**。header-only 事件路由：`ui::is_rml24_targets_line()` + `ui::dispatch_targets_line() -> {Valid, Rejected, NotATargetsLine}`。iCraft-free，host 可测。 |
| `overlay/board_package/board_ui_live_rml24_final.cpp` | 接入分发 + 状态 + 触摸 + 渲染门控（见 §3）。 |
| `overlay/ui_sw/ui_render.hpp` | 新增 `namespace target_list_ui` 几何常量 + `render_target_list()` 声明。 |
| `overlay/ui_sw/ui_render.cpp` | 新增 `ui::render_target_list()` 定义（列表 + 选中详情）。 |
| `tests/test_target_list_ui.cpp` | **新增**。host 单测（84 项断言）。 |
| `docs/UI_RML24_TARGETS_INTEGRATION.md` | 本文档。 |

未改动（红线）：`target_list_rml24_parse.hpp`、`target_list_state.hpp`、所有 Python 文件、result/state 解析语义、五页 UI 结构（FIXED）、`SHA256SUMS_UI2.txt`、模型身份。

## 3. 板端主程序改动位置（board_ui_live_rml24_final.cpp）

- L44-45：`#include "target_list_dispatch.hpp"` / `#include "target_list_state.hpp"`。
- L550-553：新增 `ui::TargetListState target_list_state;`（`set_page_size(kRowsPerPage)`）、计数器 `targets_received` / `targets_rejected`。
- L560：reconnect 时 `target_list_state.clear_selection();`（新生产者重启 target id 空间）。
- L636-660：drain 循环新增分发分支，位于 result 分支 `continue` 之后、`parse_state_frame` 之前：
  - `Valid` → `target_list_state.apply(tdo.event)`，`++targets_received`，刷新 `last_valid_message_rx`/`have_valid_message`，打印 `UI_RX type=rml24_targets valid=1`，`continue`（**不落入 rejected**）。
  - `Rejected` → `++rejected; ++targets_rejected`，打印 `valid=0 reason=...`，`continue`（计入 rejected，**不计入 state_rejected**）。
  - `NotATargetsLine` → 无操作，原样落入 state 分支。
- L915-948：触摸释放处理（CLASSIFY 页 + BAND_SCAN 模式，`ControlTapDetector::Edge::Up` + `active_page()==0` + `s.point.valid`）：
  - `ui::target_list_ui::hit_row` 命中 → `target_list_state.select(rows[row]->target_id)`，打印 `UI_TARGET_SELECT`。
  - `ui::target_list_ui::hit_page` 命中 → `set_page_offset(±1)`（带边界钳制）。
- L1040-1052：渲染前门控。`band_scan = (display.work_mode == "BAND SCAN")`；当 `!selected_has_valid_data()` 或 result 帧的 `spectrum_center_hz`（llround 后）≠ 选中目标 `center_hz` 时，清 `display.iq_display_valid=false; display.meas.valid=false;`（渲染端不画旧星座/params）。FIXED 模式跳过该门控。
- L1077-1080：渲染 switch 的 `default:`（page 0）分支：`band_scan ? render_target_list(...) : render_main(...)`。页 1-4 不变。
- L1127-1129：退出时打印 `UI_TARGETS_STATS received=... rejected=...`。

## 4. 列表页渲染（ui_render.cpp）

`render_target_list()` 复用现有 `fill_rect/outline_rect/draw_top_bar/draw_info_strip/draw_nav/draw_text`。布局几何集中在 `ui_render.hpp` 的 `target_list_ui` 命名空间（`kRowsPerPage=6`、行矩形 `row_rect`、`hit_row`/`hit_page`），渲染器与触摸 hit-test 共享同一份几何，手指命中行 = 渲染行。

- 左列：`MULTI-TARGET SCAN` 顶栏 + `SCAN TARGETS` 汇总（`targets=N page X/Y`）+ 按中心频率升序的行列表（id / MHz / status / top1 / conf%）。
- 底部：prev/next 翻页按钮。
- 右列：选中目标详情（Top3 + confidence + last_seen + center/bw/power/backend）；无选中或 `!selected_has_valid_data()` 时显示 "no selection" 回退。

## 5. 收口标准对照

1. **分发不落入 rejected**：`dispatch_targets_line` 以顶层 `"type"` 键嗅探（与键序无关、计深度、防嵌套误判）。合法 targets 行 → `Valid` 分支；畸形 targets 行 → `Rejected`（计入 rejected + targets_rejected，不进 state_rejected）；其它行 → `NotATargetsLine` 原样落入 state 分支。
2. **列表页**：`TargetListState::summary_line()`（targets=N）、`visible_page()`（按 center_hz 排序 + 分页）、`select(target_id)`。
3. **选中一致性**：渲染门控用 `selected_has_valid_data()` + `spectrum_center_hz == selected->center_hz`；`apply()` 在选中目标消失/未分类/过期时清 selection（`params_valid_=false`）。
4. **BAND_SCAN 门控**：渲染 switch 与触摸 handler 都以 `work_mode == "BAND SCAN"` 为条件；FIXED 走原 `render_main` + 原控件路径。
5. **逐字节不变**：result/state 解析语义、五页结构、FIXED 页面、页 1-4 渲染均未改。

## 6. 验证（host，未 aarch64）

编译（WSL g++ 15.2.0，iCraft-free，仅测两个冻结 header + 新 dispatch header + 测试文件）：

```
wsl.exe -e bash -c 'cd "/mnt/f/嵌赛/rml24_ac_integration_20261029" \
  && g++ -std=c++17 -Wall -Wextra -I overlay/board_package \
     tests/test_target_list_ui.cpp -o /tmp/test_target_list_ui \
  && /tmp/test_target_list_ui'
```

结果：**编译通过（-Wall -Wextra 无告警输出），运行输出 `ALL CHECKS PASSED (84 checks)`，退出码 0。**

覆盖：`parse_rml24_targets` 合法（含空 targets 数组、未分类、power_valid null）与非法（缺字段/confidence 越界/未分类带非零 confidence/未知 status/未知 backend/top3>3/尾随内容）路径；`TargetListState` 排序/分页钳制/选择/clear/vanish/unclassify/expire/unclassified_label UTF-8；`dispatch_targets_line` Valid/Rejected/NotATargetsLine 路由 + 键序无关 + 嵌套 type 不误判。

**未验证（待板端）**：整机 `board_ui_live_rml24_final.cpp` 的 aarch64 编译（依赖 iCraft/libiio/framebuffer 板库，host 无这些头文件）、实屏渲染、真触摸命中、真实 `rml24_targets` 数据流。**不宣称板端 PASS，不写 RF_PASS / PROJECT_COMPLETE。**
