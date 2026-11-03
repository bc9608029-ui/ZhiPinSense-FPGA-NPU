# M29 RML24 FIX10CLASS24 DUALSDR2：受控 RX 增益扫描方案

- 任务：fix10class24-dualsdr2 Batch 2 RF 扫描勘误
- 状态：`M29-RML24-FIX10CLASS24-DUALSDR2-CANONICAL-REPLAY-READY-FOR-BOARD-RF-SWEEP`
- 本文是用户执行手册；API 不碰板。

## 0. 勘误与边界

原方案提出将 PC TX 衰减从 `-40` 提升到 `-35/-30 dB`，但生产 PC TX 程序具有硬安全门禁：

```text
--tx-atten -35.000 exceeds the -40 dB safety ceiling; refusing
```

因此原 TX 三档扫描不可执行。`-35/-30 dB` 均不得使用，不得修改或绕过 `-40 dB` 安全门禁。

本方案改为：

- PC TX 衰减始终固定为 `-40 dB`；
- 只改变板端 RX gain：`30 -> 35 -> 40 dB`；
- 不修改模型、恢复数学、同步/CFO/SRO、训练参考或任何验收门限；
- 不加入 BPSK 特判、per-class 补偿或失败重试绕过；
- 每个增益档均由设备精确写后读回；生产路径现有 `require_exact_d(..., "RX gain")` 负责 fail-closed；
- 增益上调不等同于保证同等幅度的 SNR 提升，只以实测指标判定。

## 1. 固定参数与唯一变量

| 参数 | 值 |
|---|---|
| PC TX attenuation | `-40 dB`（硬安全上限，全程不变） |
| center | `2400000000` |
| sample-rate | `2560000` |
| rf-tx-target-rms | `2048` |
| rf-path | `direct-cable` |
| input-kind | `radioml-d2-2p56m` |
| tx-bw | `18000000` |
| RX gain 扫描 | `30 / 35 / 40 dB` |
| 两样本 | BPSK source_index=1500；4ASK source_index=500 |

唯一变量是板端 `--rx-gain`。

## 2. 扫描顺序

1. 已有 `rx-gain=30` 结果作为基线：BPSK residual=0.111490、4ASK residual=0.081803、`rx_clipped=0`，总门禁 FAIL。
2. 下一档运行 `rx-gain=35`。
3. 若 35 dB 全部通过，停止升增益，在 35 dB 复跑 3 次。
4. 若 35 dB 未通过且没有触发停止条件，再运行 `rx-gain=40`。
5. 若 40 dB 仍不能稳定通过，停止并如实报告；不得继续提高增益或放宽门限。

每次板端运行前都要重新启动一次 PC TX 服务。PC 服务的命令始终相同。

## 3. PC 命令（PowerShell，每次运行前启动）

先用 `iio_info.exe -s` 取得本次 PC Pluto URI，再设置 `$TxUri`：

```powershell
$Root = 'F:\嵌赛\fix10class24_dualsdr2_work\sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2'
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

必须看到两条 `PREWARM` 和 `listening on 0.0.0.0:39010` 后再运行板端。

## 4. 板端命令

### 4.1 RX gain = 35 dB

```bash
ROOT='/root/fix10class24_diag_1773390748/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2'
cd "$ROOT"

SWEEP_OUT="/tmp/rml24_sweep_rxg35_$(date +%s)"
SWEEP_LOG='/root/rml24_sweep_rxg35.log'

bash scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --tx-control=tcp://192.168.126.10:39010 \
  --rx-uri=usb:1.3.5 \
  --input-kind=radioml-d2-2p56m \
  --center=2400000000 \
  --rx-gain=35 \
  --rf-tx-target-rms=2048 \
  --rf-path=direct-cable \
  --diagnostic-classes=BPSK,4ASK \
  --diagnostic-per-class=1 \
  --dump-failed-rx \
  --dump-recovery-diagnostics \
  --out-dir="$SWEEP_OUT" \
  2>&1 | tee "$SWEEP_LOG"

SWEEP_RC=${PIPESTATUS[0]}
echo "SWEEP_RC=$SWEEP_RC"
echo "SWEEP_OUT=$SWEEP_OUT"
```

### 4.2 RX gain = 40 dB（仅在 35 dB 未通过且未触发停止条件时）

先重新启动 §3 的 PC TX 服务。板端使用与 §4.1 完全相同的命令，仅替换：

```bash
SWEEP_OUT="/tmp/rml24_sweep_rxg40_$(date +%s)"
SWEEP_LOG='/root/rml24_sweep_rxg40.log'
```

以及：

```text
--rx-gain=40
```

## 5. 结果提取

```bash
grep -E \
'CFO |RECOVERY|CLASSIFY|TWO_SAMPLE_RESULT|MEASUREMENT_RESULT|M22_RUNTIME_RESULT|GATE_RESULT|ERROR|FAIL' \
"$SWEEP_LOG" | tail -n 300
```

逐样本记录：

- `gain_mag`、`payload_gain_mag`、`payload_rms_gain_mag`
- `rx_clipped`
- `coarse_cfo_hz`、`fine_cfo_hz`、`total_cfo_hz`
- `training_corr`、`training_residual`
- `payload_training_corr`、`payload_training_residual`
- `valid`、`failure`
- `baseline_pred`、`rf_pred`、`prediction_agreement`
- `tx_restore_ok`、`rx_restore_ok`

## 6. 每档通过条件

以下条件必须全部满足：

1. `scored=2`
2. `rf_excluded=0`
3. `prediction_agreement=2/2`
4. `training_estimate_valid=2/2`
5. `negative_control=PASS`
6. `cfo_finite=1`
7. `cfo_in_range=1`
8. `tx_restore_ok=1`
9. `rx_restore_ok=1`
10. 两个样本 `payload_training_residual <= 0.10`
11. 两个样本 `rx_clipped=0`
12. `nan_or_inf=0`
13. `GATE_RESULT ... result=PASS`

## 7. 立即停止条件

任一档出现以下任一情况即停止，不进入更高 RX gain：

- 任一样本 `rx_clipped != 0`
- 任一字段出现 NaN/Inf，或 `nan_or_inf != 0`
- `training_corr` 或 `payload_training_corr` 相比上一档明显下降
- residual 相比上一档明显上升
- 设备拒绝 RX gain 写入或精确读回不一致
- PC TX 日志不是 `tx_atten=-40.00`

## 8. 最低通过档的 3 次复跑

找到最低通过 RX gain 后，保持 TX `-40 dB` 和该 RX gain，完整重复 3 次。每次：

- 重新启动 PC TX 服务；
- 使用独立的 `--out-dir` 与日志；
- 必须逐次满足 §6 全部条件。

只有 3 次全部 PASS，才进入 24 类各 1 样本测试。24 类测试需要为全部 24 个 source index 预热 PC burst cache；不得仅沿用两个样本的 prewarm 参数，否则会正确触发 `BURST_CACHE_MISS`。完整 24 类命令应在 3 次复跑通过后单独生成和核对。

## 9. 状态约束

本扫描只是板端测量，当前最高状态仍为：

```text
M29-RML24-FIX10CLASS24-DUALSDR2-CANONICAL-REPLAY-READY-FOR-BOARD-RF-SWEEP
```

在真实板测完成前禁止写 `SMOKE-PASS / RF-PASS / 24CLASS-PASS / PROJECT_COMPLETE / FINAL_*`。
