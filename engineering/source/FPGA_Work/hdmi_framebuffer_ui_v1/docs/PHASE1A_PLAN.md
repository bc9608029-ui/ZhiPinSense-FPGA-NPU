# Phase 1A 计划 — PS 写 DDR 静态帧 → PL 读 → 720p HDMI

> 状态：**计划定稿（侦察完成）**。本文件是 Phase 1A 的实现蓝图，所有结论均可追溯源码。
> 分阶段验收：**1A-PL（位流构建）→ 1A-PS（PS 测试程序）→ 1A-上板**，每阶段输出 PASS/FAIL 与证据，失败即停。

---

## 0. 侦察结论（本轮新确认，补齐 PHASE0_AUDIT 的"待确认"项）

### 0.1 显示帧缓冲读取路径 = PS DDR，经 **HP2_1** 端口（不再待确认）

证据链（全部源码行号）：
- `ps_ai_peripheral.sv:850` `frame_to_ps_largebuf frame_to_ps_inst0(...)`，
  其 `m00_axi_*` 主端口连到 `S_AXI_HP2_*`（行 867-914）。
- `ps_ai_peripheral.sv:1336` `ps_ai_wrapper` 实例化 `.S_AXI_HP2_1_* (S_AXI_HP2_*)`：
  即 `frame_to_ps_largebuf` 内的 `aq_axi_master` 经 **PS7 的 `S_AXI_HP2_1` 高带宽从端口**读 **PS DDR**。

> 因此 **Phase 1 的 DDR 是 PS DDR（PS7 内 DDR3 控制器），不是 PL 侧 MIG。**

### 0.2 官方设计有两套 DDR，勿混用

| DDR | 控制器 | 顶层引脚 | 位宽 | 用途 |
|---|---|---|---|---|
| **PS DDR3** | PS7 内 DDR 控制器（复用对象） | `FIXED_IO_0_*` + `DDR_0_*` | 32-bit，MT41K256M16 RE-125 | Linux/PS + PL 经 HP 访问；**显示帧缓冲在此** |
| **PL DDR3** | `mig_ddr3_u0`（`mig_7series_0`，`ps_ai_peripheral.sv:1815`） | `ddr3_*`（独立 64-bit） | 64-bit | NPU(BUYI AI) 专用，原生 `app_*` 接口 |

**Phase 1A 只复用 PS DDR3，不碰 `mig_ddr3_u0`。**

### 0.3 寄存器 0x40080054 与控制路径（已在 PHASE0_AUDIT 确认，此处固化）

- `0x40080054 = frame_ctrl.slv_reg21 = camera_rd_addr`，写"帧缓冲字节地址 >> 3"（27 位有效，8 字节对齐）。
- 地址链：`camera_rd_addr[26:0] → rd_burst_addr → {rd_burst_addr,3'd0} → M_AXI_ARADDR`（字节地址）。
- `frame_ctrl` 是 AXI-Lite 从设备，时钟 `gp_clk`（50M），PS 经 GP 主端口（官方经 `User_GP0`）访问，基址 `0x40080000`。

### 0.4 PS 侧运行环境 = 板载 Linux + iCraft 运行时（关键，解决了"裸机还是 Linux"）

- 官方应用 `hdmi_display.hpp` 用 `device_.defaultRegRegion().write(0x40080054, chunk->begin.addr() >> 3)`、
  `display_chunk_` 来自 iCraft `getMemRegion("udma").malloc(...)`——**iCraft 的 malloc 直接返回物理地址**（"udma" 区 = PS-DDR 保留池，**不是** PL-DDR 的 `defaultMemRegion` 区）。
- 板上 Linux 无 DRM/fbdev（`fmqlmp-verify.dtb`），但冒烟程序在板上用 `g++ -std=gnu++17` 直接编译、链接 iCraft。
- **结论**：Phase 1A 的 PS 测试程序 = 一个精简版 iCraft C++ 程序（`Device::Open` → `getMemRegion("udma").malloc(W*H*2)` → 写 RGB565 静态帧 → `defaultRegRegion().write(0x40080054, addr>>3)` → 保持显示）。**在板上编译运行**，不依赖 Docker 交叉编译。

### 0.5 复用/构建环境（沿用已验证色条工程的结论）

- Vivado **2018.3**（`D:\Xilinx2018.3\Vivado\2018.3`）真实构建；2020.2 仅 Hardware Manager。
- FMSH 补丁：`source $JFM_PATH/ip_patch/run.tcl` + `add_hook_tcl_to_prj`，`JFM_PATH=D:/FMSH/JFM_Kits`（正斜杠）。
- 器件 `xc7z030ffg676-2`；FMSH IP 仓库 = 官方 `PS_AI IP` 目录（`processing_system7:5.5` 等）。

---

## 1. Phase 1A 架构

```
板载 Linux + iCraft
   │  write(0x40080054, fb>>3)      write RGB565 静态帧到 PS DDR
   ▼
PS7（复用官方 ps_ai.bd：PS DDR3 配置 + HP0-3/HP2_1 + GP 主端口 + AI 控制 IP，全部官方原样）
   │   GP0 ──────────────► frame_ctrl (AXI-Lite @0x40080000, slv_reg21=camera_rd_addr)
   │   S_AXI_HP2_1 ◄────── aq_axi_master（64-bit 读 PS DDR）
   ▼
frame_read_write_largebuf（64→16bit RGB565 拆包 + 4 缓冲 read_addr_0..3 + VTC 时序）
   │  RGB888 + de/hs/vs @ 74.25MHz
   ▼
uihdmitx / TMDSEncoder / oserdese2_10to1（复用色条已验证 TMDS 链，引脚 AC17/AA15/Y16/W16 TMDS_33）
```

**时钟**（色条已验证）：200MHz 板上晶振 `sys_clk_p/n` → MMCM1 27MHz → MMCM2 74.25MHz(像素)+371.25MHz(TMDS×5)。

**时钟树（本轮侦察补齐，全部源码可证）**：
- PS7 `FCLK_CLK0` = **50 MHz**（`clk_wiz_0.xci` 的 `CLKIN1_PERIOD=20.000ns`）。
- `ps_ai_wrapper` 内部 `clk_wiz_0`：FCLK_CLK0 → `gp_axi_aclk`=**100MHz** + `clk_200mhz`=**200MHz**（`.xci` `CLKOUT1=100/CLKOUT2=200`）。
- `gp_clk = ps_clk_out = gp_axi_aclk = 100MHz`（`ps_ai_wrapper.sv:486` + `demo_clkrst_wrapper.v:51`）。
- `hp_clk`（HP 口时钟）= 官方用 `ddr_clk`（MIG ui_clk）。Phase 1A 无 MIG，**自建 MMCM3：200MHz→100MHz** 作 `hp_clk`，独立于 PS7 上电顺序。
- `frame_read_write_largebuf`：`mem_clk=hp_clk`，`read_clk=cam_clk(74.25)`，内部异步 FIFO；`read_req/read_req_ack` 握手在 mem_clk 域，经 `level_cross`（2/3 级同步）跨到 cam_clk 域。
- `aq_axi_master`（1-bit ID/8-bit LEN/32-bit ADDR/64-bit DATA）↔ `S_AXI_HP2_1`（5-bit ID/4-bit LEN）需宽度适配（ID 补 0、LEN 截断、WID=0、USER 悬空）。
- 读地址链（官方原样）：`camera_rd_addr[26:0] → rd_burst_addr → RD_ADRS={rd_burst_addr,3'd0} → M_AXI_ARADDR`。
- `read_len`：1080p=`27'd518400`；**720p=`27'd230400`**（1280×720×16/64）。
- `frame_ctrl` 关键默认值：`camera_rd_addr=27'h7E0_0000`(0x54)、`frame_ctrl_ver=32'h20230218`(0x0C)、`display_en=~disable_hdmi_2` 默认**=1 使能**、`soft_rst=0`。

---

## 2. 文件清单（复用 vs 新建）

### 2.1 复用（逐字，不改）
| 文件 | 来源 | 用途 |
|---|---|---|
| `ps_ai.bd`（及其生成物 `ps_ai_wrapper`） | `fpai_demo_fpga/.../sources_1/bd/ps_ai/` | **PS7 + DDR3 配置 + HP/GP + AI 控制**（指令 #1 强制复用，不手填 DDR 参数） |
| `rtl/ps_ai_wrapper.sv` | `fpai_demo_fpga/rtl/` | FMSH 手写 wrapper（实例化 BD 核心 `ps_ai`，正确暴露 HP2_1/GP/AI 端口） |
| `frame_ctrl.v` | `fpai_demo_fpga/rtl/display/` | **标准 AXI-Lite 从设备**（无 mna_gp 依赖），基址 0x40080000，含 0x40080054；依赖 pulse_cross_camera / bridge_s / level_cross（跨时钟握手） |
| `frame_read_write_largebuf.v` | 同上 | DDR 读 + RGB565 拆包 + **4 缓冲**（read_addr_0..3 + index）；干净 FIFO 接口 |
| `aq_axi_master.v` | 同上 | 64-bit AXI 主设备（读 DDR，连 HP2_1） |
| `pulse_cross_camera.v` / `bridge_s.v` | 同上 | frame_ctrl 的跨时钟脉冲/握手依赖（合成时发现缺失，已补） |
| `frame_fifo_read.v` / `frame_fifo_write.v` | 同上 | `frame_read_write_largebuf` 的突发读写状态机依赖（合成时确认需要，已补） |
| `afifo_16i_64o_largebuf` / `fifo_1` / `afifo_64i_16o_128`（IP XCI） | 同上 | `frame_read_write_largebuf` 的 FIFO IP 依赖 |
| `uihdmitx.v` / `TMDSEncoder.vhd` / `oserdese2_10to1.v` / `video_define.v` | `hdmi_board_bringup_v1/fpga/rtl/` | 720p TMDS 发送（已上板验证） |
| 相关 FMSH AI 控制 RTL（BD 内 IP） | `ps_ai.bd` 自动生成 | 随 BD 复用 |

> **不复用 `frame_trans.sv` / `frame_to_ps_largebuf.v`**：前者引入 FMSH 私有 `mna_gp_ww_itf` + `mna_gp2axi` + 摄像头 resize→NPU 通路，后者耦合相机写路径与 1080p VTC。改为直接复用其内部**干净的标准 AXI-Lite `frame_ctrl` + `frame_read_write_largebuf`（含 4 缓冲）+ `aq_axi_master`**，读控制与 720p 时序自写（见下）。

### 2.2 新建
| 文件 | 说明 |
|---|---|
| `hdmi_framebuffer_720p_top.sv` | 顶层：实例化 `ps_ai_wrapper` + `frame_ctrl` + `fb_read_720p` + `frame_read_write_largebuf` + `aq_axi_master` + MMCM + TMDS 链；绑 DDR/FIXED_IO/HDMI/时钟/复位/led |
| `fb_read_720p.sv` | **新写**：720p 时序(74.25MHz) + 读控制（驱动 frame_read_write_largebuf 的 read_req/read_len/read_addr_index/read_en）+ RGB565→RGB888；一个缓冲基址 = `frame_ctrl.camera_rd_addr` |
| `constrs/hdmi_framebuffer_720p.xdc` | HDMI 引脚 + sys_clk(200M) + sys_rst + led（复用色条 xdc 的引脚值）；DDR/FIXED_IO 引脚由 PS7 IP 自动约束 |
| `build_phase1a.tcl` | Vivado 2018.3 构建脚本（参考色条 `build_hdmi_colorbar_720p.tcl`，增加 BD 导入 + `ip_repo_paths` + PS7） |
| `sw/phase1a_fb_test.cpp` | PS 侧 iCraft 测试程序（写静态 RGB565 + 写 0x40080054） |
| `sw/build_on_board.sh` / `README` | 板上编译 + 运行说明 |
| `fpga/procise_run_disable_icap.tcl` / `call_procise_disable_icap.bat` | Procise 生成 `*_disable_icap.bit`（临时 JTAG 加载用，**不写 Flash**） |
| `fpga/program_phase1a_jtag.tcl` | Vivado 2020.2 HW Manager 临时 JTAG 加载脚本（器件校验 `PART==xc7z030`） |
| `docs/PHASE1A_BRINGUP.md` | 1A-上板逐步指南（接线/上电/Procise/JTAG/运行/验收/回滚） |

---

## 3. 构建流程（1A-PL）

1. 新建工程目录 `F:\FPGA_Work\hdmi_framebuffer_ui_v1\fpga\`，拷贝复用 RTL 与 BD。
2. `build_phase1a.tcl` 要点：
   - `set_property ip_repo_paths {官方 PS_AI IP 目录}`（解析 `processing_system7:5.5`）。
   - `create_project ... -part xc7z030ffg676-2`。
   - 导入 `ps_ai.bd` → `generate_target all` → 生成 wrapper（`ps_ai_wrapper`）。
   - 添加复用 RTL + 顶层 + xdc。
   - `source $JFM_PATH/ip_patch/run.tcl` + `add_hook_tcl_to_prj`。
   - synth → impl(route) → 时序门（WNS≥0/WHS≥0）→ DRC(0 Error) → write_bitstream → `_disable_icap.bit`。
3. **验收门（1A-PL PASS 条件）**：synth/impl 完成、WNS≥0、TNS=0、WHS≥0、THS=0、DRC 0 Error、位流 + `_disable_icap.bit` 产出、SHA-256 记录。

---

## 4. PS 测试程序（1A-PS）

- `phase1a_fb_test.cpp`（iCraft，板上 `g++ -std=gnu++17` 编译）：
  1. `Device::Open` → `defaultRegRegion()` 读回 `0x40080054`（复位值 `0x7E0_0000`）与版本寄存器。
  2. `getMemRegion("udma").malloc(1280*720*2, false)` 得物理地址 `fb`（PS-DDR 保留区；**不用** `defaultMemRegion()`——那是 PL-DDR）。
  3. 填静态 RGB565 测试帧（红/绿/蓝/棋盘/计数等可切换，默认棋盘）。
  4. 校验 `fb` 8 字节对齐、`fb>>3` 在 27 位范围。
  5. `write(0x40080054, fb>>3)`，再**回读确认**写入值。
  6. 打印 `PHASE1A_PS_PASS`（地址/对齐/回读全正确）。
- **验收门（1A-PS）**：读回值 = 写入值 = `fb>>3`，8 字节对齐，范围合法；屏幕显示对应静态帧。

---

## 5. 分阶段验收与边界声明

| 阶段 | 我做什么 | 我不做什么 |
|---|---|---|
| 1A-PL | 真实 Vivado 2018.3 构建，出位流 + 报告 + SHA | 不写 Flash、不碰板 |
| 1A-PS | 写测试程序 + 板上编译命令 + 逐步指南 | 不代你上板 |
| 1A-上板 | 给逐行临时 JTAG 加载步骤 | 你本人执行 |

- 所有"上板"结论待你本人实测；本报告**不构成已上板声明**。
- 失败即停：1A-PL 任一验收门不过 → 停并报最差路径，不改冻结 RTL。

---

## 6. 风险与实现时需对齐的细节

1. **BD 生成**：`ps_ai.bd` 需 `ip_repo_paths` 指向 FMSH `PS_AI IP`；`generate_target` 需在补丁前完成。实现时用官方 `.xpr` 的 `IPRepoPath` 做对照。
2. **AI 端口处理**：`ps_ai_wrapper` 暴露大量 NPU/AI 端口（`pl_araddr/awaddr`、`AI_HP/AI_GP`、`BYolo_GP*`、`User_GP1`、`PJTAG` 等）。Phase 1A 只接 `DDR/FIXED_IO + GP0 + S_AXI_HP2_1 + 时钟/复位`，其余 tie-off；不实例化 NPU/SDI/MIG。
3. **HP/GP 时钟频率**：对齐官方（`gp_clk`=50M、`hp_clk` 频率待核对官方 clk_wiz 输出），实现时确认。
4. **地址映射**：`0x40080000` 段必须仍在 BD 地址映射中（复用 BD 即自动保留），实现时回读确认。
5. **缓存一致性**：iCraft `malloc` 的 DMA 区是否 uncached、写后是否需 flush——实现时以官方 `hdmi_display` 用法为准（官方直接 write 未显式 flush，说明该区为设备一致性/uncached 路径）。
