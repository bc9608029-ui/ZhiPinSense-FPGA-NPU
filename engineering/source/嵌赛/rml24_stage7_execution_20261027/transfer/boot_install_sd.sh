#!/bin/bash
set -euo pipefail
WORK=/root/rml24_boot_persistence_20261027
CAND=$WORK/candidate_lf
DEV=/dev/mmcblk0p1
MP=/mnt/rml24-boot-persist
[ -b "$DEV" ]
[ -d /sys/block/mmcblk0/mmcblk0p1 ]
[ "$(cat /sys/block/mmcblk0/mmcblk0p1/size)" = 2097152 ]
[ "$(cat /sys/block/mmcblk0/device/type)" = SD ]
! findmnt -n --source "$DEV" >/dev/null
(cd "$CAND" && sha256sum -c SHA256SUMS.txt)
echo '44fcdd2bd7704e9e24a6fa7421913ff2d52125d448c2279cb8f04ea7983d7503  /root/rml24_stage7_execution_20261027/boot_original_backup_20261027.tar.gz' | sha256sum -c -
mkdir -p "$MP"
mount -t vfat -o rw "$DEV" "$MP"
cleanup(){ umount "$MP"; }
trap cleanup EXIT
echo 'ff350477e624c50d2f8180fb4b9130ec7688fbc7ca553412ed7c3dd2a68b31ef  '"$MP/BOOT.bin" | sha256sum -c -
echo 'a13c985eb5031d75ec7069333897cae38944ba5fbadd509828b63e6a48408560  '"$MP/uEnv.txt" | sha256sum -c -
[ ! -e "$MP/download.bit" ]
[ ! -e "$MP/uEnv.pre_rml24.txt" ]
cp "$MP/uEnv.txt" "$MP/uEnv.pre_rml24.txt"
cp "$CAND/download.bit" "$MP/download.bit.new"
cp "$CAND/uEnv.txt" "$MP/uEnv.txt.new"
echo '22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9  '"$MP/download.bit.new" | sha256sum -c -
echo 'b81563447febf35023b7c99a918bd204270518a87ea9cff169a11fbf26d1f4a9  '"$MP/uEnv.txt.new" | sha256sum -c -
sync
mv "$MP/download.bit.new" "$MP/download.bit"
mv -f "$MP/uEnv.txt.new" "$MP/uEnv.txt"
sync
sha256sum "$MP/BOOT.bin" "$MP/Image" "$MP/uEnv.txt" "$MP/download.bit" "$MP/uEnv.pre_rml24.txt" > "$WORK/installed_sd_files.sha256"
cat "$WORK/installed_sd_files.sha256"
echo RML24_SD_PERSISTENT_FILES_INSTALLED