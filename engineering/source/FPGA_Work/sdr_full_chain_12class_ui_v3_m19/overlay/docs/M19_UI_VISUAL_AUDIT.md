# M19 UI 界面视觉整理 — 现状审计（修改前必读）

日期：2026-10-08
基准：`sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package`（M18-SW1.1 冻结全量包）
审计方式：**只读核对**，未修改任何代码 / 模型 / RTL / 位流 / 历史交付包。
状态：本文件是 M19 的**第一交付物**（Phase 1），仅陈述现状与差距，不含实现。

---

## 1. 审计范围与方法

审计对象（只读）：

| 文件 | 作用 |
|---|---|
| `ui_sw/ui_render.hpp` / `ui_sw/ui_render.cpp` | Style A 三页渲染器 + `Palette` + `mode_ui` 按钮几何 |
| `ui_sw/font_atlas.hpp` / `font_atlas.cpp` / `font_atlas_data.cpp` | 预烘焙 DejaVu 位图字体（20/24/28/40/52px） |
| `ui_sw/ui_state_map.hpp` | `ResultFrame -> UiState` 桥接 |
| `ui_sw/ui_dirty_state.hpp` | `display_changed` + `FlipScheduler`（事件驱动翻转） |
| `board_package/board_ui_live_12class.cpp` | 服务端：页面分发、触摸导航、控制通道、提交循环 |
| `board_package/touch_geometry.hpp` | 三区底部导航命中 + 翻页状态机 |
| `board_package/touch_mode_control.hpp` | 第三页五按钮点击检测 + 请求/应用状态机 |
| `board_package/mode_control.hpp` / `control_channel.hpp` / `work_mode_engine.hpp` | 模式令牌 / 反向控制通道 / 工作模式引擎 |
| `host_tests/test_ui_v3_pages.cpp` | 现有三页映射 + 渲染主机测试 |

结论全部标注到 `文件:行号`（行号以本包内文件为准）。

---

## 2. 现状盘点（事实）

### 2.1 字体图集（baked，禁止运行时缩放）

`font_atlas.hpp` 明确：**绝不运行时缩放字形**，每个尺寸都是预烘焙位图。
`font_atlas_data.cpp:52437–52449` 实际烘焙尺寸：

| 字重 | 尺寸 (px) |
|---|---|
| Regular | 20, 28, 40, 52 |
| Bold | 20, 24, 28, 40, 52 |
| Mono | 20, 28, 40, 52 |

- **缺失**：16、18、32、44、48 px。
- `font_atlas_data.cpp` 是 6.4 MB 生成物；其 PC 侧生成脚本 `design_mockups/tools/gen_font_atlas.py`
  **不在板端包内**（本包 `design_mockups/` 为空）。

### 2.2 调色板（Style A，RGB565，`ui_render.cpp:260–275`）

| 语义 | 值 | RGB565 八位 | 用途 |
|---|---|---|---|
| bg | `#0F141B` | (15,20,27) | 页面背景 |
| surface | `#1A212B` | (26,33,43) | 卡片底 |
| surface_alt | `#121A24` | (18,25,36) | 信息条 / 芯片底 / 未选按钮 |
| text | `#E7ECF2` | (231,236,242) | 主文本 |
| dim | `#8B98A8` | (139,152,168) | 次文本 / 标签 |
| primary | `#4A90E2` | (74,144,226) | 选中 / 强调 |
| success | `#3DDC84` | (61,220,132) | LIVE / APPLIED / 运行 |
| warning | `#E8A93C` | (232,169,60) | STALE / PENDING / 停止 |
| error | `#E5605F` | (229,96,95) | ERROR / REJECTED / TIMEOUT |
| outline | `#2A3542` | (42,53,66) | 边框 |
| accent_bar_bg | `#141B25` | (20,27,37) | 置信条底 |

- 语义色 token 现有 11 个；**缺** `interactive`、`selected`、`disabled`。
- 抽查对比度（相对 luminance，WCAG 公式）：
  - `text` on `bg` ≈ 15.8:1；`dim` on `bg` ≈ 6.2:1；`dim` on `surface_alt` ≈ 6.0:1；
  - `success` on `surface` ≈ 9.1:1；`warning` on `surface` ≈ 7.9:1；
  - `primary` on `surface` ≈ **4.9:1**（最紧，仍 ≥ 4.5:1）。
- “状态永不用颜色单独表达”**已满足**：状态徽标 = 文字 + 形状 + 颜色
  （`draw_status_badge`，`ui_render.cpp:105–115`）。

### 2.3 布局坐标（硬编码魔法数，无统一头文件）

- **无 `ui_theme.hpp` / `ui_layout.hpp`**。所有坐标、间距、字体尺寸、颜色分散硬编码在
  `ui_render.cpp` 各函数内。示例（`ui_render.cpp`）：
  - 页面边距 `25` / 右缘 `1255`（`draw_header`、`draw_info_strip`、各卡片）；
  - header 标题 `(25,50)`、状态徽标 `x=1255,y=38`、分隔线 `y=78`；
  - 信息条 `y0=558,y1=624`，4 段各 `1230/4`；
  - 底部导航 `y0=630,y1=719`，三区各 `c.w/3`；
  - 主结果卡 `y=84..252`，概率卡区 `y=288..556`，`card_grid()` 内 50/44 等。
- 网格注释声明为「横向 5px / 纵向 6px」（`ui_render.hpp:5`、`THREE_PAGE_UI_CONTRACT.md:18`），
  **非 8px 网格**。坐标普遍不可被 8 整除（`25/45/620/655/1255`、`84/132/200/252/558/630`）。
- 唯一集中定义几何的是 `mode_ui` 命名空间（`ui_render.hpp:134–165`，M16 按钮几何），
  供渲染器与触摸命中测试共用——这是一个好的先例，M19 可推广到全页。

### 2.4 页面骨架现状

`draw_header`（`ui_render.cpp:129–139`）= 左侧标题 `fb(28)` + 右侧状态徽标 + 可选模型短 SHA。
**没有**：系统名、当前工作模式、RUN/STOP、控制连接状态——这些目前只在 MODE 页详情卡内
（`render_mode` 的 detail card，`ui_render.cpp:639–645`）。

`draw_info_strip`（`ui_render.cpp:142–156`）= SNR / LATENCY / FRAME / SOURCE 四段，
三页共享（PARAMETERS / MODE 页也调用）。

`draw_nav`（`ui_render.cpp:159–177`）= 底部三区，标签 `CLASSIFY / PARAMETERS / MODE`，
`fb(24)`，等宽 `c.w/3`，选中项以 `surface_alt` 底 + `primary` 形状/文字高亮。

- 底部导航触摸几何由 `touch_geometry.hpp` 的 `kNavY0=630 / kNavY1=719 / kTabCount=3`
  独立硬编码（**未**复用 `draw_nav` 的常量——两处需人工保持一致，是潜在漂移点）。
- 启动序列无弹窗（`board_ui_live_12class.cpp:380–435`：blank → clear → 渲染 waiting 帧 →
  编程 rd_addr → unblank）。**“无启动 HDMI 弹窗”已满足**。

### 2.5 三页现状

| 页 | 函数 | 现状要点 |
|---|---|---|
| 页 0 CLASSIFY | `render_main` | 结果卡（Top-1 类名 `fb(52)` + `CONFIDENCE` `fb(40)` + 置信条）+ **双列 12 类概率卡全量** |
| 页 1 PARAMETERS | `render_parameters` | 2 卡：`SIGNAL & SPECTRUM`（8 行）+ `LEVEL & MODEL`（8 行），键左值右 |
| 页 2 MODE | `render_mode` | 3 模式按钮（名 `fb(28)` + 描述 `r20`，无逐按钮状态标签）+ START/STOP + 详情卡 7 行 |

- 页 0 错误态：`NO SIGNAL` `fb(52)` + `no valid data on input`（`ui_render.cpp:289–298`）。
- 页 0 STALE 态：`STALE DATA` 芯片 + 类名降为 `dim`。
- 页 0 **MOCK 态未在结果卡与 LIVE 区分**（仅 header 徽标画空心方块；结果卡仍按
  `conf>=0.6` 显示 `CONFIDENT`/`LOW CONFIDENCE`，`ui_render.cpp:306–311`）。
- 页 1 行：`draw_kv_row`（`ui_render.cpp:188–192`）= 标签 `fr(20) dim` 左、值 `fm(20) text` 右；
  **单位内嵌在数值串里**（如 `fnum("%.1f dBFS", …)`、`fnum("%.1f dB", …)`），未分离。
- 页 1 缺失值用 `"--"`（两个连字符），非规范的 `—`/`N/A`。
- 页 2 详情卡 7 行：current mode / requested mode / run state / control connection /
  last command / command status / feedback（`ui_render.cpp:639–645`）。
- 页 2 模式按钮：仅高亮 `applied` 模式；`PENDING/REJECTED/TIMEOUT` 只在详情卡
  `command status` 行体现，**不在对应按钮上**。
- 页 2 START/STOP：`on=running`（START 高亮）与 `on=!running`（STOP 高亮），但仍可点击，
  点击后 `request_ex` 返回 `Idempotent`（`ALREADY RUNNING`/`ALREADY STOPPED`）。
  **无 disabled 视觉态**。

### 2.6 触摸几何（现状）

- 底部导航：`y∈[630,719]` 90px 原始高 → 5/6 缩放 ≈ 75px 物理高（≥64px ✓）。
- 模式按钮：`y∈[90,190]` 100px → ≈83px（✓）；宽 390、间距 15、x0=25。
- START/STOP：`y∈[200,270]` **70px → ≈58.3px 物理高（< 64px 规范下限）**。
- 三页切换 `TouchNav`：UP 边沿 + DOWN 点命中 + `debounce_ms` 折叠（`touch_geometry.hpp:104–146`）。

### 2.7 性能机制（现状，M19 红线）

- 事件驱动翻转：`display_changed()`（逐字段精确比较）+ `FlipScheduler::should_submit()`
  （内容变化 且 距上次 submit ≥ min_interval_ms）——`ui_dirty_state.hpp`。
- 提交/跳过机制：`submits` / `skips` 计数，`UI_RUNTIME_STATS` 证明空闲路径不重翻。
- 渲染热路径：**无文件读取**；`fill_rect`/`outline_rect`/`draw_text` 为纯内存整数运算。
- 每帧小堆分配：`render_parameters`/`render_mode` 每帧构造 `{const char* k; std::string v}` 数组
  （8 + 7 个 `std::string`）——**存在每帧堆分配**（量小，但规范要求“无每帧大分配”，可优化）。
- 数值刷新频率：当前随 `display_changed` 门控（字段变即重绘），上限为显示帧率（默认 30Hz），
  未对“数值 ≤5Hz”单独采样/去抖。

---

## 3. 与 M19 规范逐条对照（分级）

分级约定：**Critical** = 规范硬性要求当前完全缺失/相悖，影响信息一致性；
**Warning** = 偏离规范但可接受、需权衡；**Opportunity** = 优化 / 清理 / 文案统一。

### 3.1 Critical

| # | 发现 | 证据 | 规范要求 |
|---|---|---|---|
| C1 | 无统一视觉规范头文件，坐标/字体/颜色全部硬编码魔法数 | `ui_render.cpp` 全局；`ui_render.hpp:134–165` 仅 `mode_ui` 例外 | 建 `ui_theme.hpp` + `ui_layout.hpp`（8px 网格、固定边距、≤4 字级、定宽数值列、语义色 token） |
| C2 | 无统一顶部状态栏（系统名 / 模式 / RUN-STOP / 连接状态） | `draw_header` `ui_render.cpp:129–139` 仅标题+徽标；模式/运行/连接仅 MODE 页 | 顶部状态栏：`系统名 \| 模式 \| RUN/STOP \| 连接状态` |
| C3 | 参数页分组与规范不符，且单位未分离 | `render_parameters` `ui_render.cpp:526–554` 2 组、单位内嵌 `fnum("%.1f dBFS",…)` | 4 组：Signal Level / Spectrum / Signal Quality / RF Configuration；label 左 / value 右 / **unit 分离** |
| C4 | MODE 页按钮无逐按钮状态标签，START/STOP 无 disabled 态 | `render_mode` `ui_render.cpp:583–618` 仅名+描述+高亮 | 每按钮 name+description+**status**；START 在 RUNNING 时 disabled、STOP 在 STOPPED 时 disabled |
| C5 | 主分类页类名字号 52px 超规范上限 48px，且显示全部 12 类 | `render_main` `ui_render.cpp:314`（`b52`）、`336–374`（全量网格） | 主类名 40–48px；Top-3 最多 |

### 3.2 Warning

| # | 发现 | 证据 | 说明 |
|---|---|---|---|
| W1 | 网格为 5px/6px，非 8px；坐标普遍非 8 对齐 | `ui_render.hpp:5`；`25/45/620/655/1255` 等 | 迁移 8px 网格会改变大量坐标 → 需重新截屏对比（快照必须重建） |
| W2 | 无 `interactive` / `selected` / `disabled` 语义色 token | `Palette` `ui_render.hpp:26–29` | 规范要求语义色 token 覆盖 disabled 等状态 |
| W3 | 数值列右对齐但非定宽（小数点不齐）；缺失用 `"--"` | `draw_kv_row` `ui_render.cpp:188–192`；`"--"` 遍布 | 规范：定宽右对齐、未知 = `—`/`N/A` 绝不 0 |
| W4 | START/STOP 按钮高 70px 原始 → ≈58.3px 物理，< 64px 触摸下限 | `ui_render.hpp:140–142`（`kRunY0=200,kRunY1=270`） | 需增高或扩大命中区（命中区几何由 `button_rect` 与渲染共用，须同步改） |
| W5 | MOCK 态在结果卡未与 LIVE 视觉区分 | `render_main` `ui_render.cpp:306–311` 无 `Status::Mock` 分支 | 规范：ERROR / STALE / MOCK 三者各自 distinct |
| W6 | 初始“等待有效输入”态 = Stale + `top1="--"`，无独立文案 | `board_ui_live_12class.cpp:417–427`（`waiting`） | 规范：`NO SIGNAL` / `Waiting for valid input` 语义区分 |
| W7 | 底部导航几何常量在渲染器与触摸层各一份，易漂移 | `draw_nav` `ui_render.cpp:160` vs `touch_geometry.hpp:32–34` | 应收敛为单一 `ui_layout` 常量源 |

### 3.3 Opportunity

| # | 发现 | 证据 |
|---|---|---|
| O1 | `render_diag` / `render_touch` / `render_legend` 为死代码（live 服务端只调用 `render_main/parameters/mode`） | `board_ui_live_12class.cpp:753–757`；仅 `test_ui_live.cpp:374–375` 引用 |
| O2 | 每帧小堆分配（`render_parameters`/`render_mode` 构造 `std::string` 数组） | `ui_render.cpp:526–554` |
| O3 | 底部导航标签 `CLASSIFY/PARAMETERS/MODE` 与规范 `CLASS/PARAMETERS/MODES` 文案不一致 | `draw_nav` `ui_render.cpp:163` |
| O4 | 数值字段无 ≤5Hz 采样/去抖（当前随帧率） | `ui_dirty_state.hpp`（`display_changed` 逐字段，无时间门控） |

---

## 4. 关键设计决策点（须在实现前确认）

### D1 字体图集约束（最重要）

规范字级区间 `40–48 / 28–32 / 20–24 / 16–18` 与图集实际 `{20,24,28,40,52}` 的映射：

| 规范层 | 图集可选 | 结论 |
|---|---|---|
| 主类名 40–48 | **40**（52 超上限，44/48 缺） | 用 40，弃 52 |
| 标题 28–32 | 28 | 用 28 |
| 值/按钮 20–24 | 20 / 24(Bold) | 用 20 / 24 |
| 标签 16–18 | **无**（最小 20） | 见下 |

- **标签 16–18px 在图集中不存在**。两条路径：
  - **(a) 用现有 20px 当标签层**（推荐默认）：`{40,28,24,20}` = 恰 4 级，满足「≤4 字级」与
    「主体内容 ≥16px」，且**零图集再生**、零运行时缩放、零性能风险；唯一不满足的是
    「16–18px 标签」这个字面区间（20px 仍 ≥16px）。
  - **(b) 再生图集补 16/18（及可选 32/44/48）**：需 PC 侧 `gen_font_atlas.py`（DejaVu 光栅化），
    该工具**不在板端包内**，需回到源工程执行并重烘焙 6.4MB `font_atlas_data.cpp`。
- **审计建议默认走 (a)**；是否补图集由用户拍板（若补，属“源工程侧”变更，须单独核验 SHA 与
  逐像素回归）。

### D2 8px 网格迁移的影响面

- 现坐标几乎全非 8 对齐；迁移到 8px 网格 = 大面积坐标重排 → **全部 7 张截屏快照必须重建**，
  且 `mode_ui` 按钮几何（`ui_render.hpp:134–165`）与 `touch_geometry.hpp` 的导航带
  （`kNavY0/kNavY1`）必须同步，否则触摸命中与渲染错位。
- 8px 网格下 1280 宽 / 720 高的边距可取 24px（非 25），需重新核对各卡片布局不溢出。

### D3 三页 vs 五页

- 现 nav 为 3 页（CLASSIFY / PARAMETERS / MODE），`render_diag`/`render_touch` 已是死代码。
- M19 只做三页视觉整理，**不动** `render_diag`/`render_touch`（避免破坏 `test_ui_live.cpp`）；
  是否删除死代码属 O1，默认**保留不动**（谨慎原则）。

### D4 状态字符串口径

- 规范要求 MODE 页按钮状态 `SELECTED/PENDING/APPLIED/REJECTED/TIMEOUT/DISCONNECTED`。
- 现状 `command_status` 值为 `-- / PENDING / APPLIED / REJECTED / TIMEOUT`（`touch_mode_control.hpp:619`），
  另有 `ctl_connected` 的 `CONTROL CONNECTED/DISCONNECTED`。`SELECTED` 需由「applied 模式 == 该按钮」
  推导为逐按钮状态标签，不新增状态机状态（避免触碰冻结的请求/应用状态机）。

---

## 5. 红线（M19 一律不碰）

1. 模型 / 标签 / 分类阈值 / RTL / XDC / 位流 / SDR-NPU 数据链。
2. `direct_framebuffer_backend.{hpp,cpp}` 的 framebuffer / 换帧 / `submit_frame` / 页翻转生产逻辑。
3. M18-0 A/B/C/D 诊断工具（`board_display_diagnostic.cpp` / `build_display_diagnostic.sh` /
   `display_diagnostic.{hpp,cpp}`）。
4. 触摸映射语义（swap/invert/裁剪/UP 边沿翻页/去抖）、`touch_evdev.hpp` 设备枚举。
5. 反向控制通道与请求/应用状态机（`mode_control.hpp` / `control_channel.hpp` /
   `touch_mode_control.hpp` 的 `ModeControlState` 语义）——只**读**其状态用于渲染，不改其逻辑。
6. M14–M18-SW1 历史交付包、冻结位流 `22fec95c…`、模型 raw `2ae95275…`。
7. 不得降低任何现有断言/门限；不伪修复 64QAM。
8. 性能红线：不提高刷新率、不连续同帧提交、渲染热路径不读文件、每帧不大分配、
   CPU ≤ M18-SW1 基线、`FlipScheduler` 提交/跳过机制保留。

---

## 6. 建议实施顺序（供下一阶段）

1. `ui_sw/ui_theme.hpp`：语义色 token（补齐 `interactive/selected/disabled`）+ 字体层级常量。
2. `ui_sw/ui_layout.hpp`：8px 网格、固定边距、信息条/导航/卡片几何、定宽数值列，并让
   `mode_ui` / `touch_geometry` 引用同一常量源（收敛 W7）。
3. 统一页面骨架：顶部状态栏（系统名/模式/RUN-STOP/连接状态）+ 三页复用 + 底部导航。
4. 逐页重构：页 0（Top-3、主类名 40px、MOCK 区分、NO SIGNAL/Waiting 语义）、
   页 1（4 组卡片 + 单位分离 + `—`/N/A）、页 2（逐按钮状态 + START/STOP disabled）。
5. `host_tests/test_ui_layout_m19.cpp` + `artifacts/ui_m19/*` 7 张固定输入截屏 + 对比度/边界断言。
6. `docs/M19_UI_BEFORE_AFTER.md` + 全量回归（`-Wall -Wextra -Werror`、ASan/UBSan、
   touch 导航/模式控制/dirty-state、M18-SW1 验收主机测试、framebuffer/display 诊断主机测试）。
7. 版本化打包 `dist/sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz` +
   `dist/m19_ui_polish_patch.tar.gz`（确定性 tar、SHA256SUMS、diff 零差异、PROVENANCE）。
