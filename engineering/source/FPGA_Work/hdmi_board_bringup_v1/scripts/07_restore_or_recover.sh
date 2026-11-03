#!/usr/bin/env bash
# 07_restore_or_recover.sh — rollback to the official board image.
# Run on the HOST.  Restores the official BOOT.bin / full SD image so the board
# returns to its shipping state.  Only ever run when the user explicitly asks.
set -u

# Official boot assets (shipped with the board / ICraft reference impl).
OFFICIAL_BOOT_DIR="/f/嵌赛/04_ICraft/v3.36.1/FMQL30TAI参考实现/悟净开发板/位流/悟净LITE版_BOOT_25122301_单路PLIN+pHDMI(外置detpost)"
FULL_SD_IMAGE="/f/嵌赛/06_板载Linux系统镜像/icraft_v3_ubuntu20.04_aarch64_sd_image.bin"

echo "This script restores the OFFICIAL board image.  It is a rollback only."
echo "  - SD FAT boot files: BOOT.bin, Image, fmqlmp-verify.dtb, u-boot"
echo "  - or full SD re-image with imageUSB.exe"
echo
echo "Because the colorbar test is a VOLATILE JTAG load, a simple power cycle"
echo "already reverts it; permanent restore is normally unnecessary."
echo
echo "Options (manual):"
echo "  1) Power cycle  -> reverts the temporary JTAG colorbar load."
echo "  2) Re-copy the official BOOT.bin etc. to the SD FAT partition:"
echo "       cp $OFFICIAL_BOOT_DIR/BOOT.bin /media/SD/bits/"
echo "  3) Full re-image: use imageUSB.exe with $FULL_SD_IMAGE"
echo
echo "No action taken by this script.  Run one of the above only if you mean it."
