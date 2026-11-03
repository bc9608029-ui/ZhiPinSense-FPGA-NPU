# M29 RML24 fix10class24-tx-rms-sweep1 — TX 数字幅度工作点扫描审计

任务：对比 `rf-tx-target-rms = 2048/1536/1024`，判断降低 TX 数字 IQ 幅度能否减少双 SDR 模拟链
非线性、提升 24 类准确率。**仅用当前 BF16 模型**（不组合 TF32；组合等两任务各自完成后再定）。
最高允许状态 `M29-RML24-FIX10CLASS24-TX-RMS-SWEEP1-READY-FOR-BOARD-TEST`。
禁写 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / NEW_PRODUCTION_TARGET_RMS。
RMS 基线 2048；1536（-25%）/1024（-50%）；TX 模拟衰减锁 -40 dB；禁 >2048、禁抬发射功率。

参考值：单 SDR BF16 RMS2048 = 23/24；双 SDR BF16 强制 = 18/24。

## Phase A — 参数入口审计（✅ 入口完整，无需改 runner）

基线树 `F:\嵌赛\fix10class24_scalarwl_4way_work\sdr_rml24_fix10class24_scalarwl_4way` 中两个 runner
**均已完整接线** `--rf-tx-target-rms`，符合「入口完整只加编排、不改 runner」。

### 单 SDR runner `board_package/iq_rf_loopback_24class_bf16_fix10.hpp`

| 行 | 作用 |
|---|---|
| 410 | `target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0)` 解析 |
| 745-746 | `fix10canonical::buildTxBurstFromFrozen(fz.path, fz.complex_count, fz.sha256, target_rms)` |
| 836 | `rec_cfg.payload_tx_target_rms = target_rms` |
| 838 | `recover_payload_with_coarse_cfo(rx, rec_cfg, expected.tx_scale)` |

### 双 SDR runner `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`

| 行 | 作用 |
|---|---|
| 363 | `target_rms = board::opt_d(argc, argv, "--rf-tx-target-rms", 2048.0)` 解析 |
| 549 | `sess.target_rms = target_rms`（RMS 传 PC TX 会话） |
| 702-703 | `fix10canonical::buildTxBurstFromFrozen(fz.path, fz.complex_count, fz.sha256, target_rms)` |
| 842 | `rec_cfg.payload_tx_target_rms = target_rms` |
| 844 | `recover_payload_with_coarse_cfo(rx, rec_cfg, expected.tx_scale)` |

### tx_scale / burst_sha 语义（`iq_pc_tx_board_rx_transfer_fix10.hpp`）

- `TxBurstBuild{payload_sha_pre, payload_sha_post, burst_sha, target_rms, tx_scale, ...}`
- `build_tx_burst_from_frozen`：`r.tx_scale = target_rms / native_rms`（实际缩放因子，来自 target_rms）；
  `payload_sha_pre` = 冻结 CI16 SHA（**不随 RMS 变**）；`payload_sha_post`/`burst_sha` = 缩放后字节 SHA
  （**随 RMS 变**）。
- `buildTxBurstFromFrozen` 复用上述缩放/校验后用内嵌 canonical 组件重建 burst 并重算 `burst_sha`。

### PC/板 RMS 一致性已 fail-closed（双 SDR）

双 SDR 的 PREPARE/READY 握手（`iq_pc_tx_board_rx_transfer_fix10.hpp` 371-378 / 432-440）逐字段比对
`payload_sha_pre`/`payload_sha_post`/`burst_sha`/`tx_scale`，PC 与板端任一 `payload_sha_post` 或
`tx_scale` 不一致即 fail-closed，**不产生分类**。单 SDR 本地 TX+RX 共用同一 `target_rms`，无 PC 侧，
无跨端不一致可能。→ 任务「PC 与板 RMS/tx_scale 不一致 → fail-closed、不分类」已由既有握手满足。

### 记录字段的结论

- `requested_target_rms`：runner 启动横幅已打印 `rf_tx_target_rms=%.3f`（单 559 / 双 502），编排脚本
  亦从自身传入的 `--target-rms` 记录，可交叉核对。
- `actual_tx_scale` / `burst_sha`：runner **不逐样本打印**（单 SDR 完全无；双 SDR 只在 PREPARE/READY
  协议 JSON 中）。二者是 (冻结 CI16, target_rms) 的**确定性函数**。→ 编排/审计层通过**离线确定性
  canonical 预算工具**记录预期 tx_scale/burst_sha（additive host 工具，非 runner 修改），与双 SDR 握手
  的 fail-closed 值一致。

## Phase B / C / host 测试 / Phase D（✅ 完成）

- **Phase B** `scripts/run_fix10class24_tx_rms_sweep1.sh`：单/双 SDR 编排（`--link=single|dual`/
  `--rx-uri`/`--tx-control`/`--mode=short2|full24`/`--target-rms=2048|1536|1024`/`--out-root`/`--run`）。
  Fail-closed：RMS 三选一、`--tx-atten=-40` 固定（无更高衰减语句）、输出目录拒绝覆盖、
  single 禁 `--tx-control`、dual 必须有 `--tx-control`、PC 与板同 RMS（`--rf-tx-target-rms` 两处同值）、
  日志记录 RMS/model SHA/link/out_dir。目录 `single_bf16_rms2048_run1/` 等。**不改两个 runner**。
- **Phase C** `scripts/audit_fix10class24_tx_rms_sweep1.py`：prefix 无关、字段辨识的 fail-closed 判读器
  （单 `FIX10CLASS24_BF16_SINGLESDR_*` / 双 `FIX10CLASS24_BF16_*` 同场解析），per-config 指标
  （scored/rf_excluded/coverage/gated/e2e/forced raw24/prediction agreement/label correct/finite/
  repeat deterministic/residual/corr/CFO/clip/WL 比例/capture attempts）+ 每样本 + 每类跨 RMS 变化 +
  残差汇总；输出 `results/tx_rms_sweep1/{inventory,per_sample_results,rms_summary,
  class_transitions,residual_summary}.tsv + summary.json`。门拒样本仅在 `--icraft-run` + `--dump-failed-rx`
  留档时用冻结 BF16 在 Host 强制分类，标 `DIAGNOSTIC_GATE_BYPASS=1`（`HYBRID_BOARD_GATED_PLUS_HOST_FORCED`，
  非板端 NPU、非门禁放行）；无 icraft-run 时 `forced_raw24_accuracy=PENDING`。自测 `SELF_TEST_OK`。
- **host 测试** `host_tests/test_fix10class24_tx_rms_sweep1.py`：14/0 PASS，加载同一判读器 + 静态检查同一
  编排脚本（RMS 三选一、TX -40、禁词不出现在任何 echo/heredoc 输出、single/dual 接线、拒覆盖、
  PC 同 RMS、单/双 marker 解析、门拒强制标 DIAGNOSTIC_GATE_BYPASS、config.meta 解析、缺 meta/bad 名 fail-closed、
  全套接线）。已接入 `host_tests/run_tests.sh`。
- **Phase D** `docs/M29_RML24_FIX10CLASS24_TX_RMS_SWEEP1_BOARDTEST.md`：板测矩阵
  （D1 单 SDR 3 RMS×24 类；D2 双 SDR 3 RMS；D3 最优 RMS 复测 ×2）+ 8 条候选判定 + 离线判读命令。

## 待板端执行（测量，非 PASS）

板测命令见 `docs/M29_RML24_FIX10CLASS24_TX_RMS_SWEEP1_BOARDTEST.md`。禁止本任务在任何
RMS 档位写出 RF_PASS / SMOKE_PASS / PROJECT_COMPLETE / FINAL_* / NEW_PRODUCTION_TARGET_RMS。

## 红线（本阶段未触碰）

BF16 模型 json `28272abc…`/raw `c1781aec…`、24 类标签序、0.100 门、恢复器、canonical 三组件、
TX -40 上限、分类窗口与预处理链。本任务只新增编排/审计/测试/文档，不改两个 runner 的现有行为。
