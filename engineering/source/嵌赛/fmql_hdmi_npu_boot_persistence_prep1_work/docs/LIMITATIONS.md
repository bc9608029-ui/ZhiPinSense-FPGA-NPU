# 限制与证据缺口（诚实标注）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
本文件列出所有「离线无法完成 / 未证实」项，禁止任何后续把「未证实」当「已证实」的写法。

## 1. 候选 BOOT.bin 无法离线生成（方案 A 核心限制）

- **Procise 是闭源 GUI**（`FMSH_Procise_2025.1.1….exe`，未安装；「Create Image」是 GUI 操作）。
- **`.bif` 未取得**：位于 `F:\嵌赛\2026嵌赛FPGA开发\BOOT_Gen.rar`（`7030ai_psin.bif`），本地无 7z/unrar，无法解压。
- **板实际 FSBL 未采集**：vendor 参考 FSBL `FSBL251210_ddr400_demo.out`（SHA `5501c470…`）未必是板实际版本。
- 因此：本任务**没有、也不声称生成** BOOT.bin。只交付「输入物（.bit + vendor 参考组件）+ 配方 + 只读校验脚本」。

## 2. 板端未采集的事实（写板前必须补）

1. 板实际 U-Boot `printenv`（bootcmd / loadbit / uenvcmd / 分区映射）。
2. 板当前 SD FAT 分区（mmcblk0p1）内的 BOOT.bin 内容与 SHA；rootfs 根下是否有 `download.bit`、`/root/bits`。
3. 板实际启动设备（MIO3~MIO5 跳线：SD 还是 QSPI）。
4. 板端 secure boot 是否启用（vendor BOOT.bin 加密字=0，仅证明 vendor 镜像未加密，不证明板端设置）。
5. 板端 FMSH FPGA Manager Linux 驱动接受的镜像格式（本地无驱动源码）。
6. QSPI mtd0/mtd1 的实际角色（是否承载第二启动路径）。

## 3. 未暴露寄存器无法定位

HDMI/VTC enable、分辨率/同步参数、MMCM/PLL lock、HDMI reset/disable、DMA 读帧状态的具体 MMIO 偏移未随附到本工作树；`read_display_registers_ro` 只读「已确认寄存器 + 已知 sysfs」，不猜测未知偏移。若 A/B 两侧可见寄存器一致但物理输出不同，必须写「可能是未暴露的 PLL、复位、PHY、I2C HDMI 芯片或 JTAG 重配置副作用」。

## 4. 位流内部 NPU/DMA 微观结构无法离线核验

- 地址图 / 寄存器契约层面：已核验一致（`results/bitstream_identity.json`）。
- 位级 NPU 网表 / DMA 微观结构：无法离线核验（需重新跑 Vivado/Procise 综合实现后逐字节比对，或拿设计 DCP）。RTL 来源锚定于 `SOURCE_PROVENANCE_SHA256.txt`。

## 5. 主机侧无法实跑的项

- `read_display_registers_ro.cpp` 无法在 Windows 对 `/dev/mem` 实跑；**主机无任何 C/C++ 编译器（g++/gcc/clang/cl 均缺失）**，故 g++ 语法编译检查也未执行。已用 Python 静态检查代替：剥注释后 `{}`/`()`/`[]` 括号配平、`O_RDONLY`/`PROT_READ`/`mmap`/`munmap`/`/dev/mem` 存在、无 `PROT_WRITE`。板端或交叉环境编译是未来用户步骤。
- aarch64 交叉编译未执行（主机无 aarch64 工具链验证）；板端 C++ 工具需板端或交叉环境编译。
- 所有 systemd 单元为**模板**，未安装、未 enable、未跑进程生命周期（host_tests 只做静态+模拟校验）。

## 6. 不得写的状态

最高只写 `FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP1-OFFLINE-EVIDENCE-COMPLETE`。
**不写** BOARD_PASS / BOOT_PASS / AUTO_DISPLAY_PASS / PROJECT_COMPLETE。
「开机自动显示通过」只能在用户完成备份、实际部署并**至少三次完整断电重启验证**后由用户确认。
