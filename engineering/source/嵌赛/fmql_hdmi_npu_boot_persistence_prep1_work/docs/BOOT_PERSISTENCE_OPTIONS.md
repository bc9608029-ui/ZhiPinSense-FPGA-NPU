# 三种启动方案评估（阶段 C）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。

## 方案 A — 启动镜像固化（BOOT.bin 到 SD FAT）

**机制**（vendor 官方）：BootROM → FSBL 从 SD FAT 分区（mmcblk0p1）读 BOOT.bin → FSBL 编程 PL（BOOT.bin 内嵌位流）→ BL31 → U-Boot → kernel。`30TAI使用教程.pdf §3`：「替换 FAT 分区中的 BOOT.bin … 重启系统后位流生效」。

- **合并位流如何进入正式启动镜像**：Vivado 生成 `.bit` → 复制到 `BOOT_Gen` 解压目录 → 用 Procise「Create Image」按 `7030ai_psin.bif` 打包 `.bit`+FSBL+bl31+u-boot → 产出 BOOT.bin（bin）。
- **输出文件格式**：BOOT.bin（FMSH 启动镜像：`0xAA995566` 魔数 + `"FMSH"` 标识 + 分区表 + [FSBL, bitstream, BL31, u-boot]，加密字 `@0x28`）。
- **写入位置**：SD 卡 FAT 分区（mmcblk0p1）的 BOOT.bin（vendor 教程 §3.3）。
- **是否影响原 bootloader/kernel**：替换 BOOT.bin 会替换 FSBL/u-boot；kernel（Image）在 FAT 分区单独存放，不受影响（除非同时替换）。
- **双镜像/回退**：vendor 无内置 A/B 槽位；需自备份原 BOOT.bin（见 BACKUP_AND_ROLLBACK）。
- **断电中断恢复**：SD 写入中断可能损坏 BOOT.bin → 需 JTAG 恢复 + 备份恢复。
- **风险**：需闭源 Procise GUI；`.bif` 未取得；板实际 FSBL 未采集；secure boot 未确认。

## 方案 B — Linux 启动后软件加载（U-Boot `fpga loadb`）

**机制**（vendor Lite 参考包 `uEnv.txt`）：U-Boot `loadbit=mmc rescan && fatload mmc 0:2 0x10000000 download.bit && fpga loadb 0 0x10000000 $filesize`，随后 `booti` 启动 kernel。PL 在 kernel 之前被编程，kernel 随后全新枚举 NPU/DMA/udmabuf。

- **驱动是否提供加载入口**：是 U-Boot `fpga loadb`（vendor 流程），非 Linux FPGA Manager。
- **.bit 是否可直接加载**：是（vendor 流程即用 `.bit`）。
- **设备树/DMA/udmabuf/NPU 是否需重新绑定**：否——PL 编程先于 kernel，kernel 启动即枚举。
- **是否破坏 Linux/内存**：否（PL 编程发生在 kernel 加载前）。
- **失败回退**：`.bit` 不在/损坏 → `fpga loadb` 失败，U-Boot 环境回退（无位流则与现状一致：黑屏但系统可登录，JTAG 可救）。
- **风险**：依赖板实际 U-Boot 环境含 `loadbit`/`fpga loadb`（板端未采集，仅 bootargs 字节一致）；vendor `mmc 0:2` 与板 `mmcblk0p2=ext4 rootfs` 布局不一致，需以板实际 uEnv 为准。

## 方案 C — 保留 JTAG（开发/赛前低风险备用）

**机制**：上电 → JTAG 加载工作位流 → 手动/自启 UI。当前板端已验证（JTAG 重载后 HDMI/UI/触摸正常）。

- **不冒充最终自动启动方案**；仅作为 A/B 失败时的兜底。

## 风险表（详见 `results/solution_risk_matrix.tsv`）

| 方案 | 关键风险 | 等级 |
|---|---|---|
| A 生成 BOOT.bin | 闭源 GUI + `.bif` 缺失 | HIGH |
| A 写入 SD FAT | 红线禁止我写；需备份+授权 | HIGH |
| A FSBL 一致性 | 板实际 FSBL 未采集 | HIGH |
| A 断电中断 | BOOT.bin 损坏 | HIGH |
| B uEnv 依赖 | 板实际 U-Boot env 未采集 | MEDIUM |
| B 分区布局 | vendor mmc 0:2 vs 板 ext4 rootfs 冲突 | MEDIUM |
| B .bit 可加载 | vendor 已证 | LOW |
| B NPU/DMA 重绑 | 无需 | LOW |
| C JTAG | 非自动 | LOW |
| Linux FPGA Manager | 驱动格式未知 | HIGH |
| secure boot | 板端未采集 | MEDIUM/HIGH |

## 结论：只能推荐一个主方案

**主方案 = A（启动镜像固化，BOOT.bin 到 SD FAT）**。依据：
1. 它是 vendor 唯一明文写「重启系统后位流生效」的**权威开机自动加载路径**；
2. 方案 B 的 vendor 参考 `uEnv.txt` 与板端实际分区布局冲突（`mmc 0:2 fatload` vs `mmcblk0p2 ext4`），可靠性未证实；
3. 方案 B 可作为**低风险第一步**（先板端采集 uEnv 确认），但不作为最终主方案；
4. 方案 C 是开发/兜底，不是自动启动。

**但 A 离线不可交付**：BOOT.bin 需闭源 Procise GUI + `.bif`（本地无法解压）+ 板实际 FSBL（未采集）。因此本任务交付 A 的「输入物 + 逐步骤配方 + 校验脚本」而非最终 BOOT.bin（诚实标注，见 LIMITATIONS）。
