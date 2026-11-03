# M29 RML23 Stage H-F / Route F — fix9r 逐文件训练帧恢复 审计与交付记录

状态：**`M29-RML23-IQ-RF-LOOPBACK-FIX9R-READY-FOR-BOARD-TEST`**（待用户上板 46 样本复测）

---

## 1. 为什么是 fix9r（根因）

fix9 已证明 D2 物理 RF 闭环 + 23 类准确率测量路径可行（`M29-RML23-IQ-RF-LOOPBACK-READY-FOR-BOARD-TEST`）。
但 fix9 板测结果 **46/46 valid、correct 仅 5/46 = 10.87%**（4ASK 0/2）。根因：

- `estimate_global_gain` 把每个文件的复增益 `a_i = |a_i|·exp(j·arg a_i)` 塌缩成**一个**中位幅度 / 圆周平均相位；
- 发射端 TX LO 在每次 `tx_start_cyclic` 重锁 → 逐文件相位随机；
- 单一全局相位无法抵消逐文件随机相位 → 几乎每个星座都旋转 → 接近随机（10.87%）。

fix9r 改为**逐文件**恢复：每个 payload 用类别无关的 Zadoff-Chu **训练帧**（前导 + 尾）括起来，
从**前导**逐文件估计 `timing_offset / gain_mag / phase_deg / cfo_hz / sro_ppm / phase_drift_deg`，
再对 payload 施加逆变换，然后进入 D2 恢复链分类。**只从已知训练帧估计，绝不用 payload（§7 泄漏禁令）。**

## 2. 逐文件恢复链

```
RX burst = [前导 1024][guard 2048][payload 53760][guard 2048][尾 1024] @ 2.56 MSPS
              │ 已知 ZC 根 r=1 (kTrainAmp=2048)      │ 已知 ZC 根 r=3
              ▼
iqrfrec::estimate(rx, search_limit=4096)
  1. 前导峰值互相关 → timing_offset + training_corr
  2. 前导 LS 复增益 → gain_mag + phase_deg
  3. 尾重定位 → sro_ppm
  4. 前导-vs-尾相位差 → cfo_hz + phase_drift_deg
  5. 归一化残差 → training_residual
              ▼
iqrfrec::apply(rx, rec)  →  undo 定时 / 复增益 a⁻¹ / CFO（锚定前导峰）/ SRO（线性插值，乘 (1+sro)）
              ▼
int16 → chain.push_int16 → apply_d2_restore_to_stream(rec_scale) → select_classification_window
              ▼
npu.infer → merge_logits_23 → argmax
```

**无全局增益、无校准趟**。RF 保真门：`training_corr >= 0.9` 且 `training_residual <= 0.05`，不过门 → `rf_excluded`（不评分）。

## 3. 文件清单（相对 fix9 基线 `2205750c7d…`）

**新增（10）**

| 文件 | 任务 |
|---|---|
| `board_package/iq_rf_training_frame.hpp` | Task C：Zadoff-Chu 前导/尾 + burst 布局 + deinterleave |
| `board_package/iq_rf_per_frame_recovery.hpp` | Task C/D：逐文件 estimate/apply（含 SRO 方向修正） |
| `board_package/iq_rf_loopback_transfer_fix9r.hpp` | Task D：构帧发射（复用验证过的 PlutoTx） |
| `board_package/iq_rf_fix9r_baseline.hpp` | Task E：46 样本精确基线 fail-closed 加载器 |
| `board_package/iq_rf_loopback_23class_fix9r.hpp` | Task E/F/G：逐文件恢复 runner + 四 token |
| `scripts/analyze_iq_rf_loopback_recovery.py` | Task A：根因分析器（9/9 self-test） |
| `scripts/build_route_f_fix9r_exact_baseline.py` | Task B：46 样本基线生成器（5/5 self-test） |
| `host_tests/test_iq_rf_loopback_23class_fix9r.cpp` | Task H：24 场景 / 71 检查 |
| `scripts/package_iq_rf_loopback_fix9r.py` | Task J：本打包器 |
| `docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R_AUDIT.md` | Task I/J：本审计 |

**修改（4，仅 fix9r 布线）**

| 文件 | 变更 |
|---|---|
| `board_package/gate9_phase.hpp` | 增 `iq-rf-loopback-23class-fix9r` 相位 |
| `board_package/board_gate9_full_chain_rml23.cpp` | `#include` + runner 包装 + dispatch |
| `host_tests/build_host_tests.sh` | 构建 fix9r 测试 |
| `host_tests/run_tests.sh` | 运行 fix9r 测试 |

## 4. fix10 暂停说明（重要）

Route G fix10（双 SDR）已暂停，其磁盘文件全保留。四个布线文件（上表「修改」四项）在磁盘上同时带 fix9r 与 fix10 编辑，`sdr_adapter/pluto_device.hpp` 带 fix10 主机测试 CFO/SRO 注入。打包器在打包时把四个布线文件**重建为仅 fix9r 内容**（移除 fix10 编辑），`pluto_device.hpp` 按不变 fix9 基线携带。因此本包 = fix9 + fix9r，**不含任何 fix10**。fix10 磁盘文件未被触碰。

## 5. 离线验证结果

| 项 | 结果 |
|---|---|
| `test_iq_rf_loopback_23class_fix9r`（fix9r） | **pass=71 fail=0** |
| `test_iq_rf_loopback_23class`（fix9，无回归） | pass=93 fail=0 |
| `test_pluto_external_tx`（fix10 TX） | pass=24 fail=0 |
| `test_iq_external_rf_rx_23class`（fix10，**已暂停，非 fix9r 回归**） | pass=41 fail=12（帧同步/CFO/SRO 未完成） |
| `host_tests/syntax_check.sh` | gate7 / gate9 / gate10 / gate9_rml23 全 OK |
| `analyze_iq_rf_loopback_recovery.py --self-test` | 9/9 |
| `build_route_f_fix9r_exact_baseline.py --self-test` | 5/5 |

`test_iq_external_rf_rx_23class` 的 12 处失败属于暂停的 fix10（未完成的帧同步/CFO/SRO 实现）；fix10 测试不含 `iq_rf_per_frame_recovery.hpp`，与本 fix9r 无关。

## 6. 红线遵守

- 模型及 NPU 二进制、23 类标签与 24→23 合并规则、production RX 默认路径、正式模型预处理、RTL/XDC/位流/Flash：**未改**；
- fix9 已验证的 `iq_digital_loopback.hpp` / `iq_digital_loopback_sync.hpp` / `iq_rf_loopback.hpp` / `iq_rf_loopback_transfer.hpp` / `iq_rf_loopback_23class.hpp`：**只 #include 复用，未改**；
- RF 安全上限 `kSafeTxCeilingDb=-40.0` / `kSafeTxAttenDb=-89.75`：**未改**。

## 7. 板端复测命令（用户上板，我禁碰板）

```bash
# 1. 生成 46 样本精确基线（在 frozen-dir 有 route_d2_rf_manifest.tsv 的机器上）
python3 -I scripts/build_route_f_fix9r_exact_baseline.py \
    --d2-manifest <frozen>/route_d2_rf_manifest.tsv \
    --out route_f_fix9r_exact_baseline.tsv --expect-holdout 46

# 2. 板端 23 类逐文件恢复准确率
./run_gate9_rml23.sh --phase=iq-rf-loopback-23class-fix9r \
    --input-kind=radioml-d2-2p56m --frozen-dir=<frozen> \
    --baseline=route_f_fix9r_exact_baseline.tsv \
    --center=2400000000 --rx-gain=10 --tx-atten=-40 --rf-path=direct-cable
```

预期 token：`ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS`（correct/46 明显高于 fix9 的 5/46）。

## 8. 工件

见 `dist/`：`sdr_rml23_live_iq_rf_loopback_fix9r_patch.tar.gz` + `sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz`（SHA 见打包器输出）。
历史包（fix7/fix8/fix9 及 fix9r 之前所有包）**未被覆盖**。
