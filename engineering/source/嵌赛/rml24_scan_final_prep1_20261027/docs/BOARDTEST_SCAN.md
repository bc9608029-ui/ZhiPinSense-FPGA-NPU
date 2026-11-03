# 板端测试顺序（必须按门执行）

## 0. 前提

- 使用已验证的 Stage 7 最终树副本，不覆盖唯一基线。
- TX/RX 同轴及衰减配置保持 Stage 7 安全设置。
- 本包 SHA 校验通过。

## 1. 审计并安装增量

```bash
SCAN=/root/rml24_scan_final_prep1_20261027
FINAL=/root/<stage7-final-tree-copy>
bash "$SCAN/deploy/install_scan_overlay.sh" --target "$FINAL"
bash "$SCAN/deploy/install_scan_overlay.sh" --target "$FINAL" --apply
```

第一条只审计不写文件；第二条才安装。任何 prerequisite SHA 不符都停止，不能强行覆盖。

## 2. 板端构建 UI

按 Stage 7 的 assemble 流程生成最终 UI 树，然后：

```bash
cd "$FINAL/<assembled-ui-tree>"
taskset -c 0 bash board_package/build_ui_live_rml24_final.sh
```

必须看到 `UI_BUILD_RESULT result=PASS`。

## 3. 先做固定模式回归

PC 仍用 2.4 GHz 默认：

```powershell
python -I pc_runtime/rml24_scan_tx.py `
  --legacy-root <EVIDENCE_ROOT> `
  --dataset <STAGE7_DATASET> `
  --manifest <STAGE7_MANIFEST> `
  --out <FRESH_TX_OUT> `
  --listen-host 192.168.126.10 `
  --tx-uri "usb:<TX_URI>" `
  --center-hz 2400000000
```

板端：

```bash
bash "$FINAL/board_runtime/run_dualmode_receiver.sh" \
  --run /root/rml24_dualmode_fixed_$(date +%s) \
  --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/<model_rml24_bf16> \
  --control-host 192.168.126.10 \
  --initial-mode FIXED --save
```

固定模式若明显低于 Stage 7 基线，立即回退，不进入扫频。

## 4. 窄扫频独立验证

PC 把公开中心频率改为 2401.3 MHz；数据、模型和帧格式不变：

```powershell
python -I pc_runtime/rml24_scan_tx.py `
  --legacy-root <EVIDENCE_ROOT> `
  --dataset <STAGE7_DATASET> `
  --manifest <STAGE7_MANIFEST> `
  --out <FRESH_SCAN_TX_OUT> `
  --listen-host 192.168.126.10 `
  --tx-uri "usb:<TX_URI>" `
  --center-hz 2401300000
```

板端先扫 2399–2403 MHz：

```bash
bash "$FINAL/board_runtime/run_dualmode_receiver.sh" \
  --run /root/rml24_dualmode_scan_$(date +%s) \
  --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/<model_rml24_bf16> \
  --control-host 192.168.126.10 \
  --initial-mode BAND_SCAN \
  --scan-start-hz 2399000000 \
  --scan-stop-hz 2403000000 \
  --scan-step-hz 1000000 --save
```

验收至少包括：LO readback 全通过、首帧找到公共帧、锁定频率误差、后续帧走 locked check、无标签、恢复有限、准确率、恢复失败和完整 240 分母。

把板端 `capture/results.json` 复制回电脑后判分：

```powershell
python -I scripts/score_dualmode_run.py `
  --results <SCAN_CAPTURE>\results.json `
  --truth <STAGE7_PC_PACKAGE>\truth\expected_private.json `
  --expected-center-hz 2401300000 `
  --out <FRESH_SCORE_DIR>\scan_score.json
```

判分器对缺帧和无效帧一律记错，分母固定为真值清单的 240；同时输出完整混淆矩阵、全扫次数、锁定检查次数和最大频率误差。

## 5. 触控切换

窄扫频通过后才测试屏幕 MODE 页：FIXED、BAND SCAN、STOP、START。AUTO LOCK 必须显示拒绝/未启用，不能假装已实现。

## 6. 最后才更新自启动

只有定频回归和扫频验证均通过，才用已验证的 boot-persistence 流程把服务入口从 Stage 7 固定接收器切到双模式脚本。更新前保留原 service 和 Stage 7 树，以便一条命令回退。

