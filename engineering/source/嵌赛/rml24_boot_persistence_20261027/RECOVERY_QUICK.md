# Recovery for the SD boot configuration change

Original BOOT.bin/kernel/QSPI were not changed. Verified original files and QSPI copies are in backup/boot_original_backup_20261027.tar.gz (SHA256 44fcdd2bd7704e9e24a6fa7421913ff2d52125d448c2279cb8f04ea7983d7503).

If U-Boot stops before Linux, use the same original kernel/DTB boot sequence already present in the original uEnv (no saveenv):
```
mmc rescan
fatload mmc 0:1 0x10080000 Image
fatload mmc 0:1 0x11000000 fmqlmp-verify.dtb
booti 0x10080000 - 0x11000000
```
Confirm command help first if the prompt differs. These commands boot the existing Linux without requiring the new PL-load step.

To undo the persistent config, restore original uEnv.txt from backup/sd_boot_backup/backup/uEnv.txt to the SD FAT boot partition. Original SHA256 a13c985eb5031d75ec7069333897cae38944ba5fbadd509828b63e6a48408560. The same bytes also remain on SD as uEnv.pre_rml24.txt. Do not overwrite BOOT.bin or kernel.

In Linux, stop and disable rml24-receiver.service and rml24-ui.service to undo automatic app startup. Original /etc/rc.local was left unchanged; its backup is in board work/system_before/rc.local. The installed /opt/rml24-system can remain for manual recovery.

The backup QSPI files are evidence/recovery copies only. No Flash write is required to undo this SD-file change.