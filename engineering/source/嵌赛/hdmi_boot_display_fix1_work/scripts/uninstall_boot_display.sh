#!/usr/bin/env bash
# uninstall_boot_display.sh -- 回退：停用并删除 RML23 UI 自启服务，回到全手动状态。
#
# 只删本方案写入的文件：/etc/systemd/system/boot-display-ui.service + /opt/sdr/bin/board_ui_live_rml23。
# 绝不触碰其他文件/模型/结果/Flash/BOOT.bin/位流。停止 UI 只 kill -TERM 名字匹配进程，
# 绝不 pkill/killall。
set -uo pipefail

SERVICE_NAME="boot-display-ui"
DEST_BIN="/opt/sdr/bin/board_ui_live_rml23"
SOCK_FILES="/run/sdr_amr_ui_rml23.sock /run/sdr_amr_control_rml23.sock"
PID_FILE="/tmp/sdr_ui_live_rml23/ui_live_rml23.pid"

if [ "$(id -u)" -ne 0 ]; then
    echo "FAIL must_run_as_root"; exit 2
fi

# 停服务（可能未启动，忽略错误）
systemctl stop "$SERVICE_NAME.service" 2>/dev/null || true
systemctl disable "$SERVICE_NAME.service" 2>/dev/null || true

# 停 UI 服务端（若在跑）：仅按 PID 文件 + cmdline 名字匹配，安全 kill -TERM
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        if grep -q 'board_ui_live_rml23' "/proc/$pid/cmdline" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
            echo "UI_STOPPED pid=$pid"
        else
            echo "REFUSE_KILL pid=$pid (cmdline 不匹配，跳过)"
        fi
    fi
fi
rm -f "$PID_FILE" /tmp/sdr_ui_live_rml23/ui_live_rml23.sock $SOCK_FILES 2>/dev/null || true

rm -f "/etc/systemd/system/$SERVICE_NAME.service"
rm -f "$DEST_BIN"
systemctl daemon-reload 2>/dev/null || true

echo "UNINSTALL_OK service=$SERVICE_NAME removed=1"
echo "已回到全手动状态：JTAG 加载位流 + 手动 start_live_rml23.sh。"
