# M24-A 集成接口（P1 模型无关离线模块 → M22/M23）

> 状态：`M24-P1-OFFLINE-MODULES-READY` / `24CLASS_MODEL_NOT_READY`
> 范围：本阶段只交付 6 个**模型无关**的离线模块与 24 类接口 stub，不接入
> Gate 9/10 主链路，不修改 M22/M23 任何交付物，不碰 RTL/XDC/位流，不启动 Vivado。

## 1. 模块清单与 namespace

所有模块在 `namespace m24` 下，头文件位于 `sdr_adapter/`，均为 header-only
（`inline` 函数 / 类内实现），可直接 `#include` 无需链接。

| 头文件 | 内容 | 依赖 |
|---|---|---|
| `m24_fft.hpp` | 基-2 DIT FFT（double）、Hann 窗、幅度/dB、fftshift、频率轴、噪声底、峰值检测、峰值保持 | 无（自足） |
| `m24_waterfall.hpp` | 定容环形缓冲瀑布图、时间序读取、显示降采样 | 无 |
| `m24_ui_scheduler.hpp` | 显示刷新调度（分类/控制优先、10–20 Hz 限速、最新帧合并） | 无 |
| `m24_patrol.hpp` | 自动巡检状态机（mock 适配器） | 无 |
| `m24_event.hpp` | 事件记录（去重合并/容量封顶/文件轮转/写失败 fail-closed） | 无 |
| `m24_class24_contract.hpp` | 冻结的 `[N,2,1024]→24` 输入输出契约 + 权威 24 类标签序 | 无 |
| `m24_class24_stub.hpp` | 24 类接口 stub（确定性假 logits，仅 SIMULATED） | `m24_class24_contract.hpp` |

## 2. 现在可直接接入 M22/M23 的模块（不依赖 24 类模型）

以下模块**完全模型无关**，可在不等待 24 类模型训练的情况下，直接作为独立
离线模块接入频谱监控链路（M22/M23）的**离线侧**，用于预研与主机测试：

1. **`m24_fft.hpp`（CPU 参考 FFT）** —— 频谱监控的谱分析基元。M22/M23 已有多信号/参数
   估计，本模块提供带窗、dB、fftshift、峰值检测、噪声底、峰值保持的参考实现，可作为
   M22 巡检/瀑布的离线谱源。**接入方式**：`#include "sdr_adapter/m24_fft.hpp"`，调用
   `m24::fft` / `m24::detect_peaks` 等。不改变任何现有数据链。
2. **`m24_waterfall.hpp`（瀑布图缓存）** —— 定容环形缓冲，内存 `capacity×cols×4` 字节
   恒定，不会无界增长。可直接作为离线瀑布/谱图的缓存层。
3. **`m24_ui_scheduler.hpp`（刷新调度）** —— 显示刷新限速与最新帧合并，**离线只产生
   渲染决策（帧号+统计）**，不写 framebuffer、不驱动真实 UI。可在主机离线验证
   10–20 Hz 刷新与合并语义后，再决定是否搬到真实 UI 层。
4. **`m24_patrol.hpp`（巡检状态机）** —— 纯逻辑状态机 + mock 适配器，STOP 在 O(1) 步内
   终止。可先用 mock 适配器离线跑通 11 态流转，之后替换 `PatrolAdapter` 的
   `tune/read_power_dbm/measure` 三个回调即可对接真实 RF（但**本轮不接真实 RF**）。
5. **`m24_event.hpp`（事件记录）** —— 事件去重/封顶/轮转/落盘，模型无关，可直接作为
   巡检/信号事件的记录层。

## 3. 必须等待 24 类模型训练完成的模块

6. **`m24_class24_stub.hpp`（24 类接口 stub）** —— **只能用于接口/UI 开发与契约测试**，
   不能用于任何真实分类结果。它固定 `[N,2,1024]→24` 形状与标签序，输出**确定性假
   logits**，每个结果都标记 `simulated=true`，**绝不写 `24CLASS_PASS`，绝不报告假
   logits 准确率**。

   **真实 24 类分类**（正式模型 `raw logits`、`argmax`、`class_name`）必须等到 24 类
   模型训练完成，见 `docs/M24_A_CLASS24_TODO.md`。在此之前，任何接入主链路、对标
   `12CLASS_CHAIN_VALIDATION_MODEL` 的动作都是禁止的（红线）。

## 4. 明确不做的集成（红线）

- **不**接入 Gate 9/10 主链路。
- **不**修改 M22/M23 交付物（`m23_*.hpp`、`ood_u_*`、`test_m23_p0.cpp` 等）。
- **不**修改 RTL/XDC/位流，不启动 Vivado。
- **不**用 pilot checkpoint 冒充最终 24 类模型。
- **不**伪造 NPU 模型 / 假 logits 准确率。
- **不**改动 12 类模型 / 触摸语义 / UI 布局。
- **不**逐帧向串口刷日志。
- **不**生成冒充可上板验收的全量包。

## 5. 接口契约速览

```cpp
// FFT
m24::Spectrum s = m24::fft(const std::complex<double>*, std::size_t n);
//   s.valid==false 当 null / n 非 2 的幂 / NaN/Inf（fail-closed）

// 瀑布图
m24::Waterfall wf(capacity_rows, cols);
wf.push(frame);                    // 新帧覆盖最旧，内存恒定
auto flat = wf.read_oldest_first(); // 时间序（最旧→最新）
auto row  = wf.downsample_newest(k);// 显示降采样

// 刷新调度（默认关闭=逐帧直渲）
m24::UiRefreshScheduler sched;
sched.configure(12.0);             // 10..20 Hz，<=0 关闭
sched.submit_spectrum(frame_id);   // 只保留最新待渲帧
bool render = sched.tick(now_s);   // true=现在渲染
sched.submit_control(event_id);    // 控制/分类永不限速、不合并

// 巡检（mock）
m24::PatrolStateMachine patrol;
patrol.configure(cfg); patrol.start();
patrol.step(now_s, mock_adapter);  // 每次一步转换；stop() 后 1 步内 STOPPED

// 事件
m24::EventRecorder rec;
rec.configure(capacity, merge_cfg);
rec.set_sink([&](const std::string& line){ return sink.write(line); });
rec.record(e);                     // 去重合并/封顶；写失败 fail-closed

// 24 类 stub（SIMULATED ONLY）
m24::Class24Stub stub;
m24::Class24Manifest m; m.model_sha256 = /* 64 hex, 缺失则拒载 */;
stub.load(m);
auto r = stub.classify(iq, n);     // 恰好 24 维，r.simulated 恒真
```
