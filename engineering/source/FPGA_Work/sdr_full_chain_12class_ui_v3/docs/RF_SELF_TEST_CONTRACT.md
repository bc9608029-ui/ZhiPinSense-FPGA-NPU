# 十二类 RF 自测契约（任务 39e5 UI v3 · M9 / Gate 10）

> 本文件是 M9 可执行契约，定义 `board_package/board_gate10_selftest_12class.cpp`
> 的行为、门禁与红线。波形生成规则引用 `WAVEFORM_CONTRACT.md`（M9 前置）与
> `TRAINING_SIGNAL_CONTRACT_AUDIT.md`（M0）；新增参数一律标 `NEW_TEST_PARAMETER`。

## 1. 目的与定位

Gate 10 是**十二类真实 RF 自测**：把十二类调制波形在板端合成 → 经 Pluto TX 发射 →
经同一设备 RX 采集 → 走与 Gate 9 完全相同的 SDR→张量预处理链 → NPU 逐帧分类，
验证"真实射频链路上的十二类识别"端到端可用。

- **这不是模型最终判定**：Gate 10 是自测（self-test），证明的是"链路 + 模型对真实
  十二类波形的分类能力"。它**绝不**覆盖 OOD=NO_GO / FINAL_MODEL_PASS 红线（见 §8）。
- 波形生成器 + ×20 上采样器在主机已测试（`host_tests/test_rf_waveform_12class.cpp`，
  66 断言）；Gate 10 本体是板端程序（iCraft + libiio），主机只做 `-fsyntax-only` 校验，
  链接留待板端。

## 2. 信号路径

```
build_tx_waveform(cls, seed)                        每类一遍
  128 kS/s 合成（每 1024 帧 RMS=1.0，连续相位）       rf_waveform_12class.hpp
  ──×20 polyphase 上采样（make_20x_upsampler）──► 2.56 MS/s
  ──峰值限幅至 peak_limit DAC 计数（不削顶）──► int16 交织 [I,Q,...]

PlutoTx(loopback, confirm_safe_rf_path)              安全状态机（同 Gate 9）
  prepare() → start_cyclic()（cyclic TX 缓冲）

board::capture_contiguous(required_input(frames))    单次连续 RX refill（同 Gate 9）

PreprocessChain 两遍：
  pass 1  rec_scale=1.0 → 测量重建帧 RMS → rec_scale = 1/rms_mean
  pass 2  rec_scale=1/rms_mean → 逐帧 → NpuClassifier12.infer → argmax

逐类统计 matched/count + 12×12 混淆矩阵 → 门禁（§6）
```

## 3. 两遍 RMS 定标（核心设计，NEW_TEST_PARAMETER）

- **为何要两遍**：不同类 PAPR 差异巨大（OFDM 高 PAPR，恒定包络 2FSK/GFSK/WBFM 低 PAPR）。
  生成器每 1024 帧把 RMS 归一到 1.0，但 ×20 上采样后再做**峰值限幅**（全局单因子
  `scale = peak_limit / 峰值`），不同类的实际 RMS 因此不同（峰值越接近限幅，RMS 越高）。
- **做法**：先以 `rec_scale=1.0` 跑一遍预处理，测出重建帧平均 RMS，再取 `rec_scale=1/rms_mean`
  跑第二遍分类，把模型输入映射回训练域 RMS≈1.0。
- **语义**：这是**每类一次的标量定标**，等价于校准后的全局 `receiver_scale`，**不是**
  禁止的逐帧 RMS 归一化（`AUTO_LEVEL_MODEL_INPUT_AUDIT.md`）。每个类的定标在其 20 帧内恒定。

## 4. 参数与默认值

| 参数 | 默认 | 说明 |
|------|------|------|
| `--frames` | 20 | 每类分类帧数（`required_input` 按此分配单次 RX refill） |
| `--tx-frames` | 64 | TX 波形长度（帧数）；64 帧 = 1.31 M 样本 ≈ 512 ms 循环周期 |
| `--min-match-rate` | 0.90 | 每类 match_rate 下界 |
| `--peak-limit` | 1638 | TX 峰值限幅（0.8×2048，12-bit 域不削顶） |
| `--rx-gain` | 10 | RX 增益（manual 模式） |
| `--loopback` | digital | digital（不发射频，默认）/ rf（外发，需 `--confirm-safe-rf-path`） |
| `--tx-atten` | -89.75 | 工作衰减（安全地板）；RF 模式须显式抬高到 ≤ -40 dB |
| `--seed` | 0x39e50001 | 波形 seed（可复现） |
| `--center` | 2450000000 | 中心频率（RF 模式用） |
| `--class` | （空） | 只测单类 `0..11`；缺省测全部 12 类 |
| `--model-sha` | 由 run 脚本注入 | 权威模型 raw SHA（`common.sh` 读 `model_12class.sha256`） |

## 5. cyclic TX 回绕毛刺（已判非问题）

- 波形循环点：线性/AM/OFDM 无相位记忆（OFDM 回绕即正常块边界）；2FSK/GFSK/WBFM
  相位在零均值符号/消息下回到接近 0。
- 更关键：TX 用 64 帧长波形（512 ms 循环），RX 采集 20 帧（410k 样本 ≈ 160 ms），
  采集窗口落在回绕点之前，回绕毛刺根本不在窗口内。

## 6. 门禁（每类 + 总体）

单类 PASS 需**全部**满足：

1. `captured` 为真（单次 refill 交付足量，无超时/短帧/溢出/丢帧/不连续）且 `cont.ok()`；
2. `produced == frames`（帧数足）；
3. `valid == produced`（每帧 12 logits、argmax∈[0,11]、confidence∈[0,1]、版本 `12class-chain-v1`）；
4. `match_rate >= min_match`（该类 argmax 命中率）；
5. RF 模式额外要求 `--confirm-safe-rf-path` 已给（`tx.prepare()` 已强制，此为二重校验）。

总体 PASS = **所有被测类**都 PASS 且设备恢复成功（`final_gate_pass` 闭合
restore_result=FAIL 的 fail-open）。诊断输出含逐类 `matched/count`、`match_rate`、
`rec_scale/rms`、`tx_peak/tx_rms`、`classify_us_mean`、`short/overflow/drop/disc`，
以及 12×12 混淆矩阵对角线汇总（`total_matched/total_count/total_rate`）。

## 7. 退出码与结果行

- 0 = PASS，1 = FAIL，2 = device-not-found。
- 权威结果单行 `GATE_RESULT gate10_selftest_12class pass|fail <detail>`，由
  `board::emit` 直打 stdout 并原样透传退出（沿用 v3 "串口观察者效应" 教训：热路径零额外 I/O）。

## 8. 红线

- 离线最高只标 `READY-FOR-GATE10-DISPLAY-AND-CONTROL-INTEGRITY-HARDWARE-TEST`；**绝不**写
  `12CLASS_RF_PASS / FINAL_MODEL_PASS / OOD_PASS / FULL_SYSTEM_FINAL_PASS`。
- 模型标签 `12CLASS_CHAIN_VALIDATION_MODEL`，OOD=NO_GO；Gate 10 自测通过**不等于**模型上线判定。
- Gate 10 是**独立自测**：它用 §八 `12class-chain-v1` 记录自己做计数，**不产 v2**，
  **绝不喂 MODE/PARAMETERS 页**（那些是 Gate 9 生产者的职责）。
- RF 模式（`--loopback=rf`）外发射频：默认禁用，必须显式 `--confirm-safe-rf-path`，
  且 TX 衰减绝不超过 -40 dB 天花板（`pluto::kSafeTxCeilingDb`）。
- 类别标签只用于**预期标签记录/混淆矩阵**，绝不进入 NPU 输入或推理代码。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
