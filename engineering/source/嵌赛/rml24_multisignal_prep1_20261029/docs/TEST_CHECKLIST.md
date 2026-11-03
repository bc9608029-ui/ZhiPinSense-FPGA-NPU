# 独立测试清单（任务 3）

全部为离线测试，`python -m pytest -q` 一键运行。逐项对应测试函数。
D/E 节的 12.5 kHz 可分辨与 25 dB 动态范围是**离线测试目标（待板测验证）**，
不是冻结承诺。

## A. 目标数量

| 场景 | 期望 | 测试 |
|------|------|------|
| 0 目标（纯噪声） | 无目标、无观测 | `test_simulate.py::test_zero_targets` |
| 1 目标 | 检出 1、分类正确 | `test_one_target` |
| 2 目标（频率分离 250 kHz） | 检出 2、无虚警 | `test_two_targets_frequency_separated` |
| 3 目标 | 检出 3 | `test_three_targets` |

## B. 范围边缘

| 场景 | 期望 | 测试 |
|------|------|------|
| 目标在 `start_hz` 与 `stop_hz` 边缘 | 均检出 | `test_range_edge_targets` |

## C. 进出场与老化

| 场景 | 期望 | 测试 |
|------|------|------|
| 目标第 2 周期进场、第 4 周期出场 | 首次发现延迟 0；3 周期未检出后老化丢弃 | `test_entry_and_exit_with_aging` |
| 老化状态机（missing→expired） | 连续 N 周期后移除 | `test_tracker.py::test_aging_marks_missing_then_expires` |
| target_id 永不复用 | 老化后新目标用新 id | `test_target_id_is_never_reused_after_aging` |

## D. 不同功率 / 动态范围

| 场景 | 期望 | 测试 |
|------|------|------|
| 弱信号比强信号低 25 dB（5 bin 外） | 均检出 | `test_psd.py::test_near_neighbor_dynamic_range_25_db_boundary` |
| 强弱差 25 dB、相距 250 kHz（仿真） | 均检出 | `test_simulate.py::test_different_powers_within_dynamic_range` |

## E. 近邻分辨率与不可分辨

| 场景 | 期望 | 测试 |
|------|------|------|
| 两音 12.5 kHz（5 bin） | 2 个候选 | `test_psd.py::test_two_tones_resolvable_at_12_5_khz` |
| 两音 7.5 kHz（3 bin） | 合并为 1（不可分辨） | `test_two_tones_unresolvable_at_7_5_khz_merge` |
| 仿真中 7.5 kHz 双目标 | 检 1、漏 1（如实计错） | `test_simulate.py::test_unresolvable_close_pair_counts_as_miss` |
| 40 kHz 宽信号 | 单一候选、带宽 ≥25 kHz | `test_occupied_bandwidth_wider_signal` |

## F. 判分口径

| 场景 | 期望 | 测试 |
|------|------|------|
| 全检出 + 全分类正确 | 检出率 1.0、分类 2/2 | `test_scoring.py::test_full_detection_perfect_classification` |
| 漏项固定计错 | 检出率 0.5、missed=[2] | `test_miss_is_a_fixed_error` |
| 虚警单独报告 | detection 1.0 + false_alarm | `test_false_alarm_is_reported_separately` |
| 重复目标 | duplicate_groups 非空 | `test_duplicate_targets_detected` |
| 错分类不影响检出 | 检出 1.0、分类 0/1 | `test_wrong_classification_reported_separately_from_detection` |
| 未分类不计为正确 | unclassified_matched=1 | `test_unclassified_matched_target_not_counted_as_correct` |
| 首次发现延迟 / 重访周期 | 数值正确 | `test_first_discovery_delay_and_revisit_intervals` |

## G. TX 波形合成与频谱审计（任务 4）

| 场景 | 期望 | 测试 |
|------|------|------|
| 公共帧单位 RMS | rms≈1.0 | `test_tx_synth.py::test_common_frame_unit_rms` |
| 多载波求和 | 功率叠加 | `test_synthesize_sums_carriers` |
| int16 削顶封顶 | 幅度 ≤ full_scale | `test_to_int16_clipped_is_in_range` |
| 载波越界拒绝 | 超可用半带报错 | `test_carrier_offset_must_be_inside_usable_band` |
| 帧长不一致拒绝 | 报错 | `test_synthesize_rejects_mismatched_frame_lengths` |
| 保护带合规 | guard_ok、clip 0、互调<0、串扰<-20 dB | `test_spectrum_audit.py::test_two_well_separated_carriers_pass_guard` 等 |
| 保护带违规 | 5 kHz 间距 guard_ok=False | `test_guard_violation_when_too_close` |
| 峰均比随载波数增长 | PAPR(4 载波)>PAPR(2 载波) | `test_papr_grows_with_more_carriers` |

## H. UI 模型

| 场景 | 期望 | 测试 |
|------|------|------|
| 扫描坐标换算 | bin 549 → +92.5 kHz | `test_ui_model.py::test_spectrum_frame_scan_coordinates` |
| 换目标清空星座 | select 后旧 IQ 清空 | `test_select_replaces_constellation_never_accumulates` |
| 目标消失清空选择 | refresh 后 selected=None | `test_refresh_drops_vanished_selection_and_clears_constellation` |
| 选未知目标 fail-closed | 抛 KeyError | `test_select_unknown_target_raises` |
