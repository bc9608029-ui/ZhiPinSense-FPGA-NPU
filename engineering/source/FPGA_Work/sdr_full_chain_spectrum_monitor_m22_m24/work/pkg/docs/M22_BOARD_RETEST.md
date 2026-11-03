# M22.1 板端复测说明

状态：离线交付 `M22_RUNTIME_HARNESS_ERRATA_READY` + `M22_UI_LAYOUT_ERRATA_READY_FOR_BOARD_TEST`。以下复测在真屏上执行，结果用于把 UI 状态升级到 `UI_VISUAL_PASS`（在此之前**不得**写 `UI_VISUAL_PASS / UI_HARDWARE_PASS / PROJECT_COMPLETE`）。

## 一、为什么不需要重训模型

本次仅修改：脚本进程编排（`scripts/`）、UI 渲染层（`ui_sw/`，只读 `UiState`，不碰模型输出/分类决策）、测试与文档。**模型、标签序、预处理、RTL、XDC、位流、SDR 数据链、NPU 推理逻辑均未改动**（证明见 `docs/M22_UI_ERRATA1_DIFF.md` §三）。

因此：
- 无需重新执行模型训练。
- 无需重跑无 UI 的 10000 帧基线（Gate 9 核心未变）。
- 若后续任何改动触及 Gate 9 核心，则必须重跑 10000 帧。

## 二、前置：分辨率与帧缓冲门禁（§四.3）

在视觉验收前，先采集真实显示参数：

```sh
fbset -s
cat /sys/class/graphics/fb0/virtual_size
cat /sys/class/graphics/fb0/bits_per_pixel
```

记录到复测报告。目标为 1280×720（RGB565）。若实测分辨率/位深与 1280×720 不符，把实测值反馈回来，布局常量（`LayoutMetrics`）需按实测再校验一次——**不得凭假设冻结最终像素坐标**。

## 三、定向复测步骤

1. **M22 runtime regression（240 帧）**
   `bash scripts/run_m22_runtime_regression.sh`
   判据：`M22_RUNTIME_REGRESSION result=PASS`，`reopen=0`、`spike_free=1`、`fd_growth=0`、`rss_ok=1`、`wait` 不再报 `not a child of this shell`。

2. **M22 runtime baseline（1000 帧）**
   `bash scripts/run_m22_runtime_baseline.sh`
   判据：`M22_RUNTIME_BASELINE result=PASS`，`reopen=0`、`spike_free=1`。

3. **M18-SW1 touch acceptance**
   `bash scripts/test_m18_sw1_touch_acceptance.sh`（或既有验收脚本）
   判据：`TOUCH_CONTROL=PASS` 保持；触摸命中区域/页面切换/模式控制语义不变。

4. **三页人工视觉验收（CLASSIFY / PARAMETERS / MODE）**
   逐项确认：文字无重叠、无越出卡片/按钮/屏幕；行距/边距/列对齐；层级清晰；MODE 按钮名称/描述/状态不侵占；START/STOP 视觉可辨；重要信息优先。

5. **UI 开启下的 Gate 9 并发运行**
   见 §四性能约束报告项，UI 进程与推理线程解耦、Unix Socket 非阻塞的确认。

6. **真屏照片**
   拍摄三页 + 问题修复位置的照片（本次 3 处修复位置：顶栏 MODE 值、顶栏 model SHA、信息条 SOURCE），作为视觉验收证据。

## 四、性能与稳定性报告项（§六，板端采集）

UI 修改后需记录并报告：

| 项 | 口径 |
|---|---|
| UI 进程 CPU 占用 | `top`/`pidstat` 采样 |
| RSS 初值 / 末值 / 峰值 | 单位 KB |
| UI 提交 / 丢帧 / 合并帧 | 帧后端统计 |
| Gate 9 P50/P95/P99/max | UI 开 vs 关对比（不得用无 UI 基线冒充） |
| reopen | 仍须 = 0 |
| spike_free | 仍须 = 1 |
| FD / 线程 / RSS 增长 | 是否持续增长（泄漏判定） |

**注意**：UI 相关性能数据只能真屏采集，离线无法测。切勿用无 UI 的 M22 基线当作"UI 并发性能通过"。

## 五、红线

- 复测前不写 `UI_VISUAL_PASS / UI_HARDWARE_PASS / PROJECT_COMPLETE`。
- 可保留已取得状态：`M22_RUNTIME_HARDWARE_PASS`、`TOUCH_CONTROL=PASS`。
- 离线最高状态：`M22_RUNTIME_HARNESS_ERRATA_READY` + `M22_UI_LAYOUT_ERRATA_READY_FOR_BOARD_TEST`。
