# 判分口径（任务 5，合同 §8）

实现：`src/scoring.py`。机器可读报告字段见 `ScoreReport.to_dict()`。

## 输入

- **冻结预期目标集合**：`GroundTruthTarget(truth_id, center_hz, class_name,
  entry_seconds, exit_seconds, power_db, bw_hz)`。进出场时间窗定义其活跃区间。
  `power_db` 是判分侧真值的相对幅度（dB，相对尺度，非 dBm），仅用于离线仿真。
- **观测列表**：每目标每周期一条（`target_id, center_hz, last_seen, top3,
  confidence`），由 `src/simulate.py` 在每次扫频周期末按 tracker 快照产出。
- **时间窗**：可选 `[t0, t1)`，默认整段运行。

## 匹配规则

- 报告目标按 `center_hz` 与真值目标在 `MERGE_RADIUS_HZ`（6 250 Hz）内且落在
  该真值的 `[entry, exit)` 内匹配。
- 同一真值被多个 `target_id` 同时匹配 → 计入**重复目标**。

## 指标（检出与分类分开报告）

| 指标 | 定义 | 字段 |
|------|------|------|
| 检出率 detection_rate | 匹配到的唯一真值数 / 期望目标数 | `detected_targets/expected_targets` |
| 漏检 miss | 期望但从未匹配的真值；**漏项固定计错**，不删分母 | `missed_truth_ids` |
| 虚警 false alarm | 报告但匹配不到任何真值的目标 | `false_alarm_target_ids` |
| 重复目标 duplicate | 同一真值被多个 target_id 同时匹配（去重失败） | `duplicate_groups` |
| 首次发现延迟 | 真值进场到首次匹配的秒数（≥0） | `first_discovery_seconds` |
| 重访周期 | 同一目标相邻两次检出间隔（秒） | `revisit_intervals_seconds` |
| 分类正确 | 仅在“被匹配且已分类”的目标上判定 top1 类名是否等于真值类名 | `classification.correct/wrong/classified/accuracy` |

## 关键口径（合同 §8 逐条落实）

1. **检出与分类分开报告**：`classification` 是独立子报告，分类错误不改变
   `detection_rate`；检出错误不进入分类分母。
2. **漏项固定计错**：分母恒为期望目标数，失败项不删、不择优。
3. **不得只对收到的目标报准确率**：分类准确率分母是“被匹配且已分类”的目标，
   未分类的匹配目标单列 `unclassified_matched`，漏检目标不进入分类分母
   （它们已在检出侧计错，不重复计）。
4. **分类红线**：分类本身（`classifier` 回调 / 冻结 NPU）不读真值；`score()`
   只在判分侧拿分类输出与真值比对，这是判分的职责，不是分类的输入。
