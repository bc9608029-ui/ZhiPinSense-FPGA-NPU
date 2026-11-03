# M29 RML24 — Report Evidence Ledger 审计（rml24-report-evidence1）

- 任务：39e5（rml24-report-evidence1，只读证据台账）
- 工作树：`F:\嵌赛\rml24_report_evidence1_work\`
- 目标：为最终报告建立统一的「结论 → 证据 → 文件 → SHA → 限制」可追溯链。
- 最高允许状态：**`M29-RML24-REPORT-EVIDENCE-LEDGER-READY-FOR-ROOT-CAUSE-INSERTION`**
- 禁写：`SMOKE-PASS / RF-PASS / 24CLASS-PASS / RXONLY-PASS / PROJECT_COMPLETE / FINAL_*`；API 不碰板、不跑 SDR、不重训/量化、不改任何生产/源工作树。

---

## 1. 范围与红线

只读证据台账。10 个源树只读引用（不写入）；`enclosure-prep2` 不存在，记录
`SOURCE_NOT_PRESENT`。无法确认的数字填 `NOT_VERIFIED`。证据分层硬规则：

1. **Host ≠ 板端 NPU**（L4 主机 BF16 ≠ L7+ 板端 NPU）
2. **数字直注 ≠ RF**（L7 直注 ≠ L8 RF 回环）
3. **两样本 ≠ 24 类**（L5/L7/L8 两样本 ≠ L9+ 24 类）
4. **强制分类 ≠ 生产门禁通过**（诊断工具 ≠ L10）
5. **NPU 映射 ≠ 实测性能**（L6 部署可行性 ≠ 板端实测准确率/时延）

## 2. 阶段完成状态（A–I）

| 阶段 | 内容 | 状态 |
|---|---|---|
| A | 源树清点（9 PRESENT + 1 SOURCE_NOT_PRESENT） | 完成 |
| B | 重算关键 SHA（模型/规范帧/板端转储/审计档，非抄旧报告） | 完成 |
| C | 读取关键证据（4 审计档 + baseline + capture_inventory + prospective + UI） | 完成 |
| D | 证据分层合同（12 级）+ 结果术语 | 完成 |
| E | 21 条 claim → 证据矩阵 | 完成 |
| F | 9 张结果表 | 完成 |
| G | 3 张架构图（mermaid） | 完成 |
| H | 报告骨架（草稿/已证结论/待补证据） | 完成 |
| I | 检查器 + pytest + 最终状态 | 完成 |

## 3. 源树（10）

9 个 `PRESENT`（`fix10prep_work`、`fix10prep2_work`、`fix10prep3_work`、
`fix10class24_prep1_work`、`fix10class24_dualsdr1_work`、`fix10class24_dualsdr2_work`、
`fix10class24_rxresidual_audit1_work`、`fix10class24_prospective_validation_prep1_work`、
`constellation_ui_desktop1_work`），指纹见 `evidence/source_tree_hash_before.tsv` /
`after.tsv`。第 10 个 `enclosure-prep2` = `SOURCE_NOT_PRESENT`。

> **只读保证**：本台账向所有源树写入 **0 字节**。7 个源树前后指纹一致
> （before == after）。2 个源树被**其他任务并发修改**，前后快照可能不同，
> 差异非本台账所致：
> - `fix10class24_rxresidual_audit1_work` —— 主线 rxresidual-audit1 正在写入
>   （Phase D/E/F 的 `.force_classify_cache`、`replay_*.cpp/.hpp`、`run_*.sh`；
>   快照 1340 → 1343 文件）；
> - `constellation_ui_desktop1_work` —— UI 桌面核验 agent（任务二）正在写入
>   （Qt build 产物；快照 217 → 218 文件）。
>
> 检查器 `check_tree_hash_consistency` 对这两棵树放宽为「PRESENT + SHA 合法」，
> 对其余 7 棵树仍严格要求 before == after。

> 注：源树清单按 RML24 交付链重构（本任务规范文本已随会话压缩），
> 凡无法逐字还原处均已标注；关键 SHA 均为本会话重算，未从旧报告抄录。

## 4. 关键重算 SHA（本会话）

- BF16 模型 json `28272abc…` / raw `c1781aec…`；源 checkpoint `96cd25f8…`
- canonical preamble `d4b4bb3a…` / payload_training `f06e9b3d…` / tail `ccddabe1…` / manifest `4b59ac5b…`
- 板端转储归档 `08ef944e…`；network_mapping_report `16d1716a…`
- 各证据档 SHA 见 `claim_evidence_matrix.tsv`。

## 5. 21 条 claim

见 `evidence/claim_evidence_matrix.tsv`。其中 VERIFIED（含 VERIFIED_NEGATIVE）20 条、
PENDING 0 条（本台账不产板端证据）、无 L9/L10/L11 断言。

## 6. 待补证据（PENDING）

- `[PENDING_RXRESIDUAL_AUDIT]` —— 主线强制分类/残差分解（Phase D/E/F 未完成）
- `[PENDING_UI_DESKTOP_RESULTS]` —— 星座 UI 桌面最终核验结论
- `[PENDING_24CLASS_RF_PROSPECTIVE_VALIDATION]` —— 板端 24 类 RF 前瞻验证
- `[PENDING_FPGA_UTILIZATION_REPORT]` —— FPGA 资源利用率报告

见 `report/PENDING_EVIDENCE.md`。

## 7. 校验

- `python -I scripts/check_report_evidence.py` —— 14 检查类全过
- `python -I -m pytest -q host_tests/test_report_evidence.py` —— 全过

## 8. 最终状态

**`M29-RML24-REPORT-EVIDENCE-LEDGER-READY-FOR-ROOT-CAUSE-INSERTION`**

下一动作由主线/根因插入任务执行：把 `[PENDING_RXRESIDUAL_AUDIT]` 等证据回填进
`report/RML24_SYSTEM_REPORT_DRAFT.md`。在板端 2 样本 RF 恢复稳定（residual ≤ 0.10）
之前，不写任何 SMOKE/RF/24CLASS/PROJECT/FINAL 结论。
