# M29 RML24 fix10class24-rxresidual-audit1 — 失败 RX 强制分类与残差归因审计

状态：**`M29-RML24-FIX10CLASS24-RXRESIDUAL-FORCED-CLASSIFICATION-AUDIT-COMPLETE`**（host BF16 完成）

本任务 = **诊断专用离线管道**，回答两个问题：
1. 残差 0.11~0.15 的失败样本（被生产门禁 `payload_training_residual <= 0.100` 拒绝）是否仍产出 baseline 一致的 24 类预测？
2. 哪种未补偿误差主导残差？

**分层声明**：本任务所有分类结论均来自 **host 端冻结 BF16 前向（`icraft-run --backends Host`）**，
结果统一标注 `HOST_BF16_FORCED_CLASSIFICATION`，**不是板端 NPU 实测**。强制分类正确 **不构成 RF PASS**。

---

## 一、输入转储数量 + 身份 SHA（Phase A）

| 项 | 值 |
|---|---|
| 归档 | `rml24_rx_diagnostics_full_1773379631.tar.gz` |
| 归档 SHA256 | `08ef944e099270f5c166415df17eabed5c3324ff03a2940182318d4abef76922`（先验校验通过） |
| 样本数 | **30**（15 capture_id × source_index ∈ {500, 1500}） |
| 布局 | 带宽 18/10/5/3 MHz 各 3 轮 + 增益 40/45/50 dB 各 1 轮 |
| source_index | 500 = 4ASK（raw24_class=1）、1500 = BPSK（raw24_class=3） |
| 每 capture_id | 恰好含 source_index 500 与 1500 **各一次**（无多余/缺失，fail-closed 校验） |
| 前端参数 | 从每轮 `run.log` 读回：`rx_bw_ok=1`、`rx_gain_ok=1`；`nco_offset=0.0`（evidence=`production_default_and_board_command_omission`） |
| 失败项 | 全 30 样本 `failure=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`（failure_enum=10），`payload_training_corr` 0.988~0.994 |

产物：`results/rxresidual_audit/capture_inventory.tsv`（30 行）。

---

## 二、canonical 逐字段复现（Phase B 底座）

生产恢复路径在 host 端经 canonical 参考（内嵌 `iq_fix10_canonical_frame_data.hpp`，`source_arch=aarch64`，
payload-training SHA `f06e9b3d…`）逐字段复现板端，tolerance 内 **27/0**（前序 dualsdr2 已证）：

| 字段 | 板端 | host canonical | tolerance |
|---|---|---|---|
| timing_offset | 36074 | 精确 | 精确 |
| coarse_cfo_hz | -118.325 | 复现 | 2e-2 Hz |
| fine_cfo_hz | -6.265 | 复现 | 2e-2 Hz |
| payload_training_corr | 0.9933165 | 复现 | 1e-5 |
| payload_training_residual | 0.1161988 | 复现 | 1e-5（> 0.10） |

provisional payload 只重算 payload 域字段（`payload_phase_deg=arg(canonical_a_pay)`、`payload_gain_mag=|canonical_a_pay|`），
其余（timing/cfo/sro/`payload_rms_gain_mag`/tx_scale）复用 `estimate(aligned)` 的 preamble/能量派生值；
作用于 **`aligned`**（已 coarse 去旋 + 分数定时校正），非 raw rx。`rec.valid=false` 与原始 failure **保留、不伪装**。

---

## 三、生产接线等价性（Phase C，HARD GATE）

PASS fixture（`rec.valid=true`、residual<1e-3）上证明诊断镜像与生产 `iqrfrec::apply` **逐阶段字节一致**：

| 阶段 | 一致 | SHA256 |
|---|---|---|
| apply == apply_provisional | ✓ | `799c5972ec7608160eb6c683bd4fc352216bc0cf27fe2fd3a23d17c6e5e48f49` |
| payload_iq | ✓ | `7f0047739f320468a6edc254983dd6c5f441c6023d25e89a165381e6ee0e97f5` |
| recovered_stream | ✓ | `26972a9d7bd22ce8b94b75ade0114708d160ccf73c31810cb3c28af3d78c0c01` |
| classification_window | ✓ | `1f981766179bf394cc7f1ad9b87664789feaccff0beed996aedb49bd7df37b94` |
| model_input | ✓ | `1f981766179bf394cc7f1ad9b87664789feaccff0beed996aedb49bd7df37b94`（== window，同为 [2,1024]） |

`apply_provisional` 为纯诊断命名空间 `replay24force`，本身不检查 `valid`，仅保留 unsafe-gain/tx-scale fail-closed；
**不放进 `iqrfrec`，不改红线 `apply`**，生产 runner 无法误用。

---

## 四、各残差带预测一致率（Phase D）

30 样本按 `payload_training_residual` 分段，**每带 baseline_agreement 与 label_correct 均 100%**：

| 残差带 | 样本数 | baseline_agreement | label_correct | 其中 4ASK |
|---|---|---|---|---|
| 0.11–0.12 | 6 | 6/6 | 6/6 | 3 |
| 0.12–0.13 | 14 | 14/14 | 14/14 | 4 |
| 0.13–0.14 | 7 | 7/7 | 7/7 | 5 |
| 0.14–0.15 | 2 | 2/2 | 2/2 | 2 |
| 0.15–0.16 | 1 | 1/1 | 1/1 | 1 |
| **合计** | **30** | **30/30** | **30/30** | 15 |

`finite=30/30`、`repeat_argmax_deterministic=30/30`、`repeat_logits_byte_identical=30/30`（≥2 前向）。
`result_layer` 统一 `HOST_BF16_FORCED_CLASSIFICATION`。

---

## 五、强制分类是否 correct（Phase D 主判据）

**是（host BF16 层）。** 30/30 样本：
- `baseline_agreement=1`（`raw24_pred == baseline_pred`，主判据）；
- `label_correct=1`（`raw24_pred == source_label`，BPSK→3 / 4ASK→1，单独报）。

即在残差 0.11~0.15 的失败样本上，生产恢复 + 分类链即便绕过 0.10 门，产出的 24 维 logits argmax 仍与冻结 baseline 及真实标签一致。

**但这不证明放宽生产门限是安全的**——见第六、七节。

---

## 六、主导残差源（Phase E）

训练块（1024 样本）4 个固定候选模型（const_phase / residual_cfo / wide_linear `a·m+b·conj(m)` / fir5 固定 5-tap+ridge），
前半块拟合、后半块验证、固定阶数、归一化到生产模型能量 Σ|m|²：

| 归因 token | 样本数 |
|---|---|
| `DOMINANT_RESIDUAL_IQ_IMBALANCE` | **18** |
| `DOMINANT_RESIDUAL_RANDOM_NOISE` | 11 |
| `DOMINANT_RESIDUAL_FREQUENCY_SELECTIVE` | 1 |

**主导源 = 宽线性 IQ 不平衡（18/30）**，其次为随机噪声（11/30）。残余 CFO 与常量相位**均非主导**——
即生产恢复后的剩余误差主要来自镜像抑制不足与 RF 噪声，而非残余频偏/相位漂移。
（注：生产已做的复增益/payload phase/fine CFO/分数定时**未重算成新收益**，只拟合恢复后的剩余误差。）

---

## 七、是否支持重判 0.10（Phase F）

**不支持据此推荐全局生产门限。** 结论上限为
`EVIDENCE_SUPPORTS_A_PROSPECTIVE_THRESHOLD_VALIDATION`，**不写 `NEW_PRODUCTION_THRESHOLD=0.16`**。

- 30 样本**全部是被 0.100 拒绝后才转储的失败样本 =「失败条件抽样」**，不是全体 RF 样本；
- 阈值 0.12 起才接纳（0.12 接纳 6、0.16 接纳 30），且接纳样本 30/30 强制分类正确（含 0.15 最坏 1 例）；
- 但缺少：独立 PASS+FAIL 验证集、覆盖 24 原始类、无信号/错误同步/低相关负例、验证「放宽不误接纳错误窗口」；
- **0.10 保持基线，不自动改生产值。**

前瞻验证框架（正 120 负 39 空捕获计划 + 自动判读 + Wilson CI）已另立
`fix10class24-prospective-prep1`，待真实 RF 采集后执行，届时才可对门限做正式判读。

---

## 八、缺什么 24 类证据

1. **只覆盖 24 类中的 2 类**（BPSK=3、4ASK=1）；其余 22 原始类无失败样本，无法断言全类一致性；
2. **无板端 NPU 实测**——本结论仅 host BF16；板端数字直注需另走 `...-INPUTS-READY-FOR-BOARD-NPU-TEST` 路径；
3. **无负例**（无信号 / 错误同步 / 低相关窗口）——放宽门限是否会误接纳错误窗口未验证；
4. **样本数有限**（30，且同分布内高度相关），不能外推到全体 RF 运行分布。

---

## 九、选择偏差披露

- 输入 = 生产门禁 0.10 **拒绝后**转储的失败样本集合，**不含任何 PASS 样本**；
- 因此「30/30 强制分类正确」**只能**说明失败样本仍含可分类信息，**不能**反推放宽门限的误接纳率为 0；
- 本任务刻意不据标签拟合任何参数、不用期望 payload 冒充真实恢复、不因分类正确写 RF PASS。

---

## 交付物与验证

| 交付物 | 位置 |
|---|---|
| 诊断核心（`replay24force::apply_provisional` + 分解） | `host_tools/replay_fix10class24_failed_rx_force_classify.{cpp,hpp,sh}` |
| 审计脚本（inventory/classify/threshold） | `scripts/audit_fix10class24_failed_rx_forced_classification.py` |
| 测试 | `host_tests/test_fix10class24_failed_rx_force_classify.{cpp,py}` |
| 结果 | `results/rxresidual_audit/{capture_inventory,per_capture_results,raw24_logits,threshold_sensitivity,residual_attribution}.tsv` + `summary.json` |

**验证（离线，不碰板）**：
1. `bash host_tests/build_host_tests.sh && bash host_tests/run_tests.sh` → **ALL HOST TESTS PASSED**（含 18 新测试 + 全套既有回归）；
2. `replay_fix10class24_failed_rx_force_classify.sh --self-test` → **PASS**（PASS fixture 全路径五阶段字节等价）；
3. 红线头 `board_package/` 与基线树逐字节一致；canonical 3 组件（contracts/ + `iq_fix10_canonical_frame_data.hpp`）未动；
4. 30 个 dump 目录 `--export-provisional` 各落 5 文件 + SHA 全对。

---

## 停止条件核验

1. ✅ 归档 SHA 及 30 样本身份通过；
2. ✅ 30 样本 canonical 重放在既定容差内（27/0）；
3. ✅ PASS fixture 完整路径逐阶段等价；
4. ✅ 15 capture_id 齐全、30 主键唯一、每 capture_id 恰好含 500 与 1500 各一次；
5. ✅ Host BF16 对每个输入输出 24 维有限 logits；
6. ✅ 强制分类结果、残差归因、选择偏差完整披露；
7. ✅ 生产门限、恢复器、runner、模型、红线头全部未改。

**下一步由用户决策**：是否开放板端数字直注包（`...-INPUTS-READY-FOR-BOARD-NPU-TEST`）以取得真实 NPU 判定；
或按 `fix10class24-prospective-prep1` 走前瞻门限验证。本任务到此暂停，不自动进入门限修改或恢复器修改。
