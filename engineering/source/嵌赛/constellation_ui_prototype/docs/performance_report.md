# 性能报告（performance_report.md）

## 诚实结论：GUI 性能门禁 = NOT-RUN

本交付机（Windows 11）上**没有可用的 Qt C++ 工具链**（无 MSVC `cl.exe`、无 MinGW、无 clang、无 cmake；Anaconda 装有 Qt 5.15.2，但只有 win32-msvc 规范且缺编译器）。因此：

- GUI **无法在本机编译/运行**；
- 以下桌面 GUI 性能门禁一律 **NOT-RUN**（未运行，未伪造任何数字）：
  - 1024 点 ≥ 30 FPS；
  - 4096 点 ≥ 20 FPS；
  - 10 分钟无内存增长；
  - UI 解析阻塞 ≤ 100 ms。

**没有伪造任何截图、FPS 或内存数据。** 一旦在有 Qt 工具的机器上构建 `constellation_viewer`，按 README 的步骤即可复测这些门禁。

## 本机可诚实给出的替代测量（WSL + g++ 15.2，纯 C++，非 GUI FPS）

`bench/bench_prep.cpp` 测量每帧 C++ 数据路径（fail-closed 加载含 SHA-256 + 抽稀 + 单位坐标变换）。这是 GUI 每帧最重的纯 C++ 部分，给出**预算下限**而非帧率：

| 帧 | 复数点数 | 加载（含 SHA-256，最小 20 次） | 4096 点变换（最小 200 次） |
|---|---|---|---|
| `bpsk_clean_model_input.json`（8 KB planar f32） | 1024 | 2.3 ms | < 0.01 ms |
| `bpsk_recovered_payload.json`（8 KB planar f32） | 1024 | 2.3 ms | < 0.01 ms |
| `bpsk_raw_rx.json`（215 KB interleaved ci16） | 53760 | 5.2 ms | < 0.01 ms |

说明：

- 以上是 **WSL 通过 /mnt/f（9p 桥接 NTFS）读盘**的冷缓存数值；原生桌面文件系统会更快。数字仅代表“C++ 每帧预处理成本”。
- 即便按最坏 5.2 ms 计，也远低于 33 ms（30 FPS）和 50 ms（20 FPS）的每帧预算，也低于 100 ms 的解析阻塞红线。
- 4096 点抽稀 + 单位变换是纯元素级乘加，`-O2` 下自动向量化，实测为微秒级以下；**渲染本身是 C++ 场景图（QSGGeometryNode + QSGVertexColorMaterial，每点一个 4 顶点/6 索引四边形），无 QML JS 解析、无 Canvas、无逐点 QML 对象**，这是满足帧率门禁的设计依据，而非实测值。

## 设计上支撑门禁的依据（非实测）

1. 二进制解析、SHA-256、抽稀、自动缩放**全部在 C++**；QML 不做任何二进制/逐点 JS。
2. 默认显示 1024 点、上限 4096 点，使用**确定性等间隔抽稀**（`decimate_indices`，非随机、无闪烁）。
3. 每帧仅一次 `setPoints()` 推送（QVector<QPointF> + QVector<QColor>），渲染器一次性重建 geometry；点数是恒定的（抽稀后 ≤ 4096），**无每帧分配增长**。
4. `auto_scale_range` 是 98 分位稳健缩放，少数离群点不会让主体塌缩。

## 结论

- **GUI 性能门禁：NOT-RUN**（无 Qt 工具链，诚实记录）。
- **C++ 数据路径微基准（WSL）：已实测**，单帧预处理在最坏情况下 ~5.2 ms，远低于帧率/阻塞预算。
- 待用户在具备 Qt 的桌面环境构建后复测真实 GUI FPS。
