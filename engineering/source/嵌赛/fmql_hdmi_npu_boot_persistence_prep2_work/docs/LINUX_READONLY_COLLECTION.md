# Linux 只读采集手册（PREP2）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本手册所有命令**只读**，由用户本人在板端串口/SSH（root）执行。不写启动介质、不写 Flash、
不写 FPGA 配置、不加载位流、不改 env、不 kill 进程、不 reboot。

## 0. 前置

1. 把 `scripts/` 复制到板端（如 `/root/fmql_boot_prep2/scripts/`）。
2. 采集全程只读；脚本退出码 0 = 采集完成；任何需写权限的探测一律 SKIP 并记 SKIP。

## 1. 宽口径只读采集（含本次两处修复）

```bash
bash scripts/collect_fmql_boot_state_v2.sh > /tmp/fmql_boot_state_v2_$(date +%s).txt 2>&1
cat /tmp/fmql_boot_state_v2_*.txt
```

覆盖：`/proc/cmdline`、`/proc/mtd`、`/proc/partitions`、`lsblk -f`、`mount`、块设备符号链接、
候选启动/位流文件（含 `/root/bits`、`/` 根下 `download.bit`/`BOOT.bin`/`uEnv.txt`）、
`/sys/class/fpga*`、dmesg 启动记录、`fw_printenv`（仅 `/etc/fw_env.config` 配置有效时）、
systemd 单元、FPGA Manager `name/state/firmware`、驱动模块 `modinfo`、
`/lib/modules/$(uname -r)` 与 `/usr/src` 驱动源码枚举、`frame_ctrl` 版本（devmem 经归一化，
修复 PREP1 的 `0x0x` 双前缀）、udmabuf0 sysfs、UI 进程/socket/日志。

**本版两处修复（对应 PREP1 问题）：**
1. devmem 输出经 `scripts/normalize_devmem_value.sh` 归一化——`20230218`/`0x20230218`/`0X20230218`
   都归一为小写 `0x20230218`，不再出现 `0x0x20230218`。
2. 板端编译器选择用 `scripts/select_cxx.sh`（`g++` → `c++` → `aarch64-linux-gnu-g++`），
   全缺打印 `CXX_NOT_FOUND` 并停止，绝不假装编译成功。

## 2. SD 启动分区只读审计

```bash
bash scripts/collect_sd_boot_partition_ro.sh
cat /tmp/sd_boot_audit_*/result.txt
cat /tmp/sd_boot_audit_*/boot_partition.sha256
```

产物（`/tmp/sd_boot_audit_<epoch>/`）：
`device_info.txt`（设备/父设备/sysfs 双重确认/容量）、`partition_info.txt`（UUID/类型/容量）、
`file_list.txt`（目录树）、`boot_partition.sha256`（源逐文件 SHA）、`backup/`（只读复制出的备份）、
`backup.sha256`（备份逐文件 SHA，用于与源比对）、`SHA256SUMS.txt`、`result.txt`。

安全保证：设备用 `/sys/block/mmcblk0/mmcblk0p1` + `/proc/partitions` 双重确认；已挂载只记录挂载点；
未挂载只用 `mount -o ro`；绝不 remount rw；备份只复制「出」分区，绝不复制「回」；脚本创建的
临时只读挂载在结束（含出错）时 `umount`。

## 3. 只读 MMIO 寄存器采集（A/B 诊断）

```bash
# 板端编译（先选编译器，全缺则停，不假装成功）
CXX="$(bash scripts/select_cxx.sh)" || exit 1
"$CXX" -O2 -o /tmp/read_display_registers_ro scripts/read_display_registers_ro.cpp
# A 侧（重启后黑屏）
/tmp/read_display_registers_ro > /tmp/regs_A.txt 2>&1
# （用户 JTAG 加载工作位流后）B 侧（亮屏）
/tmp/read_display_registers_ro > /tmp/regs_B.txt 2>&1
diff -u /tmp/regs_A.txt /tmp/regs_B.txt || true
```

判定规则见 `docs/DISPLAY_AB_EVIDENCE.md`（PREP1 已交付，此处沿用）：
就绪判据 = 进程存活 + `UI_VERSION_CHECK ... ok=YES` + `UI_FB_READY phys=...`（不是只看 `UI_LIVE_READY`）。

## 4. 采集后核对冻结身份

- 工作位流 `combined_npu_hdmi_disable_icap.bit` SHA256 = `22fec95c64f3db727dd250e5768cdadec82f4c4d2de088392980b95a632932e9`。
- JTAG 加载该位流后：`frame_ctrl 0x4008000C == 0x20230218`、UI `UI_VERSION_CHECK ... ok=YES`、`UI_FB_READY`。
- 这只能证明「JTAG 工作位流可用」，**不能**证明「固化/自动显示已完成」。

## 5. 红线（本手册不包含任何下列操作）

不 `dd` 写 mtd、不 `flashcp`、不 `fpgautil -b`、不写 `/dev/mem`、不写 FPGA Manager `firmware`/`loading`、
不写 `/dev/xdevcfg`、不改 U-Boot env、不 program Flash、不 `systemctl enable/start`、不 reboot、
不 `pkill/killall`、不 `mount -o rw`、不 `cp` 回启动分区。
