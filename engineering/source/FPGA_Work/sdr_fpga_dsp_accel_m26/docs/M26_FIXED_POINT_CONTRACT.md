# M26 定点数值契约（Fixed-Point Contract）

任务 id="39e5" · M26 · 本契约定义 M26 每个流式模块的输入/内部/输出位宽、Q 格式、舍入、饱和与溢出行为。RTL（`rtl/*.sv`）与 C++ 定点比特精确模型（`golden/m26_fixed_model.hpp`）**必须逐位一致**；C++ 浮点黄金模型（`golden/m26_golden.hpp`）提供对齐基准。

> 本契约只约束 **M26 新建模块**，不修改冻结的生产 Mandatory Core 数值契约（`sampling_and_iq_contract.md`）。

---

## 0. 通用约定

| 约定 | 定义 |
|---|---|
| 输入 IQ | 交织 `[I,Q]`，signed 16-bit，**Q1.15**（二进制点 15），每复数 2 槽（`AXI-Stream tdata[31:0]`，`{I[15:0], Q[15:0]}`） |
| Q 记法 | `Qm.n` = signed，1 符号位 + m 整数位 + n 小数位，总宽 = m+n+1；范围 `[-2^m, 2^m - 2^-n]` |
| 饱和 | **对称饱和**（symmetric saturating）：正饱和 `2^m - 2^-n`，负饱和 `-2^m` |
| 舍入 | **round half away from zero**（`nearest_ties_away_from_zero`），与冻结 int8 量化一致 |
| 溢出 | **禁止无说明自然溢出**；每次右移/截断前先舍入，每次加/乘若可能超宽先显式饱和 |
| 复位 | 异步复位（低有效 `rst_n`），复位后所有寄存器=0，**不得输出旧数据** |
| 旁路 | 每级独立 `bypass` 使能；旁路时数据**逐样本直通、顺序不变**（组合直连，非寄存旁路） |
| 流水 | 每级允许流水；首样本延迟（latency）在 `M26_RESOURCE_AND_TIMING_BUDGET.md` 逐级列出 |

---

## 1. DC 偏置消除（`m26_dc_removal`）

一阶高通：`y[n] = x[n] − x[n−1] + R·y[n−1]`，`R = 1 − 2^-7 = 127/128`。

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15 |
| 内部 | `x − x_d1 + (y_d1 − (y_d1>>7))`，36-bit Q1.30（避免中间截断） |
| 输出 | 16-bit Q1.15（先舍入再对称饱和） |
| 复位 | 清除 `x_d1`、`y_d1` |

---

## 2. 能量 / RMS 统计（`m26_energy_rms`）

窗口 `N = 1024`（与帧长一致）：`power[n] = I[n]² + Q[n]²`，`energy = Σ power[n]`，`rms = sqrt(energy / N)`。

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15（I、Q 分别） |
| `power` | `I²+Q²`，**32-bit 无符号 Q0.30**（与 Mandatory Core 32-bit power 口径一致） |
| `energy` 累加器 | 1024 个 Q0.30 求和 → **48-bit 无符号 Q0.30**（1024 < 2^10，需 +10 整数位；48 宽有 17 整数位余量，不溢出） |
| `rms` 输出 | 16-bit 无符号 Q0.15（`sqrt(energy/N)` 后量化；`energy` 先右移 10 得 Q0.30 均值再开方） |
| 峰值 | `peak = max power[n]`（32-bit 无符号）与 PAPR 可选输出 |

---

## 3. 信号存在检测（`m26_signal_presence`）

镜像 host `signal_presence.hpp` 状态机：`NO_SIGNAL / ACQUIRING / SIGNAL_PRESENT / SIGNAL_LOST`，滞回阈值 + N/M 帧滞回。

| 项 | 值 |
|---|---|
| 输入 | rms（16-bit Q0.15） |
| 阈值 | `thr_enter` / `thr_exit`（16-bit Q0.15，运行时可配），`thr_exit < thr_enter`（滞回） |
| 帧滞回 | `enter_m` / `exit_n`（运行时可配，4-bit） |
| 输出 | 4 态 presence（2-bit）+ 逐帧 `presence_changed` |

---

## 4. NCO 复数混频（`m26_nco`）

`y[n] = x[n] · exp(−j2π f/fs · n)`，频率 `f` 运行时配置（32-bit 相位增量 `Δφ = round(f/fs · 2^32)`）。

| 项 | 值 |
|---|---|
| 相位累加器 | 32-bit 无符号，模 2^32（自然回绕，**非溢出**，合法） |
| 正/余弦 | 相位高 10-bit 查 1/4 波 LUT（`2^10` 深度 × 16-bit Q1.15），象限折叠；LUT 内置或构建时初始化 |
| 复乘 | `I_out = I·cos − Q·(−sin)`、`Q_out = I·(−sin) + Q·cos`（注意负频率符号），每乘积 32-bit，求和 33-bit，**先舍入再对称饱和** |
| 输出 | 16-bit Q1.15（I、Q 分别） |

---

## 5. FIR 低通/带通（`m26_fir`）

对称系数，抽头数 `T`（构建时参数，默认 32；运行时/构建时可配置系数）。

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15 |
| 系数 | 16-bit Q1.15（对称折叠，累加前乘 2） |
| MAC 累加器 | **48-bit Q1.30**（T≤64 时 16×16×T 不溢出；输出右移 15 得 Q1.15） |
| 输出 | 16-bit Q1.15（先舍入再对称饱和） |
| 结构 | 转置型（transposed）单乘法器/周期，或并行 MAC（`M26_RESOURCE_AND_TIMING_BUDGET.md` 比较 DSP 占用） |

---

## 6. 抽取（`m26_decimator`）

| 项 | 值 |
|---|---|
| 合法倍数 | **仅 {2, 4, 8}**（其它值 fail-closed：`cfg_error` 置位并停止输出） |
| 行为 | 每 D 个输入样本输出 1 个（相位 0 对齐，`tlast` 随输出帧重计时） |
| 旁路 | `bypass` 时 D=1 等效（不改数据顺序） |

---

## 7. Hann 窗（`m26_hann`）

周期 Hann：`w[n] = 0.5 − 0.5·cos(2πn/N)`，`N=1024`，`n=0..1023`。

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15 |
| 系数 | 16-bit Q1.15（round(w[n]·2^15)，构建时 ROM） |
| 输出 | `x[n]·w[n]` → 16-bit Q1.15（先舍入再饱和） |

---

## 8. 1024 点流式 FFT（`m26_fft_1024`）

基-2 DIT，逐级 1/2 缩放（10 级 → 总缩放 1/1024，等价「scaled FFT」；与 C++ 黄金 `m24_fft.hpp`（unnormalized，`|X|=A·n`）换算关系见 §12）。

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15（复数） |
| 蝶形 | `A' = (A + B·W)/2`、`B' = (A − B·W)/2`，复数乘 32-bit、加减后右移 1（**先舍入**），中间 24-bit |
| 旋转因子 | 16-bit Q1.15，构建时 ROM（`exp(−j2πk/N)`） |
| 输出 | 16-bit Q1.15（每级饱和一次） |
| 结构 | 单蝶形内存型（in-place，地址发生器），或流水型（见 `M26_RESOURCE_AND_TIMING_BUDGET.md` 比较） |

---

## 9. fftshift（`m26_fftshift`）

| 项 | 值 |
|---|---|
| 行为 | 输出 bin `k` = 输入 bin `(k + N/2) mod N`（把 DC 移到中心），纯地址重映射，无算术 |
| 数据 | 位宽不变量（16-bit Q1.15） |

---

## 10. 复模方（`m26_mag_sq`）

| 项 | 值 |
|---|---|
| 输入 | 16-bit Q1.15（复数） |
| 输出 | `|X|² = Re² + Im²` → **32-bit 无符号 Q0.30** |

---

## 11. 噪声底估计（`m26_noise_floor`）

| 项 | 值 |
|---|---|
| 输入 | 32-bit Q0.30（功率谱） |
| 方法 | 中值噪声底（对 1024 bin 取中值）或百分位（默认 30%）；为避免取整偏差，实现为**排序后取中位**（构建时参数选择） |
| 输出 | 32-bit Q0.30（噪声底估计 `N0`） |

---

## 12. CFAR 检测（`m26_cfar`）

单元平均 CFAR（CA-CFAR），保护单元 + 参考单元显式配置。

| 项 | 值 |
|---|---|
| 输入 | 32-bit Q0.30 功率谱 + 噪声底 `N0`（可选偏移基准） |
| 参数 | `guard_cells G`、`ref_cells R`（两侧各 R）、`threshold_scale T`（Q2.14，运行时/构建时配置） |
| 门限 | `thr[k] = T · mean(ref window)`（参考窗口不含保护单元与被测单元） |
| 判决 | `P[k] > thr[k]` → 检测（1-bit 掩码） |
| 边界 | bin 索引越界处参考窗口截断；`G`、`R` 非法（如 2R+2G ≥ N）→ fail-closed |
| 虚警 | 虚警率在 `M26_OOC_SYNTHESIS_REPORT.md` 以黄金对齐数据报告 |

---

## 13. 候选频段合并（`m26_candidate_merge`）

| 项 | 值 |
|---|---|
| 输入 | CFAR 检测掩码（1024 bit） + 功率谱（32-bit Q0.30） |
| 合并 | 相邻（间距 ≤ `merge_gap`，默认 2 bin）的检测 bin 合并为一个候选 |
| 候选上限 | **硬上限 `MAX_CAND`（默认 16）**；溢出时置 `candidate_overflow` 状态并保留前 MAX_CAND 个最强候选 |
| 每候选输出 | `center_freq`（功率加权质心）、`bandwidth`（**99% 功率带宽**，见 §14）、`power`（候选内功率和）、`bin_start/bin_end` |
| 抗带外单谱线 | 单一孤立 bin 不得因合并扩展到全带宽（`merge_gap` 限界） |

---

## 14. 99% 功率带宽（`m26_occupied_bw`）

**禁止**沿用 M23 脆弱的「最左到最右谱线跨度」作为正式占用带宽。

| 项 | 值 |
|---|---|
| 定义 | 从候选峰值 bin 向两侧扩展，累计功率达到候选总功率的 **99%** 时的带宽（bin 数 × bin 宽） |
| 实现 | 候选内功率总和 `Ptot` → 以峰值 bin 为种子，按功率降序加入相邻 bin，直到累计 ≥ 0.99·Ptot；带宽 = 覆盖 bin 数 |
| 单 bin 候选 | 带宽 = 1 bin |

---

## 15. 全链缩放的黄金换算（关键）

黄金 FFT（`m24_fft.hpp`）**非归一化**：`|X[m]| = A·n`（幅度 = 幅度×n，n=1024）；Hann 相干增益修正 `A = 2·|X_w|/n`。
M26 RTL FFT 逐级 1/2 缩放 → 总增益 **1/n**。故 RTL 输出 `|X_rtl| = |X_golden| / n`（同一输入），即：

```
X_golden[k] = X_rtl[k] · 1024     （复数幅度）
P_golden[k] = |X_golden|² = P_rtl[k] · 2^20
```

功率谱、噪声底、CFAR 门限、99% 带宽的黄金对齐均按此换算；数值验证（`golden/m26_verify.cpp`）在**功率谱域**比较（避免幅度符号/相位口径差）。

---

## 16. 元数据输出（spec §三要求）

每帧输出携带：`frame_id`（递增）、`timestamp`（样本计数）、`sample_count`。断流/复位后 `frame_id` 从 0 重计；旁路路径元数据**不**改变。

---

## 17. fail-closed 汇总

| 触发 | 行为 |
|---|---|
| 抽取倍数 ∉ {2,4,8} | `cfg_error`，停止输出 |
| CFAR 参数非法 | `cfg_error`，停止输出 |
| NCO `f` 越界（|f|>fs/2） | 相位增量饱和到 ±fs/2，置 `cfg_warning` |
| 复位后 | 所有输出寄存器=0，`tvalid=0` |
