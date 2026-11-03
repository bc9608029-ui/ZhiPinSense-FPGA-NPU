# 备份与回退方案（任务 §十二）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
**本方案不把「理论上可恢复」当成已验证恢复**；JTAG 恢复为板端已验证路径，其余标注待验证。

## 1. 任何实际写入前必须准备（逐项）

| # | 项目 | 命令/方法 | 产物 |
|---|---|---|---|
| 1 | 当前分区表 | `fdisk -l /dev/mmcblk0`（只读） | `backup/fdisk_mmcblk0.txt` |
| 2 | 原 bootloader/kernel/启动区只读 SHA | `sha256sum /dev/mmcblk0p1`（整分区读）+ 分区内逐文件 SHA | `backup/mmcblk0p1.sha256` |
| 3 | 原 BOOT.bin 备份 | 挂载 FAT 只读复制 `BOOT.bin`（不改源） | `backup/BOOT.bin.orig` |
| 4 | 备份校验 | 对每份备份再算 SHA，与源比对一致 | `backup/SHA256SUMS.txt` |
| 5 | 串口进入 U-Boot | 上电串口 `console=ttyPS0,115200n8`，3s 内回车（vendor uEnv `bootdelay=3`） | 手册记录 |
| 6 | JTAG 恢复 | 用 PL JTAG 口加载 `combined_npu_hdmi_disable_icap.bit`（板端已验证） | 手册记录 |
| 7 | SD/其他备用启动 | SD/QSPI 双启动跳线（vendor 手册 §4.2） | 手册记录 |
| 8 | 写入失败/断电恢复 | 若 BOOT.bin 损坏：U-Boot 停 → JTAG 重载 → 恢复原 BOOT.bin | 手册记录 |
| 9 | 绝不覆盖分区 | **QSPI mtd0/mtd1（角色未确认）、mmcblk0p2 rootfs、PL DDR、模型/结果文件** | 清单 |
| 10 | 用户确认点 | 写入前逐条确认备份存在且 SHA 校验通过 | 确认记录 |

## 2. 备份脚本（板端，未来用户执行）

`scripts/collect_fmql_boot_state.sh` 的备份段落只做**只读**采集。真正备份（复制 BOOT.bin 出来）由用户手动执行：

```bash
mkdir -p /root/boot_backup_$(date +%Y%m%d)
mount /dev/mmcblk0p1 /root/bits 2>/dev/null || true   # 只读挂载: 加 -o ro 更稳
mount -o remount,ro /dev/mmcblk0p1 2>/dev/null || true
cp -a /root/bits/BOOT.bin /root/boot_backup_*/BOOT.bin.orig
sha256sum /root/bits/BOOT.bin /root/boot_backup_*/BOOT.bin.orig | tee /root/boot_backup_*/SHA256SUMS.txt
umount /root/bits
```

## 3. 回退步骤（写入 BOOT.bin 失败/需回退时）

```bash
# 串口进入 U-Boot（bootdelay=3s 内回车）→ 停在 U-Boot 提示符
# 方式 A：SD 恢复（另一台电脑/读卡器）
#   将 backup/BOOT.bin.orig 覆盖回 SD FAT 分区的 BOOT.bin（vendor 教程 §3.3）
# 方式 B：板内恢复（系统仍能启动时）
mount /dev/mmcblk0p1 /root/bits
cp backup/BOOT.bin.orig /root/bits/BOOT.bin
sync
umount /root/bits
reboot
# 方式 C：JTAG 恢复（BOOT.bin 损坏、系统起不来时）
#   用 PL JTAG 加载 combined_npu_hdmi_disable_icap.bit（板端已验证路径）
#   屏幕/UI 恢复后，再按方式 A/B 修复 BOOT.bin
```

## 4. 回退核验

1. `sha256sum BOOT.bin` == 原备份 SHA；
2. 重启后行为回到「安装前」（黑屏、需 JTAG 或新 BOOT.bin）；
3. 分区表未变（`fdisk -l` 与备份一致）；
4. QSPI mtd0/mtd1 未被触碰（`cat /proc/mtd` 与备份一致）。

## 5. 红线重申

- **绝不写 QSPI mtd0/mtd1**（角色未确认，可能承载第二启动路径）。
- **绝不写 mmcblk0p2 rootfs 的模型/结果文件**。
- 备份校验未通过 → 禁止任何写入。
- secure boot 未确认 → 禁止写入自签 BOOT.bin。
