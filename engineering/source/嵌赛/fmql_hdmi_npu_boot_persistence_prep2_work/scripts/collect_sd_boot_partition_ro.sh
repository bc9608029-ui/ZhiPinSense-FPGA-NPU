#!/usr/bin/env bash
# collect_sd_boot_partition_ro.sh -- SD 启动分区（mmcblk0p1）只读审计。
#
# 目的：在不写任何启动介质/Flash/FPGA 配置的前提下，采集 SD FAT 启动分区的
#       设备身份、挂载状态、分区 UUID/类型/容量、目录树、逐文件 SHA，并把启动文件
#       复制到 /tmp 备份目录（只读源、只写备份目录，绝不写回启动分区）。
#
# 安全红线（本脚本强制）：
#   - 设备身份用 sysfs + /proc/partitions 双重确认，绝不只凭名字。
#   - 已挂载：只记录真实挂载点；未挂载：只用 mount -o ro 临时只读挂载。
#   - 绝不 remount rw、绝不 mount 不加 -o ro、绝不向挂载点/设备写任何字节。
#   - 备份复制方向固定为：FROM 只读挂载点 TO $OUTDIR/backup；绝不反向。
#   - 绝不 sync、绝不 touch/改源文件时间、绝不删除/改名启动文件。
#   - 脚本创建的临时只读挂载在结束时（含出错时）umount。
#
# FORBIDDEN（本脚本内绝不出现）：dd of=、flashcp、cp 到启动分区、sync 后写、
#   fw_setenv、saveenv、fpga load、写 FPGA Manager sysfs、写 /dev/mem、写 /dev/xdevcfg。
#
# 用法（用户本人在板上执行，需 root 才能 mount）：
#   bash collect_sd_boot_partition_ro.sh
# 产物目录：/tmp/sd_boot_audit_<epoch>/（device_info.txt、file_list.txt、
#   boot_partition.sha256、backup/、backup.sha256、SHA256SUMS.txt、result.txt）
#
# 可覆盖环境变量（板上保持默认即可；主机 mock 演练见 host_tests/test_sd_partition_ro.sh）：
#   BOOT_DEV               目标分区（默认 /dev/mmcblk0p1）
#   BOOT_OUTDIR            产物目录（默认 /tmp/sd_boot_audit_<epoch>）
#   BOOT_SYS_ROOT          sysfs 根（默认 /sys）
#   BOOT_PROC_PARTITIONS   /proc/partitions 路径（默认 /proc/partitions）
#   BOOT_TEST_MODE         仅当设为 1 且真实 /sys/block/mmcblk0 不存在时，放宽块设备检查（主机演练用）
set -u

DEV="${BOOT_DEV:-/dev/mmcblk0p1}"
OUTDIR="${BOOT_OUTDIR:-/tmp/sd_boot_audit_$(date +%s 2>/dev/null || echo 0)}"
SYS_ROOT="${BOOT_SYS_ROOT:-/sys}"
PROC_PARTITIONS="${BOOT_PROC_PARTITIONS:-/proc/partitions}"

# 测试模式守卫：仅当显式开启且真实板上 /sys/block/mmcblk0 不存在时生效。
# 真实 FMQL 板上 /sys/block/mmcblk0 必然存在，因此测试模式在板上永不生效。
TEST_MODE=0
if [ "${BOOT_TEST_MODE:-0}" = "1" ] && [ ! -d "/sys/block/mmcblk0" ]; then
    TEST_MODE=1
fi

log() { echo "[sd_boot_ro] $*"; }
fail() { log "FAIL $*"; exit 1; }

# 规范化设备名（允许省略 /dev/ 前缀）
case "$DEV" in
    /dev/*) ;;
    *) DEV="/dev/$DEV" ;;
esac
BASE="$(basename "$DEV")"           # mmcblk0p1
PARENT="${BASE%%p[0-9]*}"            # mmcblk0
[ "$PARENT" != "$BASE" ] || fail "无法从 $BASE 推导父设备（不是分区名）"

# ---- 0) 设备身份确认（不只看名字）----
if [ "$TEST_MODE" = "1" ]; then
    log "TEST_MODE: 放宽块设备检查（仅主机演练；真实板上不会触发）"
    # 测试模式下不要求 /dev 下存在真实块设备；仅确认演练提供的 BOOT_DEV 路径存在（主机 mock 为普通文件）。
    [ -e "${BOOT_DEV:-/dev/mmcblk0p1}" ] || fail "测试模式下 BOOT_DEV 不存在: ${BOOT_DEV:-/dev/mmcblk0p1}"
else
    [ -b "$DEV" ] || fail "设备 $DEV 不是块设备"
fi
[ -b "/dev/$PARENT" ] || [ "$TEST_MODE" = "1" ] || fail "父设备 /dev/$PARENT 不是块设备"
[ -d "$SYS_ROOT/block/$PARENT/$BASE" ] || fail "$SYS_ROOT/block/$PARENT/$BASE 不存在（不是 $PARENT 的真实分区）"
grep -qE "[[:space:]]${BASE}[[:space:]]*$" "$PROC_PARTITIONS" 2>/dev/null || fail "$BASE 不在 $PROC_PARTITIONS"
grep -qE "[[:space:]]${PARENT}[[:space:]]*$" "$PROC_PARTITIONS" 2>/dev/null || fail "$PARENT 不在 $PROC_PARTITIONS"

# 记录分区容量（sysfs size 单位 = 512B 扇区）
SECTORS="$(cat "$SYS_ROOT/block/$PARENT/$BASE/size" 2>/dev/null || echo UNKNOWN)"
CAP_BYTES=UNKNOWN
case "$SECTORS" in
    UNKNOWN) ;;
    *) CAP_BYTES=$((SECTORS * 512)) 2>/dev/null || CAP_BYTES=UNKNOWN ;;
esac

mkdir -p "$OUTDIR"
{
    echo "device=$DEV"
    echo "parent=$PARENT"
    echo "sysfs_dir=$SYS_ROOT/block/$PARENT/$BASE"
    echo "sectors=$SECTORS"
    echo "capacity_bytes=$CAP_BYTES"
    echo "test_mode=$TEST_MODE"
} > "$OUTDIR/device_info.txt"
cat "$OUTDIR/device_info.txt"

# ---- 1) 挂载状态记录 ----
mounted=0
mp=""
if command -v findmnt >/dev/null 2>&1; then
    if findmnt -n -o TARGET --source "$DEV" >/dev/null 2>&1; then
        mp="$(findmnt -n -o TARGET --source "$DEV" 2>/dev/null | head -n1)"
        mounted=1
    fi
else
    if mount 2>/dev/null | grep -qE "^${DEV}[[:space:]]+on[[:space:]]+"; then
        mp="$(mount 2>/dev/null | grep -E "^${DEV}[[:space:]]+on[[:space:]]+" | head -n1 | sed -E 's#^[^[:space:]]+ on ([^[:space:]]+) type.*#\1#')"
        mounted=1
    fi
fi

CREATED_MOUNT=0
if [ "$mounted" = "1" ]; then
    log "device 已挂载 mountpoint=$mp"
    [ -d "$mp" ] || fail "记录到的挂载点 $mp 不是目录"
    # 记录挂载选项（确认 ro/rw 状态，但绝不改动）
    findmnt -n -o OPTIONS --source "$DEV" 2>/dev/null | sed 's/^/mount_options=/' || true
else
    log "device 未挂载，将只读挂载 mount -o ro $DEV $OUTDIR/mnt_ro"
    mkdir -p "$OUTDIR/mnt_ro"
    if ! mount -o ro "$DEV" "$OUTDIR/mnt_ro" 2>"$OUTDIR/mount_err.txt"; then
        fail "mount -o ro 失败：$(cat "$OUTDIR/mount_err.txt" 2>/dev/null)"
    fi
    mp="$OUTDIR/mnt_ro"
    CREATED_MOUNT=1
fi

# 守卫：产物目录绝不落在挂载点内（防止写到启动分区）
case "$OUTDIR" in
    "$mp"|"$mp"/*) fail "OUTDIR($OUTDIR) 位于挂载点($mp)内，拒绝继续（防止写启动分区）" ;;
esac

# 结束时卸载脚本创建的临时只读挂载
cleanup() {
    if [ "$CREATED_MOUNT" = "1" ]; then
        umount "$OUTDIR/mnt_ro" 2>/dev/null || log "WARN 临时只读挂载卸载失败: $OUTDIR/mnt_ro（请手动 umount，勿改为 rw）"
    fi
}
trap cleanup EXIT

# ---- 2) 分区 UUID / 类型 / 容量 ----
{
    echo "=== blkid -o export $DEV ==="
    blkid -o export "$DEV" 2>/dev/null || echo "(blkid 不可用或无信息)"
    echo
    echo "=== lsblk -f $DEV ==="
    lsblk -f "$DEV" 2>/dev/null || echo "(lsblk 不可用)"
    echo
    echo "=== lsblk -b -o NAME,SIZE,FSTYPE,UUID,LABEL $DEV ==="
    lsblk -b -o NAME,SIZE,FSTYPE,UUID,LABEL "$DEV" 2>/dev/null || echo "(lsblk 不可用)"
} > "$OUTDIR/partition_info.txt"
cat "$OUTDIR/partition_info.txt"

# ---- 3) 目录树 + 逐文件 SHA（源，只读）----
find "$mp" -mindepth 1 | sort > "$OUTDIR/file_list.txt"
log "目录树行数=$(wc -l < "$OUTDIR/file_list.txt" 2>/dev/null || echo UNKNOWN)"

: > "$OUTDIR/boot_partition.sha256"
while IFS= read -r f; do
    [ -f "$f" ] || continue
    rel="${f#"$mp"/}"
    sz=$(stat -c '%s' "$f" 2>/dev/null || echo -1)
    sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
    echo "${sha:-UNAVAILABLE}  $sz  $rel" >> "$OUTDIR/boot_partition.sha256"
done < "$OUTDIR/file_list.txt"

# 重点启动文件显式报告（存在/缺失都如实记录）
echo
echo "--- 重点启动文件存在性与 SHA ---"
for name in BOOT.bin BOOT.BIN uEnv.txt download.bit; do
    found=0
    while IFS= read -r f; do
        [ -f "$f" ] || continue
        if [ "$(basename "$f")" = "$name" ]; then
            found=1
            sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
            echo "  PRESENT  $name  sha256=${sha:-UNAVAILABLE}  size=$(stat -c '%s' "$f" 2>/dev/null || echo -1)"
        fi
    done < "$OUTDIR/file_list.txt"
    [ "$found" = "0" ] && echo "  ABSENT   $name"
done

echo
echo "--- 其它启动文件（u-boot* / *.dtb / *.bit / *.bif 等）---"
while IFS= read -r f; do
    [ -f "$f" ] || continue
    bn="$(basename "$f")"
    case "$bn" in
        u-boot*|*.dtb|*.bit|*.bif|*.bit.bin|Image|image.ub|uImage|*.elf|*.out|*.bin)
            echo "  FILE  $bn  sha256=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')  size=$(stat -c '%s' "$f" 2>/dev/null || echo -1)"
            ;;
    esac
done < "$OUTDIR/file_list.txt"

# ---- 4) 备份：只读复制到备份目录（绝不写回启动分区）----
log "备份：从只读挂载点 $mp 复制到 $OUTDIR/backup"
mkdir -p "$OUTDIR/backup"
while IFS= read -r f; do
    [ -f "$f" ] || continue
    rel="${f#"$mp"/}"
    dest="$OUTDIR/backup/$rel"
    mkdir -p "$(dirname "$dest")"
    cp "$f" "$dest" 2>>"$OUTDIR/copy_err.txt" || fail "备份复制失败: $rel"
done < "$OUTDIR/file_list.txt"

# 备份目录逐文件 SHA（用于与源比对）
( cd "$OUTDIR/backup" && find . -mindepth 1 -type f | sort | while IFS= read -r f; do
      rel="${f#./}"
      sz=$(stat -c '%s' "$f" 2>/dev/null || echo -1)
      sha=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
      echo "${sha:-UNAVAILABLE}  $sz  $rel"
  done ) > "$OUTDIR/backup.sha256"

# 源/备份 SHA 比对（相对路径对齐：备份 SHA 不含前导 ./）
sed 's#^\./##' "$OUTDIR/backup.sha256" > "$OUTDIR/backup.sha256.norm" 2>/dev/null || cp "$OUTDIR/backup.sha256" "$OUTDIR/backup.sha256.norm"
if diff -q "$OUTDIR/boot_partition.sha256" "$OUTDIR/backup.sha256.norm" >/dev/null 2>&1; then
    log "备份 SHA 与源一致"
else
    log "WARN 备份 SHA 与源不一致（见 boot_partition.sha256 vs backup.sha256.norm）"
fi

# 最终 SHA256SUMS.txt（相对路径，源视图）
cp "$OUTDIR/boot_partition.sha256" "$OUTDIR/SHA256SUMS.txt"

{
    echo "device=$DEV parent=$PARENT mounted=$mounted mountpoint=$mp created_ro_mount=$CREATED_MOUNT"
    echo "capacity_bytes=$CAP_BYTES"
    echo "file_count=$(grep -c '' "$OUTDIR/boot_partition.sha256" 2>/dev/null || echo 0)"
    echo "backup_dir=$OUTDIR/backup"
    echo "RESULT=OK (read-only audit complete)"
} > "$OUTDIR/result.txt"
cat "$OUTDIR/result.txt"

log "DONE 产物目录 $OUTDIR（只读审计完成，未写任何启动介质/Flash/FPGA）"
exit 0
