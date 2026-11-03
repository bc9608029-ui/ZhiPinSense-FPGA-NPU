# RML24 Pilot 指标口径审计（只读审计 + 修复）

任务：立即只读审计 24 类 pilot 指标口径，暂缓正式候选冻结。本报告逐项回答 8 个调查点，
给出根因与修复，并在末尾输出冻结门禁 `RML24_PILOT_METRIC_AUDIT result=PASS`。

> 状态：**根因已确认 = 指标实现错误（前缀截断导致单类子集）**，已修复评估代码。离线环境
> 未执行正式 GPU 训练，`runs/` 下无任何已保存 pilot checkpoint，故「用已保存 best checkpoint
> 重新评估 + 重建 pilot summary/ranking」这一步**不适用**（无 checkpoint 可重评估）；修复对
> 下一次 pilot 运行起效。

---

## 0. 结论速览

| 调查点 | 结论 |
|---|---|
| 1. epoch「rated」vs trial「rated_0_20」由谁计算 | 都最终调用同一 `_summary`/`slice_accuracy`，但**喂入的数据集不同** |
| 2. 两者 manifest/split/样本数/SNR 范围 | epoch = 全验证集(~511k)；trial(修复前) = 验证集**前 16384** = OOK 单类 |
| 3. 是否只 validation、绝不碰 test | **是**（两处都 `split="validation"`，pilot 全链无 test 访问） |
| 4. 是否评估同一 best checkpoint | **是**（都读 `checkpoints/best.pt`） |
| 5. 训练/验证泄漏 | **无**（前缀偏差是「口径/代表性」缺陷，非泄漏；切分零交集已审计） |
| 6. 为何 epoch ~0.80–0.85 而 trial ~1.0 | **指标实现错误**：trial 只评 OOK 单类（前缀截断） |
| 7. 是否只按 rated 选，忽略 macro_f1/snr0/min_class | **是**（V1.1 冻结单指标设计；默认单候选晋升纯 `rated_0_20_accuracy`） |
| 8. t003/t006 是否有效配置重复 | 无落盘结果（离线未训）；机制上按**全量 canonical signature** 去重，正确 |

---

## 1. Q1/Q2 — 两条「rated_0_20」的计算路径

### 1.1 epoch 日志里的「rated」（训练循环内的每轮验证）

- 计算函数：`V2Trainer._run_epoch` → `_summary(...)`（`v2/trainer.py:187`，`_summary` 定义在
  `training/ad_amr_v1_1_trainer.py:22`）。
- `rated_0_20_accuracy = slice_accuracy(lambda snr: 0.0 <= snr <= 20.0)`（`ad_amr_v1_1_trainer.py:39`）。
- 数据：`val_loader = build_rml24_loader(cfg, "validation", ...)`（`training/rml24_run.py:58`），
  由 `RadioML2018Dataset(split="validation")` 构建，**无 `max_per_stratum`/`allowed_snrs` 限制**，
  即**全量验证集**：24 类 × 26 SNR × 819 ≈ 511,056 样本；SNR −20…+30，`rated_0_20` 取 0…20 共 11 档。

### 1.2 trial 结束的「rated_0_20」（pilot 排名/选候选真正用的指标）

- 选择指标读取：`v2/results.py:25-28` `selection_score(result)` = `result["baseline"]["metrics"]["rated_0_20_accuracy"]`。
- `baseline` 由 `training/rml24_run.py:82` `evaluate_rml24(cfg, best_path, split="validation", samples=eval_samples)` 产出；
  `evaluate_rml24`（`evaluation/evaluate_rml24.py:97`）同样调用 `_summary(...)`（`:120`）。
- 数据（修复前）：`_build_eval_dataset` 用 `Subset(dataset, list(range(limit)))`，`limit = min(16384, len)`。
  `eval_samples` 的 pilot 默认 = **16384**（`training/rml24_pilot.py` 旧默认），formal 走
  `samples=None → config["evaluation"]["samples"]=262144` 的同款前缀。

### 1.3 前缀为何是「OOK 单类」

切分索引按 `(label, snr)` **排序**拼接（`scripts/audit_radioml2018.py:125`
`for (label, snr), pieces in sorted(grouped.items())`），每 (类,SNR) 层贡献 `int(4096×0.2)=819` 个验证样本。
因此验证集前 16384 个样本 ≈ 20 个层 = **仅 class 0（OOK）的 SNR −20…+18**。

→ trial「rated_0_20」实际 = **OOK 单类、SNR 0…18 的准确率**（≈1.0 的平凡高分），
  而 epoch「rated」= **全 24 类、SNR 0…20 的准确率**（≈0.80–0.85）。二者同名不同口径。

---

## 2. Q3/Q4/Q5 — 隔离与 checkpoint 一致性

- **只 validation、不碰 test**：`run_rml24_trial` 硬编码 `split="validation"`（`rml24_run.py:82`）；
  `evaluate_rml24` 写 `final_blind_test_accessed: split == "test"`（`evaluate_rml24.py:128`），pilot 中恒为 False。
  test 仅由冻结后的 `run_final_evaluation.py:59` 访问一次。**无 test 访问。**
- **同一 best checkpoint**：trial 评的是 `paths["checkpoints"]/best.pt`（`rml24_run.py:65,82`），
  即 `V2Trainer.fit` 按「全量验证集 rated_0_20」选出的最优轮保存点。**同一 checkpoint。**
- **无泄漏**：子集只取 `split="validation"` 索引；切分零交集在 `audit_radioml2018.py:146-149` 强制校验。
  前缀偏差是**代表性/口径**缺陷（少覆盖类别），不是 train→val 泄漏。

---

## 3. Q6 — 根因

**指标实现错误（口径 bug），非字段命名问题。** 具体三处同根因：

1. `evaluation/evaluate_rml24.py::_build_eval_dataset`（旧）用 `Subset(dataset, range(limit))` 前缀截断；
2. `training/rml24_pilot.py` 默认 `eval_samples=16384`；
3. `configs/rml24_base.yaml` `evaluation.samples=262144` 作为 `samples=None` 的回退，仍是前缀（262144 ≈ 前 12 类，仍缺 12 类）。

因为索引是 label-major，前缀 = 越靠前的类别越多，直至单类。trial 排名因此被「OOK 单类高分」污染，
整个 pilot 排序在修复前是**无效/误导**的。

---

## 4. Q7 — 选择是否只看 rated

**是。** `selection_score` 只取 `rated_0_20_accuracy`（`v2/results.py:25-28`）；`rank` 按它排序、
`prune` 按它剔除（`v2/results.py:52-82`）。`rml24_select._second_candidate_qualifies`
（`rml24_select.py:94-101`）仅在 `--allow-second-candidate` 下为**第二候选**引入
`worst_class_recall`/`low_snr_accuracy`/`min_qam_recall`；默认单候选晋升纯 `rated_0_20_accuracy`。
`macro_f1`/`snr_0`/`min_class` 全程只报告、不参与主排名。这符合 V1.1 冻结单指标设计，但意味着
**修复前的 broken rated 完全主导了排名**。

---

## 5. Q8 — t003/t006 配置重复

- 离线未执行训练，`runs/` 下无任何 `result.json`，故 t003/t006 为**假设问法**，无实值可查。
- 去重机制正确：`rml24_select._dedupe`（`rml24_select.py:69-91`）按
  `canonical_candidate_signature`（`v2/candidate_signature.py:135`）分组，该签名哈希
  **全量训练面**（loss/focal_gamma/label_smoothing/optimizer/lr/wd/scheduler/…）。两 trial 仅当
  **有效超参全同**才是重复，且会被正确折叠。
- 注意（效率而非正确性）：静态轴 `adamw_lr/adamw_wd` 对 sgd 也采样、`sgd_lr/sgd_wd` 对 adamw 也采样
  （`rml24_pilot.py:71-79`），只解码相关轴；仅「未使用轴」不同的两 trial 会解码为同一有效配置 →
  被去重折叠，但会浪费一点 pilot 预算。trial 名 `t{index}_loss{loss}_opt{optimizer}` 是**有损**的
  （只含 loss+optimizer），但不影响去重正确性（去重用全量签名，非名字）。

---

## 6. 修复（指标实现错误 → 修复评估代码）

### 6.1 `evaluation/evaluate_rml24.py`

- 新增纯函数 `_stratified_indices(labels, snrs, limit, seed)`：按 (class, SNR) 层**比例分配预算 +
  固定种子逐层洗牌**，返回代表性子集（保类/SNR 分布、确定性、无重复）。
- `_build_eval_dataset`：`samples=None` → **全量冻结验证集**（与 epoch 口径一致）；
  有界预算 → 分层子集（不再是前缀）。

### 6.2 `training/rml24_pilot.py`

- `eval_samples` 默认 `16384` → `None`（`--eval-samples` 默认 `None`），使 pilot 基线评估走
  **全量验证集**，与 epoch 日志口径完全一致；用户仍可显式给有界预算（分层，非前缀）。

### 6.3 回归测试 `tests/test_rml24_eval_caliber.py`

5 断言：记录旧前缀=OOK 单类；分层子集覆盖全 24 类/26 SNR；0–20dB 切片仍跨全类；确定性；`limit≥n` 返回全集。

---

## 7. 复评/重建说明（不适用）

条件动作②要求「在冻结 validation 切分用已保存 pilot best checkpoint 重新评估 + 重建
pilot summary/ranking」。因 **离线未执行训练，`runs/` 无任何 checkpoint**，该步骤**无对象可执行**；
修复对下一次 pilot 起效，届时 `rated_0_20_accuracy` 即为正确口径。

---

## 8. 验证结果

- `python -m pytest tests/ -q`：**203 passed, 4 skipped**（4 = 本地缺 optuna `importorskip`）。
- `python -m compileall` 改动三文件：**OK**。

---

## 9. 已有 checkpoint 统一重评工具（reassess）

修复生效对「下一次 pilot」起效；若 AutoDL 上**已存在**一批按旧口径评出的 pilot
`best.pt`，本工程新增 `scripts/reassess_existing_rml24_pilots.sh`（后端
`scripts/reassess_rml24_pilots.py`）在**不重训、不改 checkpoint** 的前提下统一重评：

```bash
scripts/reassess_existing_rml24_pilots.sh --pilot-root runs/rml24_base/pilot
# 可选：--eval-samples N（有界预算 → 统一分层子集）、--index-seed S、--output-dir D
```

该工具的硬保证：

- **只 validation、绝不碰 test**：只构造 `RadioML2018Dataset(split="validation")`，
  `final_blind_test_accessed` 恒为 `False`。
- **所有 trial 用同一份样本索引**：索引集只算一次（`samples=None` → 全量冻结验证集；
  有界预算 → `_stratified_indices` + 固定种子 `20261003`），每个 checkpoint 都在该同一子集上打分。
- **只读元数据、不读旧 rated**：仅读 `result.json` 的 `trial/seed/v2/training/model_name`，
  从不读 `baseline/history/best_selection_score`。
- **重算五指标**：`accuracy` / `macro_f1` / `rated_0_20_accuracy` / `snr_0_accuracy` /
  `min_per_class_accuracy`（`_summary` 现算，非旧值）。
- **输出覆盖**：样本数、24 类覆盖数、26 SNR 覆盖数（类/SNR 不全 → FAIL）。
- **重建 ranking + formal candidate plan**：按 canonical signature 去重后重排，产出
  `reassessed_pilot_ranking.json` / `reassessed_formal_candidate_plan.json` /
  `reassessed_pilot_ranking.csv`，formal plan 可直接交给 `run_rml24_formal --candidates`。

**最终排序规则（明确，非单一饱和值）**：降序字典序键
`(round(rated_0_20_accuracy / 1e-4), min_per_class_accuracy, snr_0_accuracy, macro_f1, accuracy)`
——主指标 `rated_0_20_accuracy` 量化到 `1e-4`，近并列（饱和）时落到
`min_per_class_accuracy` / `snr_0_accuracy` / `macro_f1` 决胜。四个指标全部同时报告，
不只用 `rated_0_20`。

## 10. 冻结门禁

```
RML24_PILOT_METRIC_AUDIT result=PASS
```

重评运行时门禁（AutoDL 对已有 pilot 重评时，由脚本后端唯一输出）：

```
RML24_PILOT_REASSESS result=PASS|FAIL
```
