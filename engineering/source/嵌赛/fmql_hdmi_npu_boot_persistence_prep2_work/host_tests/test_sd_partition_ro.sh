#!/usr/bin/env bash
# test_sd_partition_ro.sh -- collect_sd_boot_partition_ro.sh 动态演练（mock mount/findmnt/blkid/lsblk + 假分区树）。
#
# 本主机无 /dev/mmcblk0p1 块设备，故用 BOOT_TEST_MODE=1 + BOOT_SYS_ROOT/BOOT_PROC_PARTITIONS
# 指向假树，并把 BOOT_DEV 指到一个普通文件。BOOT_TEST_MODE 仅在真实 /sys/block/mmcblk0 不存在时生效，
# 真实板上永不触发（安全网见脚本内注释）。
#
# 场景：1 已挂载  2 未挂载(ro 挂载+备份+卸载)  3 BOOT.bin 缺失  4 空格文件名  5 mount 失败 fail-closed
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="$HERE/../scripts/collect_sd_boot_partition_ro.sh"
[ -f "$S" ] || { echo "FATAL: missing $S"; exit 1; }

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

mkmockbin() { # $1=bindir
    local B="$1"; mkdir -p "$B"
    cat > "$B/findmnt" <<'EOF'
#!/usr/bin/env bash
if [ "${MOCK_MOUNTED:-0}" = "1" ]; then
    case "$*" in
        *OPTIONS*) echo "ro,relatime" ;;
        *) echo "${MOCK_MP:-/mnt/boot}" ;;
    esac
    exit 0
fi
exit 1
EOF
    cat > "$B/mount" <<'EOF'
#!/usr/bin/env bash
if [ "${MOCK_MOUNT_FAIL:-0}" = "1" ]; then echo "mount: mock failure" >&2; exit 1; fi
mntpoint="${@: -1}"
mkdir -p "$mntpoint"
if [ -d "${MOCK_FAKE_DIR:-}" ]; then cp -r "${MOCK_FAKE_DIR}/." "$mntpoint/" 2>/dev/null || true; fi
echo "$mntpoint" >> "${MOCK_MOUNT_LOG:-/tmp/mock_mount_log}"
exit 0
EOF
    cat > "$B/umount" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${MOCK_UMOUNT_LOG:-/tmp/mock_umount_log}"
exit 0
EOF
    cat > "$B/blkid" <<'EOF'
#!/usr/bin/env bash
echo "DEVNAME=/dev/mmcblk0p1"
echo "TYPE=vfat"
echo "UUID=1234-ABCD"
exit 0
EOF
    cat > "$B/lsblk" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *-f*) echo "NAME FSTYPE LABEL UUID MOUNTPOINT"; echo "mmcblk0p1 vfat boot 1234-ABCD" ;;
    *) echo "mmcblk0p1 1073741824" ;;
esac
exit 0
EOF
    chmod +x "$B/findmnt" "$B/mount" "$B/umount" "$B/blkid" "$B/lsblk"
}

setup_fake() { # $1=fake_dir $2=with_bootbin(1/0) $3=spacefile(1/0)
    local d="$1" wbb="$2" sf="$3"
    mkdir -p "$d"
    [ "$wbb" = "1" ] && { printf 'BOOTBIN_CONTENT_FAKE' > "$d/BOOT.bin"; }
    printf 'uenv fake\nbootcmd=run loadbit\n' > "$d/uEnv.txt"
    printf 'fake download bit bytes' > "$d/download.bit"
    printf 'uboot img' > "$d/u-boot.img"
    [ "$sf" = "1" ] && printf 'dtb with spaces' > "$d/my boot file.dtb"
}

run_scenario() { # $1=name  $@=rest passed to a fresh run
    :
}

# 每个场景用独立 TMP
scenario() {
    local name="$1"; shift
    local T="$(mktemp -d)"
    mkdir -p "$T/sys/block/mmcblk0/mmcblk0p1" "$T/bin" "$T/out"
    printf '4096\n' > "$T/sys/block/mmcblk0/mmcblk0p1/size"
    printf '   179        1    1048576 mmcblk0p1\n   179        0   61069312 mmcblk0\n' > "$T/partitions"
    printf 'fake block dev' > "$T/mmcblk0p1"
    mkmockbin "$T/bin"
    local FAKE="$T/fake"; mkdir -p "$FAKE"
    local WB=1 SF=0 MOUNTED=0 MFAIL=0
    # 解析场景参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --no-bootbin) WB=0 ;;
            --space-file) SF=1 ;;
            --mounted) MOUNTED=1 ;;
            --mount-fail) MFAIL=1 ;;
        esac
        shift
    done
    setup_fake "$FAKE" "$WB" "$SF"
    local envs=( BOOT_TEST_MODE=1 BOOT_DEV="$T/mmcblk0p1" BOOT_OUTDIR="$T/out"
                 BOOT_SYS_ROOT="$T/sys" BOOT_PROC_PARTITIONS="$T/partitions"
                 MOCK_MOUNTED=$MOUNTED MOCK_MOUNT_FAIL=$MFAIL MOCK_FAKE_DIR="$FAKE"
                 MOCK_MP="$FAKE" MOCK_MOUNT_LOG="$T/mount.log" MOCK_UMOUNT_LOG="$T/umount.log" )
    local out rc
    out="$(env PATH="$T/bin:$PATH" "${envs[@]}" bash "$S" 2>&1)"; rc=$?
    echo "--- scenario $name rc=$rc ---"
    printf '%s\n' "$out" | tail -n 30
    echo "---"
    # 把结果以全局变量回传
    SC_OUT="$out"; SC_RC=$rc; SC_T="$T"
}

# 场景1：已挂载 → 记录挂载点、不调用 mount
scenario "mounted" --mounted
if [ $SC_RC -eq 0 ] && printf '%s' "$SC_OUT" | grep -q 'mounted=1'; then ok "mounted: rc=0 + mounted=1"; else bad "mounted: rc=$SC_RC"; fi
if printf '%s' "$SC_OUT" | grep -q 'mountpoint='; then ok "mounted: records mountpoint"; else bad "mounted: no mountpoint"; fi
if [ ! -s "$SC_T/mount.log" ]; then ok "mounted: mount NOT called"; else bad "mounted: mount was called"; fi
if [ -f "$SC_T/out/backup/BOOT.bin" ]; then ok "mounted: BOOT.bin backed up"; else bad "mounted: BOOT.bin not backed up"; fi

# 场景2：未挂载 → mount -o ro 调用 + 备份 + umount
scenario "unmounted"
if [ $SC_RC -eq 0 ] && printf '%s' "$SC_OUT" | grep -q 'created_ro_mount=1'; then ok "unmounted: rc=0 + ro mount created"; else bad "unmounted: rc=$SC_RC"; fi
if [ -s "$SC_T/mount.log" ]; then ok "unmounted: mount -o ro called"; else bad "unmounted: mount not called"; fi
if [ -s "$SC_T/umount.log" ]; then ok "unmounted: umount called (temp mount cleaned)"; else bad "unmounted: umount NOT called"; fi
if [ -f "$SC_T/out/backup/BOOT.bin" ] && [ -f "$SC_T/out/SHA256SUMS.txt" ]; then ok "unmounted: backup + SHA256SUMS produced"; else bad "unmounted: missing backup/SHA256SUMS"; fi
if diff -q "$SC_T/out/boot_partition.sha256" "$SC_T/out/backup.sha256.norm" >/dev/null 2>&1; then ok "unmounted: backup SHA matches source"; else bad "unmounted: backup SHA mismatch"; fi

# 场景3：BOOT.bin 缺失 → 如实报告 ABSENT
scenario "bootbin-missing" --no-bootbin
if [ $SC_RC -eq 0 ] && printf '%s' "$SC_OUT" | grep -q 'ABSENT   BOOT.bin'; then ok "bootbin-missing: reports ABSENT (rc=0)"; else bad "bootbin-missing: rc=$SC_RC or no ABSENT"; fi

# 场景4：空格文件名 → 正确列出+SHA
scenario "space-file" --space-file
if [ $SC_RC -eq 0 ] && grep -q 'my boot file.dtb' "$SC_T/out/boot_partition.sha256"; then ok "space-file: listed + sha'd"; else bad "space-file: space filename lost"; fi
if [ -f "$SC_T/out/backup/my boot file.dtb" ]; then ok "space-file: backed up with spaces intact"; else bad "space-file: backup lost space filename"; fi

# 场景5：mount 失败 → fail-closed（非零退出 + FAIL）
scenario "mount-fail" --mount-fail
if [ $SC_RC -ne 0 ] && printf '%s' "$SC_OUT" | grep -q 'FAIL'; then ok "mount-fail: fail-closed (rc!=0 + FAIL)"; else bad "mount-fail: rc=$SC_RC (not fail-closed)"; fi

echo
echo "RESULT test_sd_partition_ro.sh PASS=$PASS FAIL=$FAIL"
[ $FAIL -eq 0 ]
