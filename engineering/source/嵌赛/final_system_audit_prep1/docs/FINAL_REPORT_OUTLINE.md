# 最终报告骨架（RML24→RML23 SDR/NPU 系统）

> 本文件是**报告骨架**，7 问为纲；每问的答案先挂证据级别（E1/E2/E3/E4，见 README §3），再落具体数字/SHA/日志。撰写最终报告时以本骨架为准，逐问补证据。

---

## 0. 范围与读法

- 系统 = RadioML2018 24 类 ADAMRV11Net（冻结 checkpoint `96cd25f8…`）→ 24→23 合并 → FMQL30TAI + ZG330 NPU 板端部署。
- 证据级别 E1–E4 定义见 `README.md §3`。
- 所有结论必须能回到 `results/claim_to_evidence.tsv` 的某一行。

---

## Q1. 哪些结论有直接证据（E1 板测 / E2 离线直接）

- 待填：逐条列出，每条给（结论 → 证据文件 → 数字/SHA → 级别）。

## Q2. 哪些只有离线证据（E2，尚未上板）

- 待填：canonical 包 host 回归、24 类离线资产、clean2a/clean2b 离线自检等。

## Q3. 哪些仍需板测 / 实物验证（E3/E4）

- 待填：fix10prep3 重测、clean2b 上板、24 类真实板测、UI 真实显示器验收等。

## Q4. 当前阻塞关键路径

- 待填：fix10prep3 板测失败（training_corr=0.720230<0.9）→ 新修复「分数采样对齐 + TX-off 空闲等待」→ 修复后重测 → 才解锁后续 clean2b / 24 类。

## Q5. 修复后下一测试顺序

- 待填：给出修复后的最小测试顺序（两样本 BPSK+4ASK → 通过后开放更多样本）。

## Q6. 还缺哪些数字 / 截图 / 日志 / SHA

- 待填：完整 SHA 缺口清单、板测日志、UI 截图、准确率数字等。

## Q7. 是否发现状态夸大 / 证据错配 / 版本资产混用

- 待填：本审计发现的问题（例：fix10prep3 磁盘审计文档状态落后于任务书最新板测；training_corr 与 payload_training_corr 口径区分；24→23 合并是否正确等）。

---

## 附录 A：证据索引（指向 results/*.tsv）

- 待填：artifact_registry / status_matrix / sha_registry 的交叉引用。

## 附录 B：命令台账（指向 command_registry.tsv）

- 待填。
