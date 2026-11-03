# 真实公共帧占用带宽核验（任务 4）

结论：**收回「≤10 kHz 窄带替身」假设。真实公共前导/尾是满带宽 QPSK。**

## 依据（只读，逐字配方）

A 线恢复模块 `candidate_two_dc.py`（只读）定义了公共块的逐字配方：
```python
rng = np.random.default_rng(9011)
pn  = exp(1j*(pi/4 + pi/2*rng.integers(0,4,1024)))   # 1024 个独立 QPSK 符号
train = tile(pn, 2)                                   # 2048 样本
tail  = exp(1j*(pi/4 + pi/2*rng.integers(0,4,2048)))  # 2048 个独立 QPSK 符号
```
**每样本一个独立 QPSK 符号、无脉冲成形** → 符号率 = fs = 2.56 MHz → 满带宽。

## 实测（`scripts/verify_public_bw.py`，复现上述配方，Hann 窗 Welch PSD）

| 块 | 样本数 | 占用带宽（−20 dB） | 99% 功率带宽 |
|----|--------|--------------------|--------------|
| train | 2048 | **2 558 kHz（1.00 × fs）** | 2 358 kHz（0.92 × fs） |
| tail | 2048 | **2 560 kHz（1.00 × fs）** | 2 428 kHz（0.95 × fs） |

产物：`results/public_bw_verification.json`。

## 对多信号设计的影响（必须改口径）

1. 之前的「载波占用带宽 ≤10 kHz、保护带 ≥12.5 kHz」多载波 TX 合成口径
   **不适用于真实公共帧**：真实前导占满整个 2.56 MHz 复基带。
2. 真实公共帧在频域几乎完全重叠，分离靠 `detect_public_training` 的
   despread-FFT **按 CFO 分离**（FFT 2048 点 → bin = 2.56 MHz/2048 = 1.25 kHz），
   不是靠占用带宽间隙。
3. 单 TX 瞬时带宽内**同时**呈现多个真实公共帧：需要逐 dwell 多峰检测（FPGA PSD
   路径，B 线），且多个满带宽帧互调/重叠严重；在 FPGA 辅助链验收前**不承诺**。
4. 离线 TX 多载波合成（`src/tx_synth.py`）保留为**窄带替身**工具，仅用于控制面
   波形/审计自测；它不代表真实公共帧，文档已标注。

## 回填结果

- `contract/multisignal_contract.json` 的 `tx_synthesis.assumptions` 与
  `docs/FROZEN_PARAMS.md` §4、`docs/TX_SYNTH_AUDIT.md` 中「真实公共帧占用带宽
  ≤10 kHz 待板测」已改为「已核验 = 满带宽（≈2.56 MHz Nyquist）QPSK，非窄带」。
- 待板测项改为：真实 payload 波形占用带宽（数据集 1024 复样本定义，不在此树）。
