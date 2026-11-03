# COM12 U-Boot 只读手动采集手册

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本手册所有命令**只读**，由用户本人在串口（COM12，115200-8-N-1）执行。
本手册不包含任何写 Flash、写 SD、改 U-Boot env、加载位流、写寄存器、重启（除最后一步正常 `boot`）的操作。

## 0. 红线（STRICTLY FORBIDDEN，本手册绝不执行）

- `saveenv`、`setenv <var> <val>` 后接 `saveenv`（**改环境变量并保存**）
- `mmc write`、`fatwrite`、`mmc erase`
- `sf erase`、`sf write`、`sf program`、`sf update`
- `nand erase`、`nand write`
- `fpga load`、`fpga loadb`、`fpga loadmk`（加载位流）
- `mw`（内存写）、`mm`（内存改）、`cp` 写向 Flash/NOR
- 把 `bootcmd`/`loadbit`/`norboot` 等**当探针自动运行**
- 任何 `run bootcmd` 之类（会触发加载/引导副作用）

末尾用正常 `boot` 返回 Linux 是允许的（不改变任何 env、不写任何介质）。

## 1. 进入 U-Boot

1. 串口工具（如 Tera Term / Xshell / PuTTY）连 COM12，参数 **115200 8N1**。
2. 给板上电（或按复位），在看到 U-Boot 倒计时（vendor uEnv `bootdelay=3`）时**立即回车**，停在 `ZynqMP>`（或 `U-Boot>` / 板实际提示符）。
3. 若已进入 Linux，可用 `reboot` 重来（但本阶段不建议频繁 reboot；优先一次进 U-Boot 采完）。

## 2. 先确认命令是否支持（每个命令都要先 `help` 确认）

U-Boot 版本/裁剪不同，命令可能不存在。**执行任何一条命令前，先 `help <cmd>`** 确认它存在且拼写正确。

```
help
help version
help bdinfo
help printenv
help mmc
help part
help fatls
help ext4ls
help sf
help boot
```

若 `help` 显示某命令 `Unknown command`，就在记录里写「该命令不存在」，**不要猜替代命令**。

## 3. 只读采集命令序列（逐步复制到终端，逐条记录输出）

### 3.1 版本与板级信息

```
version
bdinfo
```

### 3.2 环境变量（只读打印，绝不 saveenv）

```
printenv
printenv bootcmd
printenv loadbit
printenv uenvcmd
printenv bootargs
printenv bootdelay
printenv sdboot
printenv norboot
printenv boot_targets
printenv ethaddr
```

> 记录重点：`bootcmd` 是否含 `run loadbit`/`fpga loadb`；`loadbit` 用的设备号/分区号/文件名；
> `uenvcmd` 用的 `fatload mmc 0:X ... Image ... .dtb` 分区号；`bootargs` 的 `root=`。

### 3.3 MMC / SD 设备与分区（只读枚举）

```
mmc list
mmc dev
mmc info
part list mmc 0
```

> `part list mmc 0` 给出 SD 分区表（确认 mmcblk0p1 是 FAT boot、p2 是 ext4 rootfs 的 U-Boot 视角编号）。

### 3.4 启动分区文件清单（只读列目录）

先确认分区文件系统类型（FAT 用 `fatls`，ext4 用 `ext4ls`；用 `help fatls` / `help ext4ls` 确认存在）。

```
fatls mmc 0:1
fatls mmc 0:1 BOOT.bin
fatls mmc 0:1 uEnv.txt
fatls mmc 0:1 download.bit
```

> 记录 BOOT.bin / uEnv.txt / download.bit 是否存在及大小（U-Boot `fatls` 只给大小，不给 SHA；
> SHA 由 Linux 侧 `collect_sd_boot_partition_ro.sh` 采集）。

### 3.5 QSPI Flash 信息（只读探测）

```
sf probe
sf info
```

> `sf probe`/`sf info` 只枚举 Flash 型号/容量，**不擦除不写**。若 `help sf` 显示没有 `sf` 命令则跳过。

### 3.6 返回 Linux

```
boot
```

## 4. 记录模板（把终端输出贴进来）

```
===== COM12 U-Boot 只读采集 =====
[version] ...
[bdinfo] ...
[printenv] ...
[mmc list/info] ...
[part list mmc 0] ...
[fatls mmc 0:1] ...
[sf probe/info] ...
[结束] 正常 boot 返回 Linux
===== 结束 =====
```

## 5. 采集后回答的问题

1. U-Boot 版本/构建信息（`version`/`bdinfo`）。
2. `bootcmd`/`loadbit` 是否含 `fpga loadb`、从哪个分区（mmc 0:1 还是 0:2）载 `download.bit`。
3. `part list mmc 0` 分区表与 Linux `/proc/partitions` 是否一致。
4. QSPI 型号/容量（`sf info`）。
5. 板实际命令是否支持 `fpga loadb`（用 `help fpga` 确认，**只 help 不执行**）。

> 说明：`fpga loadb` 是否支持属于「方案 B 可行性」证据；本手册只用 `help fpga` 查支持情况，
> **绝不实际 `fpga loadb`**（那是部署阶段、用户授权后的事）。
