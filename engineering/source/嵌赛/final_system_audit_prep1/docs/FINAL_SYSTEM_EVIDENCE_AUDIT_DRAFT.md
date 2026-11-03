# M29 RML23 — 全流程证据审查与最终报告预备（final-system-audit-prep1）

> 状态：**`M29-RML23-FINAL-SYSTEM-EVIDENCE-AUDIT-DRAFT-READY`**（最高允许）
> 性质：**只读审计**。不解决 fix10prep3 板测问题、不改生产代码、不碰板、不重训/量化/打包、不提前宣称完成。
> 证据级别定义见 `README.md §3`。

## 0. TL;DR

- 全链 12 项功能状态矩阵（`results/status_matrix.tsv`）：10 项处于「离线交付态（`*-READY-FOR-BOARD-TEST` 或等价）」，1 项 **`ACTIVE / PENDING-RETEST`**（fix10prep3 真实板测未过），1 项 REJECTED/BLOCKED（24 类直接部署）。
- **没有任何一条「板测通过」结论可写**：全链无 E1 直接证据；唯一一次真实板测（fix10prep3）失败且原始日志未归档到 PC 树，只能记 E1-R。
- **核心阻塞 = fix10prep3 真实板测未过**（`training_corr=0.720230 < 0.9 → classification=SKIPPED`），新修复「分数采样对齐 + TX-off 空闲等待」进行中，尚未重新打包/构建/过板。
- 审计发现 **4 处证据错配 / 版本资产混用**（见 §3），全部如实记录，不做任何修补。

---

## 1. 证据级别与审计方法

| 级别 | 定义 |
|---|---|
| **E1** | 直接板测证据：板端原始日志/退出码/SHA **已归档到 PC 磁盘** |
| **E1-R** | 直接板测已做、但日志未归档，仅由任务书/报告转述（"报告式板测"） |
| **E2** | 离线主机证据（host 测试、确定性打包、SHA 校验、数字回环） |
| **E3** | 仅文档/任务书声明，无独立落盘产物 |
| **E4** | 待做 / 无证据 |

方法：只读审计，4 个只读子代理并行取证（board/package、model/OOD、UI、clean/24 树），本主进程汇总。所有 SHA **逐字从磁盘冻结文件读取**；只拿到 8 字符前缀的一律标「前缀仅」，不得自填后 56 位。

---

## 2. 七大问题逐条回答

### Q1 — 哪些结论有直接证据（E1）？

**无。** 全链目前**没有一条 E1 直接证据**（板端原始日志落 PC 盘）。

- 唯一一次真实板测是 fix10prep3（BPSK+4ASK 两样本），结果 `training_corr=0.720230 < 0.9`，但**板端原始日志未归档到 PC 树**，仅任务书记载 → 只能记 **E1-R**。
- 其余所有结论（含各 `READY-FOR-BOARD-TEST` 状态）都是离线交付态，不是板测通过态。

### Q2 — 哪些只有离线证据（E2）？

以下结论**明确排除板/SDR/NPU**，纯离线验证，证据充分：

| 结论 | 离线证据 | 来源 |
|---|---|---|
| 24→23 合并正确（WC=17/SC=18→AM-SSB 17） | clean2a deployed23=0.99450；class24 raw24/deployed23 24/24 全一致；`rml23_merged_contract.py` SHA 31deebc0… | fix10clean2a / class24 审计 |
| 纯净 IQ 可被冻结模型准确识别 | clean2a formal12000 raw24=0.99325、deployed23=0.99450、min recall 0.956(OQPSK)、host 29 passed | fix10clean2a |
| canonical 训练帧三组件按 aarch64 权威冻结、跨架构字节一致 | `contracts/fix10_canonical_frame_v1/manifest.tsv` source_arch=aarch64；host 回归 `FULL_REGRESSION_EXIT=0`（test_fix10_canonical_frame 44/0） | fix10prep3 |
| D2 恢复保真达标 | class24 D2 恢复 corr≥0.999652 / NMSE≤7.470e-04 / rms_scale_error≤7.611e-03 | fix10class24 |
| fix9 Route F 23 类 runner 交付 | test_iq_rf_loopback_23class 17/0（93 断言）+ 全套件 ALL PASSED | fix9 |
| fix9r2g1 baseline 合同 E2E | test_iq_rf_loopback_fix9r2g1_baseline_e2e 9/9 | fix9r2g1 |
| fix10clean2b 离线自检 | full `b6e1df3b…` host 全套 + 2 新测试 37/0+18/0 | fix10clean2b |
| AM-SSB WC/SC 高 SNR 可判别 | Phase A clean WC=0.97 / SC=1.0 / 错出族 0 | amssb_wc_sc_audit |

### Q3 — 哪些仍需板测 / 实物验证？

7 项（详见 `docs/BOARD_TEST_EVIDENCE_CHECKLIST.md §C`）：

1. fix9 Route F 四步复测（23 类准确率 + 混淆矩阵）
2. R8 两样本（fix9r2g1，BPSK+4ASK）
3. R9 46 样本回归
4. **fix10prep3 重跑**（修复后：training_corr≥0.9 + classification 正常）
5. fix10clean2b Step 6（scored=2 / prediction_agreement=2/2 / 负对照 PASS）
6. AM-SSB WC/SC Phase C/D（真实板测判别归因）
7. UI 真实显示器（构建运行 + 交互 + 截图）

### Q4 — 当前阻塞关键路径

```
ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS   ← 上游总门禁（未取得）
        ↓
fix10prep3 两样本真实双 SDR               ← 当前最直接阻塞
        │   training_corr=0.720230 < 0.9 → classification=SKIPPED
        │   （payload_training_corr=0.989795 正常，训练块去斜 OK）
        ↓
fix10clean2b Step 6 / fix10class24 上板    ← 被 fix10prep3 继承阻塞
```

- fix10prep3 当前正在追加「分数采样对齐 + TX-off 空闲等待」新修复，**尚未重新打包/构建/过板** → 记录为 `ACTIVE / PENDING-RETEST`。
- 24 类直接部署长期 REJECTED/BLOCKED（PTQ 耗尽 + E0 QAT 无接口），与板测无关，是模型域方案问题。

### Q5 — 修复后下一测试顺序

1. **fix10prep3 新修复完成** → 用户重跑 BPSK+4ASK 两样本烟测（判据 `training_corr≥0.9` + classification 正常）。
2. 通过 → **fix10clean2b Step 6**（scored=2 / prediction_agreement=2/2 / 负对照 PASS / CFO finite·in-range）。
3. 通过 → 开放 **fix10class24 集成**（24 原始类 / 23 部署类）。

### Q6 — 还缺哪些数字 / 截图 / 日志 / SHA？

6 项（详见 `docs/BOARD_TEST_EVIDENCE_CHECKLIST.md §D`）：

1. fix10prep3 板测**原始日志**（training_corr/classification 的板端原始输出，非任务书转述）。
2. 23 类准确率 + 混淆矩阵（route_f_fix9_summary.json / confusion_23.csv，全树未见）。
3. UI 真实显示器截图（offscreen 烟测 ≠ 真实渲染验收）。
4. 包 tarball 完整 SHA（fix9r2g1 / fix10prep / fix10prep2 / fix10clean2a，树内仅前缀）。
5. 8 类模型完整 SHA（仅前缀 c48979b3…）。
6. fix9r2g1 独立 DELIVERY.txt（树内缺失）。

### Q7 — 是否发现状态夸大 / 证据错配 / 版本资产混用？

**发现 4 处，如实记录如下（§3），不做修补。**

---

## 3. 关键发现（Q7 详述）

### 3.1 fix10prep3 磁盘审计文档过时（状态夸大风险）

- 磁盘 `fix10prep3_work/.../M29_RML23_FIX10PREP3_CROSS_ARCH_TRAINING_FRAME_AUDIT.md` 仍写 `CANONICAL-FRAME-READY-FOR-BOARD-TEST`。
- 但任务书记载真实板测**已失败**（training_corr=0.720230<0.9）。
- **裁定**：本审计按任务书记 `ACTIVE / PENDING-RETEST`；磁盘文档过时，已在 `results/status_matrix.tsv` 与 `open_issues.tsv` 标注。→ 若最终报告沿用磁盘旧状态，即构成「状态夸大」。

### 3.2 closed-set 最终评估数值出入（证据错配）

| 来源 | acc | rated_0_20 |
|---|---|---|
| 记忆（rml24-closed-set-final-decouple） | 0.630457 | 0.890998 |
| 磁盘 `final_checkpoint_manifest.json::selection_value` | — | 0.89099789…（**选型值**，非最终盲测） |
| 磁盘 `rml24_closed_set_final.json` | **0.6308083177** | **0.8919807834**（最终盲测） |

- 记忆的 `rated_0_20=0.890998` 对应的是**选型值**，不是最终盲测值 0.891981。
- 记忆的 `acc=0.630457` 与磁盘 0.630808 也不一致。
- **裁定**：以磁盘冻结值为准（`accuracy=0.6308083177` / `rated_0_20_accuracy=0.8919807834`）；记忆数值是另一评估运行（选型）的残留，不得混用。

### 3.3 红线头 SHA 按基线不同（版本资产混用风险）

`iq_rf_sync_recovery.hpp` 在三个基线树中 SHA 各异：

| 基线 | SHA |
|---|---|
| fix10prep2（h5） | a8b3b603… |
| fix10prep（h2） | bd0a86f7… |
| fix9r2g1 | 6f055177… |

- 红线头「字节一致」**仅相对各自基线成立，非全局一致**。
- **风险**：最终报告若写「红线头不变」而不指明「相对哪个基线」，即构成版本资产混用。

### 3.4 合并合同版本混用风险

`rml23_merged_contract.py` 在**两处 SHA 不同**：

| 位置 | SHA |
|---|---|
| 部署侧（`rml23_merged_deployment_manifest.json::merged_contract_sha256`） | f9f7f381… |
| clean2a / class24 树（raw .py 文件） | 31deebc0… |

- 二者本应指向同一份 24→23 合并合同，SHA 却不同。
- **裁定**：记录为「需复核版本」——可能是合法版本演进（部署侧更新），也可能是资产混用；**离线不可裁决**，须由用户在最终报告前确认两份 `.py` 的差异来源。

---

## 4. 诚实边界（禁写清单）

本审计**明确不写**以下任何状态，且确认全链当前都不具备写出它们的证据：

- `RF_PASS` / `RF_PATH_PROVEN`
- `SMOKE-PASS` / `FIX10_READY`
- `ROUTE_F_23CLASS_ACCURACY_MEASURED` / `_REGRESSION_PASS`
- `NPU_PASS` / `PROJECT_COMPLETE` / `FINAL_*`

全链最高允许态即「离线交付态」；所有板测通过态待用户板测证据补齐后逐条升级。

---

## 5. 交付物索引

| 文件 | 内容 |
|---|---|
| `docs/FINAL_SYSTEM_EVIDENCE_AUDIT_DRAFT.md` | 本文（七大问题 + 关键发现） |
| `docs/FINAL_REPORT_OUTLINE.md` | 最终报告骨架 |
| `docs/BOARD_TEST_EVIDENCE_CHECKLIST.md` | 板测证据清单（A/B/C/D） |
| `results/status_matrix.tsv` | 12 项功能状态矩阵 |
| `results/artifact_registry.tsv` | 资产登记（阶段/用途/输入/输出/SHA/冻结/证据级别） |
| `results/requirement_traceability.tsv` | 需求→实现→测试→板测证据→结论 |
| `results/claim_to_evidence.tsv` | 结论↔直接证据（禁止无证据结论） |
| `results/open_issues.tsv` | 未决问题/根因/影响/下一步 |
| `results/command_registry.tsv` | 命令登记（阶段/PC或板端/是否执行/退出码/日志） |
| `results/sha_registry.tsv` | 全量 SHA-256 登记 |
| `README.md` | 方法学 + 交付物清单 + 禁写 token |

---

> 本审计为 **DRAFT**：证据链已按「逐字 SHA、报告式板测标 E1-R、无证据不结论」原则整理；最终报告成稿前，须由用户补齐 Q6 所列板测原始证据并裁决 §3.4 合并合同版本差异。
