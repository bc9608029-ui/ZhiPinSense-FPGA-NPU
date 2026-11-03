# M29 RML24 FIX10CLASS24 DUALSDR-RXRECOVERY1 — 板端测试手册

- 任务：fix10class24-dualsdr-rxrecovery1（广线性 IQ 补偿 + 有界 payload-training 重捕获）板测打包收口
- 最高允许状态：**`M29-RML24-FIX10CLASS24-DUALSDR-RXRECOVERY1-READY-FOR-BOARD-TEST`**
- 禁写：`RF_PASS / SMOKE_PASS / STANDALONE_PASS / 24CLASS_PASS / PROJECT_COMPLETE / FINAL_*`；**API 不碰板**
- 本手册由用户在板端/PC 端执行；本文档内所有命令均为真实物理双 SDR 闭环，非合成验证。

---

## 1. 交付物与基线

| 项 | 文件名 | 说明 |
|---|---|---|
| FULL 板测包 | `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz` | 单顶层目录 `sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2`，含全部文件 |
| FULL 内容清单 | `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full_SHA256SUMS.txt` | `HASH *relpath` |
| PATCH 包 | `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_patch.tar.gz` | 平铺（flat），只含相对基线的变更文件 |
| PATCH 内容清单 | `dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_patch_SHA256SUMS.txt` | `HASH *relpath` |
| **基线（base）** | `sdr_rml24_fix10class24_bf16_dualsdr2_rxfrontend_full.tar.gz` | SHA `070b932259a458a18f2ce5062a975d890689ed5291f0a84ed3b900d764961f13` |

- 各包自身的 SHA256 见交付消息（打包器输出 `sha256=...`），不与内容清单混用。
- PATCH 覆盖到基线上 == FULL（打包器已做字节级 overlay 校验）。板上若已有 rxfrontend full 目录，
  可只传 PATCH 覆盖；若为全新目录，直接传 FULL 解包。

### 本交付变更（相对 rxfrontend full）

- `board_package/iq_rf_sync_recovery.hpp`（加性修改）：广线性拟合/验证 + `should_retry_payload_training_capture`。
- `board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp`（加性修改）：有界重捕获循环 + 广线性诊断打印行。
- `host_tests/test_dual_sdr_wide_linear.cpp`（新增，25 项）。
- `docs/M29_RML24_FIX10CLASS24_DUALSDR_RXRECOVERY1_AUDIT.md` + 本手册。
- `scripts/package_fix10class24_bf16_dualsdr2_rxrecovery1.py`（本交付打包器）。
- 删除文件：无（相对基线的删除集合为空，打包器 fail-closed 审计已核）。

### 红线（本交付未触碰，打包器已逐字节核验）

BF16 模型 JSON `28272abc…` / RAW `c1781aec…`、24 类标签序、`baselines/`、`clean24_smoke/`、
`contracts/`（含 canonical 3 CI16 + manifest）、13 个红线头（除 `iq_rf_sync_recovery.hpp` 外）、
`0.10` 残差门限、training corr/CFO/SRO/clip 既有有效性门、TX −40 dB 安全上限、24→23 合同、
FPGA 位流、NPU 模型、训练/量化资产。均未改。

---

## 2. 板端部署

把 FULL 包上传到板端（`scp` 或 `rsync`），解包到独立目录：

```bash
TS=$(date +%s)
ROOT="/root/fix10class24_rxrecovery1_${TS}"
mkdir -p "$ROOT"
cd "$ROOT"

# 1) 身份校验：上传前/后 tar.gz 的 SHA 必须一致（swap check）
sha256sum sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz
# 期望 = 交付消息中的 full SHA（不写死在本手册内，避免自引用）

# 2) 解包
tar -xzf sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz
cd sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2

# 3) 内容校验（fail-closed：任何 mismatch 都停止）
sha256sum -c SHA256SUMS.txt
# 期望：N 行全部 OK，无一 FAILED

# 4) 确认关键资产在树内且 SHA 正确
sha256sum model_rml24_bf16/rml24_adamrv11_bf16.json \
         model_rml24_bf16/rml24_adamrv11_bf16.raw
# json = 28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42
# raw  = c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151
```

> 若板端已部署 rxfrontend full（SHA `070b9322…` 已核验）且目录干净，可只传 PATCH：
> 先把 PATCH 平铺覆盖到该目录，再 `sha256sum -c SHA256SUMS.txt`（FULL 清单）核验 == FULL。

---

## 3. 板端构建（Gate 9R / 24 类 BF16）

```bash
cd sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2

LIBIIO_ROOT=/opt/sdr/libiio-0.26 \
ICRAFT_CMAKE_DIR=/usr/cmake \
bash board_package/build_npu_on_board.sh --gate9-rml23
```

构建结果检查：

- 成功打印：`NPU_BUILD_RESULT gate=9R result=PASS binary=.../bin/board_gate9_full_chain_rml23`
- 任何失败返回非零并打印 `NPU_BUILD_RESULT gate=9R result=FAIL`，且删除旧 `bin/` 内同名二进制（fail-closed，绝不留下陈旧可执行文件冒充本轮成功）。
- 可执行文件身份校验：

```bash
sha256sum bin/board_gate9_full_chain_rml23
# 记录该 SHA；同一包内容在同一板上重复构建应得到稳定二进制（用于复跑一致性佐证）
```

> 需要 libiio 0.26 持久化前缀 `/opt/sdr/libiio-0.26`（`sdr_libiio_0_26_persistent_recovery.tar.gz` 已装）。
> 若板端 iCraft cmake 前缀非 `/usr/cmake`，按实际改 `ICRAFT_CMAKE_DIR`。

---

## 4. PC TX 命令（PowerShell，每次板端运行前启动）

先查本次 PC Pluto URI：`iio_info.exe -s`，再设 `$TxUri`。

### 4.1 两样本（BPSK source_index=1500 + 4ASK source_index=500）

```powershell
$Root = 'F:\嵌赛\fix10class24_dualsdr_rxrecovery1_work\sdr_rml24_fix10class24_dualsdr_rxrecovery1'
$TxUri = 'usb:1.11.5'  # 每次插拔后重新查询，按实际输出修改

Set-Location $Root

& 'D:\radioconda\python.exe' -I 'host_tools\pc_tx_sdr_fix10.py' `
  --listen '0.0.0.0:39010' `
  --tx-uri $TxUri `
  --frozen-dir 'clean24_smoke' `
  --input-kind 'radioml-d2-2p56m' `
  --center 2400000000 `
  --sample-rate 2560000 `
  --tx-bw 18000000 `
  --tx-atten -40 `
  --rf-path 'direct-cable' `
  --rf-tx-target-rms 2048 `
  --prewarm-source-index 1500 `
  --prewarm-source-index 500
```

必须看到两条 `PREWARM` 与 `listening on 0.0.0.0:39010`，且 TX 衰减严格为 `-40.00`（**绝不写 `-35/-30`**，生产程序有硬门禁 `--tx-atten ... exceeds the -40 dB safety ceiling; refusing`）。

### 4.2 全 24 类（Test C/D：预热全部 24 个 source_index）

只把 `--prewarm-source-index` 换成全部 24 个（顺序无关，逐条）：

```powershell
  --prewarm-source-index 0     --prewarm-source-index 500   --prewarm-source-index 1000 `
  --prewarm-source-index 1500  --prewarm-source-index 2000  --prewarm-source-index 2500 `
  --prewarm-source-index 3000  --prewarm-source-index 3500  --prewarm-source-index 4000 `
  --prewarm-source-index 4500  --prewarm-source-index 5000  --prewarm-source-index 5500 `
  --prewarm-source-index 6000  --prewarm-source-index 6500  --prewarm-source-index 7000 `
  --prewarm-source-index 7500  --prewarm-source-index 8000  --prewarm-source-index 8500 `
  --prewarm-source-index 9000  --prewarm-source-index 9500  --prewarm-source-index 10000 `
  --prewarm-source-index 10500 --prewarm-source-index 11000 --prewarm-source-index 11500
```

> 不预热全部 24 个 source_index 会正确触发 `BURST_CACHE_MISS`（fail-closed），故全 24 类必须用 4.2 命令。
> source_index ↔ 类名对应见 `clean24_smoke/selected_samples.tsv`（0=OOK … 11500=OQPSK，AM-SSB-WC=8500 / AM-SSB-SC=9000 映射到 deployed23 的 AM-SSB）。

---

## 5. 板端测试命令（四档）

公共前缀（`$ROOT` = §2 的解包目录，`$TX_IP` = PC 的局域网 IP）：

```bash
cd "$ROOT"
bash scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --tx-control=tcp://<TX_IP>:39010 \
  --rx-uri=usb:1.3.5 \
  --input-kind=radioml-d2-2p56m \
  --center=2400000000 \
  --rx-gain=30 \
  --rf-tx-target-rms=2048 \
  --rf-path=direct-cable \
  --dump-failed-rx \
  --dump-recovery-diagnostics \
  --out-dir="<OUT_DIR>"
```

- `--rx-uri` 为板端 RX SDR 的实际 URI，按 `iio_info -s` 改。
- `--rx-bw` 本交付不强制（省略 = 默认 0 = 未指定，保持与 rxfrontend 之前基线一致）；若要复跑 rxfrontend 的 RX 带宽扫描，再显式加 `--rx-bw=...`。
- `--out-dir` 每轮**独立、不可覆盖**（Test B/D 的复跑轮各用新目录）。

### Test A — 两样本短跑（BPSK + 4ASK 各 1 样本）

```bash
OUT="/tmp/rml24_rxrecovery1_A_$(date +%s)"
LOG="/root/rml24_rxrecovery1_A.log"
# 在 §5 公共前缀基础上追加：
  --diagnostic-classes=BPSK,4ASK \
  --diagnostic-per-class=1 \
  --out-dir="$OUT"  2>&1 | tee "$LOG"
echo "A_RC=${PIPESTATUS[0]}"
```

### Test B — 两样本 3 轮稳定性

Test A 通过后，对 §5 公共前缀 + `--diagnostic-classes=BPSK,4ASK --diagnostic-per-class=1` 连续跑 3 轮，
**每轮**：重启一次 §4.1 PC TX、换独立 `--out-dir`（如 `..._B1_ / _B2_ / _B3_`）与独立日志。逐轮必须满足 §7 全部判据。

### Test C — 24 类各 1 样本（单轮）

PC TX 用 §4.2（预热全部 24）。板端**去掉** `--diagnostic-classes` / `--diagnostic-per-class`
（即 holdout = 全部 24 个 raw24 样本，`full_run=1`）：

```bash
OUT="/tmp/rml24_rxrecovery1_C_$(date +%s)"
LOG="/root/rml24_rxrecovery1_C.log"
# §5 公共前缀（不带 --diagnostic-classes）：
  --out-dir="$OUT"  2>&1 | tee "$LOG"
echo "C_RC=${PIPESTATUS[0]}"
```

### Test D — 全 24 类额外 2 轮稳定性

Test C 通过后，重复 Test C 命令 2 轮，每轮：重启 §4.2 PC TX、独立 `--out-dir`（`..._D1_ / _D2_`）与日志，
逐轮满足 §7 全 24 类判据。

---

## 6. 期望日志（grep token 清单）

每次板端运行必须**打印且可 grep**以下 token（对应需求 9）：

```bash
grep -E \
'FIX10CLASS24_BF16_WIDE_LINEAR|FIX10CLASS24_BF16_CAPTURE_RETRY|FIX10CLASS24_BF16_CAPTURE_ATTEMPTS|FIX10CLASS24_BF16_RECOVERY|FIX10CLASS24_BF16_CLASSIFY|FIX10CLASS24_BF16_TWO_SAMPLE_RESULT|FIX10CLASS24_BF16_MEASUREMENT_RESULT|M22_RUNTIME_RESULT|GATE_RESULT|ERROR|FAIL' \
"$LOG" | tail -n 400
```

逐 token 含义：

| token | 字段 | 说明 |
|---|---|---|
| `FIX10CLASS24_BF16_WIDE_LINEAR` | `enabled` / `scalar_validation_residual` / `validation_residual` / `improvement_ratio` / `image_ratio` / `reason` | 广线性**是否启用**、标量验证残差、广线性验证残差、改善比、镜像比、拒绝原因（`ENABLED` / `IMAGE_TOO_SMALL` / `IMAGE_TOO_LARGE` / `NO_IMPROVEMENT` / `NON_FINITE` / `REJECTED_OTHER`） |
| `FIX10CLASS24_BF16_CAPTURE_RETRY` | `file` / `attempts` / `reason` | 仅 `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` 且 attempts∈{1,2} 时出现 |
| `FIX10CLASS24_BF16_CAPTURE_ATTEMPTS` | `attempts` / `retries` / `final_failure` / `final_valid` | 该样本**捕获尝试次数**、重试次数、最终失败类型、最终有效性；`attempts` 必须 ≤ 3 |
| `FIX10CLASS24_BF16_RECOVERY` | `valid` / `failure` / `timing` / `gain_mag` / `fine_cfo_hz` / `sro_ppm` / `training_corr` / `training_residual` / `payload_training_corr` / `payload_training_residual` / `fidelity` / `rx_clipped` | 恢复字段；关注 `payload_training_residual <= 0.10` 且 `rx_clipped=0` |
| `FIX10CLASS24_BF16_CLASSIFY` | `baseline_pred` / `rf_pred` / `prediction_agreement` / `label_correct` / `repeat_deterministic` / `finite` | 逐样本分类对照（不用于触发重试，仅记录） |
| `FIX10CLASS24_BF16_TWO_SAMPLE_RESULT` | 见 §7 | 两样本汇总（`holdout_files==2` 时打印） |
| `FIX10CLASS24_BF16_MEASUREMENT_RESULT` | 见 §7 | 全 24 类汇总（`full_run` 时打印） |
| `M22_RUNTIME_RESULT` | `result` / `phase` / … | 运行时 harness 汇总（框架层） |
| `GATE_RESULT` | `gate` / `result` / 原因 | 门禁总判定，必须 `result=PASS` |

---

## 7. PASS/FAIL 判据（需求 10）

### 两样本（Test A/B）——以下**全部**满足才算 PASS

```text
FIX10CLASS24_BF16_TWO_SAMPLE_RESULT scored=2 rf_excluded=0
  prediction_agreement=2/2 label_correct=2/2 nan_or_inf=0
  repeat_deterministic=2/2 training_estimate_valid=2/2
  negative_control=PASS cfo_finite=1 cfo_in_range=1
  tx_restore_ok=1 rx_restore_ok=1
GATE_RESULT ... result=PASS
```

额外逐样本硬判据：

- 每个样本 `payload_training_residual <= 0.10`（红线门限，未改）
- 每个样本 `rx_clipped=0`
- 每个样本 `FIX10CLASS24_BF16_CAPTURE_ATTEMPTS ... attempts<=3`
- 每个样本 `FIX10CLASS24_BF16_RECOVERY ... valid=1 failure=NONE`
- 每个样本 `FIX10CLASS24_BF16_CLASSIFY ... finite=1`

### 全 24 类（Test C/D）——两样本判据在 24/24 上逐条类推

```text
FIX10CLASS24_BF16_MEASUREMENT_RESULT scored=24 rf_excluded=0
  prediction_agreement=24/24 label_correct=24/24 nan_or_inf=0
  repeat_deterministic=24/24 training_estimate_valid=24/24
  negative_control=PASS cfo_finite=1 cfo_in_range=1
  tx_restore_ok=1 rx_restore_ok=1
  wc=1/1 sc=1/1
GATE_RESULT ... result=PASS
```

（`wc/sc` 对应 AM-SSB-WC source_index=8500 / AM-SSB-SC source_index=9000，二者均合并映射到 deployed23 的 AM-SSB，
故各应为 1/1。逐样本 `payload_training_residual<=0.10`、`rx_clipped=0`、`attempts<=3`、`valid=1 failure=NONE` 同两样本。）

### FAIL 即停止上报

任一判据不满足即 FAIL；**不得**用标签/预测重试、不得放宽 `0.10` 门、不得把强制分类算 RF 通过。
如实上报 FAIL 与日志，不写任何 PASS 类 token。

---

## 8. 安全与停止条件（需求 11）

- **总捕获次数 ≤ 3**：每样本初始 1 次 + 至多 2 次重试（`FIX10CLASS24_BF16_CAPTURE_ATTEMPTS attempts<=3`）。
- **只重试** `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`（`final_failure=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH` 才会
  触发 `FIX10CLASS24_BF16_CAPTURE_RETRY`）；clip / sync / corr / CFO / SRO / device / network 错误**立即终止**，不重试。
- **用第一个过门样本**（通过 0.10 门即采信），**不**取最小残差、**不**按 label/prediction 重试。
- **0.10 门保持基线不变**（`kPayloadTrainingResidualMax=0.10`，测试 `test_residual_gate_unchanged` 已断言）。
- **TX 安全**：`--tx-atten -40` 全程固定；发现 PC TX 日志非 `-40.00` 立即停止；任何 RX gain 写入被设备拒绝或读回不一致即停止。
- 任一字段 NaN/Inf、或 `nan_or_inf != 0`、或任一 `rx_clipped != 0`：立即停止。

---

## 9. 失败回滚

1. **包/资产错误**：删除解包目录与板端 `bin/`，重新上传正确 FULL 包，重做 §2 身份校验。
2. **构建失败**：`build_npu_on_board.sh` 已 fail-closed（删除旧 `bin/` 目标）；排查后重跑 §3，直到
   `NPU_BUILD_RESULT gate=9R result=PASS`。
3. **测试 FAIL**：保留完整 `$LOG` 与 `--out-dir`（`--dump-failed-rx` / `--dump-recovery-diagnostics` 已落盘），
   回传主机做诊断；**不回滚红线文件**（模型/标签/canonical/恢复算法/0.10 门/TX 上限）。
4. **恢复双 SDR 闭环**：先确认 PC TX 服务重启（§4 命令）与板端 RX `iio_info -s` 可见，再重跑对应 Test。
5. 任何情况下**不碰板**改代码、不重开 SDR 之外的动作、不通过 SSH 关闭网卡；这些由用户执行并确认。

---

## 10. 状态约束

本交付只做打包、身份校验与板测说明。真实板测通过前，最高状态保持
**`M29-RML24-FIX10CLASS24-DUALSDR-RXRECOVERY1-READY-FOR-BOARD-TEST`**，
不写 `RF_PASS / SMOKE_PASS / STANDALONE_PASS / 24CLASS_PASS / PROJECT_COMPLETE / FINAL_*`。
