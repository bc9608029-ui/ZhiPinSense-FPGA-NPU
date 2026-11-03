# data-v4 十二类鲁棒性增强：pilot → formal 执行计划

**状态：`READY-FOR-AUTODL-ROBUST-PILOT`。** 这是 AutoDL 正式运行前离线能到的最高状态；
未上 AutoDL 跑出 pilot/formal 结果前，**不写任何 PASS / READY / 根因确认 / 脆弱类别结论**。

---

## 0. 一句话目标

十二类模型在 OOD 域 `cfo_strong / multipath / multi_impairment` 上 macro-F1 下降超过 0.08
正式门禁。v4 通过在**训练域**注入「核心 + 强尾 + 复合」增强（`robust.train_channel`，仅作用于
train split），低学习率从十二类正式 `best.pt` 微调，把这些 OOD 域的下降拉回 0.08 以内，
同时不破坏干净验证/额定 SNR/伪 INT8/ONNX 算子白名单等冻结门禁。

---

## 1. 已确认的基线事实（任务书 §二，只写「失败域已定位」，不写根因）

来源：`scripts/verify_paired_records.py --acceptance outputs/ad_amr_v1_1_data_v3_12class/formal/acceptance.json`。

- 冻结契约：`class_contract=12`、`promoted=false`（十二类基线自身未通过全部门禁）。
- **唯一失败门禁**：`ood_macro_f1_drop`（上限 0.08，不可放宽）。
- 双种子 OOD macro-F1 下降（负值 = OOD 反而更好）：

| 域 | 下降 | 是否超出 0.08 |
|----|------|--------------|
| `cfo_strong` | 0.124530 | **是** |
| `multipath` | 0.117748 | **是** |
| `multi_impairment` | 0.132175 | **是** |
| `clipping` | 0.028004 | 否 |
| `phase_noise` | -0.025391 | 否 |
| `iq_imbalance` | -0.021351 | 否 |

**结论措辞固定为「失败域和受损类别已定位」**，不得据此断言根因或「某类主因」。

---

## 2. 增强设计（任务书 §五，全参数在 YAML，无硬编码）

`channel/robust_augment.py::RobustChannelPipeline` 是 `ChannelPipeline` 的向后兼容扩展：
无 tail/composite 时行为逐字节一致、RNG 消耗不变。新增三个机制：

- **核心（core）**：沿用冻结 `channel` 的训练域随机范围（multipath 0.12 taps[2,4]/delay10、
  cfo 0.55 ±1200、phase_noise 0.10 [0.0001,0.003]、iq_imbalance 0.12 [-1,1]dB/[-5,5]°、
  clipping 0.06 [1.5,2.5]）。
- **强尾（tail）**：以 `tail.probability` 概率用更极端参数覆盖核心抽样：
  - CFO tail `{probability: 0.20, hz: [-2500, 2500]}`（覆盖 OOD `cfo_strong`）；
  - multipath tail `{probability: 0.15, num_taps: [3, 6], max_delay: 20}`（覆盖 OOD `multipath`）。
- **复合（composite）**：显式复合分支 `{enabled: true, probability: 0.10}`，命中时强制叠加
  cfo ±1800 + phase_noise [0.002,0.008] + iq_imbalance [-1.5,1.5]dB/[-8,8]° + multipath
  [2,5]/delay16（覆盖 OOD `multi_impairment`）。

**约束**：`phase_noise` 与 `iq_imbalance` 的**核心范围不增大**；`clipping` 保持轻概率并
监控 64QAM/4ASK；增强信道仅用于 train split，验证/OOD 仍走冻结 `channel`（`ChannelPipeline`），
类别顺序/head=12/输入 `[N,2,1024]`/归一化位置/ONNX 图/正式门禁全部不变。

---

## 3. 数据与 split 隔离

- train：`datasets/ad_amr_v4_robust_dataset.py::ADAMRV4RobustDataset`，split
  `ad_amr_v1_4_robust_train`，`self.channel = RobustChannelPipeline(robust.train_channel)`。
- val / OOD / fake-int8：仍用 `ADAMRV11Dataset` + 冻结 `config["channel"]`，
  split `ad_amr_v1_1_validation` / `ad_amr_v1_1_data_v3_12class_validation_*`。
- sample_id 隔离沿用 `SeedSequence([seed, split_code, epoch, index])`、
  `sample_id_base = split_code * 1e6`；禁止 token `test/blind` 不变。

---

## 4. 候选 A / B / C（任务书 §六）

| 候选 | CFO tail | multipath tail | composite | 配置 |
|------|----------|----------------|-----------|------|
| A | ✅ 0.20 | ❌ | ❌ | `configs/..._pilot_A.yaml` |
| B | ❌ | ✅ 0.15 | ✅ 0.10 | `configs/..._pilot_B.yaml` |
| C | ✅ 0.20 | ✅ 0.15 | ✅ 0.10 | `configs/..._pilot_C.yaml` |

- 全部从十二类正式 `best.pt` 严格加载（`_init_from_checkpoint`），低 LR `1e-4`（备选
  `2.5e-4`），`pilot.epochs=30`，BF16 AMP + 梯度有限性 + NaN/Inf fail-closed，完整
  optimizer/scheduler/checkpoint/resume，仅用 train split。
- 冻结评估：同一 validation/OOD 记录、同一 `config["channel"]`。

---

## 5. 执行流程（fail closed）

1. **preflight**：`autodl_*/run_preflight.sh` → 全量 `pytest` + `run_..._cuda_preflight.py`
   （真 CUDA + BF16：init→1 epoch→strict resume 1 epoch→验证→ONNX），写
   `ROBUST_PREFLIGHT_DONE.json` 标记（绑定 release_input_hash + class_contract）。
2. **pilot**：`scripts/run_ad_amr_v4_12class_robust_pilot.py`。基线（seed2026 eval-only）
   vs A/B/C；**唯一候选**达标才写 `selected_candidate.json`。硬门禁：
   - 每个 focus OOD 域改善 ≥ `min_improvement`（cfo 0.0446 / multipath 0.0378 / multi 0.0522）；
   - 干净验证 macro-F1/rated-0-20/SNR-0/min-rated-class 回退 ≤ `regression_bounds`；
   - fake-int8 下降 ≤ 0.03；ONNX 白名单不变 + ORT parity。
3. **lock（人工）**：审阅 pilot 结果后 `scripts/lock_robust_formal_config.py`，把唯一候选
   写为 `configs/..._robust_formal.yaml`（`robust.status: APPROVED_FOR_FORMAL` +
   `final_config_approved: true`），写 `FINAL_CONFIG_APPROVED` 标记（config SHA + 锁定后
   release_input_hash）。
4. **formal**：`scripts/run_ad_amr_v4_12class_robust_formal.py`（先校验 FINAL_CONFIG_APPROVED
   标记与 config SHA）。双种子 2026/2027，`epochs=100`、`min_epochs=30`、LR `1e-4`；
   11 项冻结门禁不变 + 附加最小改善门禁；写 `formal/acceptance.json`。
5. **采集**：`scripts/collect_formal_predictions.py`（eval-only）对 8 域
   （validation / fake_int8 / 6 个 OOD）输出逐样本 JSONL + 12×12 confusion.csv +
   per_class_accuracy.json + manifest.json，供「混淆关系」分析；不碰 public test / final blind。

---

## 6. 门禁（不变 11 项 + 最小改善）

| 门禁 | 阈值 |
|------|------|
| mean_full_macro_f1 | 0.72 |
| mean_full_accuracy | 0.72 |
| mean_rated_0_20_accuracy | 0.90 |
| mean_high_10_20_accuracy | 0.95 |
| each_seed_snr_0_accuracy | 0.85 |
| each_seed_min_rated_class_accuracy | 0.75 |
| each_seed_new_ask_rated_accuracy | 0.75 |
| max_ood_macro_f1_drop | 0.08（每种子每域） |
| onnx_max_abs_diff | 0.001 |
| fake_int8_accuracy_drop | 0.03 |
| unexpected_operators | 0 |

附加：focus 域两种子平均改善 ≥ `min_improvement`（cfo 0.0446 / multipath 0.0378 /
multi_impairment 0.0522）。

---

## 7. ONNX 措辞（任务书 §八）

- **允许策略**：`scripts/export_ad_amr_v1_1_onnx.py::ALLOWED_OPS =
  {"Add", "BatchNormalization", "Conv", "Gemm", "ReduceMean", "Relu"}`（**6-op，含 BN**）。
- **实际导出图**：`torch.onnx.export` 把 BatchNormalization **折叠进 Conv**，实测导出图为
  **5-op = {Add, Conv, Gemm, ReduceMean, Relu}**（无独立 BN 节点）。
- **不改网络**：v4 沿用同一 `ADAMRV11Net`，导出/白名单/门禁全部复用；BN 折叠是导出器行为，
  非结构改动。

---

## 8. 交付物与状态

- 新增/修改源文件见 `SHA256SUMS.txt`（`sha256sum -c` 自校验）；AutoDL 源包
  `dist/ad_amr_v1_1_data_v4_12class_robust_autodl.zip` + `.sha256`。
- CPU smoke 已离线通过：init-from-checkpoint → 2 epoch → 验证 → ONNX 5-op 白名单不变 →
  ORT parity OK（`scripts/run_ad_amr_v1_1_data_v4_12class_robust_smoke.py`）。
- **最高状态（AutoDL pilot 前）：`READY-FOR-AUTODL-ROBUST-PILOT`。** 下一步只能先
  `bash autodl_ad_amr_v1_1_data_v4_12class_robust/run_complete.sh`（setup → preflight →
  pilot），审阅 pilot 后再 `run_lock.sh` + `run_formal.sh`。任何 PASS/READY 都要等
  AutoDL 结果回来并核验。
