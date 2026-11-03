# M29 RML23 UI 视觉重构 — 设计规范与 Token 表（Task B / 步骤 B）

> 定位：1280×720 横屏嵌入式 RF 监测仪，专业、克制、深色仪器风（高端频谱仪/示波器参照），
> 关键信息醒目、次要信息安静、少元素、无装饰线/无边框堆叠/无高饱和色。
> 本规范与 `ui_layout.hpp` / `ui_theme.hpp` / `ui_render.cpp` 一一对应，测试
> `test_ui_boundary.cpp` 断言其几何与对比度。

---

## 1. ColorTokens（`ui_theme.hpp`，值冻结不变，语义不变）

| Token | RGB565 | 用途 |
|---|---|---|
| `background` | #0F141B | 页面底色 |
| `surface` | #1A212B | 主面板 / 表头底色 |
| `surface_alt` | #121A24 | 选中行 / 按钮底 / chip 底 |
| `outline` | #2A3542 | 唯一保留的 1px 发丝线（仅主卡片与信息条） |
| `text_primary` | #E7ECF2 | 一级文字 |
| `text_secondary` | #8B98A8 | 标签 / 次要文字 |
| `interactive`/`selected` | #4A90E2 | 选中高亮 / 交互 |
| `success` | #3DDC84 | LIVE / RUNNING / 高置信 |
| `warning` | #E8A93C | STALE / PENDING / 低置信 |
| `error` | #E5605F | ERROR |
| `disabled` | #5A6672 | 禁用（仅非状态） |
| `accent_bar_bg` | #141B25 | 概率条轨道 |

约束：`selected == interactive`；`text_primary/text_secondary/interactive/success/warning/error`
在 `surface` 与 `background` 上对比度 ≥ 4.5:1；`disabled` 在 `surface` 上 < 4.5:1（豁免）。

---

## 2. TypeScale（`ui_theme.hpp::font_tier`，≤4 档，字形不重生成）

| 层级 | 字号 | 权重 | 用途 |
|---|---|---|---|
| `kMain=40` | 40 | Bold | **唯一**第一焦点：当前识别类别名 `top1` |
| `kTitle=28` | 28 | Bold | 页标题 / 区块标题 / 置信度数值 |
| `kButton=24` | 24 | Bold | 底部导航 / MODE·START·STOP 按钮 |
| `kValue=20` | 20 | Bold | 所有数值 |
| `kLabel=20` | 20 | Regular | 所有标签 |

层级铁律（需求 #6/#7）：**40px 只用于 top1**；置信度/信号状态/运行模式为第二层（28px 值 +
20px 标签）；模型 SHA / 性能 / 诊断恒为第三层（20px，模型 SHA 落位信息条第 5 列）。

---

## 3. Spacing-Grid + LayoutMetrics（`ui_layout.hpp`）

- 8px 网格：`kXs=4 / kSm=8 / kMd=16 / kLg=24 / kXl=32`，页边距 `kMarginX=24`。
- 冻结带：顶栏 `0..71`（分隔线 72）、信息条 `558..624`、底部导航 `630..719`
  （与 `touch_geometry.hpp` 严格一致）。
- 内容区 `84..548`，左右安全边距 24（内容 x ∈ [24,1256)）。
- **新规则**：所有 x/y 取 4 的倍数；左对齐元素固定左锚点、右对齐固定右锚点，任何值长度
  变化不得移动其它元素（无布局跳动，需求 #10）。

---

## 4. Component 规范

### 4.1 Card（去框改底）
- 主卡片：`surface` 底 + 仅 `outline` 1px 发丝线（全页面**至多一条**主卡片框）。
- 次级区块：仅用 `surface`/`surface_alt` 底色区分，**不加描边**；行内用底部发丝线分隔
  （可选），不用逐行全宽框。
- 圆角：无（嵌入式软件渲染，禁圆角/阴影/渐变/模糊/大透明度/连续动画，需求 #20）。

### 4.2 Button（尺寸统一，命中区 = 可见区，需求 #11/#12）
- 命中区与可见区**完全一致**（同一 `button_rect()` 源）。
- 底部导航：高 90 raw（≥60 physical），全宽三等分。
- MODE 页按钮：mode 按钮 390×100，START/STOP 各 600×88；禁用态用 `disabled` 描边 +
  降饱和文字，但**仍可触摸**（幂等→feedback）。

### 4.3 Status（一律「图形 + 文字 + 颜色」，需求 #9）
- `draw_status_badge`：形状（实心圆/菱形/三角/空心圆/空心方）≥10px 位于右对齐文字左侧，
  颜色与文字一致；`NO SIGNAL` 用空心圆（聆听态），`MOCK` 用空心方。
- **每页仅一处**信号状态徽章（顶栏），移除结果卡内的第二个状态 chip，避免语义重复（W2）。

---

## 5. 页面布局

### 5.1 顶栏（0..71，去分隔线）
- 左：`model_mode` caption（20 Regular secondary）在 y=20；标题（28 Bold primary）在 y=50，
  左锚 x=24。
- 字段组（左锚固定，label 上 value 下，杜绝布局跳动）：
  - MODE：label(20 secondary, y=22) + value(20 Bold interactive, y=50)，x=312。
  - RUN：dot(r=5) + RUNNING/STOPPED(20 Bold success/warning, y=50)，x=576。
  - CTRL：label(20 secondary, y=22) + CONNECTED/DISCONNECTED(20 Bold, y=50)，x=752。
- 右：**仅**信号状态徽章（右锚 1255）。模型短 SHA 从顶栏迁出（顶栏曾出现
  `DISCONNECTED`(190px) 与 `NO SIGNAL` 徽章(左缘 1097)之间 87px 放不下 104px SHA 的几何冲突，
  需求 #18「信息拥挤」），改放信息条「MODEL」列（第三层，见 §5.2）。
- **移除** 296/556/736 三条竖直分隔线（W3）。

### 5.2 主页面（Main）
- Hero（84..276）：
  - "RECOGNIZED SIGNAL" 标签（20 secondary）y=108。
  - **top1 类别名（40 Bold primary）y=196，左锚 24（第一焦点）**。
  - 置信度组（右对齐 700..1255）："CONFIDENCE" 标签 y=108；数值 "82.0%"（28 Bold
    success/warning 按 0.6 阈值）y=196；概率条 y=204..240。
  - STALE 态：类别名/数值降为 `text_secondary`，仍显示"上次结果"+ age。
- 类目表（288..540，23 类分页）：
  - 头 "CATEGORIES"（20 secondary）y=308。
  - 6 行/页，行高 28、pitch 34，**无全宽框**；每行：序号(mono 20 secondary) + 名称
    (20 primary) + 概率条 + 百分比(mono 20)。
  - **argmax 行**：整行 `surface_alt` 底 + 左 4px `selected` 强调条 + 名称 `selected` 色，
    形成明确第一焦点（W4）。
  - 尾 "PAGE p/m"（20 secondary）y=540。
- 12 类（向后兼容）：保留 top-3 排名路径，同样去框。
- 信息条（冻结带 558..624）：`surface_alt` 底、无描边，**5 列等宽**（1232/5）
  `SNR / LATENCY / FRAME / SOURCE / MODEL`；label 20 secondary，value 20 Bold primary；
  `MODEL` 列显示模型短 SHA（空则 `--`），使 SHA 不再侵占顶栏。
- 导航沿用冻结带（630..719），底部导航 24 Bold，三等分。

### 5.3 PARAMETERS 页
四组卡（SIGNAL LEVEL / SPECTRUM / SIGNAL QUALITY / RF CONFIGURATION）：`surface` 底、
**无描边**、以 8px 网格对齐 label 左 / value 右 / unit 分离（沿用 `draw_kv_row`）。

### 5.4 MODE 页
3 个 mode 按钮 + START/STOP + 详情卡；按钮命中区=可见区；详情卡 7 行沿用 `draw_kv_row`。
feedback/command_status 用 `feedback_color`/`command_status_color`（不变）。

### 5.5 DIAG / TOUCH 页
沿用现有信息布局，去框改底、对齐 8px 网格。

---

## 6. 新增字体度量 API（`font_atlas.{hpp,cpp}`，需求 #13）

```cpp
struct TextBox { int x, y, w, h; };              // 像素包围盒（含 ascent/descent）
TextBox text_box(const std::string& s, const font_t* f, int x, int y, int spacing=0);
std::string fit_text(const std::string& s, const font_t* f, int max_w);  // 逐字截断
std::string ellipsize_text(const std::string& s, const font_t* f, int max_w); // "…"→".."
void draw_text_clipped(Canvas& c, const std::string& s, int x, int y, int max_w,
                       std::uint16_t color, const font_t* f, int spacing=0);
```

约束：无逐帧分配（`fit/ellipsize` 返回小 `std::string` 仅在最坏串/裁剪路径使用；
正常路径仍走零分配 `draw_text`）；`ellipsize` 用 `..` 替代省略号（atlas 仅 ASCII 32..126）。

---

## 7. 需求覆盖矩阵（节选）

| 需求 | 落地 |
|---|---|
| #6/#7 层级 | 40px 唯一给 top1；置信度 28px；其余 20px |
| #9 状态三要素 | `draw_status_badge` 图形+文字+颜色，每页一处 |
| #10 无布局跳动 | 左/右固定锚点，长度变化不移位 |
| #11/#12 触摸 | `button_rect` 单一源，命中区=可见区 |
| #13 字体度量 | §6 四函数 |
| #14/#15 不溢出 | `draw_text_clipped` + 最坏串测试 |
| #18 去装饰 | 去竖直分隔线、去逐行框、去重复标签 |
| #19 对比度 | `test_ui_boundary` 全 token 断言 |
| #20 无特效 | 全程纯 RGB565 填充/文字 |
| #21 无逐帧分配/不扰 NPU | 渲染路径零 `new`，不触 NPU 线程 |
| #24 fail-closed | `render_*` 入口 `c.w==1280 && c.h==720` 守卫 |
