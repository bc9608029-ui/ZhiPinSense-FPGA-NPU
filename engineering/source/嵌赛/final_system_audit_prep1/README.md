# M29 RML23 — 最终系统证据审查与最终报告预备（final-system-audit-prep1）

- **状态令牌（唯一，不更高）**：`M29-RML23-FINAL-SYSTEM-EVIDENCE-AUDIT-DRAFT-READY`
- **本目录是唯一写入位置**：`F:\嵌赛\final_system_audit_prep1\`
- **性质**：对 RML24→RML23 SDR/NPU 全流程的**只读总审查**，产出最终报告所需的证据索引、状态矩阵与报告骨架。**不是最终报告本身**，也不解决任何板测问题。

## 1. 范围与排除

**在范围内**：RML24 24 类模型（训练/量化/OOD/冻结 checkpoint）→ RML23 23 类板端部署（fix 链：fix1→fix7 → fix8/fix9 Route F → fix9r2* 根因链 → fix9r2g1 → fix10-prep → fix10prep2 → fix10prep3 → fix10clean2a/2b → fix10class24）→ 星座图 UI 原型。

**明确排除**：不解决 fix10prep3 板测问题、不修改任何生产代码、不碰板、不重训/量化/打包、不提前宣称完成、不修改 MEMORY/生产树/正式包、不运行占用 SDR/串口/网口/板卡的程序、不装依赖/不大规模复制二进制。

## 2. 交付物清单（11 件）

| 路径 | 内容 |
|---|---|
| `docs/FINAL_SYSTEM_EVIDENCE_AUDIT_DRAFT.md` | 总审计文档（证据索引 + 7 问答卷 + 诚实边界） |
| `docs/FINAL_REPORT_OUTLINE.md` | 最终报告骨架（7 问为纲） |
| `docs/BOARD_TEST_EVIDENCE_CHECKLIST.md` | 板测/实物验证证据清单（哪些已有、哪些缺失） |
| `results/artifact_registry.tsv` | 阶段/文件/用途/输入/输出/SHA/是否冻结/证据级别 |
| `results/status_matrix.tsv` | 功能/当前状态/最后证据/缺失证据/下一门禁 |
| `results/requirement_traceability.tsv` | 最终需求/实现文件/测试/板测证据/结论 |
| `results/claim_to_evidence.tsv` | 结论 + 直接证据（禁止无证据结论） |
| `results/open_issues.tsv` | 问题/根因/影响/阻塞范围/负责人/下一步 |
| `results/command_registry.tsv` | 阶段/PC或板端/命令来源/是否执行/退出码/日志 |
| `results/sha_registry.tsv` | 所有正式模型/合同/包/manifest/baseline 的完整 SHA-256 |
| `README.md` | 本文件 |

## 3. 证据分级（所有结论必须挂级）

- **E1 直接板测证据**：真实板端/真实 SDR 上产生的日志、退出码、`training_corr`/`classification`/准确率/混淆矩阵。
- **E2 离线主机证据**：host/WSL 回归、确定性两跑、SHA 自检、单元测试、离线仿真。
- **E3 文档声明（未定位到原始证据文件）**：仅审计文档/任务书记载，本机未定位到对应原始文件。
- **E4 未验证/待办**：尚无任何证据，等待用户板测或后续步骤。

**铁律**：`claim_to_evidence.tsv` 中每条结论必须有至少一条 E1/E2 直接证据；纯 E3/E4 不得作为"已验证"结论。

## 4. 关键状态结论（本审计的核心判定）

1. **fix10prep3 记 `ACTIVE / PENDING-RETEST`**。其离线 canonical 包已交付（`M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST`，host 全量回归 `FULL_REGRESSION_EXIT=0`），但**真实板测未通过**：`training_corr=0.720230 < 0.9`（fidelity 门不过）→ `classification=SKIPPED`，另有 PC TX-off 空闲超时与第二样本未完成；现正进行「分数采样对齐 + TX-off 空闲等待」新修复。磁盘审计文档仍显示旧状态，本审计以任务书最新板测为准，不把中间态当正式交付。
2. **所有上板结论均未达到"板测通过"级别**：当前无任何 `SMOKE-PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE` 状态可写。
3. 板端权威=ARM 输出的训练帧；x86 仅用于诊断定位差异，绝不冒充权威。

## 5. 诚实边界

- 禁止写的令牌（本项目全程未写）：`SMOKE-PASS / RF_PASS / RF_PATH_PROVEN / FIX10_READY / PROJECT_COMPLETE / FINAL_*`。
- 本目录只写 `M29-RML23-FINAL-SYSTEM-EVIDENCE-AUDIT-DRAFT-READY`（DRAFT，非最终报告、非完成声明）。
- SHA 一律逐字；源文件只有 8 字符前缀的，照抄并标"前缀仅"，绝不从短前缀臆造 64 位 SHA。
