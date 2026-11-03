#!/usr/bin/env bash
# check_boot_display.sh -- 主机侧离线自检（无板端、无副作用）。
#
# 校验（修正版）：
#   1) 四个 shell 脚本 bash -n 语法通过；
#   2) collect 脚本严格只读，且不含 fpgautil（-o/-b 均无）、不含写/加载/kill 类**实际命令**；
#   3) boot_display.sh 用 board_ui_live_rml23（非 12class）、不重配 FPGA、前台 exec（无 nohup/&）、
#      就绪判据引用 UI_VERSION_CHECK 与 UI_FB_READY；
#   4) service 用 Type=simple 前台托管（非 oneshot）、ExecStart 绝对路径二进制 + rml23 socket；
#   5) install 部署 UI 二进制到 /opt/sdr/bin 并设绝对路径，且不含位流加载/fpgautil；
#   6) uninstall 无 pkill/killall **实际命令**（仅按 PID 文件 kill -TERM），名字为 rml23。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
S="$(cd "$SCRIPT_DIR/scripts" && pwd)"
FAIL=0

# 剥离注释行（含行首空白 + #）
noc() { grep -vE '^[[:space:]]*#' "$1"; }

echo "== 1) bash -n 语法 =="
for f in "$S/collect_boot_display_state.sh" "$S/boot_display.sh" \
         "$S/install_boot_display.sh" "$S/uninstall_boot_display.sh"; do
    if bash -n "$f" 2>/tmp/bashn.err; then
        echo "  OK  $(basename "$f")"
    else
        echo "  FAIL $f"; cat /tmp/bashn.err; FAIL=1
    fi
done

echo "== 2) collect 只读 + 无 fpgautil =="
if noc "$S/collect_boot_display_state.sh" | grep -nE \
   'fpgautil|[[:space:]]>[[:space:]]*/sys/|dd[[:space:]]+of=|flash_erase|mtd_debug|systemctl[[:space:]]+(start|stop|enable|disable|restart)|(^|[[:space:]<>|])(kill|pkill|killall)[[:space:]]|(^|[[:space:]])rm[[:space:]]'; then
    echo "  FAIL collect 含 fpgautil 或写/加载/kill 实际命令（见上）"; FAIL=1
else
    echo "  OK  collect 无 fpgautil、无写/加载/kill 实际命令"
fi

echo "== 3) boot_display.sh 二进制/无重配/前台/就绪 =="
ok=1
noc "$S/boot_display.sh" | grep -q 'board_ui_live_rml23' || { echo "  FAIL 未用 board_ui_live_rml23"; ok=0; }
noc "$S/boot_display.sh" | grep -q 'board_ui_live_12class' && { echo "  FAIL 含 board_ui_live_12class"; ok=0; }
noc "$S/boot_display.sh" | grep -nE 'fpgautil|/sys/class/fpga_manager|/dev/xdevcfg|combined_npu_hdmi' && { echo "  FAIL 含 FPGA 重配/位流加载"; ok=0; }
noc "$S/boot_display.sh" | grep -qE 'nohup|&$| & ' && { echo "  FAIL 含后台启动(nohup/&)"; ok=0; }
grep -q 'exec "\$UI_BIN"' "$S/boot_display.sh" || { echo "  FAIL 未前台 exec 二进制"; ok=0; }
noc "$S/boot_display.sh" | grep -q 'UI_FB_READY' && noc "$S/boot_display.sh" | grep -q 'UI_VERSION_CHECK' \
    || { echo "  FAIL 就绪判据未引用 UI_FB_READY/UI_VERSION_CHECK"; ok=0; }
[ "$ok" -eq 1 ] && echo "  OK  rml23/无重配/前台 exec/正确就绪判据" || FAIL=1

echo "== 4) service 前台托管 + 正确二进制 =="
ok=1
grep -qE '^Type=simple' "$S/boot_display.service" || { echo "  FAIL Type 非 simple"; ok=0; }
noc "$S/boot_display.service" | grep -qiE 'oneshot|RemainAfterExit|nohup' && { echo "  FAIL 含 oneshot/RemainAfterExit/nohup 实际指令"; ok=0; }
grep -q '/opt/sdr/bin/board_ui_live_rml23' "$S/boot_display.service" || { echo "  FAIL ExecStart 非绝对路径 rml23 二进制"; ok=0; }
grep -q '/run/sdr_amr_ui_rml23.sock' "$S/boot_display.service" && grep -q '/run/sdr_amr_control_rml23.sock' "$S/boot_display.service" \
    || { echo "  FAIL socket 非 rml23"; ok=0; }
[ "$ok" -eq 1 ] && echo "  OK  Type=simple 前台 + rml23 二进制/socket" || FAIL=1

echo "== 5) install 部署 UI 二进制(绝对路径)+ 无位流加载 =="
ok=1
grep -q '/opt/sdr/bin/board_ui_live_rml23' "$S/install_boot_display.sh" || { echo "  FAIL 未部署到 /opt/sdr/bin"; ok=0; }
grep -q -- '--ui-bin=' "$S/install_boot_display.sh" || { echo "  FAIL 未要求 --ui-bin"; ok=0; }
noc "$S/install_boot_display.sh" | grep -nE 'fpgautil|/sys/class/fpga_manager|/dev/xdevcfg|combined_npu_hdmi|22fec95c' && { echo "  FAIL 含位流加载/重配/位流 SHA"; ok=0; }
[ "$ok" -eq 1 ] && echo "  OK  部署 rml23 二进制 + 无位流加载" || FAIL=1

echo "== 6) uninstall 无 pkill/killall(实际命令)=="
ok=1
noc "$S/uninstall_boot_display.sh" | grep -nE '\bpkill\b|\bkillall\b' && { echo "  FAIL 出现 pkill/killall 实际命令"; ok=0; }
grep -q 'board_ui_live_rml23' "$S/uninstall_boot_display.sh" || { echo "  FAIL 未用 rml23 名字"; ok=0; }
[ "$ok" -eq 1 ] && echo "  OK  无 pkill/killall + rml23 名字" || FAIL=1

echo
if [ "$FAIL" -ne 0 ]; then
    echo "RESULT=FAIL"
    exit 1
fi
echo "RESULT=PASS"
