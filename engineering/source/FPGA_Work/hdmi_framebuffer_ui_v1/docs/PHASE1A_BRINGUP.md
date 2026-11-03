# Phase 1A 上板指南 — PS 写 DDR 静态帧 → PL 读 → 720p HDMI（临时 JTAG 加载）

> 状态：**待你本人执行**。本文只给逐行步骤与判据，**我不碰板、不写 Flash**。
> 一切"上板"结论均待你实测；本文件不构成"已上板"声明。
>
> 分阶段验收：**1A-PL（位流构建）→ 1A-PS（PS 程序）→ 1A-上板（本文）**，任一阶段 FAIL 即停。

---

## 0. 目标与前提

**目标（1A 验收）**：板载 Linux 上的 iCraft 程序把一帧静态 RGB565 写进 PS-DDR 保留区，
把帧基址 `>>3` 写进 `0x40080054`（`frame_ctrl.camera_rd_addr`），PL 侧读该地址并经 720p HDMI
稳定显示 ≥10 分钟，无撕裂/花屏/丢帧。

**前置产物（缺一不可，先确认存在）**：

| 文件 | 由谁产出 | 说明 |
|---|---|---|
| `fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/hdmi_framebuffer_720p_top.bit` | 1A-PL（`build_phase1a.tcl`） | 原始位流，**不上板**，只给 Procise 做输入 |
| `fpga/vivado_prj/.../hdmi_framebuffer_720p_top_disable_icap.bit` | 1A-PL 构建**自动产出**（FMSH 补丁 `write_bitstream_post` 钩子） | **这才是 JTAG 要加载的位流**（缺失才用步骤 2 备用） |
| `sw/phase1a_fb_test.cpp` + `sw/CMakeLists.txt` + `sw/build_on_board.sh` | 1A-PS（已写好） | 板上编译运行 |

**两条硬件红线（与色条上板一致）**：
- **只用临时 JTAG 加载，永不写 Flash。** 断电即还原。
- 加载的是 `*_disable_icap.bit`，**不是**原始 `.bit`。

**位流 SHA-256（2026-10-03 第 4 轮构建）**：
- 原始 `.bit`：`99ec18b6768c6a004211639d588a26c416ce41156e47d517d6c101f9de2eedf5`
- `_disable_icap.bit`（JTAG 加载目标）：`ec162e2d004965ff507987624688d98e4293ba3675695e5526835d5fa1ee12b5`

---

## 1. 接线与上电

复用色条工程的板卡接线结论（已验证）：

| 项目 | 说明 |
|---|---|
| 电源 | 12V DC 接 **J37**，拨 **SW8** 上电 |
| PL JTAG | **20 针 U19**（不是 PS JTAG U18） |
| HDMI | PL 侧 pHDMI 输出口 |
| 串口/网口 | 板载 Linux 的登录通道（沿用官方 demo 的串口或 SSH 方式） |

**指示灯含义（本设计，见 `hdmi_framebuffer_720p_top.sv` 末段）**：

| LED | 引脚 | 含义 | 期望 |
|---|---|---|---|
| led[0] | **J1** | `MMCM1 & MMCM2 & MMCM3 & PS7 PLL` 全部锁定 | **常亮**（时钟树与 PS7 全锁） |
| led[1] | **M6** | `74.25MHz / 2^27 ≈ 0.55Hz` 慢闪 | 约每 1.8 秒翻转一次（像素时钟心跳） |

> 说明：与色条工程（led[0]=MMCM 锁、led[1]≈1Hz）略有不同，本设计 led[0] 多要求 PS7 PLL
> 锁定、led[1] 是 ~0.55Hz。判据以下表为准。

---

## 2. 步骤 1：确认板载 Linux 正常（先做，不依赖 PL 位流）

1. 接好电源/串口(或网口)/HDMI/PL JTAG 后，SW8 上电，等板载 Linux 启动完成。
2. 登录 Linux（沿用官方 demo 的登录方式），确认 shell 可用、`uname -m` 输出 `aarch64`。
3. 确认 iCraft 运行时已装：`ls /usr/lib/aarch64-linux-gnu/libicraft_*.so` 应看到一批 `.so`；
   头文件在 `/usr/include/icraft-xrt`、cmake 包在 `/usr/cmake`。

> 此时板子跑的是它自带的 Linux（PS7 + DDR3 已由板子自身启动流程配好）。本设计**逐字复用**
> 官方 `ps_ai.bd` 的 PS7/DDR3 配置，所以 PL 位流里带的 PS7 配置与板子当前运行的一致，不会改坏 DDR。

---

## 3. 步骤 2（备用）：Procise 手动生成 `_disable_icap.bit`

> **通常无需执行**：1A-PL 构建结束时会由 FMSH 补丁的 `write_bitstream_post` 钩子**自动产出**
> `hdmi_framebuffer_720p_top_disable_icap.bit`（与 `.bit` 同在 impl_1 目录）。仅当该文件缺失时才走本步骤。

在 **Windows 本机**（不是板上）手动生成：

```
cd /d F:\FPGA_Work\hdmi_framebuffer_ui_v1\fpga
call_procise_disable_icap.bat
```

等价于直接调：

```
D:/fudanwei/Procise/bin/procise.exe F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/procise_run_disable_icap.tcl
```

- 脚本内容：`set_device JFMQL30TAI676H` + `increment_bit_cfg_v3 <in.bit> <out_disable_icap.bit> -disable_icap`。
  （FMSH 补丁还会在 `vivado_prj/` 下自动生成同内容的 `procise_run_disable_icap.tcl` + `call_procise_disable_icap.bat`，二者等价。）
- **验收**：出现 `fpga/vivado_prj/.../hdmi_framebuffer_720p_top_disable_icap.bit`。
- 若 Procise 报找不到输入 `.bit`，回到 1A-PL 确认构建已完成（`reports/build_summary.txt` 里有 `BITSTREAM=...`）。

---

## 4. 步骤 3：临时 JTAG 加载（Vivado 2020.2 Hardware Manager）

在 **Windows 本机**，用 Vivado **2020.2**（只用于 Hardware Manager，不碰 2018.3 构建）：

```
D:/Xilinx/Vivado/2020.2/bin/vivado.bat -mode tcl -source F:/FPGA_Work/hdmi_framebuffer_ui_v1/fpga/program_phase1a_jtag.tcl
```

脚本要点（见 `program_phase1a_jtag.tcl`）：
- `connect_hw_server` → `open_hw_target`，JTAG 频率 1MHz。
- 校验：恰 1 个器件，且 `PART == xc7z030`（否则拒绝，防连错板）。
- `program_hw_devices` 加载 `*_disable_icap.bit`，**volatile，无 `-p`，不写 Flash**。

**验收**：脚本打印 `PHASE1A_JTAG_LOAD_COMPLETE`，且板上 **led[0]（J1）常亮**、**led[1]（M6）慢闪**。
此时 HDMI 应已输出画面（尚未写入帧缓冲时可能是底色/复位值对应画面）。

> ⚠️ 若 JTAG 加载导致 Linux 串口断流/崩溃：说明板子自身启动流程在抢占 PL 配置。**先断电 → 重新上电恢复 Linux → 再按"步骤 1 先起来 Linux，再跑本步骤"的顺序重来一次**。位流是易失的，断电后 PL 回到板子默认，无副作用。

---

## 5. 步骤 4：板上编译并运行 PS 测试程序

把 `sw/` 目录拷到板上（scp/串口文件传输/U 盘，任选一种）：

```
scp -r sw <board>:/tmp/phase1a_sw/
ssh <board>
cd /tmp/phase1a_sw
./build_on_board.sh            # 优先 CMake 构建；失败则 ./build_on_board.sh g++
./build_on_board.sh run checker  # 默认棋盘；或 run bars / gradient / red / green / blue
```

**期望输出（逐行）**：

```
[1A-PS] frame_ctrl version   = 0x20230218 (expect 0x20230218)
[1A-PS] 0x40080054 reset      = 0x07e00000 (expect 0x07e00000)
[1A-PS] udma framebuffer phys = 0x...（8 字节对齐、fb>>3 落在 27 位内）
[1A-PS] filled pattern 'checker' into udma buffer
[1A-PS] wrote 0x40080054 = 0x... , read back = 0x...（两者相等）
PHASE1A_PS_PASS fb=0x... fb>>3=0x... pattern=checker
```

- 若 `Device::Open` 报权限错：用 `sudo ./build_on_board.sh run checker` 重试。
- 程序在 `std::cin.get()` 处保持，**保持进程存活**，PL 才会持续显示这一帧。

---

## 6. 验收判据（1A-上板 PASS / FAIL）

**PASS（全部满足才算）**：

1. `PHASE1A_PS_PASS` 打印，且读回值 = 写入值 = `fb>>3`，`fb` 8 字节对齐、`fb>>3` 在 27 位范围。
2. HDMI 显示**稳定静态棋盘**（或所选图案），边界白框、灰格清晰，无花屏/抖动。
3. **连续 ≥10 分钟**画面稳定，无撕裂、无闪烁跳变、无冻屏。
4. 全程 led[0]（J1）常亮、led[1]（M6）慢闪（时钟不丢锁）。

**FAIL（任一即停，记录证据后按第 8 节排查）**：

- 程序打印任一 `[1A-PS] FAIL` 或 `WARN`（版本/复位值不符）。
- 读回 ≠ 写入。
- 屏幕无画面 / 全黑 / 花屏 / 画面滚动错位（地址或时序不对）。
- 显示途中撕裂、丢帧、冻屏（DDR 读带宽或跨时钟域问题）。

**证据收集（PASS/FAIL 都要留）**：程序完整 stdout、屏幕上图案照片/录像（≥10 分钟段）、
led 状态、JTAG 脚本完整输出、`_disable_icap.bit` 的 SHA-256。

---

## 7. 安全回滚

- **任何异常，先断电（SW8 关）再上电**，板子回到它默认启动流程，PL 位流（易失）消失，无 Flash 改动。
- 永不执行任何写 Flash 的命令；本流程全程只有 `program_hw_devices`（volatile）。

---

## 8. 失败排查清单

| 症状 | 最可能原因 | 检查 |
|---|---|---|
| led[0] 不亮 | 时钟树/PS7 PLL 未锁 | 200MHz 晶振 C8/C7、`mmcm*_locked`、PS7 FCLK；JTAG 是否真加载成功 |
| 有画面但颜色/位置错 | `fb>>3` 或 720p 时序 | 程序打印的 `fb`/`fb>>3` 是否合法；`read_len=230400` 是否一致 |
| 撕裂/闪烁 | 单缓冲（本阶段预期之外的抖动） | Phase 1B 才上双缓冲；先确认不是带宽/复位问题 |
| 全黑 | `display_en` / 复位 / HP 读失败 | `frame_ctrl.display_en` 默认 1；`0x40080054` 写对 |
| Device::Open 失败 | 权限 / iCraft 未装 / NPU 参数 | `sudo`；检查 URL `axi://zg330aiu?...` 或退回裸 `axi://zg330aiu` |

> 本阶段（1A）只验收"静态单帧稳定显示"。撕裂/双缓冲是 **Phase 1B**、动态图案与 ≥10 分钟带宽统计是 **Phase 1C**，不要在本阶段提前叠加。
