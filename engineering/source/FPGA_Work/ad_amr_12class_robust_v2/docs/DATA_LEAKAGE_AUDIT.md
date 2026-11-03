# 数据泄漏审计（DATA_LEAKAGE_AUDIT）

> 任务：十二类调制识别模型 V2 鲁棒性改进 · 阶段六（严格防泄漏）
> 生成：2026-10-07。记录 V1 已实现的防泄漏机制 + V2 必须遵守/新增的约束。
> 规格 §六：拆分必须按「源」分组，而不是随机切窗口。

## 0. V1 既有防泄漏机制（冻结事实，来自 `datasets/ad_amr_dataset.py` / `ad_amr_v1_1_dataset.py` / `radioml2018_dataset.py`）

1. **按 split 字符串派生独立随机流**：`split_code = blake2s(split_string)[:4]`，`sample_id_base = split_code * 1_000_000`，不同 split（train/val/test/OOD/fake-int8）的样本 id 区间**完全不重叠**。
2. **每样本 seed 可追踪**：`SeedSequence([seed, split_code, epoch, index])` → 同一 `(seed, split, epoch, index)` 永远产出字节一致的 clean/noisy 记录。
3. **训练/验证分离**：训练 split 的 `epoch` 参与 seed（每 epoch 不同），验证/测试 `epoch=0` 固定。
4. **选择命名空间隔离**：`assert_selection_split` 拒绝非 `validation` 或含 `test`/`blind` token 的 split 用于模型选择；`FORBIDDEN_SELECTION_TOKENS = ("test", "blind")`。
5. **盲测集访问禁止**：`ADAMRV11Dataset` 构造即拒绝 `blind` split；V1 全程 `final_blind_test_accessed=false`。
6. **公开数据 fail-closed 切分**：RadioML 只读 audited `split_indices.npz`，HDF5 size/mtime/index SHA 三重校验，训练只能从已审计索引启动。
7. **公开数据不混入目标头训练**：RadioML 24 类仅用于 trunk 预训练；目标头全新初始化后微调，避免 source 签名成为标签捷径。

## 1. V2 必须遵守的泄漏红线（规格 §六）

**同一「源」的所有相邻窗口必须同 split，禁止跨源混切：**

| 源粒度 | 规则 |
|--------|------|
| 同一原始波形 / seed | 全部窗口同 split |
| 同一连续采集文件 | 全部窗口同 split |
| 同一 RF 会话 | 全部窗口同 split |
| 同一段长录音 | 全部窗口同 split |
| 同一发射配置 | 全部窗口同 split |

**禁止：**

- 一个长录音切片后随机分散到 train/val/test；
- 相邻帧分别进入训练和测试；
- 先增强再随机拆分（增强前必须完成按源拆分）；
- 用 test 计算归一化统计量；
- 查看 test 结果后调整增强范围；
- 把板端黄金输入同时加入训练。

## 2. V2 建议的 split 结构（规格 §六，冻结）

```
train
validation
synthetic_frozen_test
public_cross_domain_test
real_rf_development
real_rf_final_holdout
deployment_golden
```

- `real_rf_final_holdout` 只能在候选配置冻结后运行**一次**。
- `synthetic_frozen_test`（D2）一次生成、文件哈希冻结、测试时禁止再生成/替换。
- 量化校准集可含真实 Pluto 子集，但**不能**用 `real_rf_final_holdout`（规格 §十五）。

## 3. V2 新增防泄漏工具（离线实现）

- `tools/split_by_session.py`：按 SigMF session 元数据（采集会话 id / 中心频率 / 发射配置）把样本归入同一 split，杜绝同 session 跨 split。
- `tools/check_data_leakage.py`：跨 split 检测样本 id / seed / 源签名重叠；检测板端黄金输入是否混入训练集。
- 两者 fail-closed：发现可疑重叠即非零退出，阻断后续训练。

## 4. 状态红线

- 泄漏检查是训练前置门（`setup → environment preflight → data audit → leakage check → baseline reproduce → pilot`，规格 §十七）。
- 我禁碰板、禁写 Flash；上板由用户本人执行。
- 本审计不据此修改任何 V1 上游文件。
