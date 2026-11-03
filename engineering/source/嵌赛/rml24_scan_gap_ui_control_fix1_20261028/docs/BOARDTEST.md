# 板端测试步骤（独立候选，不覆盖正式版）

## A. 安装到新测试树

将整个交付目录上传到板端，例如 `/root/rml24_scan_gap_ui_fix1_delivery`，然后：

```bash
set -euo pipefail
DELIVERY=/root/rml24_scan_gap_ui_fix1_delivery
BASE=/root/rml24_standalone_execution_20261027/candidate
TEST=/root/rml24_scan_gap_ui_fix1_test_$(date +%s)
bash "$DELIVERY/scripts/install_overlay.sh" --base "$BASE" --out "$TEST"
printf '%s\n' "$TEST" | tee /root/rml24_scan_gap_ui_fix1_test_root.txt
```

安装器先校验五个被冻结基线文件的 SHA；不匹配即停止。它复制 BASE 后再叠加，绝不就地修改 BASE。

## B. 构建与语法检查

```bash
set -euo pipefail
TEST=$(cat /root/rml24_scan_gap_ui_fix1_test_root.txt)
python3 -m py_compile \
  "$TEST/rml24_final/board_runtime/standalone_receiver.py" \
  "$TEST/rml24_final/board_runtime/receiver_repeat_mean_gapfix1.py" \
  "$TEST/rml24_final/runtime/scan_lock_policy.py"
cd "$TEST"
taskset -c 0 bash board_package/build_ui_live_rml24_final.sh
test -x bin/board_ui_live_rml24_final
```

任何编译失败都不得进入 RF 测试。

## C. 控制与实屏（不发射）

1. 用独立 socket 启动候选 UI 与接收器，不能同时运行原服务。
2. 第五页应只显示 `FIXED`、`BAND SCAN`，不得出现 AutoLock 按钮。
3. 依次点四个频率字段，确认数字键盘、BACK/CLEAR/CANCEL/APPLY。
4. 检查合法命令最终出现 `APPLIED`；非法频率或过多扫频点显示 `REJECTED/INVALID RANGE`。
5. 用控制 socket 查询：

```bash
printf 'GET_TUNING\n' | socat - UNIX-CONNECT:/run/rml24_gapfix_control.sock
printf 'SET_MODE AUTO_LOCK\n' | socat - UNIX-CONNECT:/run/rml24_gapfix_control.sock
```

第一条应返回 fixed/start/stop/step 与 readback；第二条必须返回 ERR。

## D. 真实 RF 回归

复用上一轮同一 240 波形、同一真值、同轴链路和计分器，新建运行目录，不能覆盖 `candidate_fixed02` 或 `candidate_scan01`。

接收入口使用：

```bash
USER_RF_VALIDATION_APPROVED=YES \
LOCKED_MISSES_BEFORE_RESCAN=5 \
LOCKED_RESCAN_HOLD_SEC=1.0 \
bash "$TEST/rml24_final/board_runtime/run_repeat_mean_gapfix1.sh" \
  --run <fresh-run-dir> \
  --legacy-root /root/amr_rescue_20261025 \
  --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 \
  --initial-mode FIXED
```

扫频轮将 `--initial-mode` 改为 `BAND_SCAN`，并显式传入与发射计划相同的 start/stop/step。TX 与计分仍用上一轮冻结脚本，不能把窗口数当独立样本。

## E. 必须回传

- 构建完整日志与 UI 运行日志；
- 触控四字段的命令/ACK/readback 记录和实屏照片；
- 定频、扫频各 240 固定分母逐样本结果；
- missing、rejected、misclassified 分开统计；
- 完整接收 JSONL 和 TX 私有时间真值；
- 两次全扫的耗时分布和重扫次数。

通过标准见主交接 §6。测试结束恢复原 `rml24-ui` / `rml24-receiver`；不得修改 enable 状态或开机默认。
