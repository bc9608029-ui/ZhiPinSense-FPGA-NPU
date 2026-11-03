# 多频点发射 — 板端短测手册（待执行）

> 状态：**待用户执行**。本文档是交付方案，不是已完成证据。执行者：用户本人（串口/PC）。
> 我（API）不碰板、不发射、不写 Flash。执行后请把结果表 + 原始 IQ/频谱回传，我再据此判读。

## 0. 前置与红线

- 发射是**真实 RF**，开始前确认现场无其他占用、天线/负载/衰减已接好。
- 已知纯数字结论（勿忘）：**镜像（+2.56 MHz 采样副本）约 −28 dBc**，接收端曾报 **±2.56 MHz 别名**。这两点必须用频谱/原始 IQ 单独核对，不能只看相关器输出。
- 本短测只验证**发射源**；与巡扫整体验收、定频/扫频 240 回归是**分开的**，不可混用。

## 1. 确认当前接收服务与连接

1. 确认接收服务稳定在位（`systemctl status` 或等价），记录原服务状态/参数。
2. 若做原始 IQ 诊断：**独占 RX**，先保存原服务状态，结束后恢复，**禁止并发争抢同一 SDR**。
3. 记录：接收设备、连接方式、LO、Fs、BW、增益。

## 2. 发射序列（PC 端，TX Pluto）

在 PC 运行（`$python=/d/Anaconda/python`，工作目录 `F:\嵌赛\rml24_multifreq_tx_validation_20261029`）：

```bash
# 先做一次 dry-run，确认四场景落盘与 SHA（不发射）
$python scripts/multifreq_tx.py \
  --manifest F:/嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json \
  --dataset  F:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset \
  --out results/tx_board_dry

# 真实发射：显式 URI；每阶段时长按 RX 完整扫描耗时冻结（推荐 >=30s 保证足够观察）
$python scripts/multifreq_tx.py \
  --manifest F:/嵌赛/rml24_final_integration1_work/pc_runtime/selftest_manifest_240.json \
  --dataset  F:/嵌赛/rml24_stage7_execution_20261027/pc/rml24_final_stage7_pc_selftest/dataset \
  --out results/tx_board_run1 \
  --transmit --tx-uri usb:1.12.5 \
  --link F:/AMR_Rescue_20261025/pluto_link_probe.py \
  --phases silence,a_only,b_only,both,a_only,silence \
  --phase-seconds 30
```

- 序列：**静默 → A-only → B-only → both → 撤去B(→A-only) → 静默**。
- 阶段时长要足够观察，**不把跨相位残留误判为伪目标**（每相位之间留观察窗口）。
- 关注 TX 事件日志 `TX_EVENT` 与 `transmit_run.json` 里的 `config_ok`、`restore_ok`、`restore_errors`。**`restore_ok` 全真且 `restore_errors` 为空才算停发/恢复验证通过**。

## 3. 接收端核对（逐路再双路）

1. **定频接收**分别在 A=2400.0 MHz、B=2403.6 MHz 验证公共帧与分类；原始 IQ 频谱取证（固定接收配置、避免削顶、报告实际读回）。
2. 核对两路中心、真实占用带宽（预期 ~2.56 MHz）、杂散/镜像。
3. 在疑似别名频点（真实中心 ±2.56 MHz）采集，**关联原始 IQ 频谱与相关检测**，区分「真实 RF 能量」与「相关器虚假频率估计」。
4. **仅有相关器输出不能证明存在真实额外发射信号**；没有频谱仪就如实写「第二台 SDR 测量」，不称计量校准；SDR 混叠/前端影响仍需不同 LO/采样率受控对照排查。
5. 逐路单独可识别后再验收双路；若单独可识别但双路失败，先区分 TX 叠加 / 接收带宽与动态范围 / 接收算法，不直接归咎模型。

注意：原「搜索锁定」接收器**不能汇总多目标**，不可用「只显示一个目标」判 TX 失败；巡扫尚未实施，TX 短测与巡扫验收分开。

## 4. 结果表模板（回传）

| # | 相位 | 期望 | 实测中心(MHz) | 占用带宽(MHz) | 镜像/别名(dBc 或 MHz) | 公共帧识别 | 分类 | 备注 |
|---|---|---|---|---|---|---|---|---|
| 1 | silence | 无辐射 | | | | 无 | — | |
| 2 | a_only | 2400.0 | | | | 是/否 | | |
| 3 | b_only | 2403.6 | | | | 是/否 | | |
| 4 | both | 2400.0 + 2403.6 | | | | 是/否 | | |
| 5 | a_only(撤B) | 2400.0 | | | | 是/否 | | 验证撤去B无残留 |
| 6 | silence | 无辐射 | | | | 无 | — | |

补充回传：
- `transmit_run.json`（config_ok / restore_ok / restore_errors / events）。
- 原始 IQ 频谱截图或 `.c16`（标注 LO/Fs/BW/增益）。
- 别名频点取证（若采集）。

## 5. 判据

- 逐路（A/B）中心、带宽、公共帧/分类通过 + 双路两路可区分 + 停发/恢复 `restore_ok` 全真 → 可信双频点 RF 源证据成立，可升级状态（但仍**不是**巡扫/模型验收）。
- 否则保留 `OFFLINE_TX_PREP_VERIFIED_RF_PENDING` 并记录失败原因，不归咎模型。
