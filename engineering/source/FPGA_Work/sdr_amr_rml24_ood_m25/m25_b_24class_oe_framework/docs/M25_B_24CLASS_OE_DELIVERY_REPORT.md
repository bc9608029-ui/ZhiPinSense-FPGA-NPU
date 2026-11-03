# M25-B 24 类 OE 增强框架交付报告

状态：**`24CLASS_BASELINE_NOT_FROZEN` / `24CLASS_OE_MODEL_NOT_TRAINED`**
（框架就绪，24 类正式 baseline 与 OE 模型均未训练/未冻结，符合用户指令"24 类正式
baseline 冻结之前禁止启动 OE 训练"）。

## 1. 交付内容

自包含 Python 框架（运行时不 import `sdr_amr_rml24_ood_v1_1`），目录：

| 组件 | 文件 | 作用 |
|---|---|---|
| 契约 | `contracts/m25b_24class_contract.py` | 冻结 24 类序/输入契约/SHA/禁词 |
| 数据协议 | `contracts/m25b_oe_data_protocol.py` | OE 样本**不是第 25 类**，带 source |
| 生成器 | `datasets/m25b_ood_generator.py` | 近/远/模糊 OOD 族，SeedSequence 三路隔离 |
| manifest | `datasets/m25b_generator_manifest.py` | 写一次、按族/分裂记 SHA |
| 隔离审计 | `audit/m25b_isolation_audit.py` | 三路分裂零交集 |
| 捷径审计 | `audit/m25b_shortcut_audit.py` | 禁走 ID HDF5 生成器路径 |
| 分数 | `ood/m25b_scores.py` | MSP/Entropy/MaxLogit/LogitMargin/Energy |
| 阈值 | `ood/m25b_thresholds.py` + `_manifest.py` | 三工作点，仅 ood_validation 锁 |
| 指标 | `ood/m25b_metrics.py` | AUROC/AUPR/FPR95/OSCR/检测准确率/bootstrap |
| OE loss | `training/m25b_oe_energy_loss.py` | CE + lambda·(relu² 能量拉推) |
| 控制 | `training/m25b_oe_controls.py` | 1+2 seed 晋升门 |
| 预算 | `training/m25b_budget.py` | phase-1 硬 ID 保护门 |
| baseline 门 | `training/m25b_baseline_gate.py` | 缺失 → NOT_FROZEN 退出 |
| NPU 边界 | `npu_boundary/m25b_npu_boundary.py` | 五段一致性/方向校验 |
| 脚本 | `scripts/*.sh`（8） | 审计/训练/校准/评测/blind/test |
| 测试 | `tests/test_m25b_*.py`（21） | 单元 + mock 流程 |

## 2. 关键设计

- **OE 不是第 25 类**：OE 样本是 logits 成形用 aux 输入，带 `source`(near/far)，绝不并入 24 类标签空间。
- **三路隔离**：`SeedSequence([seed, split_code, family_code])`，oe_aux / validation / final 零交集，逐族逐 split 计数。
- **Energy loss**：`L = CE(ID) + λ·[relu(E_ID−m_in)² + relu(m_out−E_OOD)²]`，`E=−T·logsumexp(logits/T)`，纯 CPU 后处理，NPU 仍只出 24 维 raw logits。
- **baseline 门禁**：训练/校准/final_blind 先检 baseline manifest，缺失打印 `24CLASS_BASELINE_NOT_FROZEN` 并 exit 0（fail-closed）。
- **budget 门禁**：overall acc −1pp、macro-F1 −1pp、rated_0_20 −0.5pp、min-class 不崩、低 SNR ID 拒绝、CFO/多径/相噪/IQ 失衡/clipping ID 接受、近/远 OOD 改善，任一失败 → `OE_DECISION result=REJECT`。

## 3. 验证方式（本轮离线）

- `pytest tests/ -q`（torch/onnxruntime 缺失处 `importorskip` 明确 skip；numpy-only 测试全跑）。
- `python -m compileall` 全 py。
- `bash -n` 全部 `.sh`；训练类脚本无 baseline manifest 时打印 NOT_FROZEN 并退出。
- 打包 `dist/m25_b_24class_oe_framework_patch.tar.gz` + manifest `M25_B_PATCH_SHA256SUMS.txt`（只列内容、不含自身、无裸 SHA256SUMS.txt）。

## 4. 状态红线

本框架**永不**写以下状态（真实 RF/NPU 对齐前）：`FINAL_MODEL_PASS`、
`FINAL_24CLASS_PASS`、`OOD_PASS`、`HARDWARE_PASS`、`FULL_CHAIN_PASS`、
`PROJECT_COMPLETE`、`DEPLOYMENT_PASS`、`PERFORMANCE_PASS`、`24CLASS_OE_PASS`、
`24CLASS_OE_HARDWARE_PASS`、`TEMPORAL_FUSION_HARDWARE_PASS`。

## 5. 十二问

1. **baseline 冻结定义**：`24CLASS_BASELINE_FROZEN` 需要哪些 manifest 字段与哪个 SHA 才算冻结？当前占位字段为 `model_sha256/checkpoint_path/label_order_sha256`，是否还需 `input_contract_sha256` 与 `onnx_sha256`？
2. **阈值锁定时机**：阈值只在 `ood_validation` 锁，默认 `id_accept_99`；上板后若要切 `id_accept_95` 或 `far_ood`，由谁、经何流程改锁？
3. **OE 辅助规模**：`oe_aux_train` 每族样本数（现默认 256/族）与 `lambda_oe`、`margin_in/margin_out` 的搜索域，是否沿用 V1.1 的 OE config，还是需要为 24 类重定？
4. **近 OOD 语义重叠**：`2FSK/GFSK/OFDM` 与 24 类的 `GMSK/FM` 存在语义重叠，近 OOD 拒绝的"合理目标"（AUROC/拒绝率）以什么为准？
5. **NPU 真实 logits 对齐**：fake-int8 与真实 NPU 的量化 scale 是否 per-tensor、对称？`npu_boundary` 的 `atol/rtol`（1e-3）是否满足 Energy 阈值方向一致性？
6. **OOD 与 12 类 OOD-U 的关系**：24 类 Energy OOD 阈值与已部署 12 类 `logit_margin` OOD-U 是两套独立判据还是需统一？
7. **预算门禁的 min-class 地板**：min-class 崩坏的绝对地板（现为"相对 baseline 掉 >2pp"）是否足够，是否需要绝对下限（如每类 acc ≥ 某值）？
8. **鲁棒性验收域**：CFO/多径/相噪/IQ 失衡/clipping 的强度档位与判定阈值是否与 V1.1 `RobustChannelPipeline` 一致？
9. **1+2 seed 晋升**：PROMOTE 后 2027/2028 是否必须与 2026 完全同超参，还是允许各 seed 独立搜索？预算上限是否仍为 6 次训练？
10. **final_blind 的读取范围**：`ood_final_test` 在阈值锁定后是否一次读尽、禁止回看？是否需要按族做 bootstrap CI（现 `bootstrap_ci` 已提供，默认 1000 次）？
11. **包交付边界**：`m25_b_24class_oe_framework_patch.tar.gz` 不含任何 checkpoint/模型，是否满足"框架交付"预期？何时需要补一份"训练就绪"的 OE config 样例？
12. **上板验收前置**：24 类 baseline 冻结后，先走 ONNX 导出 → fake-int8 对齐 → 真实 NPU logits 采集，再谈 OOD 阈值上板，这一顺序是否正确、有无遗漏？

## 6. 下一步（待用户指令，不擅自启动）

1. 等待 24 类正式 baseline 冻结（manifest 落盘）。
2. baseline 冻结后，先跑 `run_24class_oe_seed2026.sh`（verify 1 次）与 `run_24class_oe_decision.sh`。
3. 阈值校准 → final_blind → 上板 NPU 对齐。
