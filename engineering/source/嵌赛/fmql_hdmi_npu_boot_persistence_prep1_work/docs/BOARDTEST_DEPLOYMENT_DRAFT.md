# 安全部署测试手册（草案，任务 §六「后续由用户执行的安全测试手册」）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
**本手册是给用户未来执行的安全测试草案，不是本次已执行的板测。** 涉及写入的步骤全部需要用户明确授权、完成备份、并在红线允许范围内进行；本任务离线阶段未执行任何一步。

## 阶段 0 — 只读采集与备份（必须先做）

1. 执行 `docs/BOARDTEST_READONLY.md` 全部只读采集。
2. 执行 `docs/BACKUP_AND_ROLLBACK.md` 的备份清单（原 BOOT.bin + 分区表 + SHA，双份校验）。
3. 从采集确认：板启动设备、U-Boot env、secure boot 状态、当前 BOOT.bin SHA。

## 阶段 1 — 方案 B 探针（可选，低风险，先确认 uEnv）

前提：板端 U-Boot env 确认含 `fpga loadb` 且知道其加载 `download.bit` 的实际分区。

1. 把 `candidate/download.bit`（SHA `22fec95c…`）放到 U-Boot 实际指定的分区路径。
2. 重启，观察 dmesg / 屏幕 / `UI_VERSION_CHECK ok=YES`。
3. 记录：亮屏还是仍黑；`0x4008000C` 寄存器是否 `0x20230218`。

**预期**：若 uEnv 路径正确，PL 在 kernel 前被编程 → 屏幕亮。若仍黑，回退（删除 download.bit 或恢复原状），进入阶段 2。

## 阶段 2 — 方案 A 固化（主方案，写入 BOOT.bin）

1. **生成**：用户在 Windows 上按 `scripts/build_candidate_image.sh --help` 打印的配方，用 Procise「Create Image」生成 BOOT.bin（记录每个选项）。
2. **离线校验**：`scripts/verify_candidate_image.sh --boot-bin <新BOOT.bin> --bit <combined_npu_hdmi_disable_icap.bit>`，核对魔数、内嵌 `.bit` 身份、FSBL 与板原版比对。
3. **写入**（用户授权 + 备份已校验）：
   ```bash
   mount /dev/mmcblk0p1 /root/bits
   cp /root/bits/BOOT.bin /root/bits/BOOT.bin.orig2
   cp <新BOOT.bin> /root/bits/BOOT.bin
   sync
   umount /root/bits
   reboot
   ```
4. **三次断电重启验证**（唯一能写「开机自动显示通过」的条件，且仅用户确认后）：
   每次重启后核验：进程存活 + `UI_VERSION_CHECK ... ok=YES` + `UI_FB_READY phys=...` + 物理屏幕显示 + 触摸正常。

## 阶段 3 — UI systemd（模板，不自动安装）

`systemd/fmql-fpga-hdmi-load.service` + `systemd/board-ui-rml23.service` 为**模板**。仅在阶段 2 三次断电重启验证通过、且用户明确授权后，才由用户手动复制到 `/etc/systemd/system/` 并 `systemctl enable`。就绪判据见服务文件注释。

## 红线（本手册同样受约束）

阶段 1/2 的写入是「用户授权后执行」，离线阶段不执行。绝不写 QSPI mtd0/mtd1；绝不写 rootfs 模型/结果；secure boot 未确认前禁止写入自签 BOOT.bin；不使用 pkill/killall。
