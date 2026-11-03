# M24-A 交付报告（P1 模型无关离线模块预研）— errata1

> 状态：**`M24-P1-OFFLINE-MODULES-READY`** / **`24CLASS_MODEL_NOT_READY`**
> 工程：`sdr_full_chain_spectrum_monitor_m22_m24/work/pkg/`
> 日期：2026-10-09
> errata1 说明：仅测试/工具/文档层增量，**7 个模块头文件字节不变**，未覆盖 b20f8bc… 旧包。

## 0. 范围与红线

本阶段交付 6 个**模型无关**的离线模块 + 1 个 24 类接口 stub，全部为新增独立文件，
**未修改任何 M22/M23 交付物**，未改 RTL/XDC/位流，未启动 Vivado，未接 Gate 9/10 主链路，
未用 pilot checkpoint 冒充 24 类模型，未伪造 NPU 模型 / 假 logits 准确率，未逐帧刷串口，
未生成冒充可上板验收的全量包。24 类正式模型**尚未训练**。

errata1 相对 b20f8bc… 旧包**只改测试、工具与文档**：扩充 FFT 数值测试、新增统一性能基准
`m24_bench`、把 ASan/UBSan 拆成两个独立脚本。7 个模块头文件（`m24_*.hpp`）**字节一致**，
故采用版本化新增 errata 补丁，**不覆盖** b20f8bc… 旧包。

## 1. 交付物清单（新增文件，19 个）

**模块（`sdr_adapter/`，namespace `m24`，header-only，本轮未改动）**
1. `m24_fft.hpp` — 基-2 DIT FFT（double）+ Hann 窗 + 幅度/dB + fftshift + 频率轴 + 噪声底 + 峰值检测 + 峰值保持，非法参数/NaN/Inf fail-closed
2. `m24_waterfall.hpp` — 定容环形缓冲瀑布图，新帧覆盖最旧，时间序读取，显示降采样，显式内存
3. `m24_ui_scheduler.hpp` — 刷新调度：分类/控制优先、10–20 Hz 可配、只保留最新谱帧、中间帧合并、默认关闭
4. `m24_patrol.hpp` — 巡检状态机 11 态 + mock 适配器，STOP O(1)
5. `m24_event.hpp` — 事件记录：字段完整、去重合并、容量封顶、文件轮转、写失败 fail-closed
6. `m24_class24_contract.hpp` — 冻结 `[N,2,1024]→24` 契约 + 权威 24 类标签序
7. `m24_class24_stub.hpp` — 24 类接口 stub：缺 SHA 拒载、恰 24 维、确定性假 logits、恒 `simulated=true`

**测试/工具**
8. `host_tests/test_m24_a.cpp` — 模块测试（数值误差/容量/刷新统计/频率误差实输出，非裸 PASS）
9. `host_tests/build_m24_a.sh` — `-O2 -Wall -Wextra -Werror` 构建
10. `host_tests/run_m24_a.sh` — release 运行
11. `host_tests/run_m24_a_asan.sh` — ASan（仅 address）构建并运行
12. `host_tests/run_m24_a_ubsan.sh` — UBSan（仅 undefined）构建并运行
13. `host_tools/m24_replay.cpp` — 离线 IQ 回放工具（合成/文件 IQ → FFT→瀑布→巡检→事件）
14. `host_tools/build_m24_replay.sh` — 回放工具构建
15. `host_tools/m24_bench.cpp` — 统一性能基准（纯 FFT / FFT+窗 / 完整流程，固定参数）
16. `host_tools/build_m24_bench.sh` — 基准构建

**文档**
17. `docs/M24_A_INTEGRATION_INTERFACE.md` — 哪些模块现在接 M22/M23、哪些等 24 类模型
18. `docs/M24_A_CLASS24_TODO.md` — 24 类训练完成后的接入清单与红线
19. `docs/M24_A_DELIVERY_REPORT.md` — 本文

## 2. 验证结果（真实数值，非裸 PASS）

### 2.1 测试数量（澄清：无“pass=6”这类含义不明的裸计数）

| 配置 | 断言总数 | 通过 | 失败 |
|---|---|---|---|
| release（`-O2 -Wall -Wextra -Werror`） | **89** | 89 | 0 |
| ASan（`-fsanitize=address`，leak 开） | **89** | 89 | 0 |
| UBSan（`-fsanitize=undefined`） | **89** | 89 | 0 |

末尾输出统一为 `== result: assertions=89 passed=89 failed=0 ==`（release/ASan/UBSan 三套各自独立打印）。

**shell 脚本数 = 6**（`build_m24_a.sh`、`run_m24_a.sh`、`run_m24_a_asan.sh`、
`run_m24_a_ubsan.sh`、`build_m24_replay.sh`、`build_m24_bench.sh`），全部 `bash -n`
语法通过并各自执行成功（成功尾标 `BUILD_M24_A_OK` / `M24_A_ASAN_OK` / `M24_A_UBSAN_OK`
/ `BUILD_M24_BENCH_OK` 等）。

### 2.2 离线回放（`m24_replay --tone 2405000000 --frames 200`）

```
# frames processed       = 200
# scheduler submitted=200 rendered=131 coalesced=69 control=0
# patrol findings        = 9 (state STOPPED)
# events distinct=5 merged=4 dropped=0 write_failed=0
```

## 3. FFT 数值测试结果（对应“补充 FFT 测试”要求）

统一约定：`fs=128000 Hz`、`n=1024`，bin 宽 `= fs/n = 125 Hz`；FFT 未归一化（峰值
`|X[m]| == A·n`）；幅度恢复 `A = |X[m]|/n`。

### 3.1 bin 中心单音
- 单音 `16000 Hz`（= bin 128）、`A=1000`：**频率误差 0.000 Hz（0.000 bin）**，
  **幅度误差 −0.000**（`|X[128]|/n == 1000.000`，容差 1）。

### 3.2 偏离 bin 的单音（0.25 / 0.37 / 0.49 bin）
峰值 bin 估计器（nearest-bin）报告频率 = `峰值bin × bin宽`，误差如下：

| 偏移 | 真实频率 (Hz) | 估计 (Hz) | 误差 (Hz) | 误差 (bin) |
|---|---|---|---|---|
| +0.25 bin | 16031.250 | 16000.000 | −31.250 | **−0.250** |
| +0.37 bin | 16046.250 | 16000.000 | −46.250 | **−0.370** |
| +0.49 bin | 16061.250 | 16000.000 | −61.250 | **−0.490** |

**分辨率限制（诚实声明）**：本实现只支持**峰值 bin 估计**，单音频率分辨率为
**±0.5 bin = ±fs/(2n) = ±62.5 Hz**。它**不是**“0 Hz 通用精度”——非 bin 对齐时最坏
误差就是 ±0.5 bin，测试显式断言 `|err_bins| ≤ 0.5` 而非 0。

### 3.3 Hann 窗下的幅度修正
周期 Hann 相干增益 `sum(w) = n/2`，`w[0]=0`、`w[n/2]=1`。bin 对齐单音加窗后
`|X_w[m]| = A·n/2`，故幅度恢复 `A = 2·|X_w|/n`。实测 `raw |X_w| = 512000.0`（= A·n/2），
修正后 `A = 1000.000`，误差 < 0.001。

### 3.4 双音分辨（1 / 2 / 4 bin 间隔，Hann 窗，A1=1000 / A2=700）
“分辨”定义 = 检测到的峰值落在真实频率 ±0.5 bin 内。峰值阈值取噪声底之上 40 dB
（本无噪合成场景里“噪声底”是双精度 FFT 泄漏 ~−173…−232 dB，信号 105…114 dB，40 dB
干净分开真实峰与数值泄漏）。

| 间隔 | 峰数 | 强音 f1=10000 分辨 | 弱音 f2 分辨 | 结论 |
|---|---|---|---|---|
| 1 bin | 2* | 是 | **否**（弱音旁瓣成肩，非真峰） | 未分辨 |
| 2 bin | 1 | 是 | **否** | 未分辨（合并） |
| 4 bin | 2 | 是 | **是**（10500 Hz） | **分辨** |

\* 1 bin 间隔的“第 2 个峰”是弱音（700）旁瓣在 +2 bin 处的肩，频率 10250 Hz ≠ 真值
10125 Hz，故判定为“未分辨”——这正是 Hann 主瓣 ~4 bin 宽的体现，**不夸大**为已分辨。

**双音分辨限制（诚实声明）**：Hann 主瓣 ~4 bin 宽，两音需 ≥4 bin 间隔才能分辨；
≤2 bin 间隔合并。单音 nearest-bin 仍是 ±0.5 bin。

### 3.5 不同幅度与不同 FFT 长度
- 幅度线性：A = 1 / 10 / 1000（bin 对齐）均满足 `|X|/n == A`，误差 ≤ A·1e-6。
- 长度 n = 256 / 512 / 1024 / 2048：峰值 bin = n/8（16000 Hz），`|X|/n == 1000.000`，
  峰值 bin 随 n 线性缩放正确。

## 4. 统一性能基准（对应“统一性能基准”要求）

**环境**：WSL2（kernel 6.18.33.2），CPU `13th Gen Intel Core i9-13900H`，
`g++ 15.2.0`，编译 `-std=gnu++17 -O2`（`build_m24_bench.sh`）。固定参数 `n=1024`、
`fs=128000 Hz`、单音 `16000 Hz`（bin 128）、`A=1000`、`N=1000` 帧、每阶段预热一遍。

| 阶段 | 耗时 (µs/帧) |
|---|---|
| 纯 FFT（`m24::fft`，含其内部 16 KiB 工作缓冲分配） | **13.16** |
| FFT + Hann 窗（`apply_window` + `fft`） | **16.26** |
| 完整频谱流程（窗→FFT→幅度→dB→fftshift→噪声底→峰值检测） | **46.54** |

开销分解：窗 +3.10 µs；dB/fftshift/噪声底/峰值检测 +30.28 µs。

### 4.1 解释 12.15 µs 与 29.80 µs 的差异

两个旧数字来自**不同测量上下文**，不是真实速度差异：

- **12.15 µs**：来自 `m24_replay` 的逐帧“mean FFT time”（200 帧、进程/分配器已热、
  全回放链内摊薄）——这是**热稳态**的每帧 FFT 成本。
- **29.80 µs**：来自旧版 `test_m24_a.cpp` 里一段**临时**计时块（1000 次裸 `fft()` 紧循环），
  该块**没有预热**，把冷启动（冷分配器 / 缺页 / 冷 TLB）一起计入了均值，因此**高估**了
  每帧成本。
- **新统一基准**用同一套固定方法（N=1000、预热、预建输入、稳态均值）实测**纯 FFT =
  13.16 µs**，与 12.15 µs 一致，确认 29.80 µs 是冷启动/测量方法伪影，**已被 m24_bench 取代**。
  旧临时计时块已从测试中删除。

## 5. 十问（最终报告必答）

### Q1. FFT 频率与幅度误差是多少？
- bin 对齐单音：**频率误差 0.000 Hz**，**幅度误差 ≈ 0**（`|X[m]| == A·n` 严格成立）。
- 非 bin 对齐（nearest-bin）：**±0.5 bin = ±62.5 Hz**（`fs/(2n)`），**不是 0 Hz 通用精度**。
- 双音 4 bin 间隔（Hann）：**2 峰分辨**，峰频 10000 / 10500 Hz（误差 0 bin）。

### Q2. 单次 FFT 耗时？
- 统一基准（i9-13900H、g++ 15.2.0、`-O2`）：**纯 FFT 13.16 µs**、FFT+窗 16.26 µs、
  完整流程 46.54 µs（/1024 点）。旧的 29.80 µs 为冷启动测量伪影，已废弃（见 §4.1）。

### Q3. 10/20 Hz 刷新时 CPU 负载估算？
- 完整流程 46.54 µs/帧：20 Hz → 20×46.54 µs ≈ **0.93 ms/s ≈ 0.09% 单核**；
  10 Hz → **≈ 0.05% 单核**。（纯谱分析，不含真实采集/预处理。）

### Q4. 瀑布图内存？
- 内存 = `capacity × cols × 4 B`，构造后恒定，push 无界数据也不增长（测试/回放验证）。
- 回放示例 128 行 × 1024 bin = **512 KB**；显式 `memory_bytes()`。

### Q5. 巡检 STOP 最大响应时间？
- `stop()` 后 **1 次 `step()` 内**到达 STOPPED（O(1)），dwell/settle 由注入单调时钟驱动，不阻塞。

### Q6. 事件容量与轮转？
- 内存容量可配（默认 256，回放 512），超容 drop-oldest（`dropped` 计数）。
- 文件轮转 `RotatingFileSink(base, max_bytes, max_files)`：总磁盘有界 `max_files×max_bytes`
  （回放 4×64 KB），index 回绕覆盖最旧；写失败 fail-closed（`record` 返回 false）。

### Q7. 哪些模块可直接接入 M22/M23？
FFT、瀑布图、刷新调度、巡检状态机、事件记录 5 个模块**完全模型无关**，可立即作为独立
离线模块接入（详见 `docs/M24_A_INTEGRATION_INTERFACE.md` §2）。

### Q8. 哪些必须等 24 类模型？
24 类**真实分类**必须等正式模型训练完成。`m24_class24_stub.hpp` 仅用于接口/UI/契约测试，
输出确定性假 logits（`simulated=true`），**不得**用于真实分类或门禁。

### Q9. 是否修改了任何正式链路？
**没有。** 19 个文件全部新增；M22/M23 交付物字节未变（打包后 `diff` 验证）；无 RTL/XDC/位流
改动，无 Vivado。errata1 相对 b20f8bc… 仅测试/工具/文档增量，7 个模块头文件字节一致。

### Q10. 为什么仍是 `24CLASS_MODEL_NOT_READY`？
24 类正式模型**尚未训练**，无真实 checkpoint、无 SHA、无 NPU logits。stub 只提供确定性
假 logits 且恒标记 `SIMULATED`，从未写 `24CLASS_PASS`。状态保持 `24CLASS_MODEL_NOT_READY`。

## 6. 状态红线

- 本阶段最高状态：**`M24-P1-OFFLINE-MODULES-READY`**。
- 严禁：`24CLASS_PASS` / `FINAL_MODEL_PASS` / `OOD_PASS` / `DEPLOYMENT_PASS` / 任何可上板验收全量包。
- 离线环境未执行 24 类训练；训练与上板由用户本人执行（我禁碰板 / 禁写 Flash）。

## 7. 交付物（errata1 补丁，版本化新增，不覆盖 b20f8bc…）

- 输出：`dist/sdr_full_chain_spectrum_monitor_m22_m24_m24_a_offline_patch_errata1.tar.gz`
  （旧包 `..._m24_a_offline_patch.tar.gz` = b20f8bc… 保留不动）。
- 内容：19 个内容文件 + manifest `M24_A_PATCH_SHA256SUMS.txt` = **20 个 tar 条目**；
  manifest **19 行**（每行一个内容文件 SHA256，不含自身/不含打包脚本）。
- 包内**无任何 `SHA256SUMS.txt`**（打包脚本带 guard 断言）。
- 精确字节数与完整 64 字符 SHA256、独立解包 `sha256sum -c` 结果见交付记录（构建后填）。
