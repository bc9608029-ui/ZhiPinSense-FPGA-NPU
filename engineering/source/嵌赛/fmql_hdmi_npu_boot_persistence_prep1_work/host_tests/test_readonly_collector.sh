#!/usr/bin/env bash
# test_readonly_collector.sh -- 只读采集侧自测（在 Windows Git Bash / Linux 主机均可运行）。
#
# 覆盖（不止 grep）：
#   [T1] bash -n 语法检查 3 个 shell 脚本
#   [T2] collect_fmql_boot_state.sh 红线违禁命令扫描（写 Flash/写 FPGA/加载/kill）
#   [T3] read_display_registers_ro.cpp 只读安全静态断言（O_RDONLY、PROT_READ、无 PROT_WRITE、无写 /dev/mem）
#   [T4] fmql_fpga_hdmi_check.sh 三态退出码模拟（就绪 ok=YES / 版本错 ok=NO / 工具缺失）
#         —— 使用 mock reader + 假 udmabuf phys 文件，真实跑脚本断言退出码（模拟失败路径）
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
S="$ROOT/scripts"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "PASS: $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

echo "=== T1 bash -n 语法检查 ==="
for f in collect_fmql_boot_state.sh fmql_fpga_hdmi_check.sh build_candidate_image.sh verify_candidate_image.sh; do
    if bash -n "$S/$f" 2>/tmp/bashn_err; then
        ok "syntax $f"
    else
        bad "syntax $f: $(cat /tmp/bashn_err)"
    fi
done

echo "=== T2 红线违禁命令扫描（collect_fmql_boot_state.sh，剥注释后）==="
# 先剥掉 '#' 注释行，再扫真实命令（写 Flash/写 FPGA/加载/kill）。
# 只读的 ls -l /dev/...、cat /sys/... 不算违禁。
grep -vE '^[[:space:]]*#' "$S/collect_fmql_boot_state.sh" >/tmp/collector_nocomment
forbidden='flashcp|mtd_debug|fpgautil[[:space:]]+-b|program_flash|killall|pkill|systemctl[[:space:]]+(enable|start)|dd[[:space:]].*of=/dev/(mtd|mem|xdevcfg)|>[[:space:]]*/dev/(mtd|mem|xdevcfg)|of=/dev/(mtd|mem|xdevcfg)'
if grep -nE "$forbidden" /tmp/collector_nocomment >/tmp/forbid_hit; then
    bad "collector contains forbidden op: $(cat /tmp/forbid_hit)"
else
    ok "collector has no forbidden write/load/kill ops"
fi

echo "=== T3 read_display_registers_ro.cpp 只读安全静态断言（剥 // 注释后）==="
cpp="$S/read_display_registers_ro.cpp"
grep -vE '^[[:space:]]*//' "$cpp" >/tmp/cpp_nocomment
if grep -q 'O_RDONLY' /tmp/cpp_nocomment && grep -q 'PROT_READ' /tmp/cpp_nocomment; then
    ok "uses O_RDONLY + PROT_READ"
else
    bad "missing O_RDONLY / PROT_READ"
fi
if grep -q 'PROT_WRITE' /tmp/cpp_nocomment; then
    bad "PROT_WRITE present (forbidden mmap write)"
else
    ok "no PROT_WRITE (read-only mmap)"
fi
if grep -qE 'open\("/dev/mem".*O_WRONLY|open\("/dev/mem".*O_RDWR' /tmp/cpp_nocomment; then
    bad "/dev/mem opened with write access"
else
    ok "/dev/mem opened read-only"
fi

echo "=== T4 fmql_fpga_hdmi_check.sh 三态模拟（mock reader + 假 udmabuf）==="
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PHYS="$TMP/phys_addr"

# mock reader：输出受控的 frame_ctrl 版本
make_reader() {
    local ver="$1"
    cat > "$TMP/reader" <<EOF
#!/usr/bin/env bash
printf 'reg addr=0x4008000c value=0x%s name=frame_ctrl_VERSION(0x4008000C) ts=1.000\n' "$ver"
exit 0
EOF
    chmod +x "$TMP/reader"
}

# T4a 就绪路径
make_reader 20230218
echo "0x0000000030100000" > "$PHYS"
FPGA_HDMI_READER="$TMP/reader" FPGA_HDMI_UDMABUF_PHYS="$PHYS" bash "$S/fmql_fpga_hdmi_check.sh" >/tmp/t4a.out 2>&1
rc=$?
if [ $rc -eq 0 ] && grep -q 'ok=YES' /tmp/t4a.out; then ok "check ok=YES (rc=0)"; else bad "ready path rc=$rc: $(cat /tmp/t4a.out)"; fi

# T4b 版本错误（位流不在位）→ fail-closed
make_reader deadbeef
FPGA_HDMI_READER="$TMP/reader" FPGA_HDMI_UDMABUF_PHYS="$PHYS" bash "$S/fmql_fpga_hdmi_check.sh" >/tmp/t4b.out 2>&1
rc=$?
if [ $rc -eq 1 ] && grep -q 'ok=NO' /tmp/t4b.out; then ok "check ok=NO wrong version (rc=1)"; else bad "wrong-version path rc=$rc: $(cat /tmp/t4b.out)"; fi

# T4c udmabuf 缺失 → fail-closed
make_reader 20230218
FPGA_HDMI_READER="$TMP/reader" FPGA_HDMI_UDMABUF_PHYS="$TMP/nonexistent" bash "$S/fmql_fpga_hdmi_check.sh" >/tmp/t4c.out 2>&1
rc=$?
if [ $rc -eq 1 ] && grep -q 'udmabuf0 not present' /tmp/t4c.out; then ok "check udmabuf missing (rc=1)"; else bad "udmabuf-missing path rc=$rc: $(cat /tmp/t4c.out)"; fi

# T4d reader 缺失 → rc=2（工具缺失，不误判为就绪）
FPGA_HDMI_READER="$TMP/noreader" FPGA_HDMI_UDMABUF_PHYS="$PHYS" bash "$S/fmql_fpga_hdmi_check.sh" >/tmp/t4d.out 2>&1
rc=$?
if [ $rc -eq 2 ]; then ok "check no-reader-tool (rc=2)"; else bad "no-reader path rc=$rc: $(cat /tmp/t4d.out)"; fi

echo
echo "RESULT test_readonly_collector.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
