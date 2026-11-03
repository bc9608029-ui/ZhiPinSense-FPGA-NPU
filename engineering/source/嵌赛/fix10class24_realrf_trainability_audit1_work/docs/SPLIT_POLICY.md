# M29-RML24-REALRF-TRAINABILITY-AUDIT1 — 切分策略与泄漏判定

状态：`…-SPLIT-POLICY-COMPLETE`（纯离线）

## 1. 切分单位 = 会话（train:val:test 按会话，绝不按会话内样本）

单个真实 RF 会话共享同一 LO/SDR/温度/AGC 状态；会话内切分会把该共享状态泄漏进
train/val/test，导致验证/测试精度虚高、不反映跨会话泛化。因此最终微调的 train/val/test
必须按**整会话**切分（建议 3:1:1）。

## 2. 当前数据的泄漏判定（`inventory_verdict.json`）

- 4 个捕获会话两两源波形重叠 **24/24**（`cross_session_source_overlap`）。
- 即四个会话 = 同一组 24 源波形的重复捕获，**无法**切出独立的 train/val/test。
- 判定 `leakage_check = TRAIN_VAL_TEST_SPLIT_IMPOSSIBLE`。

## 3. 附带泄漏控制（未来采集必须满足）

- 一个源实现不得出现在多个切分（train/val/test 互斥）。
- 24 类全部留在 24 分母，不剔除门拒/错误/非有限样本。
- 恢复/DC/尺度参数不得用标签或逐样本源身份选择。
- 不得复用现有 24 个 `tx_package` 源波形作为唯一实现（已作为审计集消耗）。

详见 `CAPTURE_PLAN.md` / `results/capture_plan.json`。
