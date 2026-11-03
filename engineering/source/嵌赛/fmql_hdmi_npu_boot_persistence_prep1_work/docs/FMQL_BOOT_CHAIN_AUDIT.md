# FMQL 启动链只读审查（阶段 A）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`（仅离线证据）。
本文件不写板、不烧 Flash，所有结论逐条标注证据来源与置信度。没有本地证据的说法一律标 `UNCONFIRMED`。

## 0. 结论速览

- 板为 **FMQL30TAI / JFMQL30TAI676H 悟净 Lite**（单颗 QSPI、无 eMMC）。
- 启动链：**BootROM → FSBL → BL31 → U-Boot → Linux kernel → rootfs(mmcb/k0p2)**。
- **PL 位流加载**有两处 vendor 官方路径：
  1. **FSBL 从 BOOT.bin 加载**（`30TAI使用教程.pdf §3`：替换 FAT 分区 BOOT.bin 后「重启系统后位流生效」）；
  2. **U-Boot `fpga loadb` 从 `download.bit` 加载**（vendor Lite 参考包 `uEnv.txt`：`fatload mmc 0:2 0x10000000 download.bit && fpga loadb 0 0x10000000 $filesize`）。
- 当前板「重启黑屏」的直接原因（沿用 prior work `hdmi-boot-display-fix1`，已证实）：合并位流仅 JTAG 临时加载、上电失效，磁盘上无公开候选位流。
- vendor `.bit` 格式与我们的合并位流格式同族（同步字 `0xAA995566`），**U-Boot `fpga loadb` 直接消费 `.bit`，无需 .bin 转换**。

## 1. 上电后实际顺序（问题 1）

| 阶段 | 证据 | 置信度 |
|---|---|---|
| BootROM 按 MIO3~MIO5 跳线选 JTAG/QSPI/SD | `03_FMQL30TAI-悟净开发板手册/悟净开发板Lite（轻量版）硬件使用手册V1.0.pdf §4.2` | vendor 文档确认 |
| FSBL | vendor Lite 包 `FSBL251210_ddr400_demo.out`（SHA `5501c470…`，1,385,156 B） | vendor 产物确认 |
| BL31 | vendor Lite 包 `bl31.elf`（SHA `fdcf0af4…`，610,824 B） | vendor 产物确认 |
| U-Boot | vendor Lite 包 `u-boot`（SHA `c4570e3e…`，6,579,840 B）+ `uEnv.txt` | vendor 产物确认 |
| Linux | vendor Lite 包 `Image`（SHA `1e40bfe9…`，12,533,768 B）；`uEnv.txt uenvcmd` 用 `booti` | vendor 产物确认 |
| rootfs | 板端采集 `/proc/cmdline root=/dev/mmcblk0p2`；`mount` 显示 `/dev/mmcblk0p2 on / ext4` | 板端采集确认 |

## 2. FPGA PL 在哪一阶段加载（问题 2）

两条 vendor 官方路径并存：

1. **FSBL 路径（BOOT.bin 内嵌位流）**：`30TAI使用教程.pdf`「三. 生成BOOT.bin」：用 Procise「Create Image」把 `.bif`+`.bit`+FSBL+u-boot 打包成 BOOT.bin，替换 SD FAT 分区 BOOT.bin 后「重启系统后位流生效」。
2. **U-Boot 路径（独立 download.bit）**：vendor Lite 参考包 `uEnv.txt`：
   `loadbit=mmc rescan && fatload mmc 0:2 0x10000000 download.bit && fpga loadb 0 0x10000000 $filesize`；`bootcmd=run loadbit; run uenvcmd`。

两者都表明：**PL 在 U-Boot/FSBL 阶段、Linux 启动之前被编程**，因此「开机自动显示」在 vendor 设计上就是支持的；当前板只是没有把合并位流放到这两个位置之一（JTAG-only）。

## 3. mtd / mmc 各存什么（问题 3、4）

板端采集 `_evidence/board_capture/boot_display_state_before_jtag.txt`：

| 设备/分区 | 大小 | 内容/角色 |
|---|---|---|
| QSPI `n25q256a`（cadence-qspi e0000000.spi, 32768 KB） | 32 MiB | dmesg 确认存在 |
| mtd0 "bootloader" | 0x00400000 (4 MiB) | `UNCONFIRMED`：可能是旧/次启动镜像；`uEnv.txt` 有 `norboot=cp.b 0xE2100000 ... vxWorks` 路径，说明 NOR/QSPI 侧可能遗留另一套启动 |
| mtd1 "kernel" | 0x01000000 (16 MiB) | `UNCONFIRMED` |
| mtd2 "rootfs" | 0 | 空 |
| mmcblk0p1 | ~1 GiB (1048576 KB) | FAT 启动分区：BOOT.bin + Image + dtb（vendor 教程 §3.3 + uEnv `fatload mmc 0:1`） |
| mmcblk0p2 | ~26 GiB (27343750 KB) | ext4 rootfs（挂载于 /） |

隐藏启动镜像/设备树/FPGA 配置分区：板端采集搜索了 `/boot /lib/firmware /media /mnt /opt/sdr`（`/boot` 为空，无候选位流）；**未搜索 rootfs 根目录本身（例如 `/download.bit`、`/root/bits`），因此不能断定板端完全没有 vendor 位流文件**。vendor 教程 §3.3 提到「BOOT.bin 分区已挂载至 /root/bits」的用法——板端采集未覆盖 `/root/bits`。这是一个证据缺口。

## 4. FMSH FPGA Manager 驱动接口（问题 5、6、7）

板端采集 dmesg：`fpga_manager fpga0: FMSH FMQL FPGA Manager registered`；`/sys/class/fpga_manager/fpga0/state=operating`；**无 `/dev/xdevcfg`**；采集脚本里 `fpgautil` 未使用（prior work 已修正）。

- **Linux 侧 FMSH FPGA Manager 驱动接受的镜像格式：`UNCONFIRMED`**。本地没有内核源码 / 驱动源码（`find` 无 `*fpga*manager*` 命中），不能断言它接受 `.bit`、`.bin` 还是厂商专用格式。**因此不推荐 Linux FPGA Manager 加载路径**（除非拿到驱动源码）。
- **U-Boot `fpga loadb` 接受的格式：`.bit`（已确认）**——vendor 流程明确用它加载 `download.bit`（一个 `.bit` 文件）。
- **是否需要 FMSH 专用 bootgen**：是。BOOT.bin 由 Procise「Create Image」生成（`30TAI使用教程.pdf §3.1-3.2`），bif 文件在 `BOOT_Gen.rar`（`7030ai_psin.bif`），本地无 7z/unrar 无法解压，`.bif` 内容未取得（`UNCONFIRMED`）。

## 5. .bit 能否安全转换（问题 8）

不需要转换。已解析我们合并位流头（本任务离线）：

- 文件 `combined_npu_hdmi_disable_icap.bit`，5,980,628 B，SHA `22fec95c…`。
- 头结构：`00 09 0f f0 0f f0 0f f0 0f f0 00 00 01 61 00 <design_name>…`，设计名 `jpl_ddr_mandatory_core_top_combined;UserID=0000`，part 串 `7z030`。
- 同步字 `0xAA995566`（文件字节 `aa 99 55 66`，偏移 216）。
- vendor 参考 `ai7030_top_disable_icap.bit`（5,980,609 B，SHA `6818b7f8…`）头结构同族，设计名 `Wai7030_edif_top;UserID=53180205;Version=2018.3`。

**结论**：`.bit` 本身就是 U-Boot 可加载格式；若走 FSBL 固化路径，`.bit` 由 Procise 打包进 BOOT.bin（闭源 GUI，非手写转换）。**我们没有也不应「猜测转换」成厂商 `.bin`**（红线：只能靠猜测转换 .bit 即停）。

## 6. secure boot（问题 9）

- vendor BOOT.bin 头 `@0x28` 加密状态字 = `0x00000000`（未加密）——本任务离线解析。
- **板端实际是否启用 secure boot：`UNCONFIRMED`**（板端采集未包含该项）。写入自签 BOOT.bin 前必须先板端确认；若启用则禁止写入（红线）。

## 7. 恢复路径（问题 10）

1. **JTAG PL 重载**——当前板端已验证路径（JTAG 重载后 HDMI/UI/触摸正常，见 `_evidence/board_capture/board_ui_after_jtag.log`）。
2. **SD FAT 恢复原 BOOT.bin**——vendor 教程 §3.3。
3. **SD/QSPI 启动设备切换**——vendor 手册 §4.2 MIO3~MIO5 跳线。
4. **串口 U-Boot 控制台**——`console=ttyPS0,115200n8`。

## 8. 停/不停止判断

- 「找不到 FMQL 官方加载格式依据」：**不成立**——已找到 vendor 官方依据（`.bif→Procise→BOOT.bin` + `fpga loadb .bit`）。
- 「只能靠猜测转换 .bit」：**不触发**——不转换，`.bit` 直接可用；BOOT.bin 由闭源 GUI 生成（如实记录，不猜测）。
- 「候选镜像无法离线解析或复现」：**方案 A 的 BOOT.bin 无法离线生成**（闭源 GUI + `.bif` 未取得）——已在 §5 与 LIMITATIONS 如实标注；方案 B 的 `.bit` 载荷可离线字节复制复现。
- 「secure boot/签名状态不明」：板端未采集——**部署前必须先确认**，但不阻止离线证据交付（见 LIMITATIONS）。

## 证据文件清单（本审查实际读取）

- `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板Lite（轻量版）硬件使用手册V1.0.pdf`（已转 `_evidence/vendor_docs/lite_manual.txt`）
- `F:\嵌赛\03_FMQL30TAI-悟净开发板手册\悟净开发板硬件使用手册V1.0_嵌赛.pdf`（`_evidence/vendor_docs/full_manual.txt`）
- `F:\嵌赛\2026嵌赛FPGA开发\30TAI使用教程.pdf`（`_evidence/vendor_docs/ta30_tutorial.txt`）
- `F:\嵌赛\2026嵌赛FPGA开发\复微JFMQL30TAI器件VIVADO开发流程_V1.1….pdf`（`_evidence/vendor_docs/vivado_flow.txt`）
- `F:\嵌赛\2026嵌赛FPGA开发\FPAI_DEMO说明.pdf`（`_evidence/vendor_docs/fpai_demo.txt`）
- `F:\嵌赛\04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\位流\悟净LITE版_BOOT_25122301_….zip`（已解包 `_evidence/vendor_docs/vendor_lite_boot/`）
- `F:\嵌赛\04_ICraft\BOOT.bin`（standalone，SHA `c87b7959…`）
- `F:\嵌赛\board_capture\hdmi_boot_display_compare\boot_display_state_compare.tar.gz`（已解包 `_evidence/board_capture/`）
- `F:\FPGA_Work\sdr_full_chain_12class_combined_v1\`（合并位流工程 + `docs/ADDRESS_MAP_AUDIT.md` + `SOURCE_PROVENANCE_SHA256.txt`）
