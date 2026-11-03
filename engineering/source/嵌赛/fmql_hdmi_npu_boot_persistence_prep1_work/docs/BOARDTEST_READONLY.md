# 只读板端核验手册（任务 §六）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
本手册所有命令**只读**，由用户本人在串口/SSH 执行。不含任何 Flash/FPGA 写、加载、重启、kill。

## 0. 前置

- 已把 `scripts/` 复制到板端（如 `/root/fmql_boot_prep1/`）。
- 采集全程只读；脚本退出码 0 = 采集完成；任何需写权限的探测一律 SKIP 并记 SKIP。

## 1. 宽口径只读采集

```bash
bash scripts/collect_fmql_boot_state.sh > /tmp/fmql_boot_state_$(date +%s).txt 2>&1
cat /tmp/fmql_boot_state_*.txt
```

覆盖：`/proc/cmdline`、`/proc/mtd`、`/proc/partitions`、`mount`、块设备符号链接、候选启动/位流文件（含 `/root/bits`、`/` 根下的 `download.bit`/`BOOT.bin`）、`/sys/class/fpga*`、dmesg 启动记录、systemd 单元、`printenv`（若 U-Boot 工具可用）、fpga_manager name/state、udmabuf0 sysfs、UI 进程/socket/日志。

**关键确认项**（来自采集输出）：
1. 板实际 U-Boot `bootcmd` / `loadbit` / `uenvcmd`（是否含 `fpga loadb`、分区映射）。
2. 板当前 BOOT.bin / download.bit 是否存在及 SHA。
3. 板从 SD 还是 QSPI 启动（`/proc/cmdline` root= + dmesg qspi）。
4. secure boot 迹象（BOOT.bin 头加密字，若有工具）。

## 2. 只读 MMIO 寄存器采集（A/B 诊断）

```bash
# 编译（板端，一次）
aarch64-linux-gnu-g++ -O2 -o read_display_registers_ro scripts/read_display_registers_ro.cpp
# A 侧（重启后黑屏）
./read_display_registers_ro > /tmp/regs_A.txt 2>&1
# （用户 JTAG 加载工作位流后）
# B 侧（亮屏）
./read_display_registers_ro > /tmp/regs_B.txt 2>&1
diff -u /tmp/regs_A.txt /tmp/regs_B.txt || true
```

见 `docs/DISPLAY_AB_EVIDENCE.md` 的判定规则。

## 3. UI 就绪判据（只读观察，非安装）

手动前台启动 UI（**不重配 FPGA**），观察 stdout 标记：

```bash
/opt/sdr/bin/board_ui_live_rml23 --sock=/run/sdr_amr_ui_rml23.sock --ctl-sock=/run/sdr_amr_control_rml23.sock
```

成功 = 进程存活 + `UI_VERSION_CHECK ... ok=YES` + `UI_FB_READY phys=...`（不是只看 `UI_LIVE_READY`）。

## 4. 红线

- 不 `dd` 写 mtd、不 `flashcp`、不 `fpgautil -b`、不写 `/dev/mem`、不写 FPGA Manager firmware/loading、不写 `/dev/xdevcfg`、不改 U-Boot env、不 program Flash、不 enable systemd、不重启、不 killall/pkill。
- 本手册不包含任何上述操作。
