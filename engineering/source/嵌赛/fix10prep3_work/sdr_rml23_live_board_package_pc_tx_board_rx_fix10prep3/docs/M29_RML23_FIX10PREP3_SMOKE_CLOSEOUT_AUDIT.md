# M29 RML23 — fix10prep3 双 SDR 两样本板测收口审计（SMOKE CLOSEOUT）

> 状态：**`M29-RML23-FIX10PREP3-CANONICAL-FRAME-SMOKE-PASS`**（最高允许；仅限两样本烟测通过）
> 本档是**板测收口**记录；作者不碰板，板测由用户执行，证据来自用户回传转录。
> 禁止扩大为：`RF_PATH_PROVEN / PROJECT_COMPLETE / FINAL_PASS / FIX10_READY / FINAL_*`。
> 一次两样本烟测**不能**推断全部 23 类或 24 类均通过。

---

## 1. 板测结论（用户回传转录）

真实拓扑：PC TX SDR → 50Ω 同轴 → 板端 RX SDR → 同步/CFO/增益恢复 → 板载 NPU。

用户回报最终结果（逐字，来自用户板测转录）：

```text
FIX10PREP2_TWO_SAMPLE_RESULT scored=2 rf_excluded=0 prediction_agreement=2/2
tx_restore_ok=1 rx_restore_ok=1 negative_control=PASS cfo_finite=1 cfo_in_range=1
training_estimate_valid=2/2

M22_RUNTIME_RESULT result=PASS phase=iq-pc-tx-board-rx-23class-fix10

GATE_RESULT gate=gate9_full_chain_rml23 result=PASS
```

逐样本：

| 样本 | baseline_pred | rf_pred | label_correct |
|---|---|---|---|
| BPSK | 3 | 3 | 1 |
| 4ASK | 1 | 1 | 1 |

用户回报 `R8_RC=0`。

> 注：`FIX10PREP2_TWO_SAMPLE_RESULT` 是 `iq_pc_tx_board_rx_23class_fix10.hpp` 沿自
> fix10prep2 的 token 命名（未在 prep3 改名），其 phase 与 gate 标识正确
> （`iq-pc-tx-board-rx-23class-fix10` / `gate9_full_chain_rml23`），不构成语义问题。

### 板测日志档案状态

板端压缩日志/SHA 尚未回传至 PC。故本档**不伪造本地日志或 SHA**，如实标注：

```text
BOARD_LOG_CONTENT_CONFIRMED_FROM_USER_TRANSCRIPT
BOARD_ARCHIVE_SHA_PENDING_IMPORT
```

收到板端压缩证据并核对 SHA 后，再补记于本档「附录 A」。

## 2. 4ASK 失败 → 通过（参数未改）

- 首次真实双 SDR 三轮：4ASK 固定样本在 NPU 分类前被
  `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` 拒绝，残余值约 `0.109 / 0.111 / 0.150`；
  BPSK 通过；CFO / 负对照 / TX 恢复 / RX 恢复均通过。
- 诊断补丁（见 §4）**只增加证据采集，不改恢复或任何门限**。
- 后续 4ASK 单样本通过；最终未改变任何参数的 BPSK+4ASK 双样本测试通过（§1）。
- **结论**：通过来自既有恢复路径的真实通过，不是「降低 residual/correlation 门限」。

## 3. 最终门禁值（§1 全字段）

```text
scored=2  rf_excluded=0  prediction_agreement=2/2  tx_restore_ok=1  rx_restore_ok=1
negative_control=PASS  cfo_finite=1  cfo_in_range=1  training_estimate_valid=2/2
```

## 4. 诊断补丁判定：非门限放宽（B1 证据）

4ASK 诊断补丁 `dist/fix10prep3_4ask_recovery_diagnostic_patch.tar.gz`
（SHA `95c53008087ac2c9962c550d074f5b4e1a8ed805b711d9da105403b474d0c24f`）共 **8 个文件**：

| 文件 | 变更性质 |
|---|---|
| `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp` | 仅新增诊断字段（`payload_fractional_corr_before/after`、`payload_best_fractional_*`）与两个纯函数；源码注释明确「never participate in recovery or gating」 |
| `board_package/iq_pc_tx_board_rx_23class_fix10.hpp` | 新增 `--dump-failed-rx`（**只在 `!gate_ok` 分支**写 `failed_rx_*.ci16/.json`）+ 诊断字段打日志；不改变 gate 判定 |
| `host_tools/replay_fix10_failed_rx.cpp` | 板外 exact C++ 恢复回放工具（无 Python DSP 复刻） |
| `host_tests/build_host_tests.sh` / `run_tests.sh` | 加 replay 构建/自测条目 |
| `host_tests/test_iq_dual_sdr_23class_fix10.cpp` | 加诊断字段断言 |
| `docs/M29_RML23_FIX10PREP3_4ASK_RECOVERY_DIAGNOSTIC.md` | 审计档 |
| `scripts/package_4ask_diag.sh` | 打包脚本 |

**逐项证明（与 canonical full 包逐字 diff 得出，见 §6）**：

1. **没有修改恢复门限** — `iq_dual_sdr_coarse_cfo_recovery.hpp` 的 diff 只新增诊断字段与
   纯函数；恢复主流程新增注释明示「final rec.training_corr must still clear
   cfg.min_corr == 0.9」，residual/clip/CFO/SRO 阈值常量零改动。
2. **没有修改模型、权重、预处理** — `model_rml23/`、`model_12class/`、
   `deployment_golden/`、`contracts/` 均不在补丁内，且与 canonical full 逐字节一致。
3. **没有修改 baseline prediction** — `iq_rf_fix9r_baseline.hpp`、`iq_clean_baseline.hpp`、
   `baselines/` 均不在补丁内，逐字节一致。
4. **没有修改 24→23 合并** — `rml23_merged.hpp`、`contracts/rml23_merged_contract.py` 均不在
   补丁内，逐字节一致。
5. **没有通过放宽 residual/correlation gate 获得 PASS** — 最终门禁
   `prediction_agreement=2/2` 且 `training_estimate_valid=2/2`；diff 证明无门限常量改动。
6. **诊断字段不参与恢复结果选择** — 新增 5 个 `payload_best_*` 字段只在日志/JSON 报告，
   不进入 `rec.valid`、`gate_ok`、`rf_verdict` 或对齐选择；`--dump-failed-rx` 仅在 gate
   已失败后落盘证据。

## 5. 红线核验（B4，全树递归 SHA diff）

以 `sdr_rml23_fix10prep3_canonical_frame_boardtest_full.tar.gz`（SHA
`659c48fda6c5190e518e1b188faaa88efe04ffce63ada93fddea271b2c1804da`，656 文件）为冻结板测源，
对当前工作树（785 文件）做全树递归 SHA 逐文件比对：

**唯一不同的源码文件 = 诊断补丁的 6 个源码文件**（§4 表中除 2 个纯新增外的全部）：

- `board_package/iq_dual_sdr_coarse_cfo_recovery.hpp`（`c466b7c6…` → `447f56f7…`）
- `board_package/iq_pc_tx_board_rx_23class_fix10.hpp`（`f185ce2f…` → `2504faa4…`）
- `host_tests/build_host_tests.sh` / `run_tests.sh` / `test_iq_dual_sdr_23class_fix10.cpp`
- 根 `SHA256SUMS.txt`（packager 自动重生成）

其余差异仅为：`dist/`（打包产物）、`docs/…4ASK_RECOVERY_DIAGNOSTIC.md`、
`host_tools/replay_fix10_failed_rx.cpp`、`scripts/package_4ask_diag.sh`（诊断补丁纯新增）、
`host_tests/bin/`（构建产物）、`results/`（x86 探针产物）、`__pycache__`/`.build_burst_cache`
（缓存）。**无任何文件从 canonical full 缺失。**

**冻结资产逐字节一致（未出现在 diff 中，故零改动）**：

- 模型及权重：`model_rml23/`、`model_12class/` ✅
- 标签次序 / 24→23 合并合同：`contracts/`、`board_package/rml23_merged.hpp` ✅
- 红线头：`iq_rf_training_frame.hpp`、`iq_rf_sync_recovery.hpp`、
  `iq_digital_loopback.hpp`、`iq_pc_tx_board_rx_transfer_fix10.hpp`、
  `iq_rf_fix9r_baseline.hpp`、`iq_clean_baseline.hpp` ✅
- canonical frame 三组件：`contracts/fix10_canonical_frame_v1/{preamble,payload_training,tail}.ci16`
  （前导 `d4b4bb3a…`、训练块 `f06e9b3d…`、尾 `ccddabe1…`）✅

## 6. 回归验证（B3）

WSL（Ubuntu，g++ 15.2.0）执行 `bash host_tests/build_host_tests.sh` → `bash host_tests/run_tests.sh`：

```text
BUILD_RC=0
run_tests.sh: ALL HOST TESTS PASSED
RUN_RC=0
```

覆盖项（全部 PASS，无 FAIL）：
- canonical 训练帧：`test_fix10_canonical_frame` ✅
- PC TX 协议（§4.1 IIO 单元后缀解析 / §4.2 PREPARE 只许缓存命中 / §4.3 内容寻址缓存）：
  `test_pc_tx_protocol_fix10`（Python 三组：协议状态机 38、IIO 属性解析 15、burst cache 10）✅
- 双 SDR 恢复 + 分数定时对齐 + failed-RX dump 字段断言：`test_iq_dual_sdr_23class_fix10` ✅
- 精确 C++ 回放自测：`replay_fix10_failed_rx self-test: PASS` ✅
- PC TX/板 RX 闭环与 provenance：`test_pc_tx_board_rx_fix10` / `test_pc_tx_provenance_fix10` ✅
- 纯净 IQ 23 类：`test_clean_iq_23class_fix10` ✅
- 全套 12 类/23 类链（`test_rf_waveform_12class` 66、`test_band_scan` 31、`test_rml23_merged`、
  23 类各 loopback/gate 测试）均 PASS ✅

> 注：输出中的 `[DFB] FAIL:` 行是 `test_display_integrity`/`test_display_diagnostic` 的
> **负对照断言**（帧缓冲越界/未初始化操作必须失败），属预期失败注入，对应测试仍 PASS，
> 非回归失败。

## 7. 确定性重新打包（B5）

以冻结板测源 canonical full（SHA `659c48fd…`，656 文件）为基线，产出 post-smoke 新包
（**不覆盖旧包**；canonical frame 与 4ask 诊断两套旧包原样保留）：

| 包 | 内容文件 | SHA256 |
|---|---|---|
| `dist/sdr_rml23_fix10prep3_smoke_closeout_boardtest_full.tar.gz` | 660（+根 `SHA256SUMS.txt`） | `26bb124128a379c820b4dc137787eae6afae519eaa0db454bf7922742529becf` |
| `dist/sdr_rml23_fix10prep3_smoke_closeout_patch.tar.gz` | 10 | `ba2cb42696d4626ceede4b7917ac16344d02fd76f4c658369cdf143073ab5bce` |

sidecar：`…_boardtest_full_SHA256SUMS.txt` / `…_patch_SHA256SUMS.txt`（`HASH *relpath` 约定）。

patch = canonical-full → smoke-closeout full 的**完整增量**（8 文件 4ASK 诊断补丁 +
本审计档 + 打包脚本 `scripts/package_fix10prep3_smoke_closeout.py`）。

打包器 `scripts/package_fix10prep3_smoke_closeout.py` 的 fail-closed 审计**全过**：
- red-line 六头、protected 目录、canonical 三组件（preamble/training/tail + 头）逐字节一致 ✅
- 依赖闭包 + complete-delta + patch 自含（patch 单独 overlay 到 canonical-full 可解析全部 include）✅
- 旧 fix10（external_rf / pluto_external）零残留 ✅
- **literal overlay 验证**：canonical-full 覆盖 patch 后与 smoke-closeout full 逐字节一致 ✅
- **确定性**：每包两次构建字节一致（uid/gid 0、mtime 0、排序条目、gzip -9 mtime 0）✅

包外独立解包验证（`sha256sum -c`，非打包器自检）：
- full 660 文件全 `OK`；patch 10 文件全 `OK` ✅
- 无 `.build_burst_cache` / `__pycache__` / `host_tests/bin` / `results` / 构建日志入包 ✅
- literal overlay `diff -r`：除根 `SHA256SUMS.txt`（派生）与 patch 自身 `SMOKE_CLOSEOUT_PATCH_SHA256SUMS.txt`
  （仅存在于 patch 包内）外，逐字节一致 ✅

## 8. 状态推进

两样本烟测由用户真实上板通过，红线与诊断补丁判定全部无门限放宽，冻结资产逐字节一致。
状态由 `M29-RML23-FIX10PREP3-CANONICAL-FRAME-READY-FOR-BOARD-TEST` 推进为
**`M29-RML23-FIX10PREP3-CANONICAL-FRAME-SMOKE-PASS`**（最高允许，仅两样本烟测）。

**Phase B 收口已全部完成**：B1（板测版本确认 + 诊断补丁非门限放宽）、B2（本档）、
B3（回归 `BUILD_RC=0 / ALL HOST TESTS PASSED / RUN_RC=0`）、B4（红线全树递归 SHA diff）、
B5（确定性重打包 + 独立解包 + literal overlay 验证）。

下一动作（按任务书）：Phase B 已完全通过，以 §7 post-smoke full 包为新基线，进入
fix10class24-dualsdr1 **Phase C** 恢复 24 类双 SDR 集成（共享恢复与 TX 控制实现必须来自
本 post-smoke 包的实际板测版本）。

---

## 附录 A（板端证据归档，待回传）

```text
BOARD_LOG_CONTENT_CONFIRMED_FROM_USER_TRANSCRIPT
BOARD_ARCHIVE_SHA_PENDING_IMPORT
```

收到板端压缩日志/SHA 后补记此处，不伪造。
