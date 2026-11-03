# 三方案逐项阻断矩阵（PREP2）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
每个方案独立列出其**自身**的阻断项与证据状态；**不把一个方案的具体缺口当三方案共享阻断项**。

状态图例：`DONE`（本地已证）/ `PENDING`（待板端采集）/ `UNCONFIRMED` / `NOT_PROVEN`。

## 方案 A — SD FAT BOOT.bin（FSBL 编程 PL，vendor 唯一明文「重启后位流生效」）

| 阻断项 | 证据状态 | 采集/补法 |
|---|---|---|
| 启动源确认（BootROM 从 SD 还是 QSPI） | `UNCONFIRMED`（MIO3~MIO5 真值表为 PDF 图片） | Boot-DIP 照片 / 手动读 MIO3~MIO5；U-Boot `printenv` |
| mmc 启动分区确认（mmcblk0p1 = FAT boot） | `PENDING`（/proc/partitions 已知，分区内容未采） | `collect_sd_boot_partition_ro.sh` |
| 当前 BOOT.bin 双备份 + SHA | `PENDING` | 同上（backup/ + boot_partition.sha256） |
| `.bif` 分区顺序/属性 | `DONE`（已解压解析：FSBL→bit→BL31→u-boot, fsbl_config apu_x32） | `docs/BIF_AND_BOOTBIN_AUDIT.md` |
| 当前 FSBL/U-Boot 身份 | `UNCONFIRMED`（vendor 示例已知，板实际未知） | 板 BOOT.bin 内嵌 FSBL 源路径串比对 |
| secure boot 状态 | `UNCONFIRMED`（vendor 镜像未加密 ≠ 板端禁用） | `docs/SECURE_BOOT_AUDIT.md` + 板端输出 |
| 离线候选校验 | 校验脚本 `DONE`；候选 BOOT.bin 未生成（Procise GUI 用户步骤） | `verify_boot_artifacts.py bootbin-info` + `bit-in-bootbin` |
| 完整回滚 | 脚本/流程就绪；JTAG 为已证恢复路径 | `BACKUP_AND_ROLLBACK` + JTAG PL 重载 |

## 方案 B — U-Boot `fpga loadb download.bit`

| 阻断项 | 证据状态 | 采集/补法 |
|---|---|---|
| U-Boot 实际支持 `fpga loadb` | `UNCONFIRMED` | 板端 `help fpga`（只 help 不执行） |
| autoboot 脚本实际运行它（bootcmd/loadbit） | `UNCONFIRMED`（vendor uEnv `loadbit=… fpga loadb …` 已知，板实际未知） | U-Boot `printenv` |
| 正确设备/分区/路径 | `UNCONFIRMED`（vendor `fatload mmc 0:2` 与板 `mmcblk0p2=ext4 rootfs` 布局冲突） | 板 `printenv` + `part list mmc 0` |
| 加载地址 + 格式有 vendor 依据 | `DONE`（vendor uEnv：`0x10000000 download.bit`；`.bit` 直接可载） | vendor uEnv.txt |

> 说明：方案 B 的「loadb 是否支持/分区冲突」是 B 自身的阻断项，**不影响**方案 A。

## 方案 C — Linux FPGA Manager

| 阻断项 | 证据状态 | 采集/补法 |
|---|---|---|
| 驱动镜像格式（.bit/.bin/厂商头） | `FORMAT_NOT_PROVEN` | `collect_fmql_boot_state_v2.sh` 的 modinfo/源码枚举 |
| 安全 NPU/DMA/UI 停止顺序 | `NOT_PROVEN` | 需驱动/平台文档 |
| 加载后设备重初始化顺序 | `NOT_PROVEN` | 同上 |
| 失败回滚 + 远程连接保持 | `NOT_PROVEN` | 同上 |

> 说明：方案 C 的 `FORMAT_NOT_PROVEN` **只阻塞 C**；A/B 不受其阻塞（见 `FPGA_MANAGER_FORMAT_AUDIT.md`）。

## 汇总

- **当前唯一「本地已证可继续」的路由是 A 的输入物（.bif + 位流 + vendor 组件 + 校验脚本）与 B 的载荷（download.bit）**；
  但 A/B 的「板端实际状态」阻断项全部 `PENDING/UNCONFIRMED`，必须等板端只读采集返回。
- **在 A/B 板端阻断项补齐前，不写任何启动分区 / Flash / U-Boot env / FPGA 配置。**
