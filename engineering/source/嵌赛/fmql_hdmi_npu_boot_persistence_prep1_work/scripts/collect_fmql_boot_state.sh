#!/usr/bin/env bash
# collect_fmql_boot_state.sh -- 只读收集 FMQL 开机显示链路状态。
#
# 用途：为 FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1 提供板端事实，
#       区分「磁盘上的启动文件 / 开机实际加载 / 当前已加载 FPGA 运行态」。
#
# 安全红线（本脚本强制）：
#   - 全程只读：只用 cat/ls/mount/sha256sum/readlink/dmesg/systemctl --no-pager/pgrep/fw_printenv(若有)。
#   - 不加载位流、不写寄存器、不写 Flash、不改 U-Boot env、不 kill 进程、不调用 fpgautil -b、
#     不写 FPGA Manager firmware/loading、不写 /dev/mem、不写 /dev/xdevcfg。
#   - 任何需写权限的探测一律跳过并记 SKIP。
#
# 用法（用户本人串口/ssh 执行；只读项普通用户即可，/dev/mem 类读取需 root）：
#   bash collect_fmql_boot_state.sh > /tmp/fmql_boot_state_$(date +%s).txt 2>&1
set -u

echo "===== [0] 采集元信息 ====="
echo "hostname=$(hostname 2>/dev/null || echo UNKNOWN)"
echo "date=$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date)"
echo "uname=$(uname -a 2>/dev/null || echo UNKNOWN)"
echo "id=$(id 2>/dev/null || echo UNKNOWN)"

echo
echo "===== [A] 磁盘上的启动文件 ====="
echo "--- /proc/cmdline ---"
cat /proc/cmdline 2>/dev/null || echo "SKIP /proc/cmdline"
echo
echo "--- /proc/mtd ---"
cat /proc/mtd 2>/dev/null || echo "SKIP /proc/mtd"
echo
echo "--- /proc/partitions ---"
cat /proc/partitions 2>/dev/null || echo "SKIP /proc/partitions"
echo
echo "--- mount (根/启动介质) ---"
mount 2>/dev/null | grep -E ' on / | on /boot| on /lib/firmware| on /media| on /mnt| on /root/bits' || mount 2>/dev/null || echo "SKIP mount"
echo
echo "--- 块设备符号链接 ---"
ls -l /dev/mmcblk* /dev/mtd* /dev/mtdblock* /dev/ubiblock* 2>/dev/null || echo "(无 mmc/mtd/ubi 设备节点)"
echo
echo "--- 候选启动/位流文件（路径+大小+SHA256）---"
for d in / /boot /lib/firmware /media /mnt /run/media /opt/sdr /root/bits; do
    if [ -d "$d" ]; then
        echo ">>> $d"
        find "$d" -maxdepth 3 -type f \( \
            -name 'BOOT.bin' -o -name 'BOOT.BIN' -o -name 'boot.bin' \
            -o -name '*.bit' -o -name '*.bit.bin' -o -name 'download.bit' \
            -o -name 'image.ub' -o -name 'uImage' -o -name 'uEnv.txt' -o -name 'u-boot*' \
            -o -name '*.dtb' -o -name '*.dts' \) 2>/dev/null \
          | while read -r f; do
                sz=$(stat -c '%s' "$f" 2>/dev/null || echo -1)
                sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
                echo "  size=$sz sha256=$sha  $f"
            done
    else
        echo ">>> $d (不存在)"
    fi
done
echo
echo "--- /sys/class/fpga* 目录 ---"
ls -ld /sys/class/fpga* /sys/class/fpga_manager 2>/dev/null || echo "(无 fpga_manager 暴露)"

echo
echo "===== [B] 开机实际使用的启动/FPGA 加载记录 ====="
echo "--- dmesg: FSBL/u-boot/FPGA/bitstream/devcfg/PCAP ---"
dmesg 2>/dev/null | grep -iE 'fsbl|u-boot|fpga|devcfg|pcap|bitstream|ps7-init|mio|qspi|nand|mmc' \
    | tail -n 80 || echo "SKIP dmesg (需 root 或 dmesg 受限)"
echo
echo "--- U-Boot 环境 (fw_printenv, 若可用; 只读) ---"
if command -v fw_printenv >/dev/null 2>&1; then
    fw_printenv 2>/dev/null | grep -E 'bootcmd|loadbit|uenvcmd|bootargs|bootdelay|sdboot|norboot' \
        || echo "SKIP fw_printenv (无输出或不可用)"
else
    echo "SKIP fw_printenv (命令不存在)"
fi
echo
echo "--- systemd 单元（是否已有 fpga/ui/sdr 相关自启服务）---"
systemctl --no-pager list-unit-files 2>/dev/null | grep -iE 'fpga|bitstream|ui|sdr|display|hdmi' \
    || echo "(无相关 systemd 单元 或 systemctl 不可用)"
echo
echo "--- 已启用单元 ---"
systemctl --no-pager list-unit-files --state=enabled 2>/dev/null | grep -iE 'fpga|ui|sdr|display|hdmi' \
    || echo "(无已启用相关单元)"

echo
echo "===== [C] 当前已加载的 FPGA 配置与运行态 ====="
echo "--- frame_ctrl 版本寄存器 (0x40080000+0x0C) ---"
if command -v devmem >/dev/null 2>&1; then
    v=$(devmem 0x4008000c 32 2>/dev/null || devmem 0x4008000c 2>/dev/null || echo "READ_FAIL")
    printf "frame_ctrl_version=0x%s\n" "$v"
else
    echo "SKIP devmem (命令不存在; 请使用 read_display_registers_ro 只读工具)"
fi
echo
echo "--- FPGA 重配接口（只读枚举，不加载）---"
for m in /sys/class/fpga_manager/fpga* /sys/class/fpga_manager/*; do
    [ -e "$m" ] || continue
    echo ">>> $m"
    [ -r "$m/name" ]   && echo "  name=$(cat "$m/name" 2>/dev/null)"   || true
    [ -r "$m/state" ]  && echo "  state=$(cat "$m/state" 2>/dev/null)" || true
done
ls -l /dev/xdevcfg 2>/dev/null || echo "(无 /dev/xdevcfg 设备节点)"
echo
echo "--- NPU 设备可识别（仅列设备节点，不操作）---"
ls -l /dev/*zg330* /dev/*npu* /dev/udmabuf* 2>/dev/null || echo "(无 npu/udmabuf 设备节点)"
echo
echo "--- udmabuf0 sysfs（帧缓冲物理地址/容量）---"
for p in /sys/class/u-dma-buf/udmabuf0/phys_addr /sys/class/u-dma-buf/udmabuf0/size; do
    [ -r "$p" ] && echo "$p=$(cat "$p" 2>/dev/null)" || echo "$p (不可读)"
done
echo
echo "--- /dev/mem /dev/udmabuf0 /dev/xdevcfg 节点 ---"
ls -l /dev/mem /dev/udmabuf0 /dev/xdevcfg 2>/dev/null || echo "(部分设备节点不存在)"
echo
echo "--- UI 服务端进程与 socket（RML23）---"
pgrep -af board_ui_live_rml23 2>/dev/null || echo "(board_ui_live_rml23 未运行)"
ls -l /run/sdr_amr_ui_rml23.sock /run/sdr_amr_control_rml23.sock \
      /tmp/sdr_ui_live_rml23/ui_live_rml23.pid /tmp/sdr_ui_live_rml23/ui_live_rml23.log 2>/dev/null \
    || echo "(无 socket/pid/log 残留)"
echo
echo "--- UI 日志末 20 行（若有）---"
[ -f /tmp/sdr_ui_live_rml23/ui_live_rml23.log ] && tail -n 20 /tmp/sdr_ui_live_rml23/ui_live_rml23.log 2>/dev/null \
    || echo "(无 UI 日志)"

echo
echo "===== [采集结束] ====="
echo "collect_fmql_boot_state.sh DONE (read-only; 无任何写入/加载/kill 副作用)"
