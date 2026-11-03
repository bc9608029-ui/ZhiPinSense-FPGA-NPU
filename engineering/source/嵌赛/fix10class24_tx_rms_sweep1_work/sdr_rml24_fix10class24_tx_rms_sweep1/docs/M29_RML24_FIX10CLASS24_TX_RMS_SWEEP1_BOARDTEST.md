# fix10class24-tx-rms-sweep1 板测矩阵（quickstart）

本 PATCH 是 **flat 覆盖包**：在已部署 rxrecovery1 FULL（`6fd93f78…`）的板端树根解压即可。
它是 **测量**，不是回归 PASS；最高允许状态 `M29-RML24-FIX10CLASS24-TX-RMS-SWEEP1-READY-FOR-BOARD-TEST`。

## 一句话

只扫 TX 数字 IQ 幅度 `--rf-tx-target-rms ∈ {2048(基线),1536(-25%),1024(-50%)}`，其余逐字不动
（BF16 模型、0.100 门、恢复器、TX -40 上限），判断降低 TX RMS 能否减少双 SDR 模拟链非线性、
提升 24 类准确率。BF16 模型 ONLY（**不组合 TF32**；组合等两任务各自完成后再定）。

## 三条命令（用户串口执行；我不碰板）

```bash
# 0) 单 SDR 短测门禁（BPSK + 4ASK），先确认链路 + RMS=2048 基线健康
bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=single --rx-uri=usb:1.3.5 \
    --mode=short2 --target-rms=2048 --out-root=/tmp/rms_sweep --run=1

# D1) 单 SDR 全 24 类 × 3 RMS（自发自收 loopback=0）
bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=single --rx-uri=usb:1.3.5 \
    --mode=full24 --target-rms=2048 --out-root=/tmp/rms_sweep --run=1
bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=single --rx-uri=usb:1.3.5 \
    --mode=full24 --target-rms=1536 --out-root=/tmp/rms_sweep --run=1
bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=single --rx-uri=usb:1.3.5 \
    --mode=full24 --target-rms=1024 --out-root=/tmp/rms_sweep --run=1

# D2) 双 SDR 全 24 类 × 3 RMS（PC 控 TX + 板端 RX；先起 PC TX 服务）
#   PC 端（PowerShell）：
#     & 'D:\radioconda\python.exe' -I 'host_tools\pc_tx_sdr_fix10.py' `
#       --listen '0.0.0.0:39010' --tx-uri <TX_SDR_URI> --frozen-dir 'clean24_smoke' `
#       --input-kind 'radioml-d2-2p56m' --center 2400000000 --sample-rate 2560000 `
#       --tx-bw 18000000 --tx-atten -40 --rf-path 'direct-cable' --rf-tx-target-rms 2048
#   等 "listening on 0.0.0.0:39010"，再板端：
bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=dual --rx-uri=usb:1.3.5 \
    --tx-control=tcp://<PC_IP>:39010 --mode=full24 --target-rms=2048 \
    --out-root=/tmp/rms_sweep --run=1
#   （1536 / 1024 同理，PC 端 --rf-tx-target-rms 必须同值；握手对 payload_sha_post/tx_scale
#    fail-closed，值不同则不分类。）
```

## D3 — 最优 RMS 复测 ×2

由离线审计 `summary.json` 的 `conclusion` 判定是否有优于 2048 的 RMS；若有，把该 RMS 的
`--run=2` / `--run=3` 各再跑一轮（单/双 SDR 同 RMS），确认非单次噪声。

## 离线判读（host，跑完扫描后）

```bash
python3 scripts/audit_fix10class24_tx_rms_sweep1.py --sweep-root /tmp/rms_sweep \
    --clean24-dir clean24_smoke --icraft-run /path/to/icraft-run.exe
# 输出 results/tx_rms_sweep1/{inventory,per_sample_results,rms_summary,
#   class_transitions,residual_summary}.tsv + summary.json
```

- 门内样本 = 板端 NPU 自身预测；门拒样本仅在 `--icraft-run` 且 `--dump-failed-rx` 留档时，
  用冻结 BF16 模型在 Host 强制分类，标注 `DIAGNOSTIC_GATE_BYPASS=1`。
- `forced_raw24_accuracy` 是 **HYBRID** 证据（`HYBRID_BOARD_GATED_PLUS_HOST_FORCED`），
  绝不冒充门禁放行；无 icraft-run 时打印 PENDING。

## 8 条候选判定（审计自动 + 人工复核）

1. 单 SDR RMS2048 coverage/gated/e2e 是否 ≈ 参考 23/24。
2. 双 SDR 各 RMS 的 gated accuracy / forced raw24 是否单调随 RMS 下降而上升。
3. 每个误分类的 true→pred（是否同族升阶 / 跨族）。
4. 每类跨 RMS 正确率变化（`class_transitions.tsv` 的 `delta_vs_2048`）。
5. 残差均值/最大、corr、CFO、rx_clipped 是否随 RMS 下降而下降（非线性是否减弱）。
6. 广线性启用比例、capture attempts 是否随 RMS 变化（是否触发重捕获）。
7. 三 run 重复是否一致（D3）。
8. `conclusion`：`NO_EVIDENCE_TX_TARGET_RMS_CAUSES_ACCURACY_LOSS` 或
   `TARGET_RMS_CANDIDATE_FOR_PROSPECTIVE_VALIDATION`。

## 安全红线（本任务不越界）

- TX 衰减固定 **-40 dB**（runner 拒绝任何 `--tx-atten > -40`）；`--rf-path=direct-cable` 强制，
  无天线/无放大器。
- **禁 RMS > 2048**（编排脚本 `case` 只收 2048/1536/1024，2049/0/负/字符串一律拒）；
  禁抬发射功率；禁改 TX 模拟衰减。
- 不改两个 runner、BF16 模型 json `28272abc…`/raw `c1781aec…`、0.100 门、恢复器、canonical、
  分类窗口与预处理链。
- `LIBIIO_ROOT=/opt/sdr/libiio-0.26`（`run_gate9_rml23.sh` 透传）。

详见 `docs/M29_RML24_FIX10CLASS24_TX_RMS_SWEEP1_AUDIT.md`。
