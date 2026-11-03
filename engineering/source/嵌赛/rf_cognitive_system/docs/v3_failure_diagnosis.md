# QAM-Aware RFNet V3 失败根因诊断报告

- 日期：2026-10-01
- 冻结基线（champion）：V2 `time_power_phase`（accuracy 0.705476、macro-F1 0.697538、QAM 均值 0.464762）
- 被测对象：V3 formal（`outputs/qam_aware_v3/formal`，checkpoint=epoch 4，16/60 epochs 后 early-stop）
- 结果包：`qam_aware_v3_formal_results.tar.gz`，SHA-256 `458a220eab76279fa9da41c4f47ca3b69b2773bfe313146b8f6f32e35c3df08b`（已复核一致）

## 1. 结论摘要

V3 在 V2 兼容命名空间（V2 的温和信道分布）上**三项头部门槛全部未达标**：

| 门槛 | 要求 | V3 实际 | 差值 | 判定 |
|---|---|---|---|---|
| accuracy 增益 | ≥ +0.02 | 0.673810 | **−0.0317** | FAIL |
| macro-F1 增益 | ≥ +0.02 | 0.670350 | **−0.0272** | FAIL |
| QAM 均值增益 | ≥ +0.05 | 0.469048 | **+0.0043** | FAIL |

逐类与关键 SNR 回归详见 §3。V3 仅在高 SNR（+10/+20 dB）与 CPFSK/OFDM/64QAM 上小胜，却在 BPSK/QPSK/8PSK/2FSK 与 0 dB 大幅回退。

## 2. 根因（按证据强度排序）

### 根因 1（主因）：鲁棒增强分布过强，训练域与验收域错配

V3 的 `channel.domain_randomization` 在 V2 基线之上叠加了大量 V2 从未见过的高强度损伤：

| 损伤 | V2 基线（champion） | V3 formal |
|---|---|---|
| CFO | p=0.6, ±1200 Hz | **p=0.8, ±2000 Hz** |
| 相位偏移 | p=0.6 | **p=0.8** |
| 幅度缩放 | p=0.5, [0.7,1.3] | **p=0.7, [0.55,1.45]** |
| Rayleigh / Rician / 多径 | 关闭 | **0.15 / 0.15 / 0.25** |
| 相位噪声 / SFO / IQ 失衡 / DC 偏移 | 关闭 | **0.25 / 0.2 / 0.25 / 0.2** |
| 削波 / 窄带干扰 / 突发干扰 | 关闭 | 0.12 / 0.1 / 0.1 |

关键点：**验收门槛只在 V2 兼容命名空间（`evaluate_qam_aware_v3.py` 中 `"v2_compatible": (baseline["channel"], ...)`）上判定**，即用 V2 的温和信道分布评测。V3 用强损伤分布训练，等于把决策边界朝「对 CFO/相位/衰落不变」的方向偏移，而验收分布并不需要这些不变性 → 温和分布上全面退化。Rayleigh/Rician/多径直接扰乱幅度信息，同时破坏 QAM 的幅度区分（`direct_physical_pool` 依赖的功率矩被衰落打散），也解释了 QAM 仅 +0.43pp 而非预期的明显增益。

**证据**：混淆矩阵 `v2_compatible_confusion_matrix.csv` 显示 BPSK→CPFSK(124)/OFDM(79)、QPSK→CPFSK(146)/8PSK(110)、8PSK→CPFSK(132) 的**新增大规模 PSK↔FSK 混淆**——强 CFO/相位让 PSK 星座旋转，外观趋近恒包络 CPFSK/OFDM，V2 基线不存在此量级的混淆。0 dB 从 0.8535 掉到 0.789（−6.45pp）正是强损伤在低 SNR 叠加恶化的直接结果。

### 根因 2：checkpoint 选择用 val_loss，与验收口径（macro-F1/accuracy）错位

V3 formal 的 `best.pt` 在 **epoch 4**（`run_manifest.json` `best_epoch=4`，`best_metrics.val_loss=0.9857`）。但 `training_history.csv` 显示 val_accuracy/macro-F1 在 epoch 4 之后继续波动上升（epoch 15 val_acc=0.6429 > epoch 4 的 0.6349）。以 val_loss（带 label smoothing 的交叉熵，且受权重/正则影响）选出的 epoch 4 并非宏指标最优。

`training/resumable_trainer.py` 已实现 `checkpoint_metric`/`checkpoint_mode`（默认 val_loss/min），但 V3 配置 `qam_aware_v3.yaml` **未设置该键**，于是回退到旧默认 → 选错 checkpoint。

### 根因 3：early-stop 先于 cosine 收敛完成

`training_history.csv` epoch 16 时 `learning_rate≈8.54e-4`（cosine 60 epochs 仅完成 ~27%）。最佳 val_loss 在 epoch 4，patience=12 → epoch 16 提前停止。模型从未进入 cosine 的低学习率精调阶段。`training/resumable_trainer.py` 已实现 `minimum_epochs_before_stopping`，但 V3 配置未设置（默认 1），未生效。

### 根因 4：QAM 定向提升不足

V3 模型加入了 `direct_physical_pool`（功率/lag1 的一阶+二阶矩直连），16QAM→64QAM 混淆仍是最强混淆对（`16QAM→64QAM` 204 + `64QAM→16QAM` 284 = 488/8400 样本）。二阶矩不足以区分 16QAM（4 幅值环）与 64QAM（8 幅值环）；且根因 1 的衰落进一步打散幅度矩。需更高阶原始矩 `E[x], E[x²], E[x³], E[x⁴]`（注意：是原始矩，不是严格的 skewness/kurtosis 标准统计量）或 QAM 定向损失权重。

## 3. 逐类 / 关键 SNR 回归证据

V2 兼容命名空间（8400 样本，每类 1050）：

| 类 | V2 | V3 | Δ | 门槛(Δ≥−0.03) |
|---|---|---|---|---|
| BPSK | 0.7952 | 0.7305 | **−0.0648** | FAIL |
| QPSK | 0.6400 | 0.5229 | **−0.1171** | FAIL |
| 8PSK | 0.6352 | 0.5943 | **−0.0410** | FAIL |
| 16QAM | 0.5076 | 0.4981 | −0.0095 | pass |
| 64QAM | 0.4219 | 0.4400 | +0.0181 | pass |
| 2FSK | 0.9076 | 0.8257 | **−0.0819** | FAIL |
| CPFSK | 0.8771 | 0.8981 | +0.0210 | pass |
| OFDM | 0.8590 | 0.8810 | +0.0219 | pass |

| SNR | V2 | V3 | Δ | 门槛(Δ≥−0.01) |
|---|---|---|---|---|
| 0 dB | 0.8535 | 0.7890 | **−0.0645** | FAIL |
| 10 dB | 0.9265 | 0.9545 | +0.0280 | pass |
| 20 dB | 0.9330 | 0.9755 | +0.0425 | pass |

## 4. 已排除的因素（非根因）

- **数据泄漏/失衡**：`dataset_audit.json` `blocking_leakage_found=false`，train/val/test 指纹重叠 0，类别/SNR/pair 计数完全均衡 → 排除。
- **NaN/Inf**：`run_manifest.json` `checkpoint_reload_ok=true`、`validation_probe.finite_logits=true` → 排除。
- **类别顺序/帧契约**：`load_qam_aware_v3_config` 校验类序与 1024 采样、3 物理通道，V3 通过 → 排除。
- **模型体量/算子**：506K 参数 / 55M MAC / 1.93MB，算子仅 Conv/BN/ReLU/Add/Concat/ReduceMean/Mul/Gemm，可 iCraft/ZG330 编译 → 排除（部署可行性无回归）。
- **ONNX 导出**：双图 opset17 均 `checker_passed=true`；npu_partition 仅 `Constant`（数据节点，非计算算子）超出白名单 → 排除。

## 5. 结论

V3 失败是**训练分布过强（主因）+ checkpoint 选择口径错位 + early-stop 过早**三者叠加，而非模型架构/数据/部署契约问题。高 SNR 增益来自模型容量与直连物理矩；中低 SNR 与 PSK/FSK 回退来自过强增强。修复方向（V3.1）：温和鲁棒域（以 V2 温和信道为主体）、checkpoint 选 macro-F1、early-stop 设最小 epoch 下限、QAM 定向高阶矩 + 轻量损失权重。详见 V3.1 配置与代码。
