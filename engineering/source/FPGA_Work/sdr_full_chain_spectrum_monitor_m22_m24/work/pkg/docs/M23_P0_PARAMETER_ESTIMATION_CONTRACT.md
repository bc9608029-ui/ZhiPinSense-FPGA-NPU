# M23 P0 — 参数估计契约（Parameter Estimation Contract）

> 状态：`M23-P0-OFFLINE-MODULES-READY`（离线预研模块，非板端验收）。
> 本文档定义 M23 P0 五类参数估计的**输入/输出契约、公式、单位、有效/失效语义与误差预期**，供后续接入 M22 时双方对齐。本文只描述**纯 CPU 参考实现**，不修改 RTL/XDC/位流，不修改 12 类模型与预处理。

## 1. 范围与定位

M23 P0 在 12 类调制识别主链（Gate 9/Gate 10）之外，新增一层**信号级预分析**，输出：

1. **D：信号存在检测** —— `NO_SIGNAL` / `SIGNAL_PRESENT`（复用 `sdr::SignalPresence`）。
2. **H：参数估计** —— 中心频率、功率、RMS、SNR、占用带宽、CFO 六项。
3. **C：M20 OOD-U 接线** —— 默认关闭的 `UNKNOWN_EXPERIMENTAL` 接口（见集成接口文档）。

本契约只覆盖 **H（参数估计）** 与 **D（存在检测）** 的数值口径；四态裁决与 OOD-U 接线见 `M23_P0_INTEGRATION_INTERFACE.md`。

## 2. 输入契约

| 项 | 值 | 来源 |
|---|---|---|
| 每帧样本数 | `M23_FRAME = 1024`（与 M22 `result_frame` 帧长一致） | `m23_contract.hpp` |
| 采样率 | `fs = 128000.0 Hz`（由调用方传入，不硬编码） | `M23ParamConfig::sample_rate_hz` |
| 样本域 | 复数 count 域，12-bit 满量程 `2048`（与 `dsp_measure.hpp`/`rx_iq_format_contract.md` §3 一致） | `m23_iq_synth.hpp::kFullScaleCounts` |
| 数据类型 | `std::complex<float>`（frame 指针传入） | `estimate_params` |

CFO 估计**需要参考频率** `cfo_reference_hz`；未提供参考频率时（`cfo_reference_set == false`），`cfo_hz` 一律标记 `valid=false`（显示 `--`），不猜测。

## 3. 输出契约（`m23::M23Params`）

每项为 `ParamEstimate{ double value; bool valid; }`：

| 字段 | 单位 | 公式/口径 | 备注 |
|---|---|---|---|
| `center_freq_hz` | Hz | FFT 功率谱质心（`sdr::DspMeasure` spectral centroid） | 对单载波 = 谱峰位置；对多音/调制信号 = 功率加权质心 |
| `power_dbfs` | dBFS | `20·log10(rms_counts / 2048)`，rms 为整帧实域 RMS | 无信号/仅噪声时按噪声功率计 |
| `rms` | counts | 整帧 `sqrt(mean(|x|²))` | 12-bit count 域满量程 2048 |
| `snr_db` | dB | 谱域：信号带宽内功率 − 带外噪声功率（`sdr::DspMeasure`） | 单音/多音确定性最好；宽带调制为近似 |
| `occupied_bw_hz` | Hz | **跨度定义**：`(max_bin − min_bin + 1) × fs/fft_n`，`min/max_bin` 为超过占据功率阈值的谱线 | ⚠ 见 §7 局限性 |
| `cfo_hz` | Hz | 一阶自相关相位：`f = arg(Σ x[k+1]·conj(x[k])) / (2π) · fs`，先对 `x^M` 求主频再除以 M，再减 `cfo_reference_hz` | 阶数 M 由调制类型决定：BPSK→2、QPSK→4、单音→1 |

`estimate_params()` 返回一个 `M23Params`；六项中任一不可算（非有限 / 无参考频率 / 输入长度不符）即该单项 `valid=false`，其余项不受影响。

## 4. 有效 / 失效（valid / stale）语义

- `valid=false`：本帧该参数**无法可靠估计**（NaN/Inf、无 CFO 参考、帧长不符），UI 显示 `--`，绝不显示 0 冒充。
- **stale（失效）**：参数一旦在 `PARAM_STALE_AFTER_FRAMES = 5` 帧内未再成功刷新，标记为 stale，显示 `--`。
  - `M23ParamState::refresh(frame_index, params)` 记录最近一次成功帧号；
  - `M23ParamState::stale(frame_index)` 在 `frame_index − last_valid_frame > PARAM_STALE_AFTER_FRAMES` 时为真；
  - `render_param(e, stale)` 对 `!valid || stale` 统一渲染 `"--"`。

- 状态检测迟滞：`sdr::SignalPresence` 用 `enter_power_dbfs = -55` / `exit_power_dbfs = -62` 进入/退出，`confirm_frames = 3` 连续帧确认进入，`lost_frames = 5` 连续帧确认退出，`max_clip_ratio = 0.05` 削波保护。迟滞带 = 7 dB，避免门限附近抖动。

## 5. CFO 估计细节与混叠边界

- 对 `x^M` 做一阶自相关求主频：`f_M = arg(Σ (x[k+1]^M)·conj(x[k]^M)) / (2π) · fs`，则 `cfo = f_M / M − f_ref`。
  - 阶数 M 的作用是把调制非线性剥离成谱线：BPSK `x²` 把 ±1 折叠为 +1；QPSK `x⁴` 把四象限符号折叠为 −1；单音 M=1。
- **混叠边界**：必须满足 `|f_ref + cfo| < fs / (2M)`，否则 `f_M` 折叠。调用方负责选择与预期频偏匹配的 `cfo_reference_hz` 与 `cfo_order`；越界时估计值错误且**不报 valid=false**（属于使用契约，非运行错误）。
- `cfo_reference_hz` 语义：载波/接收机的标称中心，估计器输出**残差** `cfo_hz`（相对参考频率的偏移），不是绝对中心频率。

## 6. 合成测试与实测误差

合成测试用已知真值（`m23_iq_synth.hpp` 随样本携带真值）校验**每项数值误差**，不写裸 PASS。主机实测（`test_m23_p0.cpp`，59 断言，WSL g++ 15.2.0 `-O2 -Wall -Wextra -Werror`）：

| 参数 | 真值条件 | 实测误差 | 容差（测试断言） |
|---|---|---|---|
| `center_freq_hz` | 单音 16000 Hz，bin 对齐 | **−1.469 Hz** | ≤ 20 Hz（< 1 bin，±62.5 Hz @ fs128k/n1024） |
| `cfo_hz`（order 1） | 单音 cfo +250 Hz | **+0.454 Hz** | ≤ 5 Hz |
| `cfo_hz`（order 2） | BPSK cfo −120 Hz | **+0.251 Hz** | ≤ 20 Hz |
| `cfo_hz`（order 4） | QPSK cfo +80 Hz | **−0.520 Hz** | ≤ 50 Hz |
| `power_dbfs` | 单音 amp 1000，无噪声（真值 −6.227 dBFS） | **0.000 dB** | ≤ 0.05 dB |
| `rms` | 单音 amp 1000，无噪声 | **0.000 counts** | ≤ 1 count |
| `snr_db` | 单音 + AWGN 20 dB | **+1.658 dB 偏差** | ≤ 5 dB（宽带化近似所致，见 §7） |
| `occupied_bw_hz` | 双音 snr=0（无噪声）16 kHz span | **+125 Hz**（一个 bin） | ≤ 250 Hz |

**注**：SNR 与 occupied-BW 的误差口径见 §7；这两项是 M23 集成前需要继续改进的**已知未完成项**，本轮不改变 M22 现有 `DspMeasure` 定义。

## 7. 局限性（必须诚实披露）

1. **occupied-BW 跨度定义脆弱**：`DspMeasure` 的 occupied-BW 是 `max_bin − min_bin + 1`（跨度），只要带外出现一个越过阈值的噪声/量化谱线，跨度就会横跨整段谱（实测 tone+BPSK+AWGN 出现 `occ_bins=898` 而非 ~1）。**更稳健的定义（99% 功率带宽 / 最大连通区域）是 M23 集成期的待办项**，本轮刻意不改 `DspMeasure`（避免动 M22）。
2. **SNR 谱域口径对宽带调制偏保守**：`snr_db` 用「带宽内功率 − 带外噪声功率」，对窄带单音/双音最准（+1.66 dB 偏差）；对宽带调制信号是近似值，不应作为绝对 SNR 读数。
3. **CFO 依赖阶数正确性**：阶数必须与调制匹配（BPSK=2 / QPSK=4），否则 `x^M` 折叠不干净、主频污染；阶数选错不报错。
4. **频谱质心≠谱峰**：`center_freq_hz` 是功率加权质心，对非对称/多音信号不等于载波中心（双音时质心取两音中点，测试已按此口径对齐真值）。

## 8. 与 M22 的边界

- 本模块只**读** IQ 帧、只**输出**参数与四态裁决，不写入 M22 的 `result_frame`/模型/UI 主布局。
- 不逐帧向串口刷日志（回放工具的单帧打印是主机调试辅助，板端生产者必须静默，见集成接口文档 §5）。
- 默认关闭 OOD-U 时，行为与 M22 逐字节一致（`M23OodSwitch` 禁用路径 = 纯 argmax，不产生 `UNKNOWN_EXPERIMENTAL`）。
