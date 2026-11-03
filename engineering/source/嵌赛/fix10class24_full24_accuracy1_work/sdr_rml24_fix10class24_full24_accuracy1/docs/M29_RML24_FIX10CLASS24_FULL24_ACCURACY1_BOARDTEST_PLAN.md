# M29 RML24 fix10class24-full24-accuracy1 — 板端采集计划（Phase A）

- 任务：`fix10class24-full24-accuracy1` —— 用 rxrecovery1 采集 **24 个 raw24 类各 1 个真实双 SDR 样本**，
  回答「最新系统对 24 类真实 RF 样本到底能识别对多少个」。
- 本计划只交付**采集命令**，由用户在板端/PC 端执行；我不碰板 / 不碰 SDR。
- 基线 = rxrecovery1 FULL `6fd93f780770401056fe5c3717cf819238b1c5a0b25ed668425656b3654d6a36`。
- 最高允许状态：**`M29-RML24-FIX10CLASS24-FULL24-ACCURACY1-READY-FOR-BOARD-TEST`**。
- 禁写 `RF_PASS / SMOKE_PASS / STANDALONE_PASS / 24CLASS_PASS / PROJECT_COMPLETE / FINAL_*`。

---

## 1. 固定测试参数（不可变）

| 参数 | 值 | 说明 |
|---|---|---|
| TX 衰减 | **−40 dB** | 安全上限，绝不动 |
| RX 增益 | **35 dB** | 固定（rxfrontend1 扫描结论） |
| RX 带宽 | **18 MHz**（`--rx-bw=18000000`） | 固定（rxfrontend1 扫描最宽档） |
| 中心频率 | 2.4 GHz（`--center=2400000000`） | 固定 |
| 采样率 | 2.56 MHz（`--sample-rate=2560000` / 内部 2.56 MHz） | 固定 |
| RF 路径 | direct-cable（50 Ω 同轴直连） | 固定 |
| 样本 | 24 raw24 类 × 1 样本（full_run） | 固定 |

> 说明：rxrecovery1 板测手册 §5 的示例用 `--rx-gain=30` 且省略 `--rx-bw`；本任务按任务书
> **固定 RX gain 35 dB + RX bw 18 MHz**（= rxfrontend1 的推荐配置），故板端命令显式加
> `--rx-gain=35 --rx-bw=18000000`。其余参数与 rxrecovery1 手册一致。

---

## 2. 前置：部署 + 构建（同 rxrecovery1 手册 §2/§3）

1. 上传 rxrecovery1 FULL 包到板端独立目录，`sha256sum` 校验 == `6fd93f78…`，解包后
   `sha256sum -c SHA256SUMS.txt` 全部 OK。
2. 构建 Gate 9R / 24 类 BF16：

```bash
cd <解包目录>
LIBIIO_ROOT=/opt/sdr/libiio-0.26 ICRAFT_CMAKE_DIR=/usr/cmake \
bash board_package/build_npu_on_board.sh --gate9-rml23
# 期望 NPU_BUILD_RESULT gate=9R result=PASS
```

---

## 3. PC TX 命令（PowerShell，板端运行前先启动）

先查 PC Pluto URI：`iio_info.exe -s`，再设 `$TxUri`。**预热全部 24 个 source_index**（否则会
正确触发 `BURST_CACHE_MISS` fail-closed）：

```powershell
$Root = 'F:\嵌赛\fix10class24_dualsdr_rxrecovery1_work\sdr_rml24_fix10class24_dualsdr_rxrecovery1'
$TxUri = 'usb:1.11.5'   # 每次插拔后重新查询，按实际输出修改

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
  --prewarm-source-index 0     --prewarm-source-index 500   --prewarm-source-index 1000 `
  --prewarm-source-index 1500  --prewarm-source-index 2000  --prewarm-source-index 2500 `
  --prewarm-source-index 3000  --prewarm-source-index 3500  --prewarm-source-index 4000 `
  --prewarm-source-index 4500  --prewarm-source-index 5000  --prewarm-source-index 5500 `
  --prewarm-source-index 6000  --prewarm-source-index 6500  --prewarm-source-index 7000 `
  --prewarm-source-index 7500  --prewarm-source-index 8000  --prewarm-source-index 8500 `
  --prewarm-source-index 9000  --prewarm-source-index 9500  --prewarm-source-index 10000 `
  --prewarm-source-index 10500 --prewarm-source-index 11000 --prewarm-source-index 11500
```

必须看到 24 条 `PREWARM` 与 `listening on 0.0.0.0:39010`，且 TX 衰减严格 `-40.00`（绝不写 `-35/-30`）。

---

## 4. 板端 RX 命令（24 类各 1 样本，full_run）

`$ROOT` = §2 解包目录，`$TX_IP` = PC 局域网 IP，`$RX_URI` = 板端 RX SDR 实际 URI（`iio_info -s`）。

```bash
cd "$ROOT"
OUT="/tmp/rml24_full24_accuracy1_$(date +%s)"
mkdir -p "$OUT"

bash scripts/run_gate9_rml23.sh \
  --phase=iq-pc-tx-board-rx-24class-bf16-fix10 \
  --model-json=model_rml24_bf16/rml24_adamrv11_bf16.json \
  --model-raw=model_rml24_bf16/rml24_adamrv11_bf16.raw \
  --model-sha=c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 \
  --frozen-dir=clean24_smoke \
  --baseline=baselines/clean24_smoke_raw24_bf16_baseline.tsv \
  --tx-control=tcp://<TX_IP>:39010 \
  --rx-uri=<BOARD_RX_URI> \
  --input-kind=radioml-d2-2p56m \
  --center=2400000000 \
  --rx-bw=18000000 \
  --rx-gain=35 \
  --rf-tx-target-rms=2048 \
  --rf-path=direct-cable \
  --dump-failed-rx \
  --dump-recovery-diagnostics \
  --out-dir="$OUT" \
  2>&1 | tee "$OUT/run.log"
echo "RC=${PIPESTATUS[0]}"
```

> 与 rxfrontend1 扫描命令的唯一差别：**去掉** `--diagnostic-classes` / `--diagnostic-per-class`
> （即 holdout = 全部 24 个 raw24 样本，`full_run=1`）。

---

## 5. source_index ↔ raw24 类 对照（24 类，AM-SSB WC/SC 为独立类）

| raw24 类索引 | 类名 | source_index | | raw24 类索引 | 类名 | source_index |
|---|---|---|---|---|---|---|
| 0 | OOK | 0 | | 12 | 16QAM | 6000 |
| 1 | 4ASK | 500 | | 13 | 32QAM | 6500 |
| 2 | 8ASK | 1000 | | 14 | 64QAM | 7000 |
| 3 | BPSK | 1500 | | 15 | 128QAM | 7500 |
| 4 | QPSK | 2000 | | 16 | 256QAM | 8000 |
| 5 | 8PSK | 2500 | | 17 | AM-SSB-WC | 8500 |
| 6 | 16PSK | 3000 | | 18 | AM-SSB-SC | 9000 |
| 7 | 32PSK | 3500 | | 19 | AM-DSB-WC | 9500 |
| 8 | 16APSK | 4000 | | 20 | AM-DSB-SC | 10000 |
| 9 | 32APSK | 4500 | | 21 | FM | 10500 |
| 10 | 64APSK | 5000 | | 22 | GMSK | 11000 |
| 11 | 128APSK | 5500 | | 23 | OQPSK | 11500 |

> **AM-SSB-WC(#17) 与 AM-SSB-SC(#18) 是本任务的独立类**（主指标不合并 24→23）；
> 二者在 deployed23 才合并映射到 AM-SSB，与本任务主指标无关。

---

## 6. 期望产物（`--out-dir` 内）

```
<OUT>/route_f_fix10class24_bf16_pc_tx_board_rx_results.tsv       # 24 行逐样本结果
<OUT>/route_f_fix10class24_bf16_pc_tx_board_rx_confusion_24.csv  # 板端自产 24×24 混淆
<OUT>/route_f_fix10class24_bf16_pc_tx_board_rx_per_class.json
<OUT>/route_f_fix10class24_bf16_pc_tx_board_rx_summary.json
<OUT>/route_f_fix10class24_bf16_pc_tx_board_rx_summary.log
<OUT>/run.log                                                     # 全量日志（tee）
<OUT>/failed_rx/<source_index>/                                   # 仅被门禁拒绝的样本（7 文件）
```

逐样本判据（不用于重试，仅记录）：

- `FIX10CLASS24_BF16_RECOVERY ... valid=1 failure=NONE payload_training_residual<=0.10 rx_clipped=0`
  → 该样本 **gated**（进入 NPU 分类，`rf_verdict=RF_PRESERVES_IQ`）。
- 否则 **rejected**（`rf_verdict=RF_DISTORTS_IQ / RF_*`），且 `--dump-failed-rx` 已落盘
  `failed_rx/<source_index>/`（7 文件：`raw_rx_ci16le.bin` / `expected_scaled_payload_ci16le.bin` /
  `expected_full_burst_ci16le.bin` / `coarse_corrected_rx_cf64le.bin` /
  `recovered_payload_f32le.bin` / `recovery_diagnostics.json` / `SHA256SUMS.txt`）。

---

## 7. 回传主机

把整个 `$OUT` 目录树回传主机（`scp -r` 或 `tar czf` 后下载），作为 Phase B/C 编排器的
`--captures-dir` 输入。回传后 `sha256sum` 校验 `failed_rx/*/raw_rx_ci16le.bin` 与各自
`SHA256SUMS.txt` 一致（防传输损坏）。

---

## 8. 安全与停止条件

- TX 衰减全程 `-40 dB`；PC 日志出现 `-35/-30` 或门禁拒绝 → 立即停止。
- RX 带宽/增益写后读回 fail-closed（`rx_bw_ok=0` 或 `rx_gain_ok=0` 即报错停止）。
- 每样本捕获尝试 ≤ 3（有界重捕获）；只重试 `PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH`。
- 任一 NaN/Inf 或 `rx_clipped!=0` → 立即停止。
- 不碰板改代码、不重开 SDR 之外的动作、不通过 SSH 关闭网卡（由用户执行）。
