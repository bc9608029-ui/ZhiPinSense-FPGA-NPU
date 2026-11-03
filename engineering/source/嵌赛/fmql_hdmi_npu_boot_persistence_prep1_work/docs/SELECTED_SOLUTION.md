# 最终推荐方案（阶段 C 收口）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
**最高只写本令牌；不写 BOARD_PASS / BOOT_PASS / AUTO_DISPLAY_PASS / PROJECT_COMPLETE。**

## 推荐

**主方案：A — 启动镜像固化（BOOT.bin 写入 SD FAT 分区 mmcblk0p1），最终实现上电自动显示。**

- 唯一 vendor 明文保证「重启系统后位流生效」的路径（`30TAI使用教程.pdf §3`）。
- 合并位流 = NPU+HDMI 合并设计（`jpl_ddr_mandatory_core_top_combined`），固化后开机即加载 NPU/DMA/frame_ctrl，正是「开机自动显示 + NPU 可用」的目标状态。

## 落地顺序（离线已备，板端由用户执行）

1. **只读采集**（`scripts/collect_fmql_boot_state.sh` + `read_display_registers_ro`）：拿到板实际 U-Boot `printenv`、当前 BOOT.bin 的 SHA、分区表、secure boot 状态。
2. **备份**（`docs/BACKUP_AND_ROLLBACK.md`）：原 BOOT.bin + 分区表 + SHA，双份校验。
3. **生成 BOOT.bin**（用户本人在 Windows 上运行 Procise「Create Image」，逐步记录选项）：`.bit`（SHA `22fec95c…`）+ FSBL + bl31 + u-boot + `.bif`。
4. **离线校验候选**（`scripts/verify_candidate_image.sh`）：解析 BOOT.bin 头、核对内嵌 `.bit` 身份、比对板原 FSBL。
5. **写入 + 三次断电重启验证**（用户授权后）：核验 `UI_VERSION_CHECK ok=YES` + `UI_FB_READY phys=…`。

## 为什么不是 Linux FPGA Manager 加载

板端 `fpga_manager fpga0: FMSH FMQL FPGA Manager` 已注册但**驱动接受的镜像格式本地无源码可证**（无 `/dev/xdevcfg`、无 `fpgautil`）。不推荐在不掌握驱动格式前走该路径。

## 为什么不是「仅方案 B」

方案 B（U-Boot `fpga loadb download.bit`）vendor 参考可用，但：
- 依赖板实际 U-Boot 环境（未采集）；
- vendor `fatload mmc 0:2` 与板 `mmcblk0p2=ext4 rootfs` 布局冲突。
方案 B 仅作为**低风险第一步探针**（先板端确认 uEnv），不作为主方案。

## 影响评估（问题 4）

- **NPU/DMA**：固化的是 NPU+HDMI 合并位流，地址图不变（NPU `0x40000000`/DMA `0x80000000`/frame_ctrl `0x40080000`/pl_ddr core `0x400C0000`/udmabuf `0x30100000`），24 类链 `pl_ddr_register_map.hpp` 与之逐字节契约一致。
- **风险点**：若新 BOOT.bin 换了**与板不同的 FSBL**，可能改变 PS 外设初始化。缓解：板端采集当前 BOOT.bin 内 FSBL 并比对；启动后核验 `0x4008000C==0x20230218` 与 `0x400C0000==0x20260929`。

## 失败恢复（问题 5）

JTAG 重载（现有可用）；恢复备份原 BOOT.bin；SD/QSPI 双启动切换；串口 U-Boot 控制台。详见 BACKUP_AND_ROLLBACK。

## 写板前仍缺的证据（问题 6）

1. 板实际 U-Boot `printenv`（是否含 `loadbit`/`fpga loadb`、bootcmd、分区映射）。
2. 板实际启动设备（MIO3~MIO5 跳线：SD 还是 QSPI）。
3. 板当前 BOOT.bin 内容与 SHA（含内嵌 FSBL/位流身份）。
4. `BOOT_Gen.rar` 内 `.bif` 内容（本地无 7z/unrar）。
5. 板端 secure boot 是否启用。
6. 板端 FMSH FPGA Manager Linux 驱动接受的镜像格式（驱动源码）。

以上 6 项未补齐前，**不得写入任何启动分区**。
