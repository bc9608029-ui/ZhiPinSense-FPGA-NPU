# M20 OOD-U 协议（`docs/M20_OOD_U_PROTOCOL.md`）

任务 M20 §三–§八交付物。本文冻结「语义 OOD-U / UNKNOWN 拒识」的**问题定义、
未知信号集合、数据隔离、生成器捷径防御、评分方法与阈值冻结**全链路口径，
是阈值 manifest 与最终盲测的权威依据。所有常量均以 `ood_u/contract.py` 为单一
真相源，并与 `cpp/ood_u_contract.hpp` 逐字节镜像。

> 上游前提见 `docs/M20_MODEL_OUTPUT_AUDIT.md`：当前 NPU 输出 12 维 **raw fp32
> logits（无 Softmax）**，故本节五种评分全部可用，无需从概率伪造/反推 Energy。

---

## 三、OOD-U 定义（语义 OOD / UNKNOWN）

**OOD-U 是语义级拒识，不是信道级拒识。** 已知类（ID）与未知类（OOD）的区分
只由「调制方式是否属于当前 12 类」决定，与 SNR / CFO / 多径 / IQ 失衡 / 相噪 /
削波等**信道损伤无关**。

| 概念 | 定义 |
|---|---|
| **ID（已知）** | `LABEL_ORDER_12` 的 12 类调制（OOK, 4ASK, AM-DSB, WBFM, 2FSK, GFSK, BPSK, QPSK, 8PSK, 16QAM, 64QAM, OFDM） |
| **OOD（未知）** | 语义上**不属于**这 12 类的调制信号（见 §四集合） |
| **OOD-U / UNKNOWN** | 拒识决策标签 `UNKNOWN`（`contract.UNKNOWN`），必须与 `NO_SIGNAL`（无输入）和 `ERROR`（非有限 logits）严格区分 |
| **OOD-R（反例，非语义 OOD）** | 12 类信号在**低 SNR / CFO / 多径 / IQ 失衡 / 相噪 / 削波 / 多损伤 / 强邻近干扰**下的样本——仍属已知类，**不得**判 UNKNOWN（§九保护测试） |

**判定链（CPU 侧，`cpp/ood_u_detector.cpp:103-132`）：**

```
IQ 输入 → 当前 12 类 NPU 模型 → 12 维 raw logits
  → OOD-U 评分 score（见 §七）
  → score > threshold   ? 输出 UNKNOWN
    : 输出 argmax 的已知类（原 12 类标签）
```

- **拒识是严格不等式**：`score > threshold` 判 UNKNOWN；`score == threshold`
  判已知（接受）。该边界语义由 `tests/test_m20_scores.py::test_threshold_boundary_semantics`
  锁定，C++ 侧 `classify_or_reject` 完全一致。
- **默认关闭 = 与原 12 类 argmax 链逐字节一致**：当阈值恒不触发（例如取
  `+1e30`，而 `logit_margin` 分数 ≤ 0）时，CPU 模块输出必须与原 argmax 链
  逐字节一致（同标签、同类别下标），见 `tests/test_m20_board_boundary.py:91`。
  这是板端集成的安全边界：拒识模块是**纯增量**，不改 NPU / 不改数据链 / 不
  改原 12 类分类结果。

**三条语义红线（不可把以下当作语义 OOD）：**

1. 低 SNR 的 12 类信号；
2. CFO / 多径 / IQ 失衡 / 相噪 / 削波后的 12 类信号；
3. 强邻近干扰下的 12 类信号。

以上均落入 `ood_u/protection.py` 的 OOD-R 保护，由 §九（`test_m20_protection.py`）
强制「不得通过大量拒识低 SNR 已知类来虚假提高 OOD 指标」。

---

## 四、未知信号集合（OOD 族）

三个 OOD 族定义在 `datasets/ood_generator.py:23-35` 与 `datasets/ood_dataset.py:31-36`，
M20 只使用 `near_12 / far / ambiguous`（`near_24` 是 24 类模型的近邻族，**本任务
不使用**）。

| 族 | 成员 | 语义 | 用途 |
|---|---|---|---|
| **near_12** | `8ASK, 16PSK, 32PSK, 16APSK, 32APSK, 64APSK, 128APSK, 32QAM, 128QAM, 256QAM, OQPSK, AM-SSB-WC, AM-SSB-SC`（13 种） | 24 类调制里**不属于当前 12 类**的调制（与已知类同属通信信号，最难区分） | 主 OOD 评分族（阈值锁族之一） |
| **far** | `LFM, CW, MULTITONE, PULSE, FHOP`（5 种） | 非通信/雷达类波形（线性调频、连续波、多音、脉冲、跳频），远语义 | 主 OOD 评分族 + 阈值锁族 |
| **ambiguous** | `AM-DSB, WBFM, FM, GMSK`（4 种） | 与已知类的近等价/含混波形 | **侧报**，不计入主指标与方法选择（`benchmark.py` 的 `ambiguous_side_report`） |

- 所有 OOD 波形由 `generate_ood_iq` 用**与 ID 相同的**信号配置（采样率 128 kHz、
  符号率 16 kHz、8 样点/符号、滚降 0.35、幅度 1.0、1024 点）合成，再经**同一
  AWGN 级**；每一族/每一调制都用 `SeedSequence` 确定性生成（§五）。
- `AM-DSB` / `WBFM` 同时出现在 ID 与 `ambiguous` 族中，这是**故意**的——它们是
  已知类与含混近等价的交集样本，仅作侧报，绝不进入主 OOD 指标，也不会造成
  ID/OOD 样本字节重叠（二者分属不同 split/族，由 `assert_no_overlap` 以样本
  SHA 校验零交集）。

---

## 五、数据隔离（三套 split + 零交集）

**三套 split 由 `split_code` 烘焙进每个 `SeedSequence`，互相零交集**（`ood_u/data.py`）：

| split | code | 用途 |
|---|---|---|
| `oe_aux_train` | 1 | 仅 OE+Energy 训练可见的辅助离群点（本任务离线不跑 OE 训练，仍生成并隔离） |
| `ood_validation` | 2 | **只**用于选方法、扫温度、锁阈值（§八） |
| `ood_final_test` | 3 | **只**用于最终盲测一次（§十），永不用来锁阈值/训练 |

**生成确定性（`ood_u/data.py:123-146` / `:171-193`）**：每个样本的 RNG 由
`SeedSequence([seed, split_code, family_code, mod_index, snr_index, i])` 派生，
`seed = contract.OOD_SEED = 12600`（与模型自身训练种子无关的独立命名空间）。
`BENCHMARK_SNR_VALUES = (0, 10, 20)`（低 SNR 已知类 `-20..-10 dB` 属于 OOD-R，
由保护测试覆盖，**永不进入 OOD 阈值校准域**）。

**fail-closed 隔离保证：**

- `split_sha(records)` 对每个 split 的**排序样本 SHA-256** 计算确定性散列
  （`ood_u/data.py:87-90`），校准 manifest 记录 calibration dataset/split SHA
  （`scripts/m20_threshold_calibration.py:37-42`）。
- `assert_no_overlap(*records)` 断言**任何样本字节不得出现在两个 split/族**
  （`ood_u/data.py:93-103`），`m20_data_audit.py:57` 聚合 ID + 全部 OOD 族强制校验。
- `assert_shared_domain(*records)` 断言 ID 与 OOD 共享同一信号域配置
  （`ood_u/shortcut.py:81-90`），防生成器捷径（§六）。
- 盲测单次访问由 `ood_u/manifest.py::FinalTestGuard` 落盘审计标志强制：manifest
  未冻结前访问失败、重复访问失败（`ood_u/blind_test.py:62-67`）。

---

## 六、防止生成器捷径

**核心原则**：ID 与 OOD 必须由**同一生成器 + 同一 AWGN 级**在同一信号域产出，
否则模型可能靠功率/带宽/采样率/文件格式等廉价特征区分二者，而非靠语义。

`ood_u/shortcut.py` 提供两道 fail-closed 防线：

1. **共享域断言** `assert_shared_domain`：所有记录集的 `signal_config`（采样率/
   符号率/样点长度/幅度/频偏/相偏/脉冲成形）必须完全一致（`json.dumps(sort_keys)`
   逐项比对），不一致即 raise。
2. **模型无关廉价特征捷径审计** `audit_shortcut`：提取 4 个无需模型即可算的标量
   特征——`rms_power`（平均功率）、`papr`（峰均比）、`bandwidth_frac`（占用带宽
   占比）、`spectral_centroid`（谱质心）——逐一计算 ID vs OOD 的 AUROC；任一特征
   `|AUROC - 0.5| ≥ 0.40`（即 AUROC ≥ 0.90 或 ≤ 0.10）即判 `generator_shortcut`
   **并 fail-closed 中止**（`ood_u/shortcut.py:20` / `:66-78`；`m20_data_audit.py:74-79`）。

`m20_data_audit.py` 在 `ood_validation` 上对 ID vs（near_12 + far）跑该审计并落盘
`feature_auroc`，任一捷径即 `M20_RESULT result=FAIL`。

---

## 七、评分方法（五种，越大越 OOD）

五种评分统一「**分数越高 = 越可能是 OOD**」（`DIRECTION = "higher_is_ood"`），
全部在 raw logits 上计算（无 Softmax 依赖，故 `logit_margin` 对大公共偏移鲁棒，
`max_logit`/`energy` 同样可用）。Python 实现 `ood/scores.py`，C++ 镜像
`cpp/ood_u_detector.cpp:25-74`，两处逐项一致（由 `m20_board_replay.py` 在 1e-6
容差内比对）。

| 方法 | 定义（raw logits `z`，`p = softmax(z)`） |
|---|---|
| **msp** | `1 - max(p)` |
| **entropy** | `-Σ p·log p` |
| **max_logit** | `-max(z)` |
| **logit_margin** | `-(top1(z) - top2(z))`（用 partial sort 取前两大 logit，公共偏移不变） |
| **energy** | `-T·logΣexp(z/T)`（`T` 为温度，仅在 Energy 胜出时扫描） |

- **维度守卫** `contract.assert_logits_12`：任何入口评分前强制校验 `[N, 12]` 且
  有限（NaN/Inf → raise，绝不静默评分）。`compute_scores` 本身是共享泛型原语
  （24 类管线也复用），故 12 维守卫放在 `assert_logits_12`（`tests/test_m20_scores.py::test_score_input_dim_fail_closed`）。
- **方向**：高置信已知类必须严格低于均匀（弥散）logit 的分数（`test_score_direction_higher_is_ood`）；
  非有限 logits fail-closed（`test_score_nan_inf_fail_closed`）。

---

## 八、分数选择与阈值冻结

**全部在 `ood_validation` 上完成，`ood_final_test` 永不被触碰**（`ood_u/calibrate.py`）。

**① 方法选择 = 六准则排名聚合，非单一 AUROC**（`ood_u/calibrate.py:29-60`）：

- 准则：`auroc_near / auroc_far / auroc_overall`、`fpr95_overall`、
  `oscr_overall`、`impaired_id_accept_at_99pct`（99% 接受点处的受损已知类接受率）。
- 每准则按序赋排名，汇总最低者胜出；同分用 `overall_auroc` 破平。
- **OOD-R 门槛** `IMPAIRED_ACCEPT_FLOOR = 0.90`：某方法在 99% 接受点对受损已知
  类的接受率低于 0.90 即被淘汰（防止靠拒识已知类伪提 OOD）。该门槛写进方法选择
  的 `impaired_id_accept` 准则（`calibrate.py:23-26` / `:42`）。

**② 温度**：仅当胜出方法为 `energy` 时，在 `TEMPERATURE_SCAN = (0.5, 1.0, 2.0, 5.0)`
  上按 overall AUROC 扫描；其余方法固定 `temperature = 1.0`（`calibrate.py:63-74` / `:128`）。

**③ 三工作点**（`calibrate.py:77-109`）：

| 工作点 | 阈值定义 |
|---|---|
| `id_accept_95` | ID 分数的 0.95 分位（`quantile(id, 0.95)`） |
| `id_accept_99`（默认） | ID 分数的 0.99 分位（`quantile(id, 0.99)`） |
| `far_ood_target` | far 分数的 0.05 分位（`quantile(far, 0.05)`，目标 95% far 拒识） |

默认工作点 `DEFAULT_WORKING_POINT = id_accept_99`（`contract.py:49`），其阈值即
manifest 的 `threshold`。

**④ 写一次冻结**（`scripts/m20_threshold_calibration.py` → `ood_u/manifest.py`）：

- `build_ood_u_manifest` 把 `score_method / temperature / threshold / 三工作点 /
  model·checkpoint·NPU SHA / label_order / 输入输出契约 / calibration dataset·split
  SHA / sample_count / creation_seed / creation_time / final_test_accessed=false`
  全部固化。
- `write_ood_u_manifest(overwrite=False)` **写一次**：已存在即 `FileExistsError`，
  拒绝覆盖。读取端 `read_ood_u_manifest` 对缺失/畸形/非有限/违反契约字段
  fail-closed（`manifest.py:45-122`）；C++ 侧 `load_ood_u_manifest` 同语义
  （`cpp/ood_threshold_manifest.cpp:53-89`）。
- 最终盲测**只读**该 manifest，且 `FinalTestGuard` 强制单次访问（§五/§十）。

**⑤ 本轮实测（count=20 确定性校准，`logit_margin` 胜出）**：六准则聚合选出
`logit_margin`，`id_accept_99` 阈值 **≈ -0.153**（logit_margin 分数 ≤ 0，故阈值为
负；`score > -0.153` 判 UNKNOWN）。该值由 `run_m20_threshold_calibration.sh` 在
`count-per-class=20 / count-per-modulation=20` 下**确定性复现**，最终以
`runs/m20_threshold_calibration/ood_u_threshold_manifest.json` 落盘的值为准
（此处 -0.153 为校准结果摘要，不是硬编码常量）。

---

## 红线

- 阈值只在 `ood_validation` 锁；`ood_final_test` 仅盲测一次；**不得调低门限后重读
  盲测集**、不得为过测降低断言或阈值、不得把 64QAM 已知模型问题通过降门限伪修复。
- 不得把低 SNR / CFO / 多径 / IQ 失衡 / 相噪 / 削波后的 12 类信号当语义 OOD。
- 状态红线（`contract.FORBIDDEN_STATUS_MARKERS`）：实机 NPU + 真射频验证前，绝不写
  `OOD_PASS / HARDWARE_PASS / OOD_U_PASS / FINAL_MODEL_PASS / DEPLOYMENT_PASS /
  PROJECT_COMPLETE`。
