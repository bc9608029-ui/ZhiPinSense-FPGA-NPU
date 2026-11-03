# 启动模式证据（MIO3~MIO5 / boot-mode）

状态令牌：`FMQL30TAI-HDMI-NPU-BOOT-PERSISTENCE-PREP2-BOARD-EVIDENCE-COLLECTION-READY`。
本文件只记录「本地权威文档里找得到的」内容；找不到的一律 `UNCONFIRMED`，不猜寄存器地址。

## 1. 权威本地文档能找到的（逐条给文档名 + 页码 + 原文含义）

来源文档（已转文本，见 PREP1 `_evidence/vendor_docs/`）：

1. **《悟净开发板Lite（轻量版）硬件使用手册V1.0.pdf》§4.2 配置加载模式**
   - 对应 PDF 第 **10 页**（§4.2 正文，目录亦标注 §4.2 在第 10 页）+ 第 **11 页**（PCB/实物跳线帽图）。
   - 原文含义（文本可提取部分）：
     - 板上支持 **JTAG 启动加载、QSPI Flash 加载、SD 卡加载** 三种启动设备，通过**跳线帽**选择。
     - **MIO2** 上下拉决定开发模式是**级联模式还是独立模式**；
     - **MIO3~MIO5** 的组合决定**启动加载模式**；
     - **MIO6** 上下拉决定 **PLL 是否 Bypass**；
     - **MIO7/MIO8** 上下拉决定 **Bank500 和 Bank501 的电压**。
2. **《悟净开发板硬件使用手册V1.0_嵌赛.pdf》（full）§4.2 配置加载模式**：同样第 10/11 页，文字完全一致。

## 2. 找不到的（诚实标注）

- **MIO3~MIO5 组合 → 具体启动设备（JTAG/QSPI/SD）的真值表，本地文本证据中不存在**。
  两份手册里该真值表是 PDF 中的**图片**（`具体的模式配置和选型如下表所示` 后面是表图 + 第 11 页 PCB 跳线图），
  文本转储无法读到图片内容。因此 **具体的 8 种 MIO3~MIO5 组合映射 = `UNCONFIRMED`**。
- **板载 dip/电阻/跳线帽的「当前实际位置 → 启动设备」映射**：本地没有板实物照片或原理图标注可核对，
  = `UNCONFIRMED`。
- **文档记录的只读 boot-state 寄存器**：本地**没有任何 FMSH 文档给出** BootROM/BOOT_MODE 状态寄存器的地址。
  （FMQL30TAI 对标 xc7z030；Xilinx 同类芯片的 SLCR BOOT_MODE 寄存器地址是 Xilinx 知识，**不是** FMSH 权威证据，
  本文件**不使用也不猜测**任何寄存器地址。）

## 3. 不直接下结论的间接证据（Linux 侧，PREP1 板端采集）

- `/proc/cmdline`：`root=/dev/mmcblk0p2`（Linux rootfs 在 SD 分区 2）→ **Linux 从 SD 启动**，但这**不直接证明** BootROM 的启动源是 SD。
- dmesg：`cadence-qspi e0000000.spi: n25q256a (32768 Kbytes)` → QSPI 存在；`/proc/mtd` 有 mtd0 "bootloader"(4MiB)/mtd1 "kernel"(16MiB)/mtd2 "rootfs"(0)。
- vendor uEnv 有 `norboot=... cp.b 0xE2100000 ... bootm`（NOR/QSPI 侧可能遗留另一套启动路径）。
- 综合：**启动源（SD vs QSPI）目前无法从本地证据唯一确定**，必须由用户板端采集（见下）。

## 4. 需要用户提供/板端采集的证据（不做自动判定）

1. **Boot-DIP/跳线帽实物照片**（重点拍 MIO3~MIO5 附近的跳线帽/拨码），或用户手动读出 MIO3/MIO4/MIO5 各自是拉高还是拉低。
2. **U-Boot `printenv`**（见 `docs/COM12_UBOOT_READONLY.md`）：`bootcmd`/`loadbit`/`sdboot`/`norboot`/`boot_targets` 实际内容，用于判断默认启动路径。
3. 若用户能提供 **FMSH JFMQL30TAI 芯片用户手册/数据手册**（本地未找到），并其中给出：
   - MIO3~MIO5 真值表；或
   - 只读 boot-mode 状态寄存器地址（**必须有文档页号，才可读；否则不读**）——
   则据实补记到本文件。

## 5. 结论

- 权威结论（已确认）：**启动设备由 MIO3~MIO5 跳线选择，可选 JTAG/QSPI/SD**（两份手册 §4.2 第 10 页，文字确认）。
- 具体映射表 + 板上当前配置：**`UNCONFIRMED`**，等待用户 Boot-DIP 照片/手动读数。
- 只读 boot-state 寄存器：**本地无权威文档给地址 → 不读取、不猜测**。
