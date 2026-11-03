# fix10class24-singlesdr-ab1 板测速记（quickstart）

本 PATCH 是 **flat 覆盖包**：在已部署 rxrecovery1 FULL（`6fd93f78…`）的板端树根解压即可。

## 一句话

单 SDR 自发自收（loopback=0，同轴，同 LO/时钟），与双 SDR 逐字同恢复链，跑 24 类 BF16
分类，看 coverage / gated / end-to-end 三指标；forced raw24 板端打印 PENDING，离线补。

## 三条命令（用户串口执行；我不碰板）

```bash
# 短测门禁（BPSK + 4ASK）
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=short2

# 全 24 类
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24

# 若 24/24，再重复两轮
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24
bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24
```

## 安全红线

- TX 衰减固定 **-40 dB**（runner 拒绝任何 `--tx-atten > -40`）；`--rf-path=direct-cable` 强制，
  无天线/无放大器。
- `LIBIIO_ROOT=/opt/sdr/libiio-0.26`（`run_gate9_rml23.sh` 透传）。

## 离线补 forced raw24（host）

```bash
python3 scripts/aggregate_fix10class24_singlesdr_ab1_forced.py --phase aggregate \
    --out-dir '<OUT_DIR>' --clean24-dir clean24_smoke \
    --baseline baselines/clean24_smoke_raw24_bf16_baseline.tsv \
    --icraft-run /path/to/icraft-run.exe --model-dir model_rml24_bf16 \
    --force-classify-tool host_tools/replay_fix10class24_failed_rx_force_classify.sh
```

详见 `docs/M29_RML24_FIX10CLASS24_SINGLESDR_AB1_AUDIT.md`。
