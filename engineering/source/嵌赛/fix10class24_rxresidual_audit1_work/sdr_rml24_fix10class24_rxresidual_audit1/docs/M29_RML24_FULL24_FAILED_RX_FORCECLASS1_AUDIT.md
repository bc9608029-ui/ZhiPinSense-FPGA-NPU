# M29 RML24 fix10class24-full24-failed-rx-forceclass1 — 全 24 类失败 RX 强制分类审计

状态：**`M29-RML24-FULL24-FAILED-RX-FORCECLASS1-AUDIT-COMPLETE`**（host BF16 完成）

本任务 = 对「24 类双 SDR 测试」中**被生产门禁 `payload_training_residual <= 0.100` 排除的 20 个真实 RX 转储**
（新归档 `rml24_full24_failed_rx_1773374413`）做强制分类：绕过 0.10 门，把恢复出的 provisional payload
送入冻结 BF16 24 类模型前向，回答——**这些失败样本是否仍产出 baseline 一致的 24 类预测？**

**分层声明**：本任务所有分类结论均来自 **host 端冻结 BF16 前向（`icraft-run --backends Host`）**，
结果统一标注 `HOST_BF16_FORCED_CLASSIFICATION`，**不是板端 NPU 实测**。强制分类结果 **不构成 RF PASS**。

---

## 一、输入转储数量 + 身份 SHA（Phase A）

| 项 | 值 |
|---|---|
| 归档 | `rml24_full24_failed_rx_1773374413.tar.gz` |
| 归档 SHA256 | `53b963127b5ae8575d660366ab193f02cf8339e6f6518ef769519fecf808e6ef`（先验校验通过） |
| 样本数 | **20**（平铺布局，无 capture_id 嵌套） |
| source_index | `{0,500,1000,1500,2000,2500,3000,3500,4000,5000,5500,6500,7000,7500,8000,9000,9500,10000,10500,11500}` |
| 覆盖 raw24 类 | **20/24**（缺 32APSK=9 / 16QAM=12 / AM-SSB-WC=17 / GMSK=22） |
| 失败项 | 全 20 样本 `failure=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`（failure_enum=10），`payload_training_corr` 0.986~0.995 |
| 每样本 7 文件 | 全 `7/7`，`raw_rx_sha_ok=1`（SHA256SUMS 一致） |
| 主键 | `source_index`（20 唯一；本归档无 run.log，`nco_offset` 取生产缺省 0.0，evidence=`production_default`） |

产物：`results/full24_failed_rx_forceclass/inventory.tsv`（20 行）。

---

## 二、恢复与分类链（复用 rxresidual-audit1 诊断核心，未改）

本任务**复用** `host_tools/replay_fix10class24_failed_rx_force_classify.{cpp,hpp,sh}`（rxresidual-audit1 交付，
本次**未修改**）：canonical 参考（`iq_fix10_canonical_frame_data.hpp`，`source_arch=aarch64`）恢复 →
`replay24force::apply_provisional`（纯诊断命名空间，`rec.valid=false` 与原始 failure 保留、不伪装）→
provisional payload → `std::lround`+clip+`int16_t` → `chain::PreprocessChain`（`fs_in=2560000`、`nco_offset=0.0`、gain 1.0f）
→ `apply_d2_restore_to_stream` → `load_recovered_tensor` → `select_classification_window` → `[2,1024]` fp32 = 模型输入。

D2 资产（ref/DC/rec_scale/recovered_tensor）从 `clean24_smoke_manifest.tsv`（24 类，27 列）按 source_index 查得，
缺/重复 fail-closed。

---

## 三、生产接线等价性（Phase C，HARD GATE）

PASS fixture 上证明诊断镜像与生产 `iqrfrec::apply` 逐阶段字节一致（self-test，五阶段全 `identical=1`）：

| 阶段 | 一致 | SHA256 |
|---|---|---|
| apply == apply_provisional | ✓ | `799c5972ec7608160eb6c683bd4fc352216bc0cf27fe2fd3a23d17c6e5e48f49` |
| payload_iq | ✓ | `7f0047739f320468a6edc254983dd6c5f441c6023d25e89a165381e6ee0e97f5` |
| recovered_stream | ✓ | `26972a9d7bd22ce8b94b75ade0114708d160ccf73c31810cb3c28af3d78c0c01` |
| classification_window | ✓ | `1f981766179bf394cc7f1ad9b87664789feaccff0beed996aedb49bd7df37b94` |
| model_input | ✓ | `1f981766179bf394cc7f1ad9b87664789feaccff0beed996aedb49bd7df37b94`（== window，同为 [2,1024]） |

结论：`FIX10CLASS24_FORCE_CLASSIFY_SELF_TEST ... result=PASS`。诊断镜像与生产逐阶段字节一致，
provisional 分类链无近似误差，可进入 Phase D。

---

## 四、强制分类结果（Phase D，主判据）

**20 样本：15/20 正确，5/20 误分类**（`baseline_agreement=15/20`、`label_correct=15/20`）。
`finite=20/20`、`repeat_argmax_deterministic=20/20`、`repeat_logits_byte_identical=20/20`（每样本 ≥2 前向）。

### 误分类样本（5）

| source_index | 源类 | 残差 | baseline_pred | raw24_pred | 预测类 |
|---|---|---|---|---|---|
| 3000 | 16PSK (6) | 0.103732 | 6 | 7 | 32PSK |
| 7000 | 64QAM (14) | 0.136089 | 14 | 16 | 256QAM |
| 7500 | 128QAM (15) | 0.170485 | 15 | 16 | 256QAM |
| 9500 | AM-DSB-WC (19) | 0.113413 | 19 | 20 | AM-DSB-SC |
| 11500 | OQPSK (23) | 0.142194 | 23 | 7 | 32PSK |

全部为**易混淆邻类**（高阶 PSK/QAM 相互混淆、AM-DSB WC↔SC）。

### 关键观察：误分类 **不随残差单调**

- 残差 **最低** 的误分类样本 = 16PSK@`0.1037`（略高于 0.10 门，即「刚被拒」的样本）；
- 残差 **更高** 的 256QAM@`0.1504` 与 16APSK@`0.1517` 却 **正确**；
- 即残差高低**不能单独预测**强制分类是否正确，难分类样本在低残差处也可能翻转。

产物：`results/full24_failed_rx_forceclass/{per_sample_results.tsv, raw24_logits.tsv, summary.json}`。

---

## 五、结论（Phase F）

**`EVIDENCE_AGAINST_GATE_RELAXATION`** —— 证据**反对**放宽 0.10 门。

- 在 20 个被 0.10 门拒绝的失败样本上强制分类，**错误率 25%（5/20）**；
- 对照 rxresidual-audit1（30/30 全对）：那 30 个样本**只覆盖 BPSK/4ASK 两类容易类**，
  其「全对」不能外推到全 24 类；本任务补上 20 个不同 raw24 类后，**全谱面证据显示失败样本确有显著误分类**；
- 因此 **0.10 门正在正确拒绝退化样本**（被拒样本中约 1/4 若放行将出错），
  **不支持据此放宽生产门限**。生产门限 `production_gate_modified=0`、`production_threshold=0.1` 保持不变。

---

## 六、选择偏差与限制披露

- 输入 = 生产门禁 0.10 **拒绝后**转储的失败样本集合（`selection_bias=FAILURE_CONDITIONAL_SAMPLE`），**不含 PASS 样本**；
- 20 样本覆盖 20/24 raw24 类，但每类仅 1 样本，**无类内重复**，不能估计类内方差；
- 缺 4 类（32APSK/16QAM/AM-SSB-WC/GMSK）失败样本；
- 结论为 host BF16 层（`HOST_BF16_FORCED_CLASSIFICATION`），**非板端 NPU 实测**；
- 强制分类结果**不用于**：修改生产门限、恢复器、runner、模型、标签、canonical 资产、发射上限；
  不写 `RF_PASS / SMOKE_PASS / NEW_PRODUCTION_THRESHOLD`。

---

## 交付物与验证

| 交付物 | 位置 |
|---|---|
| 审计脚本（extract/inventory/classify） | `scripts/audit_fix10class24_full24_failed_rx_forceclass1.py` |
| 扫描脚本（20 dump 循环） | `host_tools/run_force_classify_full24_sweep.sh` |
| 测试（10 pytest，fail-closed） | `host_tests/test_fix10class24_full24_failed_rx_forceclass1.py` |
| 结果 | `results/full24_failed_rx_forceclass/{inventory,per_sample_results,raw24_logits}.tsv` + `summary.json` |
| 诊断核心（复用未改） | `host_tools/replay_fix10class24_failed_rx_force_classify.{cpp,hpp,sh}` |

**验证（离线，不碰板）**：
1. 归档 SHA `53b963127b…` 先验校验通过；20 样本身份/文件/SHA/JSON 字段/manifest 交叉核对全过（inventory fail-closed）；
2. `replay_fix10class24_failed_rx_force_classify.sh --self-test` → **PASS**（五阶段字节等价）；
3. 10 项 pytest → **10 passed**（归档 SHA 错 / 路径穿越 / 缺文件 / raw SHA 错 / JSON 缺字段 / modulation 错 / 多余目录 各 fail-closed）；
4. Host BF16 每样本 ≥2 前向，24 logits finite、argmax/logits determinism 分开记录。

---

## 停止条件核验

1. ✅ 归档 SHA 及 20 样本身份通过；
2. ✅ PASS fixture 完整路径逐阶段等价（self-test PASS）；
3. ✅ Host BF16 对每个输入输出 24 维有限 logits（20/20 finite）；
4. ✅ 强制分类结果、误分类明细、选择偏差完整披露；
5. ✅ 生产门限、恢复器、runner、模型、标签、canonical 资产全部未改（复用诊断核心未改；红线头由构造保证未动）。

**下一步由用户决策**：是否开放板端数字直注包以取得真实 NPU 判定；或按 `fix10class24-prospective-prep1`
（正 120/负 39 空捕获 + Wilson CI）走正式前瞻门限验证。本任务到此暂停，**不自动进入门限修改或恢复器修改**。
