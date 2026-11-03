#!/usr/bin/env bash
# boot_display.sh -- 手动前台启动 RML23 LIVE UI 服务端（board_ui_live_rml23）。
#
# 本脚本**不重配 FPGA、不加载位流**。位流是否在位的判定完全交给 UI 二进制自身的版本门
# （它在写任何帧缓冲寄存器前强制校验 0x40080000+0x0C==0x20230218，不符即
#  UI_LIVE_FAIL error=version_mismatch 退出 3）。
#
# 前台托管：exec 直接替换为本进程，stdout/stderr 原样输出（UI_LIVE_READY → UI_FB_INIT →
#   UI_VERSION_CHECK ... ok=YES → UI_FB_READY phys=...），失败即非零退出，不假报成功。
# 就绪判据（人读日志）：进程存活 且 UI_VERSION_CHECK ... ok=YES 且 UI_FB_READY phys=...。
#
# 红线：
#   - 不允许多个 UI 实例：已跑则幂等退出，不起第二实例。
#   - 清理旧 socket 仅当无 UI 进程在跑；绝不 pkill/killall。
#   - 不写 Flash、不替换 BOOT.bin、不放宽设备节点权限、不操作 SDR、不改冻结模型/NPU 配置。
#
# 用法（通常手动测试；系统服务 boot-display-ui.service 直接 ExecStart 二进制，不走本脚本）：
#   bash boot_display.sh [--ui-bin=/opt/sdr/bin/board_ui_live_rml23]
set -u

UI_BIN="/opt/sdr/bin/board_ui_live_rml23"
UI_SOCK="/run/sdr_amr_ui_rml23.sock"
CTL_SOCK="/run/sdr_amr_control_rml23.sock"

for a in "$@"; do
    case "$a" in
        --ui-bin=*) UI_BIN="${a#--ui-bin=}" ;;
        *) echo "usage: $0 [--ui-bin=/abs/path/board_ui_live_rml23]"; exit 2 ;;
    esac
done

log() { echo "[boot_display] $*"; }

# 0) 幂等：UI 已在跑则退出，不重复起第二实例
if pgrep -f 'board_ui_live_rml23' >/dev/null 2>&1; then
    log "UI_ALREADY_RUNNING pid=$(pgrep -f 'board_ui_live_rml23' | head -n1)"
    exit 0
fi

# 1) fail-closed：二进制必须存在且可执行（不部署到未知路径）
if [ ! -x "$UI_BIN" ]; then
    log "FAIL ui_binary_not_found $UI_BIN"
    log "      先构建并部署： ./board_package/build_ui_live_rml23.sh 产出 bin/board_ui_live_rml23"
    exit 2
fi

# 2) 清理旧 socket（此时已确认无 UI 进程在跑）
rm -f "$UI_SOCK" "$CTL_SOCK" 2>/dev/null || true

# 3) 前台 exec 启动（进程由 exec 替换；版本门/帧缓冲失败 → 二进制非零退出，不假报）
log "UI_START ui_bin=$UI_BIN sock=$UI_SOCK ctl_sock=$CTL_SOCK"
log "UI_START_FOREGROUND（就绪看 stdout：UI_VERSION_CHECK ok=YES 与 UI_FB_READY phys=...）"
exec "$UI_BIN" --sock="$UI_SOCK" --ctl-sock="$CTL_SOCK"
