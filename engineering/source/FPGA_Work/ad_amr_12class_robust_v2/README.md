# ad_amr_12class_robust_v2 — 十二类调制识别模型 V2 鲁棒性改进

> 任务：在已上板验证的十二类模型（V1，`12CLASS_CHAIN_VALIDATION_MODEL_V1`，raw SHA `2ae95275…`）基础上，
> 做**数据与架构无关的鲁棒性改进**，重点修复 V1 的三个 OOD 失败域：cfo_strong / multipath / multi_impairment。

## 红线（永不违反）

- **绝不修改** V1 模型（checkpoint/ONNX/iCraft json/raw）、已通过位流、十二类标签顺序。
- 新模型只命名 `12CLASS_ROBUST_CANDIDATE_V2`，所有门禁通过前**不**替换 V1、**不**进正式板端包。
- 不使用测试集调参；不根据最终测试结果反复改门限。
- 新工程只在 F 盘；原模型/工程/位流只读冻结。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
- 未经实机验证只标 `READY-FOR-…-TEST`，**绝不**写 `FINAL_MODEL_PASS / ROBUST_MODEL_PASS / REAL_RF_PASS / OOD_PASS / PROJECT_COMPLETE`。

## 阶段与状态

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1（阶段四） | V1 基线冻结与复现 | ✅ 完成（见下方交付物） |
| 后续 | 数据审计 / 公开数据标签映射 / 合成生成契约 / 真实 RF 采集工具 / 防泄漏 / 增广消融 / 配置搜索 / AutoDL 包 / 门禁文档 | 待做（仅离线可备部分） |

## Phase 1 交付物（本目录）

- `docs/V1_BASELINE_FREEZE.md` — V1 基线冻结（身份/标签/配置/结构/种子/产物 SHA/结果/复现判定）
- `BASELINE_SOURCE_SHA256.txt` — 冻结源文件 + 训练产物 + 部署产物逐文件 SHA
- `BASELINE_DATA_MANIFEST.txt` — D1–D4 数据域清单 + 防泄漏切分安全

## 当前最高离线状态

- 有真实 RF 之前：**`NEEDS-REAL-RF-DATA`**（D4 为空）
- 导入真实 RF 但未上板：`READY-FOR-12CLASS-V2-NPU-HARDWARE-TEST`
