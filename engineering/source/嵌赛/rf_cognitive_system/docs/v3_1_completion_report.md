# QAM-Aware RFNet V3.1 — 完成报告 (Completion Report)

Date: 2026-10-01
Scope: V3.1 model diagnosis / code correction / tests / ONNX gate / AutoDL training package.
Hardware baseline, frozen RTL, Golden, FPGA→NPU contract, V2/V3 frozen assets: **untouched**.

---

## A. V3 失败根因（基于证据）

见 `docs/v3_failure_diagnosis.md`。四个根因（均带具体数字）：

1. **增强信道失配（主因）**：V3 训练信道叠加了强瑞利/多径/窄带干扰，与 V2 兼容评估的 mild 信道分布不一致。
2. **checkpoint 按 val_loss 而非 macro-F1 选**：best_epoch=4，val_loss=0.9857，而非 macro-F1 最优轮次。
3. **早停在 epoch 16，早于 cosine 完成**：停止时 lr 仍为 8.54e-4，cosine 尚未收敛。
4. **QAM 二阶矩不足**：16QAM↔64QAM 混淆 488/8400，仅二阶功率矩无法区分高阶 QAM。

---

## B. 文件清单（新增 vs 修改）

**新增（V3.1 专属）：**

| 路径 | 作用 |
|---|---|
| `models/qam_aware_rfnet_v3_1.py` | V3.1 模型：`HigherOrderMomentPool(order=4)` + `DeployableStem1D` + 分区/构建/profile |
| `configs/qam_aware_v3_1.yaml` | 正式配置（gentle 信道 + macro-F1 checkpoint + min-epochs=60 + QAM 权重 + sdr_robustness_channel） |
| `configs/qam_aware_v3_1_smoke.yaml` | 小数据 CPU 冒烟配置 |
| `configs/qam_aware_v3_1_acceptance.yaml` | 验收门槛（与 V3 完全一致，未降低） |
| `training/qam_aware_v3_1_utils.py` | 配置加载（委托 V3 loader，复用契约校验） |
| `training/train_qam_aware_v3_1.py` | 训练入口（复用 `QAMAwareV3Trainer`） |
| `evaluation/evaluate_qam_aware_v3_1.py` | 三套件评估（v3_1_robust + v2_compatible 门槛 + sdr_robust 只报告） |
| `evaluation/check_qam_aware_v3_1_acceptance.py` | 验收门脚本（fail-closed） |
| `evaluation/audit_qam_aware_v3_1_dataset.py` | 数据泄漏/平衡审计入口 |
| `scripts/export_qam_aware_v3_1_onnx.py` | ONNX 双图导出 + 严格算子/形状门 |
| `scripts/package_qam_aware_v3_1_autodl.py` | AutoDL 一键包打包 |
| `scripts/package_qam_aware_v3_1_results.py` | 正式结果打包 |
| `tests/test_qam_aware_v3_1_resume.py` | 严格续训单测（连续 vs 中断续训一致性 + 选优策略变更拒绝） |
| `tests/test_qam_aware_v3_1_acceptance.py` | 验收门 fail-closed 单测 |
| `tests/test_qam_aware_v3_1_onnx_gate.py` | ONNX 门 fail-closed 单测 |
| `autodl_v3_1/` | README + shell 脚本（run_complete / run_smoke / setup_env / run_pilot / run_formal / resume_formal） |
| `docs/v3_failure_diagnosis.md` | 交付物 A（根因诊断） |

**修改（已存在文件，非新增）：**

| 路径 | 修改内容 |
|---|---|
| `training/resumable_trainer.py` | 严格续训 + checkpoint 选优策略拒绝逻辑（**已存在文件，本次修改，非新建**） |
| `.gitignore` | 忽略 `outputs/**`、`dist/`、`*.zip`、`*.onnx`、`*.pt` 等（**已存在文件，本次修改，非新建**） |
| `tests/test_qam_aware_rfnet_v3_1.py` | 补齐 min-epochs=60 断言 + 新增 sdr_robustness_channel 只报告断言 |
| `tests/test_qam_aware_v3_1_trainer.py` | 可反向传播的 `ConstantNet` 修复 |
| `docs/v3_1_completion_report.md` | 本报告 |

---

## C. V3.1 相对 V3 的差异

| 维度 | V3 | V3.1 |
|---|---|---|
| 训练信道 | 强干扰叠加 | **gentle**：V2-mild 为主 + 低概率 phase_noise/SFO/IQ imbalance |
| checkpoint 选择 | val_loss (min) | **val_macro_f1 (max)** |
| 早停 | epoch 16 即停 | **minimum_epochs_before_stopping=60**（=epochs=60，跑满，cosine 完成后才允许停） |
| QAM 特征 | 二阶矩 | **四阶原始矩** `E[x],E[x²],E[x³],E[x⁴]`（Mul→ReduceMean→Concat，全部 NPU 可部署） |
| 类别损失 | 均匀 | 16QAM=1.2 / 64QAM=1.3，label_smoothing=0.03 |
| ONNX 门 | 白名单外仅报告 Constant | **严格门**：任何白名单外算子 → 非零退出 |
| 鲁棒评估 | 无 | **sdr_robust 只报告套件**（不参与 V2 晋升门） |
| CUDA 可复现 | 未显式设置 | **`CUBLAS_WORKSPACE_CONFIG=:4096:8`**（所有 shell 脚本） |
| pip 镜像 | 依赖 AutoDL 默认源 | **可配置 `V3_PIP_INDEX_URL`**（默认清华，官方 PyPI 兜底，不重装/降级 torch） |
| 冻结契约 | — | 类别顺序 / sample_length=1024 / physical=3 / NPU 算子策略 **不变** |

---

## D. 数据/增强变更

- **数据切分不变**：train 100800 / val 16800 / test 16800，21 个 SNR 点（-20…20dB），与 V3/V2 完全一致（每 class×SNR 单元精确 600/100 样本，无泄漏）。
- **增强**：`cfo` p=0.6 ±1200Hz、`phase` p=0.6、`amp` p=0.5 [0.7,1.3]（V2-mild 主分布）；新增低概率 `phase_noise` p=0.1、`sfo` p=0.1 ±60ppm、`iq_imbalance` p=0.1。
- **关闭（训练信道）**：rayleigh / rician / multipath / dc_offset / clipping / narrowband_interference / burst 全部禁用（V3 的失配来源）。
- **`sdr_robustness_channel`（只报告探针）**：rayleigh p=0.2、rician p=0.2、multipath p=0.3、cfo p=0.8 ±2000Hz、phase p=0.8、phase_noise p=0.3、sfo p=0.25 ±80ppm、iq_imbalance p=0.3、dc_offset p=0.25、clipping p=0.15、narrowband p=0.15、burst p=0.15——仅评测并报告，**不参与 V2 晋升门**。
- **不改测试集调参**：`v3_1_final_blind_test` 命名空间保留，正式评估仅访问 dev test 与 snr_sweep。

---

## E. Checkpoint + 早停策略

- `checkpoint_metric: val_macro_f1`，`checkpoint_mode: max`。
- `minimum_epochs_before_stopping: 60`（epochs=60，跑满 cosine 全程）。
- `early_stopping_patience: 12`，`min_delta: 0.0001`。
- 严格续训：`resumable_trainer.py` 保存/恢复 model/optimizer/scheduler/AMP/RNG/DataLoader 生成器状态；`load_resume` 在 `checkpoint_metric`/`checkpoint_mode` 与 `last.pt` 不一致时**拒绝续训**（选优策略变更 → 拒绝）。

---

## F. QAM 定向改进

- `HigherOrderMomentPool(order=4)` 取代 V3 的二阶 `StatisticalPoolingV3`，直接物理支路输出 3×4=12 维**原始矩**（`E[x], E[x²], E[x³], E[x⁴]`——注意是原始矩，不是标准化的 skewness/kurtosis）。
- 仅用 **Mul + ReduceMean + Concat**，落在 NPU 允许算子集内，无新增不可部署算子。
- 辅助：16QAM/64QAM 类别权重 1.2/1.3，label_smoothing 0.03（轻量，不改类别顺序）。

---

## G. 参数 / MAC / 部署算子

- parameters = **506,872**；neural_macs = **55,044,608**（~55M）；fp32 参数 ~1.93 MB。
- 输入契约 `iq[N,2,1024] + physical[N,3,1024] -> logits[N,8]` 不变。
- 算子策略：**Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm only**（NPU 分区可编译）。

---

## H. 单测 + 冒烟结果（本机 CPU，已跑）

- 单测 **29 passed**：

| 文件 | 通过数 |
|---|---|
| `tests/test_qam_aware_rfnet_v3_1.py` | 10 |
| `tests/test_qam_aware_v3_1_trainer.py` | 2 |
| `tests/test_qam_aware_v3_1_resume.py` | 2 |
| `tests/test_qam_aware_v3_1_acceptance.py` | 3 |
| `tests/test_qam_aware_v3_1_onnx_gate.py` | 4 |
| `tests/test_resumable_trainer.py` | 1 |
| `tests/test_qam_aware_rfnet_v3.py` | 7 |

- 冒烟训练（2 epochs, CPU）：`train_loss=2.0999`、`val_loss=3.8705`、无 NaN/Inf；`DeployableStem1D`（affine=True 冻结）与 `affine=False` 数值完全一致。
- 冒烟评估三套件：`v3_1_robust`（report_only=false）、`v2_compatible`（exact_v2_test_namespace=true、report_only=false）、`sdr_robust`（**report_only=true**）；`final_blind_test_accessed=false`。

---

## I. 数据泄漏 + 平衡审计

- **指纹重叠（真正的泄漏信号）**：train/validation/test 两两 **全部为 0**（配置无关）。
- **正式配置平衡**：与 V3 完全相同的切分（每 class×SNR cell 精确 600/100），`_dataset_distribution` 构造上无余数 → 正式配置**精确平衡**。
- **冒烟配置**：`blocking_leakage_found=true` 的 `"not exactly class/SNR balanced"` 是**小样本伪影**（512/256/256 × 3 SNR → SNR 168-176 非整数），非数据问题；指纹重叠仍为 0。

---

## J. ONNX 导出结果（本机已跑，严格门通过）

`outputs/qam_aware_v3_1/smoke/onnx/export_report.json`：

| 项 | 结果 |
|---|---|
| e2e `checker_passed` | true（opset=17；`iq` FLOAT [1,2,1024] → `logits` FLOAT [1,8]） |
| npu_partition `checker_passed` | true（opset=17） |
| npu_partition 输入 | `iq` FLOAT [1,2,1024] + `physical_features` FLOAT [1,3,1024] |
| npu_partition 输出 | `logits` FLOAT [1,8] |
| npu_partition 算子 | Add 6 / BatchNormalization 3 / Concat 5 / Conv 24 / Gemm 2 / Mul 4 / ReduceMean 6 / Relu 22 |
| **npu_partition 白名单外算子** | **`[]`（无 Constant 节点，`DeployableStem1D` 已消除）** |
| e2e 额外算子 | Ceil/Clip/Div/Floor/GreaterOrEqual/Slice/Sub/Where（部署输入量化仿真路径，非 NPU 分区） |

门为 fail-closed：任何白名单外算子、错误 shape、错误 dtype、opset≠17、`onnx.checker` 失败 → 非零退出（`tests/test_qam_aware_v3_1_onnx_gate.py` 4 个用例验证）。

---

## K. AutoDL 包路径 + SHA-256

- 路径：`F:\嵌赛\rf_cognitive_system\dist\qam_aware_v3_1_autodl_final.zip`
- 大小：**176,738** 字节；文件：**125** 个（124 内容 + 1 `sha256_manifest.txt`）
- **SHA-256**：`75e077d5ebdf3a1a23c10471220dc52d53e4f210f5ed841b404c7d52c38f5510`
- 包内 `sha256_manifest.txt` 复核：**124 项全部匹配，0 mismatch，无缺失/多余**。

---

## L. AutoDL 唯一命令

解压到纯英文路径后：

```bash
bash autodl_v3_1/run_complete.sh
```

中断后重跑同一命令即从 `last.pt` 严格续训（详见 README）。

---

## M. 仍待 AutoDL 的验证项

| 验证 | 状态 |
|---|---|
| 完整 60-epoch CUDA 正式训练 + 续训 | **待 AutoDL**（本机 torch 为 CPU-only） |

其余全部已在本地完成或由构造保证：单测 29/29、冒烟训练/评估/审计、ONNX 双图导出 + 严格算子/形状门、验收门 fail-closed、AutoDL 包内部 SHA-256 复核。

---

## N. 冻结资产是否被修改

**否。** 六个冻结 Mandatory Core RTL、Python Golden、固定 IQ/Tensor、V2 checkpoint/ONNX/iCraft/评估、已验证 bitstream/LTX/capture/STA、FPGA Tensor 契约、final blind test、原 V3 结果压缩包——均未读取为可写目标、未覆盖、未删除。本次仅新增/修改 V3.1 专属文件与 `dist/`、`outputs/qam_aware_v3_1/` 新目录。
