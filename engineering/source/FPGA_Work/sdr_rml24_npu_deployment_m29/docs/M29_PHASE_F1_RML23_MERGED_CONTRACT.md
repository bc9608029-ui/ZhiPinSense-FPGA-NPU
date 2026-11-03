# M29 Phase F1 — 独立 23 类合并契约（AM-SSB-MERGED）

> 状态：`M29-RML24-NPU-QUANTIZATION-REMEDIATION_REQUIRED`（未变）
> 性质：部署层标签契约，**不改动** 24 类契约，不训练专家，不改 NPU 输入/24 维索引。
> 红线：禁碰板 / 禁写 Flash / 禁访问 test / 禁写 FINAL_*/NPU_PASS 等。

---

## 0. 结论

- **独立契约**：新目录 `contracts/`（不在 `_frozen/`），从冻结 24 类契约**派生**，不修改冻结契约。
- **合并语义**：`merged_AMSSB = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC) = log(exp(SC)+exp(WC))`——log 域「P(AM-SSB)=P(SC)+P(WC)」的严格实现，非删除、非无依据均值。已审计输出语义（24 维 raw logits，`OUTPUT_KIND="raw_logits_no_softmax"`），合并成立。
- **契约参数**：`source_class_count=24` / `deployed_class_count=23` / `npu_output_dim=24` / `deployment_mode=AMSSB_MERGED`；AM-SSB 两源索引 = **17（WC）/ 18（SC）**；22 类非 AM-SSB 原序保留。

---

## 1. 产物

| 文件 | 内容 |
|---|---|
| `contracts/rml23_merged_contract.py` | 权威 Python 契约（纯 stdlib，`python -I` 可导入）：标签序、索引表、合并算法、确定性 SHA、源序 SHA 校验 |
| `contracts/rml23_merged_contract.json` | 冻结 JSON（烘焙两个确定性 SHA） |
| `postprocess/rml23_merged.py` | 参考后处理：`merge_logits_24_to_23` / `predict_23` / `predict_23_full` / `merge_many_24_to_23`（向量化）；fail-closed（非 24 维 / NaN/Inf 拒绝）；`logaddexp` 用 `log1p` 稳定式 |
| `tests/test_rml23_merged_contract.py` | pytest 32 项（F1 范围离线测试） |

---

## 2. 确定性 SHA（冻结）

| 名称 | 值 |
|---|---|
| 23 类标签序 SHA | `15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88` |
| 合并契约整体 SHA | `f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e` |
| 源 24 类标签序 SHA（复用冻结） | `3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549` |

> 约定与 v1.1 一致：`sha256(json.dumps(list(...), sort_keys=True, separators=(",",":")))`。合并契约整体 SHA 额外覆盖合并索引/模式/源 SHA，故「错索引/错模式」也会 fail-closed。

---

## 3. 合并映射（24 维 → 23 维）

- `SOURCE_TO_DEPLOYED = (0..16, 17, 17, 18..22)`（24 项）。
- 索引 17（WC）与 18（SC）都落到 23 类槽位 17（AM-SSB）；19..23 依次下移一位（→18..22）。
- 非合并槽位逐值复制，原始 24 维 logits 全程保留（`predict_23_full` 同时返回 `raw_24_top1` 与 `merged_23_top1`）。

---

## 4. F1 范围离线测试结果

`pytest tests/test_rml23_merged_contract.py -q` → **32 passed**。覆盖：映射唯一+完备、AM-SSB 两源索引、22 类原序保留、logaddexp 稳定（含 ±inf/极值）、极端 logits、NaN/Inf fail-closed、非 24 维拒绝、标签 SHA 不匹配拒绝、raw24 保留、确定性 SHA、标量/向量化等价、`expert_enabled=false` 默认关闭。
