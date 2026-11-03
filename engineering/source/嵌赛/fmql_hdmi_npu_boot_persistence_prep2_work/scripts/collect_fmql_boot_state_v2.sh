#!/usr/bin/env bash
# collect_fmql_boot_state_v2.sh -- 只读收集 FMQL 开机显示链路状态（PREP2 修订版）。
#
# 相比 PREP1 collect_fmql_boot_state.sh 的修订：
#   (1) devmem 输出经 normalize_devmem_value.sh 归一化，修复 "0x0x20230218" 双前缀缺陷；
#   (2) 新增 lsblk -f、FPGA Manager 驱动 modinfo + /lib/modules/$(uname -r) + /usr/src 驱动源码枚举；
#   (3) fw_printenv 仅在 /etc/fw_env.config 存在且非空（配置有效）时运行。
#
# 安全红线（本脚本强制）：
#   - 全程只读：只用 cat/ls/mount/sha256sum/readlink/dmesg/systemctl --no-pager/pgrep/
#     fw_printenv(仅配置有效时)/modinfo/lsblk/blkid/devmem(只读)/find 枚举。
#   - 不加载位流、不写寄存器、不写 Flash、不改 U-Boot env、不 kill 进程、不调用 fpgautil -b、
#     不写 FPGA Manager firmware/loading、不写 /dev/mem、不写 /dev/xdevcfg、不 systemctl enable/start。
#   - 任何需写权限的探测一律跳过并记 SKIP。
#
# 用法（用户本人串口/ssh 执行；只读项普通用户即可，/dev/mem 类读取需 root）：
#   bash collect_fmql_boot_state_v2.sh > /tmp/fmql_boot_state_v2_$(date +%s).txt 2>&1
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 载入 devmem 归一化助手（修复 0x0x 双前缀）；助手缺失时用内联兜底，绝不复发 0x0x。
if [ -f "$SCRIPT_DIR/normalize_devmem_value.sh" ]; then
    . "$SCRIPT_DIR/normalize_devmem_value.sh"
fi
if ! command -v normalize_hex >/dev/null 2>&1; then
    normalize_hex() {
        local raw="$1"
        raw="$(printf '%s' "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [ -n "$raw" ] || return 1
        case "$raw" in *[[:space:]]*) return 1 ;; esac
        while :; do
            case "$raw" in 0x*) raw="${raw#0x}" ;; 0X*) raw="${raw#0X}" ;; *) break ;; esac
        done
        case "$raw" in ''|*[!0-9a-fA-F]*) return 1 ;; esac
        printf '0x%s' "$(printf '%s' "$raw" | tr 'A-F' 'a-f')"
        return 0
    }
fi

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
echo "--- lsblk -f (若存在) ---"
if command -v lsblk >/dev/null 2>&1; then
    lsblk -f 2>/dev/null || echo "SKIP lsblk -f (无输出/需权限)"
else
    echo "SKIP lsblk (命令不存在)"
fi
echo
echo "--- mount (根/启动介质) ---"
mount 2>/dev/null | grep -E ' on / | on /boot| on /lib/firmware| on /media| on /mnt| on /root/bits' \
    || mount 2>/dev/null || echo "SKIP mount"
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
            -o -name '*.dtb' -o -name '*.dts' -o -name '*.bif' \) 2>/dev/null \
          | while IFS= read -r f; do
                sz=$(stat -c '%s' "$f" 2>/dev/null || echo -1)
                sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
                echo "  size=$sz sha256=${sha:-UNAVAILABLE}  $f"
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
echo "--- U-Boot 环境 (fw_printenv, 仅当 /etc/fw_env.config 配置有效; 只读) ---"
if command -v fw_printenv >/dev/null 2>&1; then
    if [ -r /etc/fw_env.config ] && [ -s /etc/fw_env.config ]; then
        fw_printenv 2>/dev/null | grep -E 'bootcmd|loadbit|uenvcmd|bootargs|bootdelay|sdboot|norboot|boot_targets|ethaddr' \
            || echo "SKIP fw_printenv (无输出或不可用)"
    else
        echo "SKIP fw_printenv (/etc/fw_env.config 缺失或为空 —— 配置无效，不运行以免误读)"
    fi
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
echo "===== [C] FPGA Manager 驱动与格式证据（只读枚举）====="
echo "--- /sys/class/fpga_manager/* 的 name/state/firmware 接口（只读列出，绝不写入）---"
for m in /sys/class/fpga_manager/fpga* /sys/class/fpga_manager/*; do
    [ -e "$m" ] || continue
    echo ">>> $m"
    [ -r "$m/name" ]     && echo "  name=$(cat "$m/name" 2>/dev/null)"     || true
    [ -r "$m/state" ]    && echo "  state=$(cat "$m/state" 2>/dev/null)"   || true
    [ -e "$m/firmware" ] && echo "  firmware 接口存在(只读列出,不写)"        || true
    [ -r "$m/compatible" ] && echo "  compatible=$(cat "$m/compatible" 2>/dev/null)" || true
done
echo
echo "--- FPGA Manager 驱动模块 + modinfo ---"
for m in /sys/module/*fpga* /sys/module/*fmql* /sys/module/*devcfg* /sys/module/*pcap*; do
    [ -e "$m" ] || continue
    mod="$(basename "$m")"
    echo ">>> module=$mod"
    modinfo "$mod" 2>/dev/null || echo "  (modinfo 无信息或不可用)"
done
modinfo fpga_mgr 2>/dev/null || echo "(fpga_mgr 模块无 modinfo)"
for d in /sys/class/fpga_manager/*/device/driver /sys/class/fpga_manager/*/driver; do
    if [ -L "$d" ]; then
        echo ">>> driverlink=$(readlink -f "$d" 2>/dev/null || readlink "$d" 2>/dev/null)"
    fi
done
echo
echo "--- 驱动源码/模块枚举（只读查找，不编译）---"
KREL="$(uname -r 2>/dev/null || echo UNKNOWN)"
echo "kernel_release=$KREL"
if [ -d "/lib/modules/$KREL" ]; then
    find "/lib/modules/$KREL" -maxdepth 4 \( -iname '*fpga*' -o -iname '*fmql*' -o -iname '*devcfg*' \) 2>/dev/null | head -n 80 \
        || echo "(/lib/modules 下无匹配)"
else
    echo "(/lib/modules/$KREL 不存在)"
fi
if [ -d /usr/src ]; then
    find /usr/src -maxdepth 4 \( -iname '*fpga*' -o -iname '*fmql*' \) 2>/dev/null | head -n 80 \
        || echo "(/usr/src 下无匹配)"
else
    echo "(/usr/src 不存在)"
fi
echo
echo "--- 其它 FPGA 重配接口节点（只读枚举，不加载）---"
ls -l /dev/xdevcfg /dev/fpga* 2>/dev/null || echo "(无 /dev/xdevcfg / /dev/fpga* 设备节点)"

echo
echo "===== [D] 当前已加载的 FPGA 配置与运行态 ====="
echo "--- frame_ctrl 版本寄存器 (0x40080000+0x0C) ---"
if command -v devmem >/dev/null 2>&1; then
    raw="$(devmem 0x4008000c 32 2>/dev/null || devmem 0x4008000c 2>/dev/null || echo '')"
    raw="$(printf '%s' "$raw" | tr -d '\r\n')"
    if [ -n "$raw" ]; then
        if v="$(normalize_hex "$raw" 2>/dev/null)"; then
            echo "frame_ctrl_version=$v  (raw=\"$raw\")"
        else
            echo "frame_ctrl_version=INVALID_HEX_VALUE raw=\"$raw\""
        fi
    else
        echo "frame_ctrl_version=READ_FAIL (devmem 无输出)"
    fi
else
    echo "SKIP devmem (命令不存在; 请用 select_cxx.sh 选择编译器编译 read_display_registers_ro 只读工具)"
fi
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
echo "collect_fmql_boot_state_v2.sh DONE (read-only; 无任何写入/加载/kill 副作用)"
