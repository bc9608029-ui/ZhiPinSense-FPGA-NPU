# M29 RML23 Stage H-F / Route F — fix9r2c 可观测性审计（Phase 2 回放可行性 (a)/(b)）

状态：**`M29-RML23-FIX9R2C-ANALYZER-CORRECTED-ROOT-CAUSE-NOT-PROVEN`**（Phase 1 最高状态）。
本文档只回答一个问题：**fix9r2b 板端落盘的 5 个波形，能否在不再上板的前提下，等价回放某个 Phase 2 补偿器**（估计 + 评估）。审计结论必须**按补偿器类型分**，不得笼统归为「线性可交换」。

## 1. 现存 5 波形的处理点（在恢复链中的位置）

板端恢复链（`iq_rf_sync_recovery.hpp::apply`，与 `provisional_apply_scalar` 同构）顺序：

```
rx_raw ──[SRO 重采样]──> ──[×a_inv 复标量]──> ──[CFO 去旋转]──> recovered
```

fix9r2b 落盘的 5 个波形（`route_f_fix9r2b_waveforms.tsv`）：

| kind | 处理点 | 域 | 用途 |
|---|---|---|---|
| `expected_training` | 期望前导（TX 参考） | 参考域 | 估计补偿器的参考 |
| `aligned_rx_training` | 对齐后的原始 RX 前导 | **raw 域（未标量恢复）** | 估计补偿器的观测 |
| `training_error` | rx−g·ref | raw 域 | 定性 |
| `expected_payload` | 期望载荷（TX 参考） | 参考域 | 评估补偿器的参考 |
| `provisional_recovered_payload` | `provisional_apply_scalar` 输出 | **已标量恢复域**（SRO→×a_inv→CFO 后） | 评估补偿器的观测 |

**关键缺口：没有 `raw_aligned_rx_payload`（未做标量恢复的原始 RX 载荷）。** 补偿器的**估计**（用 `aligned_rx_training` vs `expected_training`）在 raw 域有数据；补偿器的**评估**（作用到载荷）只能在已标量恢复的 `provisional_recovered_payload` 上做，或补齐 raw 载荷捕获。

## 2. 标量恢复的可交换性前提（CFO≈0 / SRO≈0）

标量恢复 = `×a_inv`（常数复标量）+ `SRO 重采样`（时变索引重映射）+ `CFO 去旋转`（时变复标量 `e^{−j2πfk/Fs}`）。**常数复标量与任意 LTI 滤波器严格可交换**；但 `SRO 重采样` 与 `CFO 去旋转` 是**时变**算子，与 LTI 滤波器不交换。

fix9r2b 板测已独立确认 **CFO≈0、SRO≈0**（corr↔residual 自洽、无削顶、`AMPLITUDE_LIMITATION_REJECTED`）。离线分析器（fix9r2c）复算的 `fractional_delay_samples≈0.049–0.050` 也证明 SRO 级时延极小。因此在本观测区间内，`provisional_recovered_payload ≈ a_inv · rx_raw`（重采样≈恒等、去旋转≈恒等），**补偿器与 ×a_inv 的可交换性在本区间成立**。

## 3. 按补偿器类型的可交换性结论

### 3.1 复 FIR（频率选择性）/ 分数时延 —— **兼容 (a)**

复 FIR `h` 与 Farrow/FFT 分数时延 `D(τ)` 都是**线性时不变（LTI）**算子，与常数 `×a_inv` 严格交换：

```
recover(comp·rx_raw) ≈ a_inv·(comp·rx_raw) = comp·(a_inv·rx_raw) = comp·(provisional_recovered_payload)
```

→ 在 `provisional_recovered_payload` 上等价回放形状/分类，残余标量由既有增益路径处理。**走此路需严格可交换性证明**（即本节的 CFO≈SRO≈0 前提 + 补偿器 LTI 前提）。

### 3.2 widely-linear IQ 补偿 `L(x)=a·x+b·conj(x)+c` —— **不兼容 (b)，除非证明系数变换**

`conj` 与复标量不交换：`conj(g·x)=conj(g)·conj(x)`，故 `L(g·x) ≠ g·L(x)`。要在 `provisional_recovered_payload`（已 ×a_inv）上等价回放，必须把 `b→b·conj(g)/g`、`c→c/g` 变换后证明等价（g 为逐次标量增益，可自 `aligned_rx_training` 估出），或判定现有观测不足以回放 → **走 (b)**：给 `iq_rf_fix9r2b_diagnostic.hpp` 增加 `raw_aligned_rx_payload` 捕获，由用户再跑一次 R8 落盘后重放。

### 3.3 边界瞬态（帧边界窗口）—— **不兼容 (b)（倾向）**

边界衰减是**采样位置依赖的实数窗**，既非 LTI 也非复标量；且 `provisional_recovered_payload` 的样本索引已受 `timing_offset`+SRO 重映射，与 raw 域的边界位置错位。要在 provisional 域回放需已知重采样后的确切边界索引，现有观测不足以严格确定 → 倾向 (b)。

## 4. 审计结论

- **FIR / 分数时延 → (a) 兼容**：现有波形足以在离线等价回放（估计用 `aligned_rx_training`，评估用 `provisional_recovered_payload`），前提是 CFO≈SRO≈0（已确认）且补偿器 LTI。
- **widely-linear IQ → (b)**：需系数变换证明或新增 `raw_aligned_rx_payload` 捕获。
- **边界瞬态 → (b)（倾向）**：位置依赖 + 索引错位，现有观测不足以严格回放。

## 5. 与根因判定的联动（诚实底线）

即使 (a) 成立，**回放可行性 ≠ Phase 2 修复会过门**。fix9r2c 判因结果为 `NOT_IDENTIFIED → NOT_PROVEN`，理由正是 blocked-CV（连续双方向验证，guard=16，margin=5）：

- 唯一在双方向都**改善**验证 residual 的是 **M1（分数时延）**：4ASK m0=0.234→m1=0.190、BPSK m0=0.249→m1=0.210，仅 ~19% 改善，**远未达 0.5×scalar**；
- **M2（DC+IQ）≈ M0**，无改善；`b/a` 跨捕获 spread=0.108（不平衡不稳定）；
- **M3（FIR）在验证段整体劣于标量**（best_ntap=3，best_val_residual=0.928/0.882 ≫ m0=0.234/0.249）——**FIR 在同集拟合可虚低，但到验证段即恶化**，证明训练前导里的频谱结构**不随样本位置平稳泛化**（残余由噪声样逐 bin 相位 + 非平稳结构主导，非平稳 LTI 信道）。

→ **残余是复合失真（~7.5–8.5 dB 低频滚降 + 逐 bin 噪声样相位 + ~0.05 采样分数时延），无单一补偿器能在两个 blocked 方向 + 跨捕获同时把验证 residual 降到 0.5×scalar 以下。** 因此无论 (a) 还是 (b)，**当前证据都不足以支持 Phase 2 的「最小修复」被证明有效**；Phase 2 需等待新的定量证据（例如用户再跑 R8 落盘 `raw_aligned_rx_payload` 后，才能进一步区分「非平稳瞬态」与「可逆但需更长/正则化 FIR」）。
