# M29 RML23 星座图离线原型（Qt/QML + C++ 场景图）

纯**离线**真实 IQ 星座图散点查看器。读取真实 `.ci16` / `.f32` + JSON sidecar，只绘制**真实**点（绝不伪造演示点），验证性能/规模/格式/交互。不碰板、不碰 SDR、不接 socket、无 live 数据、不含模型权重/分类算法。

- 状态令牌：**`M29-RML23-UI-CONSTELLATION-HOTFIXED-AWAITING-QT-GUI-TEST`**
- 详细审计见 `docs/M29_RML23_UI_CONSTELLATION_OFFLINE_PROTOTYPE_AUDIT.md`（含 hotfix1 章节）

## 目录

```
src/         C++ 核心（Qt-free 数据层 + Qt 场景图渲染 + Controller）
qml/         QML 页面（状态栏/星座屏/绘图区/指标/播放栏/主题）
tests/       14 必测 + 4 附加 + 4 hotfix1 单元测试（Qt-free，已通过）
bench/       每帧 C++ 路径微基准（诚实下限，非 GUI FPS）
fixtures/    真实 IQ 夹具 + sidecar（valid/ 正常帧、negative/ 负样本、obsolete/ 已移出）
docs/        只读审计 / 数据格式 / 实时集成接口 / 性能报告 / 交付审计
```

## 诚实构建状态（本交付机）

| 目标 | 状态 |
|---|---|
| Qt-free 单元测试 `test_iqframe` | **已编译并运行，22/22 通过（111 断言，0 失败）**，WSL Ubuntu g++ 15.2 |
| QML 静态检查 `qmllint` | **已运行，9 个 QML 文件 0 诊断**（Anaconda Qt 5.15 自带 qmllint；退出码 0 不替代真实 GUI 运行） |
| GUI `constellation_viewer` | **NOT-RUN**：本机无 Qt 可用 C++ 工具链（无 MSVC/MinGW/clang/cmake；Anaconda 有 Qt 5.15.2 的 qmake/moc/qmlscene/qmllint，但缺 C++ 编译器） |

**没有伪造任何截图、FPS 或 GUI 测试结果。** 源码全部交付，在具备 Qt 工具的机器上按下面步骤即可构建。

## 构建

### 1. Qt-free 单元测试（任意 C++17 编译器，无需 Qt）

```bash
cd tests
g++ -std=c++17 -O2 -Wall -Wextra -I../src test_iqframe.cpp ../src/IqFrameLoader.cpp -o test_iqframe
./test_iqframe ../fixtures          # fixtures 根目录；valid/ 与 negative/ 由测试解析
```

或：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build              # 运行 iqframe_unit
```

### 2. GUI（需要 Qt 5.15：Quick + QuickControls2 + Qml）

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/constellation_viewer --fixture-dir fixtures/valid --fps 1
# 或单帧：  ./build/constellation_viewer --sidecar fixtures/valid/bpsk_clean_model_input.json
# 循环播放： ./build/constellation_viewer --fixture-dir fixtures/valid --fps 2 --loop
```

Windows + MSVC：

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_PREFIX_PATH="$env:CONDA_PREFIX\Library\lib\cmake"
cmake --build build --config Release
```

## 运行（GUI 构建成功后）

- **打开数据…**：选择单个 sidecar `*.json`（与其同目录的二进制文件会被加载）。
- **打开目录…**：列出目录内全部 `*.json` sidecar，按 `frame_id` 排序，用“上一帧/下一帧”或“继续/暂停”播放。**正常播放请指向 `fixtures/valid/`**（4 帧，全部通过校验，不会在第 5 帧失败）。
- 坐标模式：自动（98 分位稳健缩放）/ 固定 ±1 / 固定 ±2 / 自定义；越界点红色（钳位绘制、不丢弃）。自定义范围使用整数后端 ×100 的 SpinBox（Qt 5.15 SpinBox 无 `decimals`）。
- 点数上限：1024 / 2048 / 4096（确定性等间隔抽稀，非随机）。
- 截图 / 导出帧 JSON / 导出当前点 CSV / 导出诊断 —— 均写入当前目录，时间戳命名；导出 JSON/诊断带有效性字段与 `d2_rec_scale`。
- 损坏帧（长度/SHA/NaN/Inf/未知 schema/dtype/layout/stage…）在状态栏给出**持久红色错误文字**并**停止**，绝不自动跳过；错误可用「×」显式清除，不会被下一条正常校验状态覆盖。
- **指标有效性**：`confidence_valid` / `cfo_valid` / `sro_valid` / `gain_valid` / `recovery_metrics_valid` 缺失或为 false 时，UI 显示「占位/不可用」/「不可用」，绝不把数值 0 当作“真实测得的 0”；恢复标量以 `d2_rec_scale` 显示，**绝不冒充 RF `gain_mag`**。
- **RAW_RX 无真实夹具**：本原型未包含真实板端采集的原始接收数据，也不把 clean2b 的 D2 TX/冻结载荷冒充 RAW_RX；星座屏下方明确显示「RAW_RX 暂无真实夹具」。

## 红线（务必遵守）

- 无板、无 SDR、无 socket、无 live 数据；不修改 `/run/sdr_amr_ui_rml23.sock` 协议。
- 不改任何既有板端 UI / fix10prep3 / clean2b 参考树。
- 不伪造演示点；不过采样冒充 SYMBOL_SAMPLED；不改模型输入；无分类算法；无网络传输。
- 不伪造 RAW_RX：没有真实板端接收数据就不新增 RAW_RX 夹具。
- 只记录桌面（含 WSL 纯 C++）结果，不声明板端性能。
