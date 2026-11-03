# M29 RML23 星座图离线原型 交付审计

- 状态令牌（唯一，不更高）：**`M29-RML23-UI-CONSTELLATION-OFFLINE-PROTOTYPE-READY-FOR-INTEGRATION-REVIEW`**
- 交付日期：2026-10-17
- 工作目录（唯一写入位置）：`F:\嵌赛\constellation_ui_prototype\`
- 只读参考树（未写入）：`F:\嵌赛\fix10prep2_work\`、`F:\嵌赛\fix10prep3_work\`、`F:\嵌赛\fix10clean2b_work\`、`F:\FPGA_Work\`、`F:\嵌赛\enclosure_cad\`
- 未写入任何禁止令牌：`BOARD_UI_PASS` / `LIVE_IQ_PASS` / `SDR_UI_PROVEN` / `FINAL_UI` / `PROJECT_COMPLETE`

## 1. 结论摘要

- 纯离线、真实 IQ 的星座图散点查看器（Qt/QML + C++ 场景图）**源码与夹具全部交付**。
- **Qt-free 核心单测 18/18 通过（82 断言，0 失败）**，在 WSL（g++ 15.2，`-O2 -Wall -Wextra`）编译运行。
- **GUI 目标 NOT-RUN**（本机无 Qt 可用 C++ 工具链：无 MSVC/MinGW/clang/cmake），未伪造任何截图/帧率/板测结论。
- 未碰板、未碰 SDR、未改任何既有板端 UI 或 fix10prep3/clean2b 参考树、未改 `/run/sdr_amr_ui_rml23.sock` 协议、未含模型权重/分类算法。

## 2. Phase 0 只读审计

已完成并写入 `docs/existing_ui_readonly_audit.md`。要点：

- 板端既有 UI = 无 Qt / 直接帧缓冲 `ui::Canvas` RGB565 / ASCII 风格 / 1280×720 / 无 GPU；历史桌面侧曾用 Qt 5.15 QML。
- 板端 socket = AF_UNIX SOCK_STREAM，JSON-lines，schema `rml23-chain-v2`（只读，未改）。
- CFO/SRO/增益来自 `iq_rf_sync_recovery.hpp` 的 `PerFileRecovery`。
- 本原型为**桌面 Qt 5.15 QML + C++ QQuickItem 场景图**新工程，与板端 UI 完全隔离。

## 3. 技术路线（按要求）

- C++ 读/校验/缓冲 → C++ `QQuickItem`/`QSGGeometryNode` 散点 → QML 页面。
- **禁止**持续刷新的 QML Canvas 画点 —— 本实现无 Canvas，散点全部由 `ConstellationItem`（`QSGVertexColorMaterial` + `QSGGeometry::ColoredPoint2D`，每点一个 4 顶点/6 索引四边形）绘制。
- 二进制解析/SHA-256/抽稀/自动缩放全在 Qt-free C++（`IqFrame.hpp`/`IqFrameLoader.cpp`），QML 不做任何二进制/逐点 JS。

## 4. 交付文件清单

```
src/IqFrame.hpp              Qt-free 核心：Stage/DType/Layout 枚举、IqFrame、
                             IqFrameSource 接口、小端读取、SHA-256(FIPS 180-4)、
                             扁平 JSON 解析、确定性抽稀、稳健自动缩放、单位坐标变换
src/IqFrameLoader.hpp/.cpp   fail-closed 加载链 + list_sidecars + FileIqFrameSource
src/ConstellationItem.hpp/.cpp  QQuickItem 场景图散点渲染器
src/main.cpp                 Controller(Q_PROPERTY/Q_INVOKABLE) + main()/CLI 参数
qml/Main.qml                 应用窗口（状态栏/星座屏+指标/播放栏）
qml/StatusBar.qml            顶部状态栏（OFFLINE 徽章，绝不显示 LIVE）
qml/ConstellationScreen.qml  左 ~70% 星座屏（标题+图例+绘图区+页脚）
qml/ConstellationPlot.qml    绘图区（网格/坐标轴/原点/刻度标签 + C++ 散点）
qml/MetricsPanel.qml         右 ~30% 指标面板
qml/PlaybackBar.qml          底部控制栏（打开/上一帧/下一帧/坐标/点数/暂停/截图/导出）
qml/Theme.qml                配色/字号单一来源
qml/LegendDot.qml, MetricRow.qml  图例点/指标行小部件
qml/qmldir                   模块清单（文档用；同目录解析不依赖它）
qml.qrc                      QML 资源嵌入
CMakeLists.txt               iqframe_core + test_iqframe（无 Qt）+ constellation_viewer（有 Qt）
tests/test_iqframe.cpp       14 必测 + 4 附加，共 18 用例 / 82 断言
bench/bench_prep.cpp         纯 C++ 每帧路径微基准（诚实下限，非 GUI FPS）
fixtures/*.f32/.ci16/.json   真实 IQ 夹具（见 fixtures/SOURCES.md）
fixtures/SOURCES.md          夹具来源路径 + 原始 SHA + 占位字段说明
docs/existing_ui_readonly_audit.md  Phase 0 只读审计
docs/data_format.md           数据格式约定
docs/future_live_integration.md    未来实时集成接口（仅 FileIqFrameSource 实现）
docs/performance_report.md    性能报告（GUI NOT-RUN + C++ 微基准实测）
README.md                     构建说明 + 诚实构建/运行状态
```

## 5. 测试结果

- 命令（WSL Ubuntu，g++ 15.2）：`g++ -std=c++17 -O2 -Wall -Wextra -I../src test_iqframe.cpp ../src/IqFrameLoader.cpp -o test_iqframe && ./test_iqframe ../fixtures`
- 结果：**18 用例通过 / 82 断言通过 / 0 失败**，`-Wall -Wextra` 零警告。
- 覆盖：CI16 interleaved、F32 planar/interleaved、小端、错误长度拒绝、错误 SHA 拒绝、NaN/Inf 拒绝、未知 schema/dtype/layout/stage 拒绝、1024 点坐标变换、确定性抽稀、稳健自动缩放、空帧/全零帧、SHA-256 标准向量、真实夹具 SHA 验证、SYMBOL_SAMPLED 红线、扁平 JSON 解析器。
- **UI 测试 / 桌面性能门禁：NOT-RUN**（无 Qt 工具链，诚实记录，未伪造）。

## 6. 夹具（真实数据，字节级一致）

来源 `F:\嵌赛\fix10clean2b_work\clean2b_smoke\`（只读），复制后 SHA 逐字节一致，见 `fixtures/SOURCES.md`。`confidence`（0.98/0.96）为**示意占位**（本 UI 不跑模型），已在 SOURCES.md 与 data_format.md 注明。负样本（wrong_sha/wrong_length/nan_inf）均经单测验证 fail-closed。

## 7. 红线遵守核对

- 无板、无 SDR、无 socket、无 live 数据 —— 遵守（纯离线文件）。
- 不改既有板端 UI / fix10prep3 / clean2b —— 遵守（只读参考，新目录写入）。
- 不伪造演示点 —— 遵守（只绘制真实文件点；无默认合成数据）。
- 不过采样冒充符号采样 —— 遵守（SYMBOL_SAMPLED 仅当 `symbol_timing_valid=true`，否则 loader 拒绝；夹具全部 false → 视图 DISABLED）。
- 不改模型输入 / 无分类算法 / 无模型权重 / 无网络传输 —— 遵守。
- 不声明板端性能通过 —— 遵守（仅桌面/WSL 实测与 NOT-RUN 记录）。
- 停止点：交付离线原型/测试/审计后停止，未进入任何 prep2 实时集成阶段 —— 遵守。

## 8. 待用户决策项

1. GUI 需在具备 Qt 5.15 + C++ 编译器的桌面环境构建（`cmake -B build && cmake --build build`），复测 4 项桌面性能门禁与截图。
2. `confidence` 为占位值；如需真实模型置信度，须接入真实 NPU 前向输出（属实时集成阶段，超出本离线原型范围）。
3. 实时集成（UnixSocket/SharedMemory 来源）为未来阶段，本阶段只定义接口、不做实现。

## 9. hotfix1（ui-constellation-prep1-hotfix1）

状态令牌更新为：**`M29-RML23-UI-CONSTELLATION-HOTFIXED-AWAITING-QT-GUI-TEST`**（源码 hotfix 完成、Qt-free 测试与 qmllint 通过；GUI 已离屏烟测通过——`QT_QPA_PLATFORM=offscreen timeout 10 ./build/constellation_viewer --fixture-dir fixtures/valid --fps 1` 退出码 124、日志 0 字节、QML 加载无报错，补装 `qml-module-qtquick-controls` 5.15.18 后 `QtQuick.Controls 1.2` 缺失告警消失；仅当真实显示器上 Qt 构建+运行+交互+截图后才可写 `M29-RML23-UI-CONSTELLATION-DESKTOP-GUI-VERIFIED`）。

8 项修复：

- **4.1 SpinBox**：`PlaybackBar.qml` 的自定义范围 SpinBox 改为整数后端 ×100（`from:10/to:10000/stepSize:10`），`textFromValue`/`valueFromText` 用 `Number.fromLocaleString` 做 locale 安全解析，删除 Qt 5.15 不存在的 `decimals` 属性。
- **4.2 Layout 尺寸**：`Main.qml` 中段改回 `RowLayout`（`Layout.preferredWidth 7:3` + `fillWidth/fillHeight` + `minimumWidth`）；`StatusBar`/`PlaybackBar` 根项 `height` → `implicitHeight`（随字号增长）；徽章 `width/height` → `Layout.preferredWidth/preferredHeight`；`MetricsPanel` 分隔线 `height:1` → `Layout.preferredHeight:1`。全项目已无「Layout 直接子项裸 width/height」或「anchors+Layout 混用」。
- **4.3 错误显示**：`StatusBar.qml` 新增独立持久错误槽（红色+文字+`×`清除+ToolTip 完整文本），正常校验状态（绿色）与错误分离；`Controller.loadCurrent()` 成功时不再清空 `error_text_`，新增 `clearError()`，错误不被下一条正常状态静默覆盖。
- **4.4 夹具语义**：移除伪 RAW_RX —— `bpsk_raw_rx.ci16`（实为 clean2b D2 TX/冻结载荷）与旧 sidecar 移入 `fixtures/obsolete/`；不新增伪造 RAW_RX；UI 星座屏下方显示「RAW_RX 暂无真实夹具」。
- **4.5 指标有效性**：`IqFrame`/loader/sidecar 新增 `confidence_valid`/`recovery_metrics_valid`/`gain_valid`/`cfo_valid`/`sro_valid`/`metric_provenance`；`gain_mag` 与 `d2_rec_scale` 分离（恢复标量绝不显示为 RF gain）；缺省策略 = 缺失字段按 false（不可用）fail-closed；UI 显示「占位/不可用」「不可用」，不把 0 当作真实测量 0。
- **4.6 QSG 刷新**：`ConstellationItem.cpp` 在改写几何（顶点/索引/逐点颜色）后显式 `node->markDirty(QSGNode::DirtyGeometry)`（含空点分支）。
- **4.7 夹具分离**：`fixtures/valid/`（4 帧，全通过）+ `fixtures/negative/`（7 个负样本：wrong_sha/wrong_length/nan_inf + 新增 unknown_schema/unknown_dtype/unknown_layout/unknown_stage）。正常 `--fixture-dir fixtures/valid` 不会在第 5 帧失败。
- **4.8 无障碍**：所有按钮 `focusPolicy: Qt.StrongFocus`（Tab 可达、顺序=视觉顺序）；ComboBox/SpinBox 加 `Accessible.name`；`LegendDot` 加 `Accessible.ignored`；错误为红色+文字（非纯颜色）；中文经 `qsTr()`；1280×720 不截断；状态栏/播放栏高度随字号增长避免大字号遮挡。

测试：

- **5.1 Qt-free**：22/22 通过、111 断言、0 失败（WSL g++ 15.2，`-O2 -Wall -Wextra` 零警告）。新增 4 个用例：有效性字段解析+缺字段 fail-closed、valid/negative 目录隔离、禁止伪 RAW_RX、d2_rec_scale 与 RF gain 不混用。
- **5.2 QML 静态检查**：Anaconda Qt 5.15 自带 `qmllint` 对 9 个 QML 文件运行，0 诊断（exit 0）；用故意损坏的 QML 探针确认该 qmllint 会以非零退出码拒绝坏语法。退出码 0 不替代真实 GUI 运行。
- **5.3 GUI 构建**：**WSL BUILT**（2026-10-17，`build/constellation_viewer` 210640 B，Ubuntu g++ 15.2 + Qt 5.15.18）。Windows 原生仍缺 MSVC/MinGW/cmake；GUI 构建在 WSL Ubuntu 完成（该 WSL 有完整 Qt 5.15 + g++ 工具链）。
- **5.4 桌面验收**：**离屏烟测通过**（offscreen QML 加载无错、10 秒存活、日志 0 字节），但**真实显示器交互+截图未做**——`M29-RML23-UI-CONSTELLATION-DESKTOP-GUI-VERIFIED` 仍待用户在有显示器的桌面（WSLg 或 Linux 桌面）交互+截图确认。未伪造截图/FPS/CPU/内存结果。

板端边界：板端 UI = `ui::Canvas` RGB565 直接帧缓冲，1280×720，无 Qt/GPU；本 Qt 原型未集成到板端，实时集成仍为独立阶段。

