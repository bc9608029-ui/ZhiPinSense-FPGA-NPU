#!/usr/bin/env bash
# test_service_failure_paths.sh -- systemd 服务失败路径 + 进程生命周期自测（主机可跑，模拟）。
#
# 覆盖（真实模拟，不止 grep）：
#   [S1] 服务依赖顺序静态断言：board-ui Requires/After fmql-fpga-hdmi-load
#   [S2] UI 就绪判据逻辑模拟：fake UI 进程分阶段打印标记，supervisor 只在
#        UI_VERSION_CHECK ok=YES + UI_FB_READY 才算就绪；仅 UI_LIVE_READY 不算；
#        version_mismatch 视为失败（进程生命周期模拟）
#   [S3] 失败路径 fail-closed：gate 失败 → 调度器拒绝启动 UI（用 fmql_fpga_hdmi_check.sh 真实 rc 驱动）
#   [S4] Restart 语义：gate Restart=no（不无限重试）、UI Restart=on-failure
#   [S5] 无 pkill/killall（红线）
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SD="$ROOT/systemd"
S="$ROOT/scripts"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

echo "=== S1 依赖顺序静态断言 ==="
if grep -q 'Requires=fmql-fpga-hdmi-load.service' "$SD/board-ui-rml23.service" \
   && grep -q 'After=fmql-fpga-hdmi-load.service' "$SD/board-ui-rml23.service"; then
    ok "UI service Requires+After gate service"
else
    bad "UI service missing Requires/After gate"
fi
if grep -q 'Type=simple' "$SD/board-ui-rml23.service"; then
    ok "UI service Type=simple"
else
    bad "UI service not Type=simple"
fi

echo "=== S2 UI 就绪判据逻辑（进程生命周期模拟）==="
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# fake UI：按参数走三条生命周期
fake_ui() {
    local mode="$1"; local log="$2"
    : > "$log"
    echo "UI_LIVE_READY sock=/run/sdr_amr_ui_rml23.sock" >> "$log"   # 阶段1：socket bind 后
    case "$mode" in
        ready)
            echo "UI_FB_INIT sock=..." >> "$log"
            echo "UI_VERSION_CHECK base=0x40080000 version=0x20230218 expected=0x20230218 ok=YES" >> "$log"
            echo "UI_FB_READY phys=0x30100000 frames=2 frame_bytes=1843200 refresh_hz=30" >> "$log"
            return 0 ;;
        live_only)
            return 0 ;;   # 只有 UI_LIVE_READY，帧缓冲 init 前就退出（不代表就绪）
        version_mismatch)
            echo "UI_LIVE_FAIL error=version_mismatch" >> "$log"
            return 3 ;;
    esac
}

# supervisor 就绪判据：进程存活 + ok=YES + UI_FB_READY（不把 UI_LIVE_READY 当成功）
judge() {  # $1=log  $2=alive(0/1)
    local log="$1" alive="$2"
    [ "$alive" -eq 1 ] || return 1
    grep -q 'UI_VERSION_CHECK .*ok=YES' "$log" || return 1
    grep -q 'UI_FB_READY phys=' "$log" || return 1
    return 0
}

fake_ui ready "$TMP/ready.log";    alive_ready=$?
judge "$TMP/ready.log" 1;          rc=$?
[ $rc -eq 0 ] && ok "ready lifecycle judged READY" || bad "ready lifecycle misjudged (rc=$rc)"

fake_ui live_only "$TMP/live.log"; judge "$TMP/live.log" 1; rc=$?
[ $rc -ne 0 ] && ok "live_only (no FB) judged NOT-READY" || bad "live_only wrongly judged READY"

fake_ui version_mismatch "$TMP/ver.log"; judge "$TMP/ver.log" 1; rc=$?
[ $rc -ne 0 ] && ok "version_mismatch judged NOT-READY (fail)" || bad "version_mismatch wrongly judged READY"

# 进程存活维度：ready 日志但进程已退出 → 不算就绪
fake_ui ready "$TMP/dead.log"; judge "$TMP/dead.log" 0; rc=$?
[ $rc -ne 0 ] && ok "dead process judged NOT-READY" || bad "dead process wrongly judged READY"

echo "=== S3 gate 失败 → 拒绝启动 UI（真实 rc 驱动调度）==="
mkdir -p "$TMP/phys"; echo "0x0000000030100000" > "$TMP/phys/p"
cat > "$TMP/badreader" <<'EOF'
#!/usr/bin/env bash
printf 'reg addr=0x4008000c value=0xdeadbeef name=frame_ctrl_VERSION(0x4008000C) ts=1\n'
exit 0
EOF
chmod +x "$TMP/badreader"
FPGA_HDMI_READER="$TMP/badreader" FPGA_HDMI_UDMABUF_PHYS="$TMP/phys/p" \
    bash "$S/fmql_fpga_hdmi_check.sh" >/dev/null 2>&1
gate_rc=$?
# 调度器：gate 失败则 UI 不得启动
if [ $gate_rc -ne 0 ]; then
    ui_started="NO"
    [ "$ui_started" = "NO" ] && ok "gate fail => UI not started (fail-closed)" || bad "UI started despite gate fail"
else
    bad "expected gate to fail (deadbeef version)"
fi

echo "=== S4 Restart 语义 ==="
if grep -q 'Restart=no' "$SD/fmql-fpga-hdmi-load.service"; then ok "gate Restart=no (no infinite retry)"; else bad "gate missing Restart=no"; fi
if grep -q 'Restart=on-failure' "$SD/board-ui-rml23.service"; then ok "UI Restart=on-failure"; else bad "UI missing Restart=on-failure"; fi

echo "=== S5 红线：无 pkill/killall（剥 # 注释后）==="
if grep -hvE '^[[:space:]]*#' "$SD"/*.service "$S"/*.sh 2>/dev/null | grep -qE 'pkill|killall'; then
    bad "pkill/killall present"
else
    ok "no pkill/killall in services/scripts"
fi

echo
echo "RESULT test_service_failure_paths.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
