# M19 界面视觉整理 — 前后对照（Before / After）

日期：2026-10-08
基准（Before）：`sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package`（M18-SW1.1）
目标（After）：本包 `ui_sw/ui_theme.hpp` + `ui_layout.hpp` + 重构后的 `ui_render.{hpp,cpp}`
参考：`docs/M19_UI_VISUAL_AUDIT.md`（现状审计，本重构的唯一依据）

> 截屏为**固定输入**的 RGB565 全帧快照（PPM P6），由 `host_tests/make_ui_m19_snapshots.cpp`
> 生成到 `artifacts/ui_m19/`。7 张覆盖三页四种信号状态 + 参数页 + 模式页 + 状态图例。

---

## 0. 一句话总结

把分散硬编码的「调色板 + 魔法坐标」收敛为**一套语义色 token + 一个 8px 网格布局头**，三页统一为
「顶部状态栏 + 主内容 + 底部导航」骨架，并在**不改变帧缓冲/换帧生产逻辑、不提高刷新率**的前提下，
补齐主分类页 Top-3、参数页四组卡片 + 单位分离、模式页逐按钮状态 + START/STOP 禁用态。

---

## 1. 色板：`Palette` → 语义 token（`ui_theme.hpp`）

| 语义 | Before (`Palette`) | After (`Theme`) | 变化 |
|---|---|---|---|
| 背景 | `bg` #0F141B | `background` #0F141B | 不变 |
| 卡片底 | `surface` #1A212B | `surface` #1A212B | 不变 |
| 芯片/未选底 | `surface_alt` #121A24 | `surface_alt` #121A24 | 不变 |
| 主文本 | `text` #E7ECF2 | `text_primary` #E7ECF2 | 改名 |
| 次文本 | `dim` #8B98A8 | `text_secondary` #8B98A8 | 改名 |
| 强调 | `primary` #4A90E2 | `interactive` #4A90E2 | 改名 + 补 `selected`（= interactive） |
| 绿 | `success` #3DDC84 | `success` #3DDC84 | 不变 |
| 琥珀 | `warning` #E8A93C | `warning` #E8A93C | 不变 |
| 红 | `error` #E5605F | `error` #E5605F | 不变 |
| 边框 | `outline` #2A3542 | `outline` #2A3542 | 不变 |
| 置信条底 | `accent_bar_bg` #141B25 | `accent_bar_bg` #141B25 | 不变 |
| — | （缺） | `disabled` #5A6672 | **新增**（禁用态，低对比豁免） |

- 颜色**数值全部不变**（仍是冻结的 M14 Style A 色板），只做语义化重命名 + 补 `selected`/`disabled`。
- 对比度：`text_primary`/`text_secondary`/`interactive`/`success`/`warning`/`error` 在
  `surface` 与 `background` 上均 **≥ 4.5:1**（`host_tests/test_ui_layout_m19.cpp` 逐项断言）；
  `disabled` 刻意低对比（豁免，绝不用于状态单独表达）。
- 状态表达保持「文字 + 形状 + 颜色」三者一体（`status_label` + `draw_status_badge` 未变语义）。

## 2. 字级：5 种大小 → 4 级（`ui_theme.hpp::font_tier`）

| 层 | Before | After | 说明 |
|---|---|---|---|
| 主类名 | **52px**（超 48 上限） | **40px** | 弃 52，落入规范 40–48 |
| 标题 | 28px | 28px | 不变 |
| 按钮/导航 | 24px (Bold) | 24px (Bold) | 不变 |
| 值/标签 | 20px | 20px（`kValue`=`kLabel`） | 不变；图集无 16/18px，20 满足「≥16」 |

- 恰 4 级 `{40,28,24,20}`，满足「≤4 字级」；**零图集再生、零运行时缩放**（审计 D1 路径 (a)）。

## 3. 布局：魔法数 → `ui_layout.hpp`（8px 网格 + 冻结带）

- 新增 `ui::layout`：`kXs=4/kSm=8/kMd=16/kLg=24/kXl=32`、边距 24、屏幕 1280×720。
- **顶部状态栏**（新增，`kTopBarY0..71` + 分隔线 y=72）：`系统名 | MODE 值 | RUN/STOP | CTRL 连接 |`
  左侧定锚（`kTopBarTitleX/ModeValueX/RunX/CtlValueX`）+ 右侧模型短 SHA + 信号状态徽标。
  各元素**定锚**，一个值变长绝不推动相邻元素（无布局跳动）。
- **冻结带不变**：信息条 `558..624`、底部导航 `630..719`（仍与 `touch_geometry.hpp`
  `kNavY0/kNavY1/kTabCount` 一致，`test_ui_layout_m19.cpp` 交叉断言收敛 W7）。

## 4. 逐页变化

### 页 0 CLASSIFY（`render_main`）

| 项 | Before | After |
|---|---|---|
| 顶部 | `draw_header`（仅标题 + 徽标 + SHA） | `draw_top_bar`（系统名 `SDR AMR` + 模式 + RUN/STOP + CTRL + SHA + 徽标） |
| 主类名 | `fb(52)` | `fb(40)` |
| 概率卡 | 双列全量 12 类 | **Top-3**（最多 3 行，排名 + 类名 + 条 + 百分比） |
| 错误态 | `NO SIGNAL` + `no valid data on input` | `NO SIGNAL` + `Waiting for valid input`（独立 `NO SIGNAL` 芯片） |
| STALE | 类名降 `dim` | 类名/置信降 `text_secondary` + `STALE DATA` 芯片 |
| MOCK | **与 LIVE 结果卡无区分** | 类名/置信用 `interactive`（蓝）+ `MOCK DATA` 芯片（W5 修复） |

- 修复审计 C5（52px / 全量）与 W5/W6（MOCK 区分 / NO SIGNAL 语义）。

### 页 1 PARAMETERS（`render_parameters`）

| 项 | Before | After |
|---|---|---|
| 分组 | 2 卡（SIGNAL & SPECTRUM 8 行 / LEVEL & MODEL 8 行） | **4 卡**：SIGNAL LEVEL / SPECTRUM / SIGNAL QUALITY / RF CONFIGURATION |
| 单位 | 内嵌在数值串（`fnum("%.1f dBFS",…)`） | **分离**：label 左 / value 右定宽 / unit 独立列（`draw_kv_row` 3 列定锚） |
| 缺失 | `"--"` | `"--"`（图集 ASCII-only，无法渲染 `—`，以双连字符近似；绝不伪 0） |

- 修复审计 C3（4 组 + 单位分离）；W3 定宽数值列（右对齐 + 三列定锚，小数点对齐）。

### 页 2 MODE（`render_mode`）

| 项 | Before | After |
|---|---|---|
| 模式按钮 | 名 + 描述，仅高亮 applied | 名 + 描述 + **逐按钮状态标签** `SELECTED/PENDING/IDLE`（C4） |
| START/STOP | `on=running`/`on=!running` 高亮，仍可点 | **disabled 视觉态**：RUNNING 时 START 禁用、STOPPED 时 STOP 禁用（W4/W5，`test_ui_layout_m19.cpp` 断言禁用墨色只在禁用按钮内出现） |
| 详情卡 | 7 行 | 7 行不变（current/requested/run/control/last command/command status/feedback） |

- 按钮状态派生自**现有**请求/应用状态机，不新增状态（审计 D4）：`SELECTED` = applied 模式即此按钮；
  `PENDING` = `command_status==PENDING` 且 `requested_mode` 即此按钮；其余 `IDLE`。
  `REJECTED/TIMEOUT` 仍在详情卡 `command status` 行，`DISCONNECTED` 仍在 `control connection` 行。

### 触摸几何

- 底部导航 `630..719`（≈75px 物理）不变。
- 模式按钮 `90..190`（≈83px）不变。
- **START/STOP 增高**：`200..270`（70px→≈58.3px，**<64px**）→ `200..288`（88px→≈73px，≥64px）。
  命中区几何由 `mode_ui::button_rect` 单一来源，渲染与触摸命中**同步**生效（W4 修复）。
  详情卡下移至 `296..548`，行距 36，仍止于信息条上方。

## 5. 性能（红线逐条核对）

| 红线 | 结论 |
|---|---|
| 不改 framebuffer / 换帧 / `submit_frame` / 页翻转 | 未触碰（`direct_framebuffer_backend.*` 字节不变） |
| 不提高刷新率 / 不连续同帧提交 | `FlipScheduler` 提交/跳过机制原样保留 |
| 渲染热路径不读文件 | 未引入任何文件读取 |
| 每帧不大分配 | 仅保留原有少量小字符串数组（审计 O2，非大分配） |
| CPU ≤ M18-SW1 基线 | 事件驱动翻转不变；纯内存整数绘制，无新增开销路径 |
| 数值 ≤5Hz | 属 `ui_dirty_state` 时间门控（审计 O4 Opportunity），**不在本重构范围**，维持 M18-SW1 行为 |

## 6. 快照对照索引（`artifacts/ui_m19/`）

| 快照 | 场景 |
|---|---|
| `main_live.ppm` | 12 类 QPSK@0.71 LIVE：Top-3 + 顶栏 + 置信条 |
| `main_stale.ppm` | STALE：`STALE DATA` 芯片 + 类名/置信降灰 |
| `main_error.ppm` | NO SIGNAL：`Waiting for valid input` |
| `main_mock.ppm` | MOCK：蓝色类名/置信 + `MOCK DATA` 芯片 |
| `parameters.ppm` | 四组卡片 + 单位分离（有效测量数据） |
| `mode_stopped.ppm` | MODE 页 STOPPED：START 禁用 / STOP 启用 + 逐按钮状态 |
| `legend.ppm` | 四态状态图例（LIVE/STALE/ERROR/MOCK 文字+形状+颜色） |
