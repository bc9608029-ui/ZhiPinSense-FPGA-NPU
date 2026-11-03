# OOD 协议审计（V1.1）

本文冻结 12 类 / 24 类**共享 OOD 框架**的定义、口径与隔离边界，回答"哪些样本算 OOD、
阈值在哪锁、谁能在什么时候访问哪份 split"这类最容易出错的问题。目标是把 OOD 评估从
"跑一遍看 AUROC"变成"冻结口径、防泄漏、可复现"。

## 一、两种 OOD 必须区分

| 轴 | 定义 | 判断 |
|---|---|---|
| **Channel OOD**（协变量偏移） | **仍是 24 类**，只是 CFO / SNR / 多径 / IQ 失衡 / 相噪 / 脉冲 / combo 等信道损伤偏移 | 模型应**仍能识别**（closed-set 精度下降但"不拒绝"），不是 UNKNOWN |
| **Semantic OOD**（语义外） | **新的调制族**，不在 24 类内 → UNKNOWN | 模型应**拒绝**（分数越界） |

- Channel OOD：`evaluation/evaluate_rml24.py:evaluate_rml24_channel_ood`，对 `validation`
  的 ID 样本施加冻结信道损伤域，报告各域 closed-set 精度（"ID 协变量偏移仍须识别"轴）。
- Semantic OOD：`evaluation/evaluate_ood.py`，ID 用真实 RadioML test，OOD 用合成新调制族，
  报告 AUROC / AUPR-IN / AUPR-OUT / FPR95 / OSCR + 三工作点。

两者口径不同，**绝不互相替代**；Semantic OOD 的合成信号与真实 ID 存在
"ID 200 kHz vs 合成 128 kHz" 的域差（`evaluate_ood.py:201-205` 显式报告，不并入主指标）。

## 二、Semantic OOD 族（`datasets/ood_dataset.py:31-36`）

- **near_12**（仅 24 类模型有）：24 类里多出来的 13 个调制 → 对 12 类模型是近 OOD。
- **near_24**：`2FSK, GFSK, OFDM`（12 类专属）→ 对 24 类模型是近 OOD。
- **far**：`LFM, CW, MULTITONE, PULSE, FHOP`（两模型共享）→ 主指标用。
- **ambiguous**：`AM-DSB, WBFM, FM, GMSK`（近似等价类）→ **不进主指标**，仅旁报。

24 类模型主评估用 `families=["near_24", "far"]`、`threshold_family="far"`
（`evaluate_ood.py:194`）。

## 三、三套 OOD split 强隔离（防泄漏的根）

`datasets/ood_dataset.py:9-13` 定义，`SPLIT_CODES`（`:39-43`）给每套独立整数码，生成 rng 用
`SeedSequence([seed, SPLIT_CODES[split], _FAMILY_CODES[family]])`（`:103`）——同一 (seed,
split, family) 三元组可字节级复现，且不同 split **永不共享样本**。

| split | 唯一用途 |
|---|---|
| `oe_aux_train` | 仅供 OE+Energy 训练的辅助离群样本 |
| `ood_validation` | **仅供锁定阈值 / 校准温度** |
| `ood_final_test` | **仅供最终评分，绝不用于阈值或训练** |

## 四、五条分离原则（冻结）

1. **OOD calibration ≠ OOD test**：阈值/温度只在 `ood_validation` 锁，`ood_final_test` 只评一次
   （`evaluate_ood.py:84-99` 明确 `threshold_lock_split="ood_validation"`，族评分用
   `ood_final_test`，`:113-116`）。
2. **OE train ≠ OOD test**：OE 只用 `oe_aux_train` 离群样本；`ood_final_test` 永不进入 OE 训练。
3. **ID val 选模型**：模型/checkpoint 选择只用 `rated_0_20_accuracy`（validation），与 OOD 无关。
4. **OOD calib 仅锁 temp/阈值**：温度校准只对 Energy 且只在 ID logits 上做
   （`calibrate_temperature`，`evaluate_ood.py:91-93`），不碰 ID test / OOD test 的标签。
5. **ID test + OOD test 仅冻结后评一次**：`evaluate_rml24(split="test")` 记
   `final_blind_test_accessed=True`；OOD 用 `ood_final_test`，两者都在冻结阈值/温度后各评一次。

## 五、12 / 24 共享框架，但**分存、不共享阈值**

两模型复用同一 `semantic_ood_report` / 分数 / 阈值逻辑，但下列项**各自独立**，不得串用：

- temperature（各自 ID logits 校准）
- score normalization / 阈值三工作点（各自 `ood_validation` 锁）
- label contract（`LABEL_ORDER_24` vs 12 类冻结序）
- checkpoint SHA / model name（各自 manifest）
- calibration split（都是 `ood_validation`，但 ID 分布不同 → 阈值数值不同）

阈值落盘于 `ood_threshold_manifest.py`（Task I），字段含 `model_sha256 / checkpoint_sha256 /
score_method / direction / temperature / thresholds(三工作点) / calibration_dataset_sha256 /
calibration_split_sha256 / target_operating_point / calibration_samples / creation_seed`；
**写一次即只读**，final eval 只读不重算。

## 六、分数与方向（统一口径）

`ood/scores.py`：MSP（`1 - max softmax`）/ Entropy / MaxLogit（`-max logit`）/ Energy
（`-T·logsumexp(logits/T)`）四种分数**统一"越大越 OOD"**。Energy 的"越大越 OOD"方向仅在
`T=1` 成立（`T>1` 方向可能翻转），故冻结 `temperature=1.0` 起步、仅用 ID logits 校准。

## 七、fail-closed 保障

- `select_thresholds` / `fpr95` / `oscr` / `ranking_metrics` 对 NaN/Inf **fail-closed**
  （检测即 raise，不静默传播）——Task H。
- `ood/metrics.py` 增 `ood_detection_accuracy(id_scores, ood_scores, threshold)`：冻结阈值下的
  `(ID 正确接受 + OOD 正确拒绝) / (n_id + n_ood)` 单一指标。
- `ood/threshold_manifest.py`：`_require_sha`（64-hex）、write-once、读失败即 fail-closed。

## 八、OE + Energy 可区分性（Task J）

`training/oe_decision.py` 把 OE 做成"1+2 种子提升门"，**绝不掩盖 ID 退化**：

- seed 2026 先跑（verify），与冻结 baseline 比 ID 退化与 Energy OOD 增益
  （`id_degradation` / `ood_gain` 分报）；
- 仅当 ID 退化 ≤ 容差（macro_f1/rated 各 0.01）**且**至少一项 OOD 增益达标
  （AUROC +0.02 / FPR95 +0.05 / OSCR +0.02）才 `OE_DECISION result=PROMOTE` 跑 2027/2028；
  否则 `REJECT`，保留 Energy baseline。详见 `docs/OE_PROMOTION_CONTRACT.md`。

## 九、状态红线

- 最终评估最高 `READY-FOR-12-VS-24-MODEL-SELECTION`；实板/NPU 验证前**绝不写**
  `OOD_PASS / FINAL_MODEL_PASS / FINAL_24CLASS_PASS / HARDWARE_PASS / FULL_CHAIN_PASS`。
- 若 OOD 只在 OE 见过的未知族有效 → 标 `OOD_SEEN-OUTLIER_ONLY`。
