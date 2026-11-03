# v3 双缓冲位流 · 构建结果（Phase 1B/1C/2/3 共用）

> 构建时间：2026-10-04（Vivado 2018.3，`build_phase1b.tcl`，含缓冲选择 CDC 修正）。
> **状态：`READY-FOR-HARDWARE-TEST`（构建已通过，未上板）。**

## 1. 时序门（全过）

| 指标 | 值 | 门限 | 结论 |
|---|---|---|---|
| WNS（setup 最差余量） | **+3.427 ns** | ≥ 0 | ✅ PASS |
| WHS（hold 最差余量） | **+0.037 ns** | ≥ 0 | ✅ PASS |
| TNS | 0.000 | = 0 | ✅ PASS |
| THS | 0.000 | = 0 | ✅ PASS |
| 最差 setup 路径 | `rst_sr_reg[0]/C → u_fb_read_720p/u_hdmitx/.../int_rst_reg/PRE` | — | 记录 |
| 最差 hold 路径 | `write_buf/.../wr_pntr_cdc_inst/dest_graysync_ff_reg[1][10]/C → .../dest_out_bin_ff_reg[9]/D` | — | 记录 |

## 2. DRC 门（0 Error，24 Warning 全为无害项）

| 规则 | 严重度 | 条数 | 性质 |
|---|---|---|---|
| REQP-1839（RAMB36 async control） | Warning | 20 | 官方读 FIFO 的 `read_en_r_reg` 带异步复位；复位仅启动时有效，**官方 `video_rect_read_data.v` 固有结构，非本次改动引入** |
| PORTPROP-2（selectio_diff_term） | Warning | 2 | `sys_clk_p/n` 的 DIFF_TERM 被忽略，与 Phase 1A 同源 |
| RTSTAT-10（No routable loads） | Warning | 1 | 相机写路径 tie-off（`write_buf` 满/空等悬空）+ PS7 `S_AXI_HP2_BRESP/RRESP` 未接，**只读设计预期** |
| CHECK-3（rule limit reached） | Warning | 1 | 报表条数上限提示，非违规 |

**结论：DRC 0 Error；24 条 Warning 均为已知无害项，与 Phase 1A 位流同源。**

## 3. CDC / methodology（本轮修正 + 正式豁免）

详见 `docs/CDC_WAIVERS.md`。本轮完成三项**修复**（XDC 打标 + RTL 缓冲选择 1-bit 同步）：

| 项 | 修复前 | 修复后 |
|---|---|---|
| 同步器缺 ASYNC_REG（CDC-2 / TIMING-10） | CDC-2 ×9 | **0**（→ CDC-3 Info） |
| 自生成时钟按名引用（TIMING-28） | ×3 | **0**（改按 pin 引用） |
| 缓冲选择多 bit 跨域（CDC-6） | ×1 | **0**（改 1-bit 双触发同步，见 `CDC_WAIVERS.md` §1.3） |

`report_cdc` 关键计数：CDC-2=0、CDC-5=0、**CDC-6=0**（缓冲选择改 1-bit 同步后消除）、CDC-3 Info=17（含新增 `buf_sel_sync1`）。

剩余 `report_methodology` 11 条（TIMING-9×1、TIMING-24×4、TIMING-27×1、LUTAR-1×1、PDRC-190×4）与 report_cdc 结构性项（CDC-1/7/10/13/15/17）为**全局异步复位 / 准静态配置 / 诊断计数 / 官方 PS7 IP 固有**，无法在不动官方 RTL/IP 的前提下消除，已在 `CDC_WAIVERS.md` 逐条**正式豁免**。

## 4. 位流产物与 SHA-256

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `hdmi_framebuffer_720p_top.bit`（原始，不上板） | 5,980,035 B | `fdc93f10…` |
| `hdmi_framebuffer_720p_top_disable_icap.bit`（**JTAG 加载目标**） | 5,980,619 B | `686bb1e3…` |

路径：`fpga/vivado_prj/hdmi_framebuffer_720p.runs/impl_1/`。
`_disable_icap.bit` 由 FMSH 补丁 `write_bitstream_post` 钩子**自动产出**（无需单独跑 Procise）。

## 5. 本次 RTL 改动（相对 Phase 1A 单缓冲）

`fb_read_720p.sv`：
- `read_addr_1 = camera_rd_addr + 27'd230400`（buffer 1 = buffer 0 + 一帧 720p）
- 端口 `read_buf_index[1:0]` 改为 1-bit `read_buf_sel`；新增 `buf_sel_sync1/2` 双触发同步器（hp_clk 域），`.read_addr_index = {1'b0, buf_sel_sync2}`（bit0=同步后选择，bit1=0，仅 2 缓冲）

`hdmi_framebuffer_720p_top.sv`：
- `camera_wr_addr[0]` 接 `.read_buf_sel`（缓冲选择 bit0 跨域，PS 写 `0x40080050` 每帧翻转）

**冻结不动**：720p HDMI 时序、TMDS 引脚、时钟链（200→27→74.25/371.25）、`ps_ai.bd` PS7/DDR3 配置、官方 `frame_fifo_read.v`（帧起始锁存保留）。

## 6. 本次约束改动（CDC 修正）

`fpga/constrs/hdmi_framebuffer_720p.xdc`：
- `set_clock_groups` 改为按 pin 引用（消除 TIMING-28）
- 对 22 个同步器寄存器加 `set_property ASYNC_REG TRUE`（消除 CDC-2/CDC-5/TIMING-10；`read_addr_index_d0/d1` 已同域故移出，新增 `buf_sel_sync1/2`）
- 其余 CDC/methodology 警告在 `docs/CDC_WAIVERS.md` 书面豁免
