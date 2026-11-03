# M29 RML23 UI 视觉重构 — 审计报告（Task B / 步骤 A）

> 范围：`board_rml23_live/ui_sw/`（`ui_render.{hpp,cpp}`、`ui_theme.hpp`、`ui_layout.hpp`、
> `font_atlas.{hpp,cpp}`）+ `board_package/` 的 touch 几何（`touch_geometry.hpp`、
> `touch_mode_control.hpp`）+ UI 测试。基线：correctness-fix 源码
> （`sdr_rml23_live_board_package_correctness_fix.tar.gz`，SHA `81d66586…`）。
>
> 基线测试（本轮实测，全绿）：`test_ui_live 96/0`、`test_ui_v3_pages 30/0`、
> `test_ui_layout_m19 78/0`、`test_ui_rml23 27/0`。
>
> 审计方法：逐行读 5 个头文件 + 渲染器（853 行）+ 服务器（822 行）+ 状态映射（151 行）
> + touch 状态机（627 行）+ 4 个 UI 测试 + 快照工具；并生成了 27 张基线 PPM（见
> `artifacts/ui_before/`）。

---

## 1. Critical（正确性 / 鲁棒性，必须先修）

### C1. 无文本裁剪 / 无 fit·ellipsize API（用户需求 #13 / #14）
`font_atlas.hpp` 仅提供 `text_width` / `draw_text` / `draw_text_right` / `draw_text_center`。
`draw_text`（`font_atlas.cpp:53-84`）对每个字形只做画布边缘钳制，**没有任何
`text_box` / `fit_text` / `ellipsize_text` / `draw_text_clipped`**。最坏串
`AM-DSB-SC` / `RML23-AMSSB-MERGED` / `CTRL DISCONNECTED` / `ALREADY IN THIS MODE`
一旦超出容器即无任何守卫（截断靠字形级 `cx >= c.w`，越过容器右缘仍会画出）。

### C2. 无非 1280×720 fail-closed 守卫（需求 #24）
渲染器硬编码 `x_right = 1255/1256` 等右缘坐标，`fill_rect` 会钳制，但
`draw_text` / `draw_text_right` 在小于 1280×720 的画布上会**静默越界/截断**而非拒绝。
需求 #24 要求「非 1280×720 必须 fail-closed，不得越界绘制」。当前没有任何
`if (c.w != 1280 || c.h != 720) return;` 之类的守卫。

### C3. 视觉层级倒挂（需求 #6 / #7）
`render_main` 中主类别名 `top1`（`ui_render.cpp:467`）与置信度百分比
`conf_pct`（`ui_render.cpp:477`）**同为 40px Bold**。置信度是二级指标，却与
「当前识别类别」这一第一视觉焦点同字号，层级倒挂。

---

## 2. Warning（视觉质量 / 层级）

### W1. 过度加框（需求 #18 / #20）
每张卡片、每行、信息条都用 `outline_rect` 描边；23 类类目表每行一个全宽框
（`ui_render.cpp:271-273`）。整体呈「表格/网格」的调试工具观感，而非干净仪器。

### W2. 状态语义重复（需求 #9 / #17）
顶栏已有信号状态徽章（LIVE/STALE/…），结果卡内又画第二个 chip
（CONFIDENT / LOW CONFIDENCE / STALE DATA / MOCK DATA），同一页面两个重叠状态指示。

### W3. 冗余标签与装饰线（需求 #18）
顶栏同时含 `RML23-AMSSB-MERGED` 身份 caption、`MODE` 值、`CTRL` 值 + 3 条竖直分隔线
（`ui_render.cpp:180-182`），信息密度高、层级弱。

### W4. 类目表无 argmax 视觉焦点（需求 #6）
选中行仅靠 2px 边框换色 + 概率条换色（`ui_render.cpp:271-273,288`）区分，
「识别出的类别」在 23 类中缺乏第一焦点。

### W5. START/STOP 比例失衡（需求 #11 / #18）
两个 600px 宽 run 按钮（`ui_render.hpp:151`）并排三个 390px mode 按钮，run 行
视觉权重过大。

---

## 3. Opportunity（打磨）

### O1. 留白节奏
内容从 x=25 一路铺到 x=1255，仅 24px 边距，各区块之间缺乏呼吸感与清晰视觉中心。

### O2. 信息条数值字号
`draw_info_strip` 用 28px Bold 画 SNR/latency/frame/source 值（`ui_render.cpp:224`），
形成第三视觉层，且与主结果抢权重。

### O3. 置信度条脱节
置信度条（y=188..224）与百分比（y=240 基线）分离且偏薄，未与数字形成一体。

### O4. 底部导航图标稀疏
9px 图形 + 24px 文字，三个 tab 视觉不均。

---

## 4. 冻结/不可动清单（重构边界，逐条核对）

| 项目 | 结论 |
|---|---|
| `font_atlas_data.cpp`（52459 行烘焙字形） | **禁改**（需求明确：不重生成字形） |
| 底部导航几何 `kNavY0/kNavY1 = 630/719` | 冻结（`touch_geometry.hpp` + 板端依赖） |
| 信息条带 `kInfoY0/kInfoY1 = 558/624` | 冻结 |
| `UiState` / `render_*` / `status_label` / `status_badge_shape_cx` / `card_grid` / `classes_*` | 公共 API 语义冻结（`test_ui_live`/`test_ui_layout_m19` 依赖） |
| 模型 / golden / 标签序 / 24→23 merge / 预处理 / RF / socket / heartbeat / NPU / 位流 | **禁改** |
| 历史包 `cb3f204e…`/`e988707c…`/`e166bb32…`/`4abe1546…`/`81d66586…` | **禁覆盖** |

---

## 5. 结论

现有 UI 结构骨架（顶栏 / 内容 / 信息条 / 导航）可用；**核心缺陷在层级、加框、
字号分配与文本健壮性**。重构要点：去框改底、唯一 40px 焦点、补文本度量 API、
补 1280×720 fail-closed、以自动化几何测试替代肉眼验收。
