# FIX10CLASS24 DUALSDR2 RF 扫描勘误（累计）

本档是 RF 扫描方向的历史勘误，**累计**废止旧执行命令。权威执行步骤一律见
`M29_RML24_FIX10CLASS24_DUALSDR2_RX_BW_SWEEP_PLAN.md`（当前有效）。

## 勘误 1：TX `-35/-30 dB` 作废（canonical replay 批次已定）

原 Batch 2 文档中的 TX `-40/-35/-30 dB` 扫描与生产安全门禁冲突。实机启动 `-35 dB` 时，
PC TX 在任何发射发生前正确拒绝：

```text
--tx-atten -35.000 exceeds the -40 dB safety ceiling; refusing
```

因此：

- 原 `-35/-30 dB` TX 档位作废；
- `-40 dB` TX 安全上限保持不变，不修改、不绕过。

## 勘误 2：RX gain `30/35/40 dB` 扫描作废（本批次，fix10class24-rxfrontend1）

真实板测 RX-gain 三档均不稳定：

| RX gain | BPSK residual | 4ASK residual | 判定 |
|---|---|---|---|
| 30 | 0.111490 | 0.081803 | FAIL |
| 35 | 0.114635（某轮） | 0.145868（某轮） | 双 FAIL |
| 40 | PASS | 0.109481 | FAIL |

全部 `rx_clipped=0 / nan_or_inf=0 / CFO 有限且界内`。**固定 RX 增益提升无法稳定改善
归一化残差**（信号与噪声同幅放大），故 RX-gain 扫描方向作废。

当前方向改为**单变量 RX 带宽扫描**：RX gain 固定 `35 dB`、TX 固定 `-40 dB`，只扫
`--rx-bw` `18/10/5/3 MHz`。详见 `M29_RML24_FIX10CLASS24_DUALSDR2_RX_BW_SWEEP_PLAN.md`。

## 冻结与红线

- 旧 `M29_RML24_FIX10CLASS24_DUALSDR2_RF_SWEEP_PLAN.md`（RX-gain 扫描）冻结为基线，
  **不再执行**，不删除、不改写。
- 本勘误不修改模型、恢复数学、验收门限或任何红线头；不加入 BPSK 特判 / per-class 补偿 /
  失败重试绕过。
- 本批次 Phase A 只交付扫描工具 + 判读检查器，生产 `--rx-bw` 默认值不在此批改动。
