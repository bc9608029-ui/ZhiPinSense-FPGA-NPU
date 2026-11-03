# M19 界面视觉整理 — 板端验收（视觉 + 触摸）

日期：2026-10-08
包：`sdr_full_chain_12class_ui_v3_m19_ui_polish_board_package.tar.gz`
基线：M18-SW1.1（`sdr_full_chain_12class_ui_v3_m18_sw1_1_board_package`）
参考：`docs/M19_UI_VISUAL_AUDIT.md`（现状审计）、`docs/M19_UI_BEFORE_AFTER.md`（前后对照）、
`artifacts/ui_m19/*.ppm`（7 张固定输入快照，PC 端离线对照）。

> **M19 是纯视觉重构**：不改模型 / 标签 / 阈值 / RTL / 位流 / SDR-NPU 数据链 / framebuffer 换帧。
> 唯一代码改动面 = `ui_sw/ui_theme.hpp`（新）+ `ui_sw/ui_layout.hpp`（新）+
> `ui_sw/ui_render.{hpp,cpp}`（Palette→Theme + 三页骨架）+ 三处 `Palette→Theme` 调用点 +
> `host_tests/*`（新增测试）。**控制通道、请求/应用状态机、触摸命中语义、验收脚本一律未动**。

---

## 0. 前提

- 已烧权威位流：`combined_npu_hdmi_disable_icap.bit`（SHA `22fec95c…`，**JTAG 只烧它，绝不写 Flash**）。
- 已解包本包，`sha256sum -c SHA256SUMS.txt` 全 OK。
- root 运行（UI 服务端需 `/dev/mem` + `/dev/udmabuf0`）。

## 1. 构建

```sh
./board_package/build_ui_live.sh g++
# 期望 UI_BUILD_RESULT result=PASS（-O2 -Wall -Wextra -Werror）
```

构建失败即停，不带旧二进制上板。

## 2. 起 UI 服务端（看首屏，无弹窗）

```sh
./scripts/run_ui_live.sh
# 期望 UI_LIVE_READY sock=/run/sdr_amr_ui.sock pid=<pid>
#       日志首行 UI_VERSION_CHECK version=0x20230218 OK
```

首屏验收点：

- **无启动 HDMI 弹窗**：blank → clear → waiting 帧 → unblank，首屏直接是 STALE 等待帧。
- **顶部状态栏**（三页统一）：左侧系统名 `SDR AMR`，随后依次 `MODE` 值、`RUN/STOP` 圆点+文字、
  `CTRL` 连接，右侧模型短 SHA + 信号状态徽标（文字+形状+颜色）。
- 底部导航三区等宽 `CLASSIFY / PARAMETERS / MODE`，选中项高亮。

## 3. 页 0 CLASSIFY（视觉验收）

有信号（STALE→LIVE，QPSK@0.71）：

- 主类名 **40px**（非 52px），`CONFIDENCE` 值 + 右侧置信条。
- **Top-3** 概率卡（最多 3 行：排名 + 类名 + 条 + 百分比），不再铺满 12 行。
- 状态芯片：`CONFIDENT`（≥0.6，绿）/ `LOW CONFIDENCE`（<0.6，琥珀）。

三种异常态各自 distinct：

| 态 | 期望 |
|---|---|
| ERROR | `NO SIGNAL`（红）+ `Waiting for valid input` + `NO SIGNAL` 芯片 |
| STALE | 类名/置信降灰 + `STALE DATA` 芯片 |
| MOCK | 类名/置信**蓝色** + `MOCK DATA` 芯片（与 LIVE 的绿/灰明确区分） |

## 4. 页 1 PARAMETERS（视觉验收）

- **四组卡片**：`SIGNAL LEVEL` / `SPECTRUM`（上行）、`SIGNAL QUALITY` / `RF CONFIGURATION`（下行）。
- 每行 **label 左 / value 右定宽 / unit 独立列**（单位不再内嵌在数值串里）。
- 无测量数据时值显示 `"--"`（双连字符，图集 ASCII-only，非 `—`），绝不伪 0。

## 5. 页 2 MODE（视觉 + 触摸验收）

- 三个模式按钮，每个含 名称 + 描述 + **逐按钮状态标签**：
  `SELECTED`（当前 applied 模式，蓝）/ `PENDING`（在途命令目标，琥珀）/ `IDLE`（其余，灰）。
- **START / STOP 禁用态**：
  - `RUNNING` 时 **START 禁用**（灰）、STOP 启用（琥珀）；
  - `STOPPED` 时 **STOP 禁用**（灰）、START 启用（绿）。
- 详情卡 7 行不变（current / requested / run state / control connection / last command /
  command status / feedback）。

触摸验收：

1. 底部导航三区可翻页（CLASSIFY ↔ PARAMETERS ↔ MODE），UP 边沿触发，连续点按被去抖折叠。
2. 模式按钮点击 → 状态随请求/应用变化（SELECTED/PENDING）；点击已选中模式 → 详情卡 feedback 出现
   `ALREADY IN THIS MODE`（幂等，不重复下发）。
3. **禁用按钮仍可点**（RUNNING 时点 START）→ 详情卡 feedback 出现 `ALREADY RUNNING`（幂等反馈），
   不产生重复命令 —— 禁用只是视觉态，命中区几何未变（`mode_ui::button_rect` 单源）。

## 6. 回归：触摸/控制/日志验收（脚本未改，须仍 PASS）

M19 未触碰验收脚本，直接复跑 M18-SW1 单次裁决验收：

```sh
./scripts/run_m18_sw1_touch_acceptance.sh
# 期望恰一行： M18_SW1_TOUCH_ACCEPTANCE result=PASS run_id=...
```

外加触摸几何自检（M17.3 起，不变）：

```sh
./scripts/test_touch_mode_control.sh
```

## 7. 显示完整性 / 诊断回归（脚本未改，须仍 PASS）

```sh
./scripts/run_display_integrity_test.sh
# ./scripts/run_display_diagnostic.sh   # 可选，仅诊断
```

## 8. 查收口 / 收尾

- 三页视觉与第 3–5 节逐条对照；有异议时用 PC 端 `artifacts/ui_m19/*.ppm` 快照对照（固定输入）。
- 收尾 `./scripts/stop_ui_live.sh` → `UI_LIVE_STOPPED pid=<pid>`；然后 `sync && poweroff`。

## 判定红线

- 本包最高离线状态只写 **READY-FOR-M19-UI-POLISH-HARDWARE-TEST**。
- 只有用户本人上板完成第 2–6 节视觉 + 触摸验收全通过，才可把状态升级为硬件验收通过。
- **绝不写** `UI_POLISH_PASS / SCREEN_PASS / PROJECT_COMPLETE / FINAL_MODEL_PASS / OOD_PASS`。
- 不降低任何现有断言/门限；64QAM 精度是已知模型问题，不在本任务，不伪修复。
