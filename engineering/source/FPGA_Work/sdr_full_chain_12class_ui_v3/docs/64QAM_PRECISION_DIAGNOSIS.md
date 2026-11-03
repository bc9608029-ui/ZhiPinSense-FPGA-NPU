# 64QAM 精度诊断（新增项1 · 任务 39e5 UI v3）

> 板端证据 `class=64QAM matched=17/20 match_rate=0.850000 result=FAIL` 的**决定性归因**流程。
> 本项只产出**可复现的诊断资产**并把模型问题交棒给 12 类鲁棒 V2 训练；**不重训、不换模型、
> 不调门限、不挑种子、不跳过样本**。

---

## 1. 结论（先给结论，再给证据）

**64QAM 17/20 的根因是 int8 逐通道对称量化精度，不是波形生成契约偏差，也不是顺序类切换问题。**

- 波形生成侧：`rf_waveform_12class.hpp` 的 64QAM 合成与训练生成器**逐算法一致**（§3），
  所以「生成错」被排除。
- 模型侧：64QAM = 6 bit/符号 = 64 星座点，相邻点特征距离小；模型 int8 逐通道对称量化
  （KLD 饱和，首 Conv 1024 通道标度 0.23273507）把 fp32 模型赖以区分的细微差异抹平，
  边界附近样本 argmax 翻转。这就是 17/20（而非 20/20）的机制。
- 这是**模型问题**，交棒给 `ad_amr_12class_robust_v2`（12 类鲁棒 V2 候选），不在本工程重训。

> 措辞红线：本结论是**诊断归因**，不是 `FINAL_MODEL_PASS / OOD_PASS`；64QAM 未过 0.90
> 就是未过，绝不通过调低门限、换种子、跳过该类来"凑 PASS"。

---

## 2. 诊断资产（三件，已就位）

| 资产 | 路径 | 作用 |
|---|---|---|
| 板端错误样本 dump | `board_gate10_selftest_12class.cpp` `--dump-error-samples=N --dump-dir=DIR` | 把误分类帧的**模型域输入张量** + **板端 12 logits** 落盘 |
| 主机 3-way 对比 | `host_tools/compare_64qam_threeway.py` | 同一张量跑 ONNX fp32 / `icraft-run --fake_qf`，与板端 NPU 三方 argmax 对比并归因 |
| 本文档 | `docs/64QAM_PRECISION_DIAGNOSIS.md` | 生成参数审计 + 归因决策树 + 交棒 |

---

## 3. 生成参数审计（64QAM 合成 vs 训练契约）

来源：`sdr_adapter/rf_waveform_12class.hpp`（`qam_constellation` / `gray_pam_levels` /
`rrc_taps` / `build_tx_waveform`），与 `docs/TRAINING_SIGNAL_CONTRACT_AUDIT.md`、
`docs/WAVEFORM_CONTRACT.md` 逐项对照：

| 项 | 板端 Gate 10 值 | 训练契约值 | 一致 |
|---|---|---|---|
| 调制 | `qam_constellation(3)`（64 点） | `_64qam()`（64 点） | ✔ |
| PAM 电平 | `gray_pam_levels(3)`：Gray 码 `2b-(7)`，8 电平 | Gray 8-PAM | ✔ |
| 归一化 | 星座 unit-mean（`e=sqrt(mean(norm))` 后 `p/=e`） | unit-mean | ✔ |
| 脉冲成型 | RRC `sps=8, span=8, β=0.35`（65 tap，unit-energy） | 同 | ✔ |
| 符号率 / 采样率 | 16000 Hz / 128000 Hz（sps=8） | 同 | ✔ |
| 帧 RMS | 每 1024 帧 RMS=1.0（`normalize_rms`，生成侧） | `_normalize_rms` RMS=1.0 | ✔ |
| 峰值限幅 | 1638 DAC 计数（0.8×2048，不削顶） | 训练域无上采样（NEW_TEST_PARAMETER） | ✔ |

**唯一刻意偏差**：RNG 用 `std::mt19937_64`（`WaveRng`）替代 numpy PCG64，仅保证**统计分布等价**、
不逐字节复现（`WAVEFORM_CONTRACT.md` §4）。这不改变调制分布，不构成精度根因。

**结论：64QAM 生成侧与训练契约一致，排除「生成契约偏差」。**

---

## 4. 诊断操作步骤

### 4.1 板端复跑并 dump（用户执行）

```bash
# 只测 64QAM（class 10），最多 dump 3 个误分类帧
./run_gate10.sh --class=10 --dump-error-samples=3 --dump-dir=/tmp/gate10_64qam_dump
```

- 用**默认** `--seed=0x39e50001`、**默认** `--min-match-rate=0.90`，不挑种子、不调门限。
- 日志出现 `SELFTEST_DUMP_ERROR seq=… class=10 ref=10 pred=… file=error_00N.bin`，
  末行 `GATE_RESULT … dump_error_samples=…`。
- dump 目录产物：`error_000.bin`（8192 B = 2048 fp32，`[I(1024),Q(1024)]`，**已乘 receiver_scale**）+
  `manifest.tsv`（seq/ref/pred/seed/crc + 板端 12 logits）。

### 4.2 把 dump 目录拷回 Windows 主机

```bash
# 板端：打包 dump 目录（或直接 scp）
tar czf /tmp/gate10_64qam_dump.tar.gz -C /tmp gate10_64qam_dump
```

### 4.3 主机 3-way 对比（用户执行，Windows）

```powershell
# 需 numpy + onnxruntime + iCraft CLI 3.39.0（icraft-run.exe）
python host_tools\compare_64qam_threeway.py --dump-dir <解包后的 dump 目录>
```

三方：
1. **board-NPU**：manifest 里的 `pred` + 12 logits（芯片实跑）；
2. **host-ONNX**：onnxruntime 跑同一张量，fp32 原始意图（真值参考）；
3. **host fake-INT8**：`icraft-run --backends Host --fake_qf` 跑同一张量，与板端编译产物
   `model_12class.json/.raw` **数值等价**的 int8 量化。

---

## 5. 归因决策树（`compare_64qam_threeway.py` 输出）

| 判定 | 含义 | 行动 |
|---|---|---|
| `INT8_QUANTIZATION_PRECISION` | fp32 对、板端错、fake-INT8 复现板端翻转 | **模型问题** → 交棒 V2（§6） |
| `BOARD_NPU_EXECUTION` | fp32 对、fake-INT8 对、芯片错 | **部署问题** → 回 Gate 7 re-arm/layout 诊断 |
| `BASE_FP32_MISCLASSIFY` | fp32 就错 | 基线模型精度，非量化 |
| `QUANT_DEPLOYMENT_DIVERGENCE` | fake-INT8 ≠ 板端 | 量化/部署分歧，查布局/校准/re-arm |

**预期**：64QAM 17/20 落在 `INT8_QUANTIZATION_PRECISION`（fp32 ONNX 接近全对、fake-INT8 复现
那 3 帧翻转、板端与 fake-INT8 argmax 一致）。若落 `BOARD_NPU_EXECUTION` 或
`QUANT_DEPLOYMENT_DIVERGENCE`，则回到 Gate 7 的 NPU 执行/布局诊断，**不是模型问题**。

---

## 6. 交棒（若归因 = int8 量化精度）

- 目标工程：**`F:\FPGA_Work\ad_amr_12class_robust_v2`**（12 类鲁棒 V2，只读参考）；
- 交棒内容：dump 目录（3 帧张量 + 板端 logits + manifest）+ 本文档 + 对比脚本输出；
- 期望方向（V2 候选内解决，**不在本工程做**）：
  - 提升 64QAM 类别间 logits 分离裕度（特征/损失），或
  - 量化感知训练（QAT）/ 更高精度推理路径，降低 int8 边界翻转。
- 本工程**只产出**上述可复现诊断资产；**不重训、不替换** `12CLASS_CHAIN_VALIDATION_MODEL`。

---

## 7. 红线

- 不调 `--min-match-rate`、不换 `--seed`、不跳过 64QAM、不 sample 挑选凑 PASS。
- dump 写盘失败即 fail-closed（`dump_error` 标记 + result=FAIL），绝不静默丢证据。
- 结论最高标 `READY-FOR-64QAM-PRECISION-DIAGNOSIS`；**绝不**写 `64QAM_PASS / FINAL_MODEL_PASS`。
- 我禁碰板、禁写 Flash；板端复跑与主机对比均由用户本人执行。
