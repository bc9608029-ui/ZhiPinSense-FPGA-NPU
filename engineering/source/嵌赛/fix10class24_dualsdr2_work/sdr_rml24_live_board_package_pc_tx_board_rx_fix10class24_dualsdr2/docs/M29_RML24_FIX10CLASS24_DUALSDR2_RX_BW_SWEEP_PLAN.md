# M29 RML24 FIX10CLASS24 DUALSDR2：受控 RX 带宽扫描方案（fix10class24-rxfrontend1）

- 任务：fix10class24-rxfrontend1（39e5 第二阶段）—— 24 类 BF16 最终接收端 RF 前端带宽/增益稳定性收口
- 状态：`M29-RML24-FIX10CLASS24-RXFRONTEND-SWEEP-READY-FOR-BOARD-TEST`（最高允许；API 不碰板）
- 本文是用户执行手册；**唯一变量是板端 `--rx-bw`**。

## 0. 方向勘误（相对旧 RX-gain 扫描）

上一版 `M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_PLAN.md` 扫描板端 RX gain `30/35/40 dB`。
真实板测显示：`30` BPSK=0.111490 FAIL、`35` 某轮 BPSK=0.114635 + 4ASK=0.145868 双 FAIL、
`40` 4ASK=0.109481 FAIL，且全部 `rx_clipped=0 / nan_or_inf=0 / CFO 有限且界内`。结论：**固定
RX 增益提升无法稳定改善归一化残差**（信号与噪声同幅放大），故放弃 RX-gain 扫描方向。

本方案改为**单变量 RX 带宽扫描**：RX gain 固定 `35 dB`、TX 固定 `-40 dB`（硬安全上限，
不修改、不绕过），只扫板端 RX 带宽 `18 / 10 / 5 / 3 MHz`。**不修改模型、恢复数学、
sync/CFO/SRO、训练参考或任何验收门限；不加入 BPSK 特判、per-class 补偿或失败重试绕过。**

> 旧文档中 TX `-35/-30 dB` 已由 `M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_ERRATA.md` 废止；
> 本方案同样废止旧 RX-gain `30/35/40` 扫描。旧 `RF_SWEEP_PLAN.md` 冻结为基线，不再执行。

## 1. 固定参数与唯一变量

| 参数 | 值 |
|---|---|
| PC TX attenuation | `-40 dB`（硬安全上限，全程不变，禁止 -35/-30） |
| center | `2400000000` |
| sample-rate | `2560000` |
| rf-tx-target-rms | `2048` |
| rf-path | `direct-cable` |
| input-kind | `radioml-d2-2p56m` |
| tx-bw | `18000000`（PC 发射带宽，全程不变） |
| **RX gain** | **`35 dB`（固定，全程不变）** |
| **RX bandwidth** | **`18 / 10 / 5 / 3 MHz`（唯一变量，widest first）** |
| 每档轮数 | `3` |
| 两样本 | BPSK source_index=1500；4ASK source_index=500 |

唯一变量是板端 `--rx-bw`。每个带宽档、每一轮，其余参数逐字一致。

## 2. 扫描顺序

按宽度从大到小：`18 → 10 → 5 → 3 MHz`，每档 BPSK+4ASK 两样本、连续 3 轮。
**选最宽、且 3/3 全过的带宽档**作为候选（不是最窄的）。

- 若 18 MHz 3/3 全过 → 候选 = 18 MHz，停止扫描。
- 若 18 MHz 未 3/3，继续 10 MHz，依此类推。
- 若 10 MHz 与 5 MHz 都 3/3 全过 → 候选 = **10 MHz**（最宽通过档）。
- 若四档均无 3/3 全过 → 判定 `NO_STABLE_RX_BANDWIDTH`，**停止**，进入物理链路审计；
  **不得**修改算法/门限/模型，也不得擅自放宽残差门限。

## 3. PC 命令（PowerShell，每一轮前重启）

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
TX 衰减永远是 `-40`；若 PC 日志出现 `-35/-30` 或门禁拒绝，立即停止并上报。

## 4. 板端命令（逐带宽档）

推荐直接用一键扫描脚本（§4.0）。也可按 §4.1–§4.4 手工逐档跑。

### 4.0 一键扫描（推荐）

```bash
ROOT='/root/fix10class24_diag_1773390748/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2'
cd "$ROOT"

# 全程 TX 固定 -40 dB、RX gain 固定 35 dB、唯一变量 --rx-bw。
# 每轮前会打印 START_PC_TX_AND_WAIT_FOR_LISTENING 并阻塞等待回车（先按 §3 重启 PC 服务）。
bash scripts/run_fix10class24_rx_frontend_sweep.sh
```

每轮产物落 `/tmp/rml24_rxbw_<hz>_run<1..3>_<ts>/run.log`，扫描结束后用 §5 判读。

### 4.1 RX bandwidth = 18 MHz

```bash
ROOT='/root/fix10class24_diag_1773390748/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2'
cd "$ROOT"

for r in 1 2 3; do
  D="/tmp/rml24_rxbw_18000000_run${r}_$(date +%s)"
  mkdir -p "$D"
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
    --rx-bw=18000000 \
    --rx-gain=35 \
    --rf-tx-target-rms=2048 \
    --rf-path=direct-cable \
    --diagnostic-classes=BPSK,4ASK \
    --diagnostic-per-class=1 \
    --dump-failed-rx \
    --dump-recovery-diagnostics \
    --out-dir="$D" \
    2>&1 | tee "$D/run.log"
done
```

### 4.2 RX bandwidth = 10 MHz

与 §4.1 完全相同的命令，仅替换：
- 输出目录 `rml24_rxbw_10000000_run${r}_$(date +%s)`
- `--rx-bw=10000000`

### 4.3 RX bandwidth = 5 MHz

与 §4.1 完全相同的命令，仅替换：
- 输出目录 `rml24_rxbw_5000000_run${r}_$(date +%s)`
- `--rx-bw=5000000`

### 4.4 RX bandwidth = 3 MHz

与 §4.1 完全相同的命令，仅替换：
- 输出目录 `rml24_rxbw_3000000_run${r}_$(date +%s)`
- `--rx-bw=3000000`

## 5. 结果判读（主机侧，fail-closed）

把 `/tmp` 下的整个 `rml24_rxbw_*` 目录树回传主机（WSL），运行：

```bash
python3 scripts/check_fix10class24_rx_frontend_sweep.py <sweep_root>
```

检查器逐字段解析（不只看单一 GATE_RESULT token）、按 §6 重推每轮 PASS/FAIL、
选出最宽 3/3 档。输出 `CANDIDATE_RX_BANDWIDTH=<hz>` 或
`CANDIDATE_RX_BANDWIDTH=NO_STABLE_RX_BANDWIDTH`。

板端也可快速自查单轮关键字段：

```bash
grep -E 'RX_FRONTEND|HELLO_ACK|RECOVERY|CLASSIFY|TWO_SAMPLE_RESULT|ERROR|FAIL' \
  "$D/run.log" | tail -n 40
```

## 6. 每轮通过条件（§八，逐条）

以下条件必须全部满足，一轮才算 PASS：

1. 无 `FIX10CLASS24_BF16_ERROR` 行。
2. RX 前端写后读回：`rx_bw_ok=1`、`rx_gain_ok=1`、`requested_rx_bw` == 该档带宽、
   读回与请求一致（±1000 Hz 或 5%）、`requested_rx_gain=35`、读回与 35 dB 差 ≤ 0.5 dB。
3. TX 衰减为安全上限：`tx_atten_db` 与 `-40` 差 ≤ 0.05 dB。
4. 样本身份：恰好 BPSK（source_index=1500）与 4ASK（source_index=500）两样本，无重复/缺样。
5. 两样本汇总：`scored=2`、`rf_excluded=0`、`prediction_agreement=2/2`、
   `label_correct=2/2`、`repeat_deterministic=2/2`、`training_estimate_valid=2/2`、
   `negative_control=PASS`、`cfo_finite=1`、`cfo_in_range=1`、`tx_restore_ok=1`、
   `rx_restore_ok=1`、`nan_or_inf=0`。
6. 每样本：`payload_training_residual <= 0.10`、`rx_clipped=0`、`finite=1`、
   `prediction_agreement=1`、`label_correct=1`。

只有 3/3 轮全过，该带宽档才为候选档。**最宽候选档胜出**。

## 7. 立即停止条件

任一档、任一出现以下任一情况即停止，不进入更窄带宽：

- 任一样本 `rx_clipped != 0`（带宽收窄若反而削顶，属异常，需物理链路审计）。
- 任一字段 NaN/Inf，或 `nan_or_inf != 0`。
- 设备拒绝 `--rx-bw` 写入或读回不一致（`rx_bw_ok=0`）。
- 设备拒绝 `--rx-gain` 写入或读回不一致（`rx_gain_ok=0`）。
- PC TX 日志不是 `tx_atten=-40.00`（或出现 -35/-30）。
- 四档均无 3/3 → `NO_STABLE_RX_BANDWIDTH`，停止，进入物理链路审计。

## 8. 生产接线（仅在有板端证据后）

本 Phase A 只交付扫描工具，**不**把某个 `--rx-bw` 写进生产默认配置。
只有真实板测选出「最宽 3/3 全过档」后，才（在后续 Phase C）把它接入生产默认值——
仍需再次两样本复测确认。无板端证据前，生产 `--rx-bw` 保持现状（缺省=设备默认，不写）。

## 9. 状态约束

本扫描只是板端测量，当前最高状态仍为：

```text
M29-RML24-FIX10CLASS24-RXFRONTEND-SWEEP-READY-FOR-BOARD-TEST
```

在真实板测完成前禁止写 `SMOKE-PASS / RF-PASS / 24CLASS-PASS / RXONLY-PASS /
PROJECT_COMPLETE / FINAL_*`。API 不碰板；板端扫描由用户执行。
