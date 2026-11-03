# fix10class24-dualsdr1 — Phase A 暂停快照

**暂停状态令牌（最高允许，不再推进 24 类开发）：**

```
M29-RML24-FIX10CLASS24-DUALSDR-INTEGRATION-PAUSED-FOR-FIX10PREP3-CLOSEOUT
```

**暂停原因**：fix10prep3 双 SDR 两样本（BPSK+4ASK）已由用户真实上板通过
（`FIX10PREP2_TWO_SAMPLE_RESULT scored=2 rf_excluded=0 prediction_agreement=2/2
tx_restore_ok=1 rx_restore_ok=1 negative_control=PASS cfo_finite=1 cfo_in_range=1
training_estimate_valid=2/2`；`M22_RUNTIME_RESULT result=PASS
phase=iq-pc-tx-board-rx-23class-fix10`；`GATE_RESULT result=PASS`；用户 `R8_RC=0`）。
须先完成 fix10prep3 板测收口（Phase B），再以实际过板源码为新基线恢复 24 类（Phase C）。

---

## 1. 24 类工作树快照

- 树根：`F:\嵌赛\fix10class24_dualsdr1_work\sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24`
- 文件总数：**673**（无 `dist/`，无 `__pycache__`，无 `.build_burst_cache`）
- SHA 清单：`F:\嵌赛\fix10class24_dualsdr1_work\fix10class24_dualsdr1_PAUSE_manifest.txt`
  （673 行 `SHA256  relpath`，按路径排序，UTF-8，生成于 2026-10-17）

## 2. 相对 fix10prep3 基线（`F:\嵌赛\fix10prep3_work\...fix10prep3`）的差异

基线 = 用户已板测通过的 fix10prep3 工作树（含 canonical 训练帧 + fractional timing
hotfix + PC burst cache + TX 控制状态修复 + 4ASK 诊断补丁 `--dump-failed-rx` / payload
fractional correlation 字段 / exact C++ replay 工具）。

### 2.1 NEW（24 类树新增，17 文件）——24 类增量资产

- `baselines/clean24_smoke_raw24_bf16_baseline.tsv`
- `baselines/clean24_smoke_raw24_bf16_predictions.tsv`
- `baselines/clean24_smoke_raw24_bf16_report.json`
- `baselines/clean24_smoke_raw24_bf16_report.md`
- `board_package/iq_clean_iq_24class_bf16_fix10.hpp`       （Phase 3 头，已写，未编译验证）
- `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp` （Phase 4 头，已写，**未编译验证**）
- `board_package/rml24_bf16_baseline.hpp`                 （Phase 2，7 列 raw24 baseline）
- `board_package/rml24_raw.hpp`                           （Phase 2，raw24_predict，无 merge）
- `contracts/rml24_raw_contract.py`                       （Phase 2 合同）
- `model_rml24_bf16/compiler_metadata.json`
- `model_rml24_bf16/model_SHA256SUMS.txt`
- `model_rml24_bf16/network_mapping_report.json`
- `model_rml24_bf16/network_mapping_report.md`
- `model_rml24_bf16/rml24_adamrv11_bf16.json`
- `model_rml24_bf16/rml24_adamrv11_bf16.raw`
- `scripts/audit_rml24_bf16_network.py`
- `scripts/predict_rml24_bf16_baseline.py`

### 2.2 MODIFIED（SHA 与基线不同，10 文件）

| 文件 | 性质 |
|---|---|
| `board_package/board_gate9_full_chain_rml23.cpp` | 24 类接线（include、emit_frame_rml24、clean 包装、dispatch） |
| `board_package/chain_common.hpp` | 新增 `fill_result_rml24` / `contract_24` / `kRml24ResultVersion` |
| `board_package/gate9_phase.hpp` | 新增 2 个 24 类 phase |
| `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp` | ⚠ **非 24 类改动；是相对板测基线的旧版本**（缺 4ASK 诊断 fractional 字段） |
| `board_package/iq_pc_tx_board_rx_23class_fix10.hpp` | ⚠ **同上，旧版本**（缺 `--dump-failed-rx`、payload fractional correlation 字段） |
| `host_tests/build_host_tests.sh` | 旧版（缺 replay_fix10_failed_rx 等测试条目） |
| `host_tests/run_tests.sh` | 旧版 |
| `host_tests/test_iq_dual_sdr_23class_fix10.cpp` | 旧版（缺诊断字段断言） |
| `sdr_adapter/ui_report.hpp` | 新增 `result_frame_rml24_line`（24 类 schema） |
| `SHA256SUMS.txt` | 树根校验清单随新增文件变化 |

### 2.3 DELETED/MISSING（基线有、24 类树无，129 文件）

主要为：`dist/`（canonical frame 与 4ask 诊断两套包）、`docs/M29_RML23_FIX10PREP3_4ASK_RECOVERY_DIAGNOSTIC.md`、
`host_tools/replay_fix10_failed_rx.cpp`、`scripts/package_4ask_diag.sh`、`results/`（x86 分段探针）、
`host_tests/bin/*`（既有编译产物）、`__pycache__/*`、`.build_burst_cache/*`。
这些在 Phase C 重建基线时须从板测 fix10prep3 完整包补齐，**不得让旧恢复代码重新进入**。

## 3. 已知未完成项（如实记录）

1. `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`：**已写入但从未编译验证**。
2. 主程序 `board_gate9_full_chain_rml23.cpp:3572` 已引用 `run_iq_pc_tx_board_rx_24class_bf16_fix10(...)`，
   但该包装函数**尚未定义**（23 类包装在 3199，clean 24 类包装在 3152）。**当前树不可编译**。
3. 没有最终 24 类双 SDR runner（header 存在但缺包装 + 缺编译验证 + 缺 host 测试）。
4. 没有完整板测脚本 / 板端命令（§16 Gate A/B/C1/C2 用户命令未产出）。
5. 没有 `dist/`（无 patch / full 包，无 SHA sidecar）。
6. 没有最终审计文档 `docs/M29_RML24_FIX10CLASS24_BF16_DUALSDR_AUDIT.md` 和确定性板测包。
7. `scripts/build_rml24_prewarm_plan.py`（24 样本预热的 PC 端计划脚本）**未写**。
8. §11 的 6 个 host 测试全部**未写**：`test_rml24_bf16_network_audit.py`、
   `test_rml24_raw_contract.cpp`、`test_rml24_bf16_baseline.cpp`、
   `test_clean_iq_24class_bf16_fix10.cpp`、`test_pc_tx_board_rx_24class_bf16_fix10.cpp`、
   `test_rml24_prewarm_plan.py`。
9. **恢复/TX 共享实现未同步到实际板测通过的最终 fix10prep3**：`iq_dual_sdr_coarse_cfo_recovery.hpp`、
   `iq_pc_tx_board_rx_23class_fix10.hpp`、`host_tests/*` 仍是诊断补丁前的旧版本
   （缺 4ASK `--dump-failed-rx` / payload fractional correlation / replay 工具）。
   已确认 `pc_tx_sdr_fix10.py` / `fix10_burst_cache.py` / `fix10_iio_attr.py` 与板测基线**字节一致**（已同步）。

## 4. Phase C 恢复时的不变约束（备忘）

- 从 Phase B 的 post-smoke full 包建立新基线，逐项审计并迁移 24 类增量，**不整树覆盖**。
- 对 `iq_fix10_canonical_frame.hpp` / `iq_fix10_canonical_frame_data.hpp` /
  `iq_dual_sdr_coarse_cfo_recovery.hpp` / `iq_pc_tx_board_rx_23class_fix10.hpp` /
  `pc_tx_sdr_fix10.py` / `fix10_burst_cache.py` 做 SHA 对比，共享恢复与 TX 控制实现**必须来自
  Phase B 实际板测版本**。
- 补 `iq_pc_tx_board_rx_24class_bf16_fix10.hpp` + 包装 + raw24 判决 + 24 样本 baseline 精确键匹配
  + PC 端 24 样本预热 + 板端逐样本恢复/推理/判决 + WC/SC 保持两个独立 raw24 类 + 同时输出
  raw24 与 24→23 合并部署结果 + fail-closed + 失败样本保存原始 RX CI16 与元数据。
- 最高只能写 `M29-RML24-FIX10CLASS24-DUALSDR-READY-FOR-BOARD-TEST`；真实 24 类板测前禁写 SMOKE-PASS。
