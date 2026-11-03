# M29 Phase D.3 — 动态范围感知重校准（最后一次有界 PTQ 机会）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（未变；D.3 完成后仍不晋升——PTQ 已耗尽，提交 QAT 申请）
> 前序：D.2 结论已接受（停止逐层 bf16/分组二分，不执行 fc1→bf16）；QAT 暂未批准。
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁重训 / 禁自动启动 QAT / 禁写 FINAL_*/NPU_PASS 等。

---

## 0. 目标与判定边界

D.2 结论：AM-SSB-SC 崩塌是**分布式 INT8 激活动态范围失配**，根因在 AM 族输入幅度 ~10×。D.3 是唯一一次有界 PTQ 补救：**只改校准样本索引**，其余（模型/ONNX/int8/kld/batch=8）全部不变，跑一个新候选。

- 若新校准仍无法满足 min_class / 单类崩塌门禁，或修复 AM 后伤害其它 22 类 → **宣布 PTQ 耗尽，提交 QAT 申请**，不再做校准调参。
- 不自动启动 QAT；不读 test；不上板。

---

## 1. Step 1 — 输入契约审计（已完成）

### 1.1 预处理一致性（全部通过，未发现不一致 → 不触发"停止"分支）

| 维度 | PyTorch | ONNX | 校准 .bin | icraft-run |
|---|---|---|---|---|
| dtype | float32 | `iq` float32 | float32 | `@fp(32)` → Cast `@sint(8)` |
| I/Q 顺序 | `raw.T` → [2,1024] | [1,2,1024] `FD` | planar [2,1024] C 序（1024 I 后 1024 Q） | 同 |
| shape | [1,2,1024] | [1,2,1024] | [2,1024]×384 | inputs `1,2,1024` |
| 归一化 | 无（原始 RMS≈0.71–1.0） | 无 | 无 | 无 |
| rec_scale / pre_scale | — | — | — | `pre_method/pre_scale/pre_mean/channel_swap = "nop"`、`no_transinput=true` |
| 裁剪 | 无 | 无 | 无 | 输入层 int8 量化 clip ±6.686（见 1.2） |
| 字节序 | native LE | native LE | native LE | native LE |

- **`.bin ↔ HDF5 raw.T` 逐字节一致：384/384，mismatch=0**（Part A）。
- ONNX 输入契约 `{name:"iq", dims:[1,2,1024], dtype:"float32"}`。
- **结论：输入契约一致，无预处理不一致，允许继续生成新校准集。**

### 1.2 iCraft 输入层 + 首卷积量化器（`model_24class_quantized.json`）

| 张量 | storage | zero_point | scale（per-channel） | clip |
|---|---|---|---|---|
| 输入（Cast 后） | `@sint(8)` | `[]`（对称，零） | `[0.052646082, 0.052646082]`（2 通道同） | **±6.6861** |
| 首卷积输出（stem） | `@sint(8)` | `[]` | `24 × 0.05337289` | **±6.7784** |
| 首卷积权重 | `@sint(8)` | `[]` | 24 通道，min 0.001087 / max 0.007540 | — |

关键事实：**输入在进入第一个卷积前就被 Cast 成 int8**（scale 0.052646082，clip ±6.686），AM-SSB-WC 高幅输入（±43）在输入层即被裁 ~6.4×。

### 1.3 固定 1536 诊断子集逐类输入饱和率（smoking gun）

输入 clip = ±6.686；`inSat%` = 元素 |x|>clip 比例（64 样本均值 / 最大值）：

| 类 | RMS | peak | inSat% 均值 | inSat% 最大 |
|---|---:|---:|---:|---:|
| 其它 22 类 | ≈0.71 | ≈2.1–3.0 | **0.000** | 0.000 |
| AM-SSB-WC | 3.375 | 5.955 | **11.70** | **100.0** |
| AM-SSB-SC | 2.497 | 4.805 | **9.46** | **100.0** |

- 22 类输入**零饱和**；AM 族平均 9–12% 元素被裁，个别样本 100% 被裁。
- 这与 D.2 的"AM 输入 ~10× 幅度"结论在**输入层即表现为实际裁剪事件**——首层饱和就是分布式失配的起点。

（Step 1 产物：`work/d3_step1_input_contract_audit.json` + `scripts/d3_step1_input_contract_audit.py`）

---

## 2. Step 2 — 构建动态范围感知 384 校准集（已完成）

### 2.1 与旧 384 的关键差异（两处）

1. **split 变更**：旧 384/624 用 **validation** 分割；D.3 按指令改用 **train** 分割（`train_indices`，1,533,168 样本）。train 与 validation 评估域**不相交**，消除校准↔评估重叠。test 未读。
2. **幅度分层**：旧 384 只按 SNR 分层（6/5/5），无幅度控制；新 384 按 **RMS 分位数 + SNR 分位数** 联合分层。

### 2.2 选择规则（确定性，新 seed = 20281010）

- 每类取 seeded 8192 子集估计 RMS/peak/crest；按 RMS 切 5 个幅度箱（p50/p75/p90/p95）。
- 分配 `[4,3,3,3,3]`：`<p50` 4、`p50-75` 3、`p75-90` 3、`p90-95` 3、`≥p95` 3（**体部加权、非"只挑最大"**）。
- 每箱内按 SNR 升序取等距分位样本 → 低/中/高 SNR 覆盖。
- 不用 validation 结果逐样本挑；不读 test。

### 2.3 AM 族幅度覆盖（新旧对比，RMS/peak）

| 类 | 旧 384 rms[mn,med,mx] / peak | 新 384 rms[mn,med,mx] / peak | 真分布 q50/q75/q90/q95 |
|---|---|---|---|
| AM-SSB-WC | [0.69, **1.55**, 17.32] / 23.66 | [0.71, **7.18**, 13.68] / 19.95 | 1.92 / 5.85 / 10.35 / 12.77 |
| AM-SSB-SC | [0.70, **3.22**, 6.71] / 10.85 | [0.70, **5.63**, 10.51] / 12.16 | 2.17 / 4.99 / 6.59 / 7.23 |
| 其它 22 类 | ≈[0.70, 0.71, 0.73] | ≈[0.70, 0.72, 0.74] | ≈0.71（紧分布） |

- 新 384 的 AM 幅度中位数（WC 7.18 / SC 5.63）显著高于旧集（WC 1.55 / SC 3.22），并把高尾（WC 13.68 / SC 10.51 RMS，远超输入 clip 6.686）纳入校准。
- AM 幅箱覆盖实测：`<p50:4 p50-75:3 p75-90:3 p90-95:3 ≥p95:3`（两 AM 类一致）。
- 其它 22 类分布紧、新旧集一致（RMS≈0.71）。

### 2.4 产物与 SHA

- 目录 `work/calibration_384_dra/`（全新，未碰 `work/calibration_384/`）。
- `forward_list.txt` SHA `b31616b9…`；`calibration_manifest.json` SHA `f6eedb78…`。
- HDF5 `e3dd0bef…` / 索引 `9a035841…` 门禁通过；`test_split_touched=false`。
- 覆盖对比 `work/calibration_384_dra/calibration_coverage_compare.json`。

（脚本：`scripts/d3_step2_build_calibration_384_dra.py`）

---

## 3. Step 3 — 唯一新 PTQ 候选（已完成）

- 目录 `_tmp_24class_dra_384_20261011\`，`compile_dra.toml` + `run_dra.sh`。
- 唯一变量 = `[quantize] forward_dir/forward_list` → `work/calibration_384_dra/`。
- 模型/ONNX/`qdtype=int8`/`saturation=kld`/`per=channel`/`batch=8` 全部不变；**无 mix_precision（全 130 op int8，同 384 基线）**。
- 复用 `model_24class_optimized.json/.raw`（parse/optimize 不变），只跑 quantize→adapt→generate 一次。

**运行结果**：quantize exit 0 / 644s / 峰值 2.12GB；adapt exit 0 / 38s；generate exit 0 / 38s。

| 产物 | SHA | 字节 | 说明 |
|---|---|---|---|
| `model_24class_quantized.json` | `65048eba…` | 401234 | **激活 scale 变**（旧 384 `2fca4c94…` 403272B） |
| `model_24class_quantized.raw` | `e86a8b82…` | 284500 | **与旧 384 逐字节一致**（权重校准无关） |
| `model_24class_ZG.json` | `654c2f3d…` | 222560 | 新 NPU 候选 |
| `model_24class_ZG.raw` | `a588814e…` | 2853100 | 新 NPU 候选 |

**scale 变化（关键观察）**：`quantized.raw` 与旧 384 **完全一致** → 权重未变，唯一变量确系校准样本。但 `quantized.json` 的 **131/131 个 int8 张量 scale 全部变化**（>0.5%），最大 +16.5%（op121/124 深层 Conv2d/ReLU），输入层 scale **反而 −5.3%**（0.052646 → 0.049874，clip ±6.686 → ±6.334）。即：KLD 按**体部最优**（22 类多数）重排了整网 scale——深层 conv 略微放宽（+16%）、输入略微收紧（−5%），而非整体放宽以容纳 AM 尾。这印证了"共享 per-channel scale 无法按类分别放大"的结构性限制，最终判定以 Step 4 评估为准。

---

## 4. Step 4 — 固定评估（完成）→ 门禁未通过

### 4.1 1536 诊断集 icraft-run 结果（`model_24class_ZG` = `654c2f3d…`/`a588814e…`）

| 指标 | DRA384（新） | 384 基线 | fp32（同子集） | Δ vs fp32 |
|---|---:|---:|---:|---:|
| accuracy | 0.542318 | 0.539062 | 0.554036 | −1.17pp |
| macro-F1 | 0.566258 | 0.5619 | 0.561532 | +0.47pp |
| rated_0_20 | 0.835069 | 0.8385 | 0.855903 | −2.08pp |
| snr0 | 0.541667 | — | 0.555556 | −1.39pp |
| **min_class** | **0.140625（AM-SSB-SC）** | 0.0781 | 0.406250（64APSK） | **−26.6pp 错位** |
| **AM-SSB-SC** | **0.1406** | 0.078 | 0.5156 | **−37.5pp 崩塌** |
| AM-SSB-WC | 0.6875 | — | 0.6094 | +7.8pp（恢复） |
| Top-1 一致率 | 0.611979 | 0.615 | — | 远低于 0.98 门 |

（`accuracy_drop=0.01171875`；`min_class_drop=0.265625`）

### 4.2 AM-SSB-SC 崩塌未解（核心判决）

- 正确率 9/64 = **14.06%**（fp32 51.56%，−37.5pp）；高 SNR 12–30dB 3/20 = **15%**。
- 混淆去向：**36 → AM-SSB-WC**、13 → OOK、6 → 其它——与 D.1/D.2 完全同型（仍被相邻 AM 兄弟类吸收）。
- logits margin：AM-SSB-SC **median 0.0**（p90 2.33，max 4.66）vs 全体 median 1.165（p90 29.1）——**近并列小 logits 在量化下被翻转**的 D.2 根因特征依然存在。
- 逐类输入饱和（新 clip ±6.334）：AM-SSB-WC 13.6% / AM-SSB-SC 10.7%（最大 100%），其余 22 类 0.000%——**幅度分层校准未能消除 AM 输入裁剪**（输入 scale 反而收紧 −5.3%，见 §3）。

### 4.3 修复 AM 是否伤害其它 22 类？（未发生新崩塌）

| 类 | 量化 | fp32 | Δ |
|---|---:|---:|---:|
| OOK | 0.9062 | 0.7031 | **+0.203**（OOK 成 AM-SSB-SC 误判收受方，召回虚高） |
| 32PSK | 0.3906 | 0.5312 | −0.141 |
| 128QAM | 0.3438 | 0.4219 | −0.078 |
| GMSK | 0.5938 | 0.6719 | −0.078 |
| AM-DSB-SC | 0.4531 | 0.5156 | −0.062 |
| 其余 18 类 | — | — | \|Δ\|≤0.05 |

- 除 AM-SSB-SC（−37.5pp）外，其余 23 类最大跌幅 0.141pp（32PSK），**无新单类崩塌**；但 AM-SSB-SC 自身仍崩塌，不满足门禁。

### 4.4 判决

- 动态范围感知 384 校准把 AM-SSB-SC 从 7.8% 提到 14.1%，但**仍未解崩塌**（−37.5pp）；min_class 仍为 AM-SSB-SC 且 0.140625，远不达标；Top-1 一致率 0.612 远低于 0.98。
- 触发停止条件 1（"min_class / 单类崩塌门禁仍不满足"）→ **宣布 PTQ 路径耗尽，提交 QAT 申请**。

（Step 4 产物：`work/d3_step4_saturation_gate.json` + `scripts/d3_step4_saturation_gate.py`；1536 报告 `_tmp_24class_dra_384_20261011_eval_result/dra384_report.json`）

---

## 5. 结论与状态

- **PTQ 路径耗尽**：D.2 的分布式 INT8 动态范围失配根因，在"只改校准样本索引"的有界 PTQ 内不可修复——共享 per-channel scale 无法按类放大 AM，幅度分层只把 AM-SSB-SC 从 7.8% 拉到 14.1%（仍 −37.5pp）。
- **提交 QAT 申请**（未自动启动）：依据停止条件，唯一可行路径是 QAT（量化感知训练）。本阶段仅形成申请结论，**不启动** QAT 训练。
- 未碰板 / 未写 Flash / 未访问 test / 未重训 / 未自动启动 QAT。
- 状态保持 `M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`；旧 384 基线 `model_24class_ZG`、实验 A（op179→bf16）、**新 DRA `model_24class_ZG`（`654c2f3d…`/`a588814e…`）均 REJECTED**（禁碰板 / 禁写 NPU_PASS）。
- 禁写 `FINAL_MODEL_PASS / FINAL_24CLASS_PASS / OOD_PASS / HARDWARE_PASS / FULL_CHAIN_PASS / PROJECT_COMPLETE / NPU_PASS / 24CLASS_PASS / 24CLASS_SYSTEM_PASS / FINAL_PASS / FINAL_*`。
