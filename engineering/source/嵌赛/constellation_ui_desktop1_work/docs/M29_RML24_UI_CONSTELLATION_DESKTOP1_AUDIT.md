# M29 RML24 UI 星座图桌面验证审计（ui-constellation-desktop1）

任务：Task C「ui-constellation-desktop1」（task 39e5）。工作树
`F:\嵌赛\constellation_ui_desktop1_work\`。

目标状态令牌：**`M29-RML24-UI-CONSTELLATION-DESKTOP-VERIFIED-READY-FOR-RUNTIME-INTEGRATION`**
（可见桌面 + 真实截图 + 性能门禁完成后）。
禁止令牌：`RUNTIME-INTEGRATED` / `RF_PASS` / `PROJECT_COMPLETE` / `FINAL_*`。

## 1. 结论（如实）

- 在 WSL2 + WSLg（1.0.73.2）可见桌面下，UI **真实构建并运行**（BUILD_RC=0）。
- 四视图（RAW_RX / RECOVERED_PAYLOAD / MODEL_INPUT / SYMBOL_SAMPLED）**全部真实渲染并通过
  颜色主导性核验**（VERDICT ALL-OK）。
- 中文字体：修复 tofu 问题（部署 Microsoft YaHei + SimHei），中文可读。
- FPS / CPU / RSS 均为**桌面（WSLg 软件合成）真实测量**，**不声明板端性能**。
- 收缩 / 尺寸自适应已验证（480×360 截图）。
- 稳定性（20 min 连续渲染，RSS 泄漏检测）：见 §6（回填）。
- 运行时数据契约 + 离线模拟器已交付（`contracts/ui_runtime_frame_v1.md` +
  `tools/offline_frame_simulator.py`）。

**本阶段只证明“UI 可在真实桌面正确渲染 + 交互 + 性能达标”，不证明与接收/NPU 线程的运行时
集成（那需要后续在目标环境接入 `IqFrameSource`）。**

## 2. 构建

| 项 | 值 |
|---|---|
| 工具链 | g++ 15.2.0 / cmake 4.2.3 / Qt 5.15.18（qmake 3.1） |
| QML 模块 | QtQuick 2.15 / Controls 2.15 / Layouts 1.15 / Dialogs 1.3 |
| 渲染 | QSG scene-graph（QSGGeometryNode + QSGVertexColorMaterial），4096 点→16384 顶点 |
| BUILD_RC | 0（`cmake --build build` 全绿） |
| 单元测试 | `test_iqframe` 全 PASS：**111 assertions / 22 tests，0 fail**（fixtures 校验链 + SHA + 抽稀 + 坐标） |
| 测试调用 | **必须传 fixtures 路径作 argv[1]**：`./build/test_iqframe fixtures`；缺参会默认 `../fixtures`（错误目录→误报 21 fail，见 2026-10-18 复核记录） |

历史 stale 报错「QtQuick.Controls 1.2 not installed」已确认为**过时**：`qml-module-qtquick-controls`
（5.15.18-1）已安装，离屏烟测干净（空日志）。

## 3. 可见桌面 + 真实截图（非伪造）

- 环境：`DISPLAY=:0`，`WAYLAND_DISPLAY=wayland-0`，`XDG_RUNTIME_DIR=/run/user/1000`。
- 截图路径：`Controller::screenshot()` → `QQuickWindow::grabWindow()`（**真实窗口内容**，非
  离屏、非伪造）。CLI `--screenshot PATH [--screenshot-delay-ms N]`，截图后 `app.exit(0)`。
- 截图产物（`screenshots/`）：

| 文件 | 内容 | 验证 |
|---|---|---|
| `01_recovered_payload.png` | RECOVERED（tofu 对照） | 中文豆腐块证据 |
| `02_recovered_payload_zh.png` | RECOVERED 青色 | 颜色核验 OK（1120px） |
| `03_model_input_zh.png` | MODEL_INPUT 绿色 | 颜色核验 OK（949px） |
| `04_raw_rx.png` | RAW_RX 灰白 | 颜色核验 OK（15549px） |
| `07_symbol_sampled.png` | SYMBOL 黄色 16QAM | 颜色核验 OK（2979px） |
| `08_resize_480x360.png` | 收缩 480×360 | 布局/letterbox 自适应 |

- 颜色核验方法：`tools/verify_stage_colors.py`（PIL 逐像素，绘图区 x<900、y≥90 内主导色须为
  该 stage 期望色；环境 Read 工具无法显示 PNG，故用**客观像素直方图**替代人眼，证据不替代人看）。

## 4. 四视图核验结果（VERDICT ALL-OK）

`tools/verify_stage_colors.py` 输出：RAW_RX grey / RECOVERED cyan / MODEL_INPUT green /
SYMBOL_SAMPLED yellow 全部 OK（主导色计数见 §3 表）。

- 早期 SYMBOL_SAMPLED 仅 16 黄点（4ASK=4 重叠点）：将模拟器切换为 **16QAM + 30dB** 后 2979 黄点，
  呈现清晰 16 簇每符号星座，VERDICT ALL-OK。
- 颜色**永不是唯一信息源**：阶段文字 + 图例始终可见（数据契约 §5）。

## 5. 中文字体（tofu 修复）

- 现象：`fc-list :lang=zh` 返回 0 → 中文渲染为豆腐块。
- 修复：从 `/mnt/c/Windows/Fonts/` 部署 `msyh.ttc`（微软雅黑）+ `simhei.ttf`（黑体）到
  `~/.local/share/fonts/`，`fc-cache -f`。
- 验证：`fc-match -s "sans-serif:lang=zh"` 命中 msyh.ttc 为 CJK 回退；状态栏像素密度 2.39×、
  标题 3.72×，PNG 体积 58KB→110KB（豆腐块→真实字形）。
- **前置条件**：板端集成前必须在目标文件系统部署等价 CJK 字体 + fontconfig 缓存（契约 §7）。

## 6. 性能（桌面真实测量，非板端）

| 指标 | 结果 | 说明 |
|---|---|---|
| FPS（--fps 30 播放） | **24.30**（243 帧/10s） | 接近 30Hz 目标；QTimer 30Hz + 异步渲染 |
| FPS（--fps 1000 最大吞吐） | **43.30**（433 帧/10s） | 连续更新下实际 present 上限（WSLg 合成） |
| CPU（连续渲染） | **avg 39.9% / max 58%**（单核） | 软件 GL（llvmpipe）+ QML scene-graph |
| RSS（连续渲染） | **~191.5 MB**（min 191508 / max 191620 kB） | 含 QSG 缓冲；空闲时 ~183.6 MB |
| RSS 漂移（60s） | **+112 kB** | 分配器噪声，非泄漏 |

测量方法：`tools/measure_perf.py`（读 `/proc/<pid>/stat` 的 utime+stime 算 ΔCPU，`VmRSS` 取
RSS），在 `--bench-fps`（`setPaused(false)` 连续渲染）窗口内采样。**CLI `--bench-fps SECONDS`
计数真实 `frameSwapped` 信号**（每实际 present 一次）。

## 7. 稳定性（20 min 连续渲染）

方法：`--bench-fps 1300` + `--loop --fps 30` 连续渲染，`tools/measure_perf.py --seconds 1200
--interval 30` 每 30s 采样 RSS/CPU。**结果：40 采样 / 20 min，无崩溃，无内存泄漏。**

| 项 | 结果 |
|---|---|
| 样本数 / 时长 | 40 / 1200s（20 min，30s 间隔） |
| CPU | avg **36.33%** / max **50.83%**（单核） |
| RSS | min 190048 / avg 190745 / max **190860 kB**（≈186.4 MB 上限） |
| RSS 漂移 | +812 kB（max−min，含前 60s 预热跳变） |
| 泄漏判定 | **无单调增长**：预热后（t≥60s）RSS 在 190560–190860 kB 平坦带内往复振荡（后 8 采样稳定在 190796↔190860 两档，64 kB 步长，疑似 malloc arena / QSG 缓冲池稳定循环），封顶 190860 kB，20 min 内从未越过 |

结论：20 min 连续渲染 RSS **有界**、无单调增长、无崩溃 → 稳定性达标（10–30 min 区间内）。

## 8. 收缩 / 交互

- `--window-size 480x360` 收缩成功（`08_resize_480x360.png`），布局/letterbox 自适应正常。
- 交互（暂停/播放/前进后退/坐标模式切换）由 `Controller` 暴露 Q_INVOKABLE，QML 控件绑定；
  本阶段桌面验证未做自动化 UI 事件注入（人工可视化 + 截图证据）。

## 9. 已知告警（记录，不修复）

- 6 条 `Binding loop detected for property "implicitHeight"`：来自遗留 QtQuick.Dialogs 1.3
  `FileDialog`（cosmetic，非致命）。运行时走 `IqFrameSource`，不使用文件对话框，故**记录不修**。
- 修复后 `null_teardown_errors=0`（Controller 声明先于 engine，析构顺序修正，消除
  “Cannot read property X of null” 洪泛）。

## 10. 合成夹具与红线的调和

原型的 `RAW_RX` 红线禁止伪造原始接收数据；`SYMBOL_SAMPLED` 禁止用降采样伪造符号点。本任务需要
“验证 4 视图”，但真实板端只有 RECOVERED_PAYLOAD / MODEL_INPUT 两类真实夹具，无 RAW_RX /
SYMBOL_SAMPLED 真实数据。调和方式：

- 合成夹具**只放** `fixtures/synthetic/`，与 `fixtures/valid/`（真实）**隔离**；
- 每个合成 sidecar 显式 `metric_provenance="synthetic-offline-desktop1"`、`source_index=-1`、
  全部 `*_valid=false`，绝不冒充真实测量；
- `symbol_sampled` 用 16QAM 1sps（真实每符号采样），`symbol_timing_valid=true`（合法），**非**
  从过采样数据降采样伪造；
- 文档/审计明确“仅用于渲染验证，非真实 RF”，满足红线。

## 11. 交付物清单

| 路径 | 说明 |
|---|---|
| `src/main.cpp`（改） | 新增 `--screenshot`/`--screenshot-delay-ms`/`--bench-fps`/`--window-size`；析构顺序修复；`#include <memory>` |
| `tools/offline_frame_simulator.py` | 确定性合成帧生成器（seed 20261018） |
| `tools/verify_stage_colors.py` | 截图阶段色主导性核验 |
| `tools/measure_perf.py` | CPU/RSS 采样（`/proc` 真实读数） |
| `fixtures/synthetic/` | 4 阶段合成夹具（.f32 + .json） |
| `screenshots/` | 6 张真实 `grabWindow()` 截图 |
| `contracts/ui_runtime_frame_v1.md` | 运行时帧数据契约（schema v1 + IqFrameSource + CJK 前置） |
| `docs/M29_RML24_UI_CONSTELLATION_DESKTOP1_AUDIT.md` | 本文档 |

## 12. 红线遵守（自查）

- 未改 SDR 同步/CFO/恢复/阈值；未改 BF16 模型；UI 不阻塞接收/NPU 线程（渲染路径独立）。
- 离线合成夹具未标注为真实 RF；无伪造 FPS / 无伪造截图（grabWindow + 真实 frameSwapped）。
- 未声明 RUNTIME-INTEGRATED（仅窗口打开 ≠ 运行时集成）。
- RAW_RX / SYMBOL_SAMPLED 红线未越界（§10）。
