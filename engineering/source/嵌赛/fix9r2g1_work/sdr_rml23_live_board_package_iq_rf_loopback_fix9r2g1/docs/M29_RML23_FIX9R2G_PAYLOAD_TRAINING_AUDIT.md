# M29 RML23 Route F — fix9r2g 载荷域增益训练块审计与验收记录

状态：**`M29-RML23-FIX9R2G-PAYLOAD-TRAINING-READY-FOR-R8-BOARD-TEST`**（状态上限）
基线：fix9r2d 全量 `sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d.tar.gz`
（SHA `34a11a5c47545b007b9416ed246d1c1a499168a71cfdfff2548d11d87bae98bc`）

> 本文档记录 fix9r2g（合并最小功能修复）的生成算法、恢复语义、门禁迁移与 R8 验收
> 契约。红线：**我禁碰板**；禁止 `RF_PASS / RF_PATH_PROVEN /
> ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS / FIX10_READY / PROJECT_COMPLETE / FINAL_*`；
> 标签/类别/expected payload 不得参与同步、增益估计或训练块参数选择。

---

## 1. 根因（fix9r2e 定量裁决，回顾）

唯一根因 **`FIXED_SCALE_JUMP`**：前导→载荷**前向增益跳变 2.5×（+8.0~8.5 dB）**，
两区各自干净复标量、逐周期确定性重复、非频谱依赖、非载荷内瞬态。两个效应：

1. **增益差是包络驱动的**（恒包络 ZC 前导 → 低增益 0.014/0.0156；调制载荷 → 高增益
   0.037/0.0393）；
2. **残差差是频谱的**（全带宽 ZC 前导 → 0.23 残差来自 6.6 dB 信道纹波；窄带载荷 →
   3.3% 干净标量残差）。

因此**任何有效的公共训练块必须同时「被调制」（匹配包络）且「窄带」（匹配残差）**。
fix9r2g 保留原 ZC 用于同步/CFO/SRO，在 payload 紧邻位置插入一个公共、确定性、无标签、
窄带调制的训练块，用它估计**最终复标量增益**后恢复 payload。**不增加帧周期**
（`kPayloadStart=3072`、`kTotalBurstComplex=59904` 不变）。

## 2. 训练块生成算法与常量（`board_package/iq_rf_training_frame.hpp`）

```cpp
constexpr std::size_t kPayloadTrainingComplex        = 1024;            // 32 符号 × 32 采样/符号
constexpr std::size_t kPayloadTrainingOffset         = 2048;            // ZC 1024 + 零稳定区 1024
constexpr std::uint64_t kPayloadTrainingSeed         = 0x2A9E1B7DULL;   // 固定 LCG 种子（冻结）
constexpr std::size_t kPayloadTrainingSamplesPerSymbol = 32;            // ≈ 80 kHz 窄带
constexpr double       kPayloadTrainingAmp           = 2048.0;          // == kTrainAmp
```

帧布局（`kPayloadStart=3072` 不变，总长 59904 不变）：

```
ZC 前导 1024 → 零稳定区 1024 → payload 训练块 1024 → payload 53760 → 零 guard 2048 → tail 1024
```

- 训练块只占原 guard-before 的**后 1024**；前 1024 保留为零（**零稳定区**），隔离 ZC
  宽带瞬态对训练块的污染。
- 32 个 16QAM 符号足以估计一个复标量增益。

生成算法（仅 int16 版一次生成；零标签、零 payload 依赖）：

1. 16QAM 字母表 `{(a+bi) : a,b ∈ {±1,±3}} / √10`（单位平均功率）；固定种子 LCG 依次
   取 **32 个符号**。
2. 矩形脉冲（无成形）：每符号保持 `kPayloadTrainingSamplesPerSymbol` 采样。
3. 归一化到 **RMS = kPayloadTrainingAmp = 2048**（与缩放后 payload 同幅）。
4. 逐采样 `lround(clamp(x, −32768, 32767))` → int16（与 payload 同量化）。

- `payload_gain_training()`（int16 交错 I/Q，长度 `2*kPayloadTrainingComplex`）为**唯一
  真源**。
- `payload_gain_training_complex()`（`complex<double>`，长度 `kPayloadTrainingComplex`）
  **由 int16 版派生**（交错 I/Q → `complex<double>(I[k], Q[k])`），**无独立浮点路径**，
  保证 TX 样本与 RX 参考逐样本严格一致（避免舍入不一致）。

**「同路径」准确措辞**：训练块与 payload 处于**相同最终 TX 采样域、同一 buffer、同一
RF 链路**（同为最终 RMS≈2048、同 int16 量化、同 2.56 MSPS）；它**并没有**经过 payload
离线生成时的同一重采样程序——训练块是确定性直接生成的参考，payload 是离线 ci16 加载
+`tx_scale` 后的结果，二者仅在**最终 TX 幅度/量化/采样域**一致，这是增益估计成立所需
的一致性。

## 3. 恢复核心（`board_package/iq_rf_sync_recovery.hpp`）

### 新增 Failure 枚举（追加 3 个）

```cpp
PAYLOAD_TRAINING_NOT_FOUND,           // payload 增益 non-finite 或 ≤1e-12（不安全）
PAYLOAD_TRAINING_CORRELATION_TOO_LOW, // 训练块去斜 corr < min_corr
PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH,   // 训练块去斜残差 > max_residual（迁移的既有门限）
```

### 新增 PerFileRecovery 字段

```cpp
double payload_gain_mag        = 0.0;  // 训练块 LS 增益幅值（operate on payload）
double payload_phase_deg       = 0.0;  // 训练块相位
double payload_training_corr   = 0.0;  // 训练块去斜归一化 corr（仪表 + 门控）
double payload_training_residual = 0.0;// 训练块去斜残差（仪表 + 门控，迁移 0.10 门限）
```

### estimate() step 6.5：训练块去斜 LS 增益

在既有 step 6（前导 `a_fit`）之后、step 7（peak ambiguity）之前插入。**训练块的
corr、LS 增益、residual 三者使用同一组已估计 timing/CFO/SRO 与相同映射函数**（避免
双 SDR 时因 CFO 误拒绝）：

- 参考 `ref = payload_gain_training_complex()`（int16 派生）；
- SRO 拉伸（同 `stretched_pre` 约定）：RX 索引 `(offset+k)` ↔ TX 索引
  `(offset+k)/(1+sro)`，映射回 `ref[(offset+k)/(1+sro) − offset]`；
- CFO 去旋（同前导符号约定）：`derot(k) = exp(−j·2π·cfo_hz·(offset+k)/fs)`；
- `num = Σ rx[best+offset+k] · conj(ref_k) · derot(k)`；`den_r = Σ|ref_k|²`；
  `den_x = Σ|rx[best+offset+k]|²`；`a_pay = num / den_r`（LS 增益）；
- `rec.payload_gain_mag = |a_pay|`、`rec.payload_phase_deg = arg(a_pay)·180/π`；
- **去斜后 corr**（与 LS 增益同 num/den）：`payload_training_corr = |num|/sqrt(den_x·den_r)`；
- **去斜后残差**：`model(k)=a_pay·ref_k·conj(derot(k))`，
  `payload_training_residual = sqrt(Σ|err|²/Σ|model|²)`。

### validity 重构（step 8）：前导 residual 降级为仪表；不覆盖同步失败

```cpp
if (rec.failure == Failure::NONE) {
    if (!std::isfinite(rec.payload_gain_mag) || rec.payload_gain_mag <= 1e-12)
        rec.failure = Failure::PAYLOAD_TRAINING_NOT_FOUND;
    else if (rec.payload_training_corr < cfg.min_corr)
        rec.failure = Failure::PAYLOAD_TRAINING_CORRELATION_TOO_LOW;
    else if (rec.payload_training_residual > cfg.max_residual)
        rec.failure = Failure::PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH;
    else if (std::fabs(rec.cfo_hz) > cfg.max_cfo_hz)
        rec.failure = Failure::CFO_OUT_OF_RANGE;
    else if (std::fabs(rec.sro_ppm) > cfg.max_sro_ppm)
        rec.failure = Failure::SRO_OUT_OF_RANGE;
}
rec.valid = (rec.failure == Failure::NONE);
```

- 同步阶段既有失败（`TRAINING_CORRELATION_TOO_LOW`/`TRAINING_PEAK_AMBIGUOUS`/timing 等）
  **原样保留**；只有同步干净才进入训练块 + CFO/SRO 链。
- **移除**前导 `TRAINING_RESIDUAL_TOO_HIGH` 门控（`rec.training_residual` 继续计算并
  打印，仅供仪表）。
- 阈值 `min_corr=0.9`、`max_residual=0.05`（注意：计划正文「0.10 迁移」为文档口径，
  代码 `EstimateConfig` 既有默认即 0.05，数值未改动）。

### apply() 改用 payload 增益，fail-closed

`a_inv = conj(a_pay)/|a_pay|²`（由 `rec.payload_gain_mag`/`rec.payload_phase_deg` 重建
复标量），不再用前导 `rec.gain_mag`/`rec.phase_deg`（后者降级为仪表，继续打印）。

**非法增益不静默回退 `(1,0)`**：增益 non-finite/≤1e-12/训练块 corr/residual 越界时，
`estimate()` 已令 `rec.valid=false`；`apply()` 若在此状态下被错误调用，**抛
`std::runtime_error`**，**绝不把未恢复 payload 送入模型**。调用方 fidelity gate 保证
仅在 `rec.valid==true` 时调用 `apply()`；`apply()` 内部再断言 `rec.valid` 兜底。

## 4. 诊断辅助（fix9r2b / fix9r2a）

- `provisional_apply_scalar()`（fix9r2b）：改用 `rec.payload_gain_mag`/`payload_phase_deg`
  （与 `apply()` 一致），且在 `rec.valid==false` 时抛异常/返回失败（不静默回退）。
- 新增纯函数 `payload_scale_error(recovered, expected)`：
  `|rms(recovered)/rms(expected) − 1|`，**只在 R8 诊断路径调用、只对活动 payload 区
  计算**；不进入部署运行时、不从 expected payload 估参。
- `DiagnosticGateInput`：**移除** `training_residual_max`（前导 residual 门控）；
  **追加** `payload_training_exact_match`、`settling_guard_exact_zero`、
  `payload_training_residual_max`、`payload_scale_error_max`、`scored`、`rf_excluded`、
  `prediction_agreement`。
- `evaluate_diagnostic_gate()` 新增（均 fail-closed）：
  `settling_guard_exact_zero != holdout_files` → fail；
  `payload_training_exact_match != holdout_files` → fail；
  `payload_training_residual_max > 0.10` → fail（迁移阈值，不新调）；
  `payload_scale_error_max > 0.05` → fail（仅 R8 审计门）；
  `scored != holdout_files` → fail；`rf_excluded != 0` → fail；
  `prediction_agreement != holdout_files` → fail。

## 5. 回环传输（`iq_rf_loopback_transfer_fix9r.hpp`）—— 只加日志

`RfTransferResultFix9r` 追加 4 个只读端点字段（非门禁、非版本）：
`rx_gain_mode_before_capture` / `rx_gain_before_capture` /
`rx_gain_mode_after_capture` / `rx_gain_after_capture`。用既有纯读
`dev.get_rx_gain_mode()`/`dev.get_rx_gain()` 在**主捕获前**与**主捕获后**各读一次。
**不**做 fix9r2f 的重设/`rx_gain_capture_verified`/throw。

## 6. 回环主链（`iq_rf_loopback_23class_fix9r.hpp`）

1. verdict 链删除前导 `training_residual > max` 分支；`RF_PRESERVES_IQ` 由 `rec.valid`
   （新语义）驱动，其余 `RF_TX_CLIPPED / RF_RX_CLIPPED / RF_NEGATIVE_CONTROL_FAIL /
   RF_PATH_NOT_PROVEN / RF_TX_DMA_PAYLOAD_MISMATCH` 不变。
2. RX gain 端点日志一行（纯日志）。
3. R8 分类：`frozen_baseline_pred` 从冻结基线 TSV 读入（见 §7），按**稳定精确键**
   （`source_index + filename`）逐样本映射；**不得按行号或模糊文件名匹配**；键缺失/
   重复 → fail-closed；**不得用 `deployed_class` 冒充**（`deployed_class` 是真值标签，
   不是冻结离线模型预测）。`rf_pred = merged_top`；`prediction_agreement =
   (rf_pred == frozen_baseline_pred)`；`label_correct = (rf_pred == deployed_class)`（仅
   打印，不门控）。
4. 诊断路径：逐样本 `rec.payload_training_residual` 取 max；`payload_scale_error` 取 max
   （仅诊断模式、仅 R8 审计）。
5. 门禁输入填新字段；诊断模式聚合准确率打印仍为 `NOT_EVALUATED`（R8 不宣称 23 类
   准确率）。

## 7. 冻结基线 TSV（`iq_rf_fix9r_baseline.hpp`）

6 列 TSV：`source_index, sha256, deployed_class, modulation, split_role,
frozen_baseline_pred`。fail-closed：短行 / 非 64-hex sha / `deployed_class` 越界 /
`frozen_baseline_pred` 越界 / `split_role≠holdout` / 重复 `source_index` / 空行 → 拒。

## 8. R8 验收契约（板端，我禁碰板，由用户执行）

- 样本：BPSK + 4ASK 两样本（`--diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1`）。
- 接受条件：无削顶、同步有效、新训练估计有效（finite/非零/安全）、恢复 payload 尺度
  误差 ≤5%、两样本进入模型且预测与冻结离线基线一致：`scored=2`、`rf_excluded=0`、
  `prediction_agreement=2/2`。
- R8 只是两样本分类烟测，**不宣称 23 类准确率**；随后直接开放 46 样本回归。
- **通过 → 立即开放 46 样本**；**失败 → 停止并报告唯一失败项，不自动新增诊断版本**。

板端命令：

```bash
./scripts/run_gate9_rml23.sh \
  --phase=iq-rf-loopback-23class-fix9r \
  --input-kind=radioml-d2-2p56m \
  --frozen-dir="$D2_SMOKE_DIR" \
  --baseline=route_f_fix9r_exact_baseline.tsv \
  --diagnostic-classes=BPSK,4ASK \
  --diagnostic-per-class=1 \
  --center=2400000000 \
  --rx-gain=30 \
  --tx-atten=-40 \
  --rf-path=direct-cable \
  --rf-tx-target-rms=2048
```

## 9. 明确 NOT changed（红线）

- **不加** 2.5 固定补偿；**不降** corr/residual/clip 门限（residual 门限迁移、数值
  不变）；**不用**标签/类别/expected payload 做同步、增益估计或训练块参数选择
  （expected payload 仅 R8 最终审计）；**不改**模型/预处理/NPU/均衡器；**不碰**
  fix10/46 样本/690/clean-23。
- RX gain 端点读回**只是日志**，无门禁、无版本、无新 verdict。
- 不修改 `iq_rf_sync_recovery.hpp` 的既有同步/CFO/SRO 数学（本次改动仅新增 payload
  训练块步骤与 payload 增益 apply，均已完成并获批）。
