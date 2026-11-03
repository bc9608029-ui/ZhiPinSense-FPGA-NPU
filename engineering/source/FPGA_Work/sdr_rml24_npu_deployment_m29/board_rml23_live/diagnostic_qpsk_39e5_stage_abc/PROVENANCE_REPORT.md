# Stage A — 训练来源与契约取证（PROVENANCE_REPORT）

**绑定指令** 39e5 · **日期** 2026-10-11 · **输出目录** `diagnostic_qpsk_39e5_stage_abc/`

每条证据标注 **CONFIRMED**（本会话实测/由冻结工件字段证实）· **INFERRED**（合理推断但无直接日志）
· **MISSING**（未找到）· **UNKNOWN**（无法从现有工件重建）。

---

## 0. 一句话结论

**模型身份、数据身份、标签契约、输入契约、评估结果均可 CONFIRMED**（本会话 SHA 复核一致）。
**训练超参数与训练轨迹只能部分 CONFIRMED**：optimizer/loss/class_sampling/batch/amp/snr_weighting 有
冻结计划文档记载，但**没有逐 epoch 训练日志**，且 `epochs` 在三处工件中**互相矛盾**（计划=20、
checkpoint 内记录=50、base 配置=80），因此**实际训练轮数 / 早停触发点 / 每轮 loss·acc 曲线 = UNKNOWN**。

**严格未凭文件名编造任何超参**：`rml24_seed2027_best.pt` 中的 `seed2027` 与 `best` 均另由
`final_checkpoint_manifest.json` 的 `selected_seed` / `selection_value` 字段独立证实，非文件名推断。

---

## 1. 模型与权重身份（全部 CONFIRMED）

| 工件 | 路径 | SHA256（本会话实测） | 状态 |
|---|---|---|---|
| 最终 checkpoint | `_frozen/runs/rml24_base/formal/t002_…/seed2027/checkpoints/best.pt`（≡ `F:\FPGA_Work\24class_results\rml24_seed2027_best.pt`） | `96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d` | **CONFIRMED** |
| FP32 ONNX | `work/onnx/rml24_24class_opset17.onnx` | `976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51` | **CONFIRMED** |
| checkpoint 内记录 epoch | `checkpoint_epoch` 字段 | **50** | **CONFIRMED**（存入 checkpoint 本身） |
| 模型名 | `RML2018_24_BENCHMARK` | — | CONFIRMED |
| 参数数 | 280584 | — | CONFIRMED（export_report） |
| 架构 | ADAMRV11Net：denoiser(stem+3 block)+features(8 block)+classifier(Gemm+Relu+Gemm) | ONNX 67 节点 = Conv28/Relu24/Add12/Gemm2/ReduceMean1，**无 BatchNorm/归一化层** | CONFIRMED |

---

## 2. 训练超参数（有记载但需分级）

来源二：`configs/rml24_base.yaml`（base 默认）与 `_frozen/runs/rml24_base/reassess/reassessed_formal_candidate_plan.json`（正式候选计划）。

| 超参数 | 值（来源） | 状态 |
|---|---|---|
| loss | cross_entropy（formal plan v2） | CONFIRMED（文档） |
| optimizer | AdamW（formal plan v2） | CONFIRMED（文档） |
| class_sampling | balanced（formal plan v2） | CONFIRMED（文档） |
| batch_size | 256 | CONFIRMED（文档） |
| learning_rate | **3e-4**（formal plan）vs **1e-3**（base yaml） | 两文档不一致 → 实际值 **UNKNOWN**（无日志） |
| weight_decay | **1e-5**（formal plan）vs **1e-4**（base yaml） | 两文档不一致 → 实际值 **UNKNOWN** |
| epochs | **20**（formal plan）vs **80**（base yaml）；checkpoint 记录 **50** | **三处矛盾 → UNKNOWN** |
| early_stopping_patience / min_delta | 12 / 1e-4（formal plan） | CONFIRMED（文档）；是否触发 **UNKNOWN** |
| gradient_clip_norm | 2.0 | CONFIRMED（文档） |
| amp / amp_dtype | true / bfloat16 | CONFIRMED（文档） |
| snr_weighting | very_low 0.35 / rated 1.25 / zero_db 1.2 | CONFIRMED（文档） |
| SNR 范围 | −20 … +30 dB（26 级，2 dB 步） | CONFIRMED（`per_snr_accuracy` 覆盖 −20…+30） |
| 种子 | 2027 | CONFIRMED（manifest `selected_seed`，非文件名） |

> **红线遵守**：上表 learning_rate/weight_decay/epochs 两文档矛盾且无日志，**不臆造**“实际用了哪个”。
> 已声明 UNKNOWN。

---

## 3. 数据 / 划分 / 契约身份（全部 CONFIRMED）

| 工件 | 路径 / 字段 | SHA256 / 值 | 状态 |
|---|---|---|---|
| 数据集 HDF5 | `GOLD_XYZ_OSC.0001_1024.hdf5`（2555904 样本，[1024,2]） | `e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38` | CONFIRMED |
| 划分索引 | `data/radioml2018/rml24_split_indices.npz` | `9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335` | CONFIRMED（本会话 sha256sum） |
| 划分策略 | seed 20261003，[0.6,0.2,0.2]，按 (class,snr) 分层 624 层，无重叠 | — | CONFIRMED |
| 标签契约 | `contracts/rml24_contract.py`（LABEL_ORDER_24） | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` | CONFIRMED |
| 输入契约 | `[1,2,1024]` fp32 planar(I/Q)，**normalization=none**（unit-RMS ≈1.002） | — | CONFIRMED |
| 数据加载 | `datasets/radioml2018_dataset.py::__getitem__`：`iq = raw.T`（[1024,2]→[2,1024]），无归一化 | — | CONFIRMED |
| 24 类标签序 | 0=OOK…3=BPSK, 4=QPSK…16=256QAM, 17=AM-SSB-WC, 18=AM-SSB-SC…23=OQPSK | — | CONFIRMED |
| 24→23 合并契约 | 17/18 → logaddexp 合并，19..23 下移 | — | CONFIRMED（前序冻结） |

---

## 4. 训练脚本 / 导出脚本（存在性 CONFIRMED）

| 脚本 | 路径 | 状态 |
|---|---|---|
| 正式训练入口 | `sdr_amr_rml24_ood_v1_1/training/rml24_formal.py` | CONFIRMED（存在） |
| 试点训练入口 | `training/rml24_pilot.py` | CONFIRMED（存在） |
| trainer / 选择 | `training/rml24_trainer.py` / `training/rml24_select.py` / `training/rml24_run.py` | CONFIRMED（存在） |
| FP32 ONNX 导出 | `scripts/export_rml24_onnx.py`（产 `rml24_24class_opset17.onnx`） | CONFIRMED（存在） |
| 模型定义 | `models/rml24_net.py`（RML2018_24_BENCHMARK） | CONFIRMED（在 final artifacts tar 内） |
| 评估 | `evaluation/evaluate_rml24.py` | CONFIRMED（存在） |

**训练日志 / 逐 epoch 指标 / tensorboard / history**：在 `m29\_frozen`、`m29\work`、`24class_results\`、
`rml24_final_artifacts.tar.gz` 内**均未找到** → **MISSING**（`rml24_final_artifacts.tar.gz` 仅含最终工件，
不含训练轨迹；其 `.sha256` 记录 AutoDL 端 `/root/autodl-tmp/…` 的 tar SHA `0b2b7c2a…`，证来源 AutoDL）。

---

## 5. 评估指标（CONFIRMED，`rml24_closed_set_final.json`）

| 指标 | 值 | 说明 |
|---|---|---|
| test accuracy | 0.630808 | 全 24 类闭集 |
| macro_f1 | 0.636521 | |
| **QPSK per-class** | **0.6697**（24 类中第 4 项） | 合成域 QPSK 本身只有 ~67% |
| min_per_class | 0.517636（256QAM） | |
| rated_0_20_accuracy（final test） | 0.891981 | 与选点时（val）0.890998 不同，注意区分 |
| high_10_20_accuracy | 0.977270 | |
| per_snr_accuracy | −20 dB:0.045 … 0 dB:0.573 … +20 dB:0.979 … | 覆盖 −20…+30 dB |

---

## 6. deployment_golden 性质澄清（必读）

`board_rml23_live/deployment_golden/` 的 240 帧是**部署一致性/conformance golden**，用途是验证
**板端 NPU 是否忠实复现冻结 Host/FP32 参考输出**（后端一致性），**不是模型准确率评估集**。
`offline match_rate` 衡量的是“板端输出与参考 argmax 一致的比例”，**绝不等于**模型分类准确率。
任何文档不得把 golden 的 match_rate 称作“准确率”。（与冻结计划 §1.1/红线一致。）

---

## 7. 对最终判责的输入

- 训练域 = RadioML2018.01A 合成域（QPSK per-class 仅 0.6697，模型本身在合成域对 QPSK 也不强）。
- 输入契约 = 无归一化、unit-RMS、[2,1024] planar —— Stage C 将检验“精确复刻训练加载器预处理”是否足以对齐。
- 真实域 QPSK 被判为 QAM（Stage B 已量化：激活系统性放大 1.26×、谱结构失配）→ 判责收敛方向
  见最终 `JUDGMENT.md`。

**红线遵守**：未改模型/标签/golden/预处理/RTL/位流/Flash；未训练；未写 `*_PASS`/`PROJECT_COMPLETE`；
未凭文件名编造超参。
