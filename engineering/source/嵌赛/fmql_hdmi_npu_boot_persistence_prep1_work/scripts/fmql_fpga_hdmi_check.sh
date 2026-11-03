#!/usr/bin/env bash
# fmql_fpga_hdmi_check.sh -- 只读 FPGA/HDMI 就绪门（systemd fmql-fpga-hdmi-load.service 调用）。
#
# 就绪判据（全部满足才 ok=YES）：
#   1) udmabuf0 帧缓冲存在（phys_addr 文件可读）；
#   2) frame_ctrl 版本寄存器 0x4008000C == 0x20230218（合并位流在位）。
# 只读实现：优先用 read_display_registers_ro（O_RDONLY /dev/mem）；无该二进制时退 devmem（只读）。
# 绝不写寄存器、绝不写 Flash、绝不加载位流、绝不 pkill/killall、绝不无限循环。
#
# 退出码：0 = 就绪；1 = 未就绪（fail-closed）；2 = 工具缺失。
# 可测试覆盖（host 自测用，板端无需设置）：
#   FPGA_HDMI_READER          reader 二进制路径（默认 /opt/sdr/bin/read_display_registers_ro）
#   FPGA_HDMI_UDMABUF_PHYS    udmabuf phys_addr 文件路径（默认 /sys/class/u-dma-buf/udmabuf0/phys_addr）
set -u

VERSION_EXPECT="0x20230218"
READER="${FPGA_HDMI_READER:-/opt/sdr/bin/read_display_registers_ro}"
UDMABUF_PHYS="${FPGA_HDMI_UDMABUF_PHYS:-/sys/class/u-dma-buf/udmabuf0/phys_addr}"

log() { echo "[fpga_hdmi_check] $*"; }

# 1) udmabuf0 帧缓冲
if [ -r "$UDMABUF_PHYS" ]; then
    PHY="$(cat "$UDMABUF_PHYS" 2>/dev/null)"
    log "udmabuf0 phys_addr=$PHY"
else
    log "FAIL udmabuf0 not present (framebuffer unavailable)"
    exit 1
fi

# 2) frame_ctrl 版本（只读）
ver=""
if [ -x "$READER" ]; then
    out="$("$READER" 2>/dev/null)"
    # reader 输出行: reg addr=0x4008000c value=0x20230218 name=frame_ctrl_VERSION(...) ts=...
    v="$(printf '%s\n' "$out" | sed -n '/frame_ctrl_VERSION/s/.*value=0x\([0-9a-fA-F][0-9a-fA-F]*\).*/0x\1/p' | head -n1)"
    [ -n "$v" ] && ver="$v"
elif command -v devmem >/dev/null 2>&1; then
    v="$(devmem 0x4008000c 32 2>/dev/null || devmem 0x4008000c 2>/dev/null || echo '')"
    [ -n "$v" ] && ver="$(printf '0x%s' "$v")"
else
    log "FAIL no reader tool (read_display_registers_ro / devmem) available"
    exit 2
fi

if [ -z "$ver" ]; then
    log "FAIL could not read frame_ctrl version (READ_FAIL)"
    exit 1
fi

log "frame_ctrl_version=$ver expect=$VERSION_EXPECT"
if [ "$ver" = "$VERSION_EXPECT" ]; then
    log "FPGA_HDMI_CHECK ok=YES"
    exit 0
fi
log "FPGA_HDMI_CHECK ok=NO (bitstream not in place / wrong version)"
exit 1
