# M22.1 UI 布局勘误说明（Task B）

状态：`M22_UI_LAYOUT_ERRATA_READY_FOR_BOARD_TEST`（离线布局框架 + 测试完成，**待真屏复测**）

## 一、背景与状态拆分

M22 板端实测发现 7 寸屏上存在文字相互重叠、文字越出卡片/边框、行距边距不齐、信息层级不清、整体美观不足。因模型、Gate 9 核心与位流均未改动，本次仅做 UI 渲染层勘误，并据此把状态拆分为：

```
TOUCH_CONTROL=PASS          （M18_SW1_TOUCH_ACCEPTANCE result=PASS，保持不变）
UI_VISUAL_ACCEPTANCE=FAIL   （本勘误前）
UI_LAYOUT_ERRATA=REQUIRED   （本勘误前）
```

本勘误交付后：`UI_LAYOUT_ERRATA` 转为 `M22_UI_LAYOUT_ERRATA_READY_FOR_BOARD_TEST`，但**不写** `UI_VISUAL_PASS / UI_HARDWARE_PASS / PROJECT_COMPLETE`（见 §七红线）。

## 二、根因（经真实字体度量复现的 3 处缺陷 + 1 处结构缺陷）

用渲染器自身的字体度量（DejaVu Sans 预烘焙图集）测量，定位到 13 项边界回归失败背后的 3 处真实重叠/越界，外加一个结构性缺陷：

| # | 缺陷 | 实测 | 后果 |
|---|---|---|---|
| 1 | 顶栏 `MODE` 标签与模式值重叠 | `"MODE"`（Regular 20）= 65px，@312 结束于 377；模式值 @`kTopBarModeValueX=372` | 5px 重叠 |
| 2 | 顶栏 ctl 值与超长 model SHA 重叠 | `"DISCONNECTED"`（Bold 20）= 190px，@820 结束于 1010；16 字符 SHA（Mono 20）= 208px，右对齐 @1130 起点 922 | 88px 重叠 |
| 3 | 信息条 SOURCE 值越出右边界 | `"EXTERNAL ANTENNA"`（Bold 28）= 341px，@966 结束于 1307 > 右边界 1255 | 越框 52px |
| S | 结构性：渲染器依赖固定/未经验证的字体宽度，无裁剪保护 | 大量 `draw_text()` 无 clip、坐标硬编码 | 任何未预估的字符串长度都会溢出 |

## 三、修复方案

### 1. 顶栏（`ui_layout.hpp` + `ui_render.cpp`）
- `kTopBarModeValueX` 372 → **392**（网格对齐，`MODE` 标签结束于 377，留 15px 间隙；`BAND SCAN` @392 结束于 533 < divider2 556）。
- model SHA 按契约缩短为**前 8 个十六进制字符**（short-SHA，与历史 `test_ui_layout_m19` 的 `"12345678"` 一致），超长输入被截断、不再触及 ctl 值。

### 2. 信息条（`draw_info_strip`）
- 每个字段独立裁剪到自身 segment（末字段再收于条带右边界 1255）。
- 长文本走 `fit_text()`：超宽时截断并追加 `"..."`（§四.2 的"缩短/省略"策略）。

### 3. 通用层（`font_atlas.hpp/.cpp`、`ui_layout.hpp`、`ui_render.hpp/.cpp`）
- `text_box()` / `text_width()`：文本边界一律取自字体真实度量（ascent/descent/advance），不再依赖猜测宽度。
- `draw_text_clipped()`：所有文字经显式 clip 光栅化，作为越界兜底，绝不画到卡片/按钮/屏幕外。
- **region 容器标签 + `region_rect()`**：每个文本 run 打上容器 id，容器矩形由 `region_rect()` 单一来源导出（渲染器与宿主测试共用同一几何），使"文字在容器内 / 容器内两文本不交叠 / 数值列单位列对齐 / 视觉按钮==触摸矩形"全部可自动化断言。
- **`LayoutMetrics` + `layout_metrics(w,h)`**：单一运行时布局源；`w<640` 或 `h<720` 时 `fit=false`，fail-closed 只画居中 `SCREEN TOO SMALL`，不溢出。
- 数值/单位列：单位列宽取卡片内最宽单位实测值，数值列右对齐到固定锚点、单位列左对齐，二者间隔 12px，绝不交叠。
- MODE 页：名称/描述/状态标签分别用实测最宽 `SELECTED/PENDING/IDLE` 预留列宽，互不侵占；START/STOP 视觉清晰（启用/禁用颜色+描边区分），**按钮矩形与触摸命中区域共用 `mode_ui::button_rect`，语义不变**。

## 四、修改文件

| 文件 | 类型 | 要点 |
|---|---|---|
| `ui_sw/font_atlas.hpp` | 修改 | `text_box()` / `draw_text_clipped()` / 文本 trace / `TextKind` |
| `ui_sw/font_atlas.cpp` | 修改 | trace 实现 + 裁剪光栅化 |
| `ui_sw/ui_layout.hpp` | 修改 | `LayoutMetrics` + 最小尺寸门禁 + `kTopBarModeValueX` 修正 |
| `ui_sw/ui_render.hpp` | 修改 | `region::*` 枚举 + `region_rect()` |
| `ui_sw/ui_render.cpp` | 修改 | 顶栏/信息条/参数卡/导航/MODE 页布局重构 |
| `host_tests/test_ui_layout_boundaries.cpp` | 新增 | §五 12 项布局边界回归 |
| `host_tests/make_ui_m22_1_snapshots.cpp` | 新增 | 模拟预览快照（after + worst-case） |
| `host_tests/build_host_tests.sh` | 修改 | 增编两个新目标 |

完整逐行 diff 见 `docs/M22_UI_ERRATA1_DIFF.md`。

## 五、测试结果（WSL g++ 15.2.0，`-O2 -Wall -Wextra -Werror`）

| 测试 | 结果 |
|---|---|
| `test_ui_layout_boundaries`（新增，§五 12 项） | **2242 pass / 0 fail** |
| `test_ui_layout_m19`（结构常量，保持） | 78 / 78 |
| `test_ui_live`（保持） | 96 / 0 |
| `test_ui_v3_pages`（保持） | 30 / 0 |
| `build_host_tests.sh`（全量编译） | OK |

边界测试覆盖 §五全部 12 项：文本 bbox 位于父容器内；同卡两文本不交叠；数值/单位列不重叠且各自列对齐；顶栏字段不相互覆盖；底栏三区不相交；MODE 三按钮 + START/STOP 不相交；最长类名（`AM-SSB-WC`）/最长状态文本/异常文本（`EXTERNAL ANTENNA`、16 字符 SHA、`SIGNAL_PRESENT`）；ERROR/STALE/MOCK/LIVE 四态；SELECTED/PENDING/IDLE 三态；目标分辨率 + 640×480 / 800×600 fail-closed；视觉按钮矩形 == 触摸矩形；冻结导航带 == `ui_touch::kNavY0/Y1`。

## 六、模拟预览（非真屏验收）

- 修改前（M19 基线渲染）：`artifacts/ui_m19_before/`
- 修改后（7 个固定输入，与 M19 基线同输入）：`artifacts/ui_m22_1_after/`
- 最坏情况（最长类名 / 最宽测量 / 超长 SHA+SOURCE / 三态按钮 / diag / touch / 640×480 兜底）：`artifacts/ui_m22_1_worst/`

三页（CLASSIFY=`main_live`、PARAMETERS=`parameters`、MODE=`mode_stopped`）修改前后对照即上述两个目录同名校验。**这些是模拟预览，不能代替真屏验收。** 可由 `host_tests/bin/make_ui_m22_1_snapshots` 重新生成。

## 七、红线

真屏复测前**不写** `UI_VISUAL_PASS`、`UI_HARDWARE_PASS`、`PROJECT_COMPLETE`。分辨率门禁需先读取 `fbset -s` / `/sys/class/graphics/fb0/virtual_size` / `bits_per_pixel`，见 `docs/M22_BOARD_RETEST.md`。
