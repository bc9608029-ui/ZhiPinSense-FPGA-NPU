# M29 RML24 fix10class24-dualsdr2 — Phase D 真实转储根因审计（D1/D2/D3）

- 任务书：39e5（fix10class24-dualsdr2，诊断 + 最小修复，24 类 BF16 双 SDR 恢复稳定性失败）
- 工作树：`fix10class24_dualsdr2`（基线 = dualsdr1 full `25659516…`）
- 真实转储：`board_capture/rml24_bpsk_failed_rx_1500.tar.gz` → `extracted/failed_rx/1500/`
  （`raw_rx_ci16le.bin` 128000 复、`expected_full_burst_ci16le.bin` 59904 复、
  `coarse_corrected_rx_cf64le.bin`、`recovery_diagnostics.json`）
- 方法：三只临时探针（`probe_phase_d3/d4.cpp`，均在工作树**之外**，非交付物）：
  - **d3** 逐字节比较 x86 运行时训练组件 vs 冻结 canonical 组件（跨架构参考一致性）。
  - **d4** 用**冻结 canonical 参考**完整复现板端恢复（coarse CFO → 去旋 → pass2 → 分数定时 → 最终 estimate → 手工 step-6.5 payload-training 相关/残差），并把残差沿模型方向 / 正交方向分解。
- 结论：**双 SDR 失败根因已定位，且与「23→24 同步缺口」无关**。一个根因是跨架构参考（D1，诊断工具 + 板端鲁棒性），一个根因是板端真实 RF 残差（D2，噪声受限），一个根因是「BPSK 过/4ASK 过」被误读为调制相关（D3，实为 RF 实现噪声）。

---

## 1. D1（已确认）：RX 恢复参考 `payload_gain_training_complex()` 跨架构不确定

### 1.1 决定性证据（probe_phase_d3）

逐字节比较 x86 运行时（`iq_rf_training_frame.hpp`）与冻结 canonical（`iq_fix10_canonical_frame_data.hpp`，源 `source_arch=aarch64`）：

| 组件 | x86 运行时 SHA | canonical SHA | 是否字节一致 |
|---|---|---|---|
| preamble（ZC，1024 复） | `d4b4bb3a…` | `d4b4bb3a…`（`kCanonicalPreambleSha`） | ✅ 一致 |
| **payload_training（16QAM，1024 复）** | `da3fadf4…` | **`f06e9b3d…`（`kCanonicalPayloadTrainingSha`）** | ❌ **不一致** |
| tail（ZC，1024 复） | `ccddabe1…` | `ccddabe1…`（`kCanonicalTailSha`） | ✅ 一致 |

payload_training 首个差异：`int16_index=0`，x86=`-883`，canonical=`-2650`，delta=`1767`。
与 fix10prep3 审计记录**逐字一致**（「payload_training 首差异 x86=-883 vs arm=-2650」）。

### 1.2 根因链

- `payload_gain_training()`（`iq_rf_training_frame.hpp:160`）用运行时 `std::sqrt(10.0)`、
  `std::sqrt(energy/n_sym)`、`std::lround` 生成 16QAM payload 训练块。这三者对舍入跨架构敏感；
  ZC 前导/尾的 `std::sin/std::cos/std::lround` 在 int16 量化下恰好跨架构一致，故只有 payload 训练块分歧。
- **fix10prep3 只 canonical 了 TX 侧**：`build_burst_cli.cpp` → `fix10canonical::buildTxBurstFromFrozen`
  用冻结 canonical；但 **RX 恢复参考**（`iq_dual_sdr_coarse_cfo_recovery.hpp` / `iq_rf_sync_recovery.hpp`
  → `iqrftrain::payload_gain_training_complex()`）**仍在运行时生成**。这是 prep3 的**未收口缺口**。
- 后果 A（诊断工具）：主机重放器（x86 运行时参考）与板端（aarch64 运行时参考）参考不同 → 主机无法复现板端。
- 后果 B（板端鲁棒性，潜伏）：板端当前 aarch64 运行时参考 == canonical（canonical 即从 aarch64 冻结而来），
  所以**板端今天是对的**；但任何板端工具链（glibc/g++ 的 `sqrt`/`lround`）变动都会**静默**打破板端恢复参考。

### 1.3 转储侧再确认（独立证据）

`expected_full_burst_ci16le.bin`（板端期望的 TX full burst）整体 SHA = `7fc89427…`，
与 `recovery_diagnostics.json` 的 `burst_sha=7fc89427a9217546ab9233ecd342282ac3e152bd029ff1597d7dd75a338ecf17` **完全一致**；
其中 payload_training 切片（复 2048..3072）SHA = `f06e9b3d…` == `kCanonicalPayloadTrainingSha`。
→ **TX 确为 canonical**；板端 RX 参考（aarch64 运行时）== canonical（相关 0.993）；主机 RX 参考（x86 运行时）≠ canonical（相关 0.30）。

---

## 2. D2（已确认 + 主机精确复现）：板端 BPSK 残差 0.116 是真实 RF 噪声，非代码缺陷

### 2.1 主机复现（probe_phase_d4，用 canonical 参考）

对同一份 `raw_rx_ci16le.bin`，用 canonical payload_training 参考复现板端恢复，逐字段对照：

| 字段 | 板端（JSON） | 主机 canonical 复现 | 结论 |
|---|---|---|---|
| `timing_offset` | 36074 | 36074 | ✅ 一致 |
| `coarse_cfo_hz` | -118.316 | -118.325 | ✅（±0.01 Hz） |
| `fine_cfo_hz` | -6.27395 | -6.26528 | ✅（±0.009 Hz） |
| `sro_ppm` | 0 | 0.000000 | ✅ 一致 |
| `payload_gain_mag` | 0.0154811 | 0.015481068 | ✅ 一致 |
| `payload_training_corr` | 0.993317 | 0.993316525 | ✅ 一致 |
| **`payload_training_residual`** | **0.116199** | **0.116198801** | ✅ **一致** |

残差 0.116 ↔ 相关 0.993 ↔ 有效 SNR ≈ **18.7 dB**（`1/residual² ≈ 74`）。

### 2.2 残差结构（probe_phase_d4 分解）

把残差误差沿模型方向 / 正交方向分解（1024 采样）：
- 沿模型（幅度方向）功率 = 16687；正交（相位方向）功率 = 11106；模型功率 = 2058409。
- 幅度:相位 ≈ **60:40**，接近各向同性（纯热噪声应为 50:50），有约 10% 的幅度方向富余。
- 结论：残差以**热/相位噪声为主**，叠加轻微幅度失真，**无单一系统性可修分量主导**。

### 2.3 排除可修的系统性分量（逐项裁决）

| 假设 | 证据 | 裁决 |
|---|---|---|
| 残留分数定时（chord 效应） | 板端 `payload_best_fractional_timing_samples=0.300781`（应用 0.294922）；`payload_best_fractional_corr=0.99335` ≈ `payload_fractional_corr_after=0.993349` | **排除**（改用 payload 自身最优分数定时 corr 不升） |
| 残留 CFO / 漂移过校正 | 粗 -118.3 + 细 -6.27 = -124.6 Hz 漂移；对 1024 采样 block 相位斜坡 ≈0.85°，RMS≈0.245°，对 residual² 贡献 ≈1.8e-5（0.13%） | **排除**（可忽略） |
| SRO | `sro_ppm=0` | **排除** |
| 门限过松/过紧 | `max_residual=0.10` 为红线 | **不可改** |

→ 残差 0.116 是 RF 链路 SNR（≈18.7 dB）受限，**不是**恢复算法缺陷，也**没有**在红线内的代码可降它。
（参考：前导 ZC 全带残差 `training_residual=0.32872`，远高于窄带 16QAM 的 0.116，佐证链路对宽带信号失真更大；`rf_verdict=RF_DISTORTS_IQ`。）

---

## 3. D3（已确认）：「BPSK 过 / 4ASK 过」是 RF 实现噪声，非调制相关

- 门控的 payload_training 块（复 2048..3072）**对所有调制完全相同**（canonical 16QAM，调制无关）。
- 该块在 burst 内的 RF 上下文 = `[上一周期 tail][preamble][settling][payload_training]`，也与调制无关。
- 故 BPSK 的 0.116、4ASK 的 ~0.09、dualsdr1 的 0.102/0.112 **只是不同次采集的 RF 实现噪声**，
  样本数太小不足以判定「BPSK 系统性更差」；真实症结是**残差围绕 0.10 门限波动**，边际链路。
- 红线内**不做 per-BPSK 补偿 / 单标签定时 / 挑跑**，D3 的结论与红线一致：问题不在调制，在边际 SNR。

---

## 4. 修复方向（Batch 2 提案）

### 4.1 D1 修复（可在交付内、不改红线头）

**主机重放器 canonical 参考模式**（`host_tools/`，允许改）：给 `replay_fix10class24_failed_rx.*`
增加 `--canonical-reference` 模式，用 `fix10canonical` 内嵌组件复现板端恢复（即 probe_phase_d4 的逻辑），
使主机能逐字段复现板端（coarse CFO / corr / residual），结束「主机不可复现」的诊断盲区。
这是**诊断工具修复**，不改生产恢复数学、不碰 14 个红线头。

**生产恢复 canonical 化**（根治 D1 的板端鲁棒性）需要改红线头 `iq_rf_training_frame.hpp` /
`iq_rf_sync_recovery.hpp` / `iq_dual_sdr_coarse_cfo_recovery.hpp`，**本任务红线禁止**，须另立任务、经用户批准放宽后实施。

### 4.2 D2 修复（板端 RF，用户执行，非代码）

残差 0.116（SNR≈18.7 dB）是边际链路。候选（均须用户上板验证，API 不碰板）：
- **提高接收信号电平**：当前接收 payload RMS ≈ 0.01525×2048 ≈ 31（约 -36 dBFS，12-bit ADC），
  增加 RX 增益（或提高 TX 功率、降低衰减）使信号接近满量程，SNR 可提升最多 ~20 dB，残差随之降到 ~0.01。
- **公共参考时钟**：粗 CFO -118.3 Hz 且带 ~-6.3 Hz 漂移（≈-272 Hz/s）表明双 SDR 独立晶振；
  共享参考可消除 CFO 漂移与相位噪声分量。
- 不改门限（红线）、不改恢复数学（红线）。

---

## 5. 状态与后续

- 状态推进：`…-RECOVERY-DIAGNOSTIC-READY-FOR-BOARD-CAPTURE` → **`M29-RML24-FIX10CLASS24-DUALSDR-PHASE-D-ROOT-CAUSE-LOCATED`**（本审计交付时写；未写 SMOKE-PASS/RF_PASS/FIX10_READY/FINAL_*）。
- 禁写：`RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_*`；API 不碰板。
- 后续：Batch 2 交付重放器 canonical 参考模式 + 板端 RF 参数建议（用户上板复测）→ 两样本稳定过 → 全量 24 类 BF16 双 SDR 烟测。
