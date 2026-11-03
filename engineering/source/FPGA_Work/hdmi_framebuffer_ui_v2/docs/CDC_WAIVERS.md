# CDC / Methodology 警告：解决与正式豁免记录

> 日期：2026-10-04
> 范围：`hdmi_framebuffer_720p_top`（Phase 1B v3：双缓冲位流 + 缓冲选择 CDC 修正）
> 工具：Vivado 2018.3（`D:\Xilinx2018.3`）
> 结论：**可修的 CDC/methodology 项已全部「解决」，其余项「正式豁免」**。修复通过 XDC 约束属性完成（不改 RTL）；豁免以本文档为权威记录（`set_msg_config -new_severity INFO` 经实测不影响 2018.3 的 `report_methodology` 输出，故不采用工具内降级，改为逐条书面豁免）。

---

## 0. 时钟域总览（report_clocks 实测）

| 时钟 | 周期 | 来源 | 用途 |
|---|---|---|---|
| `sys_clk_p` | 5.000ns | 200MHz 晶振（C8/C7） | 全片参考 |
| `clk_27m` | 37.037ns | MMCM1（200→27） | 中间 |
| `clk_74m25` | 13.468ns | MMCM2 CLKOUT0（27→74.25） | **像素/HDMI 域** |
| `clk_371m25` | 2.694ns | MMCM2 CLKOUT1 | TMDS x5 串行 |
| `clk_100m` | 10.000ns | MMCM3 CLKOUT0（200→100） | **读通路 hp_clk 域** |
| `clk_fpga_0` | 20.000ns | PS7 FCLKCLK[0]（50MHz） | PS7 |
| `clk_out1_clk_wiz_0` | 10.000ns | clk_wiz_0（PS7 50M→100M） | **寄存器 gp_clk 域** |

三组互异步时钟：`clk_out1_clk_wiz_0`（PS7 PLL 源）、`clk_74m25`（晶振经 MMCM1→MMCM2）、`clk_100m`（晶振经 MMCM3）。`report_clock_interaction` 显示 6 条跨组路径全部 `Ignored / Asynchronous Groups`，**无时序违例**。

---

## 1. 修复项（已在 XDC 中「解决」）

### 1.1 TIMING-10 / CDC-2 / CDC-5 —— 同步器缺 `ASYNC_REG`
**现象**：`level_cross`、`bridge_s`、`disable_hdmi`、`rst_gp/hp` 复位同步都是正规 2/3-FF 同步器，但未加 `ASYNC_REG`，被 report_cdc 记为 CDC-2（9 条）/ CDC-5（1 条）。

**处理**：在 `hdmi_framebuffer_720p.xdc` 中用**单条** `set_property ASYNC_REG TRUE [get_cells -quiet {...}]` 给 22 个同步寄存器打标（含 1.3 新增的 `buf_sel_sync1/2`）。**不改官方 FMSH RTL**（level_cross.v / bridge_s.v / frame_ctrl.v 保持原样）。

> 实现要点（实测确认）：XDC 约束文件**不接受** `foreach`、`set_msg_config` 等控制/消息命令（`Designutils 20-1307`）；`get_cells -hier` 把参数当**叶子名**匹配、带 `/` 的完整路径匹配不到，故用**不带 `-hier` 的完整层级路径**。全部 22 个 cell 已在已布线网表上离线验证逐一命中。

**效果（重建实测）**：CDC-2（9→0）、TIMING-10（1→0）；1-bit 同步器全部转为 CDC-3（Info，已带 ASYNC_REG）。原 2-bit `read_addr_index[1:0]` 跨域已在 **RTL 层解决（见 1.3）**：改为 1-bit 双触发同步后 `read_addr_index_d0/d1` 变同域，**CDC-6 消失**。

### 1.2 TIMING-28 —— 自生成时钟按名引用
**现象**：`set_clock_groups` 按名字引用 `clk_100m/clk_74m25/clk_out1_clk_wiz_0`（3 条）。

**处理**：改为按 pin 引用（正是 Vivado 建议写法，pin 名逐字取自 report_clocks.rpt）：
```tcl
set_clock_groups -asynchronous \
    -group [get_clocks -of_objects [get_pins u_mmcm_200_100/CLKOUT0]] \
    -group [get_clocks -of_objects [get_pins u_mmcm_27_742/CLKOUT0]] \
    -group [get_clocks -of_objects [get_pins u_ps_ai_wrapper/clk_wiz_0_inst/inst/plle2_adv_inst/CLKOUT0]]
```

**效果**：TIMING-28 消除（3→0）。

### 1.3 缓冲选择 CDC —— `camera_wr_addr[0]` 每帧翻转，改为 1-bit 双触发同步
**纠正**：早期记录（本文件 2.3/2.6 旧版）曾把 `camera_wr_addr[1:0] → read_addr_index` 当成“准静态配置（初始化只写一次）”，**这是错的**。双缓冲乒乓切换时，PS **每帧**重写 `camera_wr_addr` 的缓冲选择位，它是**准周期翻转信号**，不是准静态信号；2-bit 多 bit 跨域存在采偏/错位风险，必须按真实翻转信号处理。

**处理（本次重建）**：在 `fb_read_720p.sv` 内做 1-bit 双触发同步，**只让 bit0 跨域**，bit1 固定为 0（本设计只有 2 个缓冲）：
```systemverilog
reg buf_sel_sync1, buf_sel_sync2;           // hp_clk 域 2-FF 同步器
always @(posedge hp_clk or posedge rst_hp) begin
    if (rst_hp)       {buf_sel_sync1, buf_sel_sync2} <= 2'b0;
    else begin
        buf_sel_sync1 <= read_buf_sel;      // read_buf_sel = camera_wr_addr[0] (gp_clk)
        buf_sel_sync2 <= buf_sel_sync1;
    end
end
...
.read_addr_index ({1'b0, buf_sel_sync2}),   // bit0=同步后的选择，bit1=0
```
- 顶层改接 `.read_buf_sel (camera_wr_addr[0])`，`fb_read_720p` 端口由 2-bit 改为 1-bit。
- `buf_sel_sync1/2` 已纳入 XDC 的 `ASYNC_REG` 列表（见 1.1，22 个 cell 之二）。
- 同步后的值仍由官方 `frame_fifo_read` 的 **S_ACK 状态在帧起始锁存**（`read_addr_index_d1 → rd_burst_addr`），帧中重写不会撕裂在飞帧。官方 `frame_fifo_read.v` **未改动**。
- 由于 `read_addr_index[1:0] = {1'b0, buf_sel_sync2}` 现在是 hp_clk 同域信号，`frame_fifo_read` 内的 `read_addr_index_d0/d1` 两拍同步器成为同域冗余（保留不改官方 RTL），**不再构成跨域**。

**效果**：多 bit 跨域消除 → **CDC-6 消失**；`buf_sel_sync1/2` 成为带 ASYNC_REG 的 1-bit 同步器（CDC-3 Info）。这修正了 2.3/2.6 旧版的错误豁免说明。

---

## 2. 豁免项（书面记录，非工具内降级）

> 为什么不用 `set_msg_config -new_severity INFO`：实测（`verify_cdc_fix.tcl`）在 Vivado 2018.3 中该命令**不改变** `report_methodology` 的 severity 输出。故以下各项以本文档为**正式豁免依据**，逐条给出不可修复的工程理由。

### 2.1 TIMING-24（4 条）—— 异步时钟组覆盖异步 FIFO IP 的 `set_max_delay -datapath_only`
**是什么**：`afifo_64i_16o_128`（read_buf）/ `afifo_16i_64o_largebuf`（write_buf）内部 XDC 有跨 `clk_100m ↔ clk_74m25` 的 `set_max_delay -datapath_only`；我们的 `set_clock_groups -asynchronous` 覆盖了它。

**为什么安全**：这两个 FIFO 是 Xilinx fifo_generator IP 的**标准异步 FIFO**（格雷码指针 + 2-FF 同步 + `xpm_cdc_single` 复位同步，report_cdc 已确认其内部同步带 ASYNC_REG，见 CDC-3 Info 7 条）。`clk_100m` 与 `clk_74m25` **本真异步**（不同 MMCM），声明为异步组是正确的顶层处理；FIFO 的 `set_max_delay -datapath_only` 是冗余的“双保险”，被异步声明取代不影响功能。**豁免。**

### 2.2 TIMING-27（1 条）—— PS7 主时钟 `clk_fpga_0` 在层级 pin 上
**是什么**：`clk_fpga_0` 主时钟由 **PS7 IP 自带 XDC**（`ps_ai_processing_system7_0_0.xdc`）在 `FCLKCLK[0]` 层级 pin 上创建。

**为什么安全**：这是官方 PS7 IP 的固有时钟定义，不能也不应改动（PS7/DDR3 复用官方配置的红线）。该 pin 驱动 PS7 内部 PLL，50MHz 仅用于派生 `clk_out1_clk_wiz_0`。**豁免。**

### 2.3 TIMING-9（1 条）—— 剩余“未知 CDC”（复位 / 准静态 / 诊断计数）
**是什么**：`set_clock_groups` 屏蔽时序后，仍存在无“双寄存器同步器”的跨域路径。加 ASYNC_REG 后，剩余的未知 CDC 属于以下三类，**都不是功能数据通路**：

| 类 | 具体路径 | 为什么安全 |
|---|---|---|
| 全局异步复位 | `sys_rst` → 各域 CLR/R（color_bar/timing_gen_xy/video_rect/frame_ctrl 计数器） | 复位键按下保持 ms 级、释放干净；`set_false_path -from [get_ports sys_rst]` 已覆盖时序；官方 demo 同款结构 |
| 准静态配置 | `camera_rd_addr[26:0]`→`rd_burst_addr`（CDC-15/CDC-17）、`over_thr[31]`→`over_cnt` CE | PS 上电/初始化时**写一次**后保持稳定；捕获侧由 `read_req_d2`（已同步）在帧起始门控，跨域时值不变，无采偏风险 |

> `camera_wr_addr[0]`（缓冲选择位）**不属准静态**——双缓冲乒乓时每帧翻转，已单独按 1.3 改为 1-bit 双触发同步，不在本豁免列。
| 诊断计数回读 | `over_cnt/fetch_cnt/done_cnt/done_2_fetch_cnt` → `S_AXI_RDATA` | 仅状态寄存器，PS 读走做调试；值可陈旧/毛刺，但不参与控制，最坏读到一个不精确的计数值 |

**豁免。** 如需进一步收敛，上板稳定后可评估把诊断计数回读改成 XPM_CDC（属后续优化，非本轮必需）。

### 2.4 LUTAR-1（1 条）—— LUT 驱动异步复位（官方 timing_gen_xy 自复位）
**是什么**：`timing_gen_xy_m0/h_cnt[11]_i_2` 这个 LUT 驱动 `color_bar`/`level_cross` 共 86 个寄存器的异步 CLR。

**为什么安全**：这是**官方 `timing_gen_xy` + `color_bar` 的自复位结构**（行计数器终值产生复位），冻结未动；色条位流（同结构）已真实构建通过。风险在于“组合逻辑驱动异步复位可能毛刺”，但该 LUT 输出由稳定计数器产生、在像素域内建立，官方 demo 长期运行无异常。**豁免。**

### 2.5 PDRC-190（4 条）—— 同步器链放置欠优（纯放置提示）
**是什么**：`report_methodology` 报 4 条“synchronized register chain suboptimally placed”：
1. `level_cross_ack/a1_clk1_d1 → a1_clk1_d2`（源侧双拍，不在同一 SLICE）
2. `level_cross_ack/a1_clk1_d2 → a2_clk2_t1`（真正跨域对）
3. `level_cross_req/a1_clk1_d2 → a2_clk2_t1`（真正跨域对）
4. `read_buf`（fifo_generator IP）复位同步链 `rst_d2_reg → rst_d3_reg`

其中第 1~3 条是**本次打 ASYNC_REG 后工具才开始检查的新增项**（此前只有第 4 条 FIFO 的 1 条）；第 4 条是 IP 自动生成。

**为什么安全**：纯放置优化提示，不影响功能与 MTBF 量级（同步器仍正确工作；ASYNC_REG 已阻止 SRL 吸收，FF 仅在相邻 SLICE 而非同 SLICE）。跨域对（#2/#3）本就在不同时钟域，强行同 SLICE 无意义；源侧双拍（#1）与 FIFO 复位（#4）为 IP/RTL 固有放置。**豁免。**

### 2.6 report_cdc 其余结构性项（CDC-1 / CDC-7 / CDC-10 / CDC-13 / CDC-15 / CDC-17）
- **CDC-1（205）1-bit 未知 CDC**：跨域 1-bit 路径无显式同步器——绝大多数是 `sys_rst`/复位、准静态配置、诊断计数（即 2.3 的三类）；`soft_rst_reg`→`rst_hp_d1_reg` 有顶层复位同步器（复位同步属此桶）。**豁免（2.3）。**
- **CDC-6（多 bit 带 ASYNC_REG）**：~~旧版曾把 `camera_wr_addr[1:0] → read_addr_index`（2-bit 缓冲选择）误判为准静态而豁免~~。**已修正**：缓冲选择每帧翻转，按 1.3 改为 1-bit 双触发同步后，该多 bit 跨域**已消除（CDC-6 消失）**，不再需要豁免。
- **CDC-7（72）异步复位未知 CDC**：即 2.3 的全局异步复位 CLR 路径，`sys_rst` 已 `set_false_path`。**豁免（2.3）。**
- **CDC-13（9）非 FD 原语**：`sys_rst` → OSerdes2 `RST/PRE`（TMDS 串行器异步复位）。官方 uihdmitx 结构，复位键电平信号。**豁免。**
- **CDC-10（1）同步器前组合逻辑**：`soft_rst_reg` → `proc_sys_reset` 的 CDC-to 输入（PS7 复位桥），Xilinx IP 结构。**豁免。**
- **CDC-15（56）时钟使能控制 CDC**：`camera_rd_addr[3:26]`→`rd_burst_addr`、`over_cnt`→`S_AXI_RDATA` 等，即 2.3 的准静态/诊断计数。**豁免（2.3）。**
- **CDC-17（3）MUX hold 控制 CDC**：`camera_rd_addr[2:0]`→`rd_burst_addr` 最低 3 位。与 CDC-15 同源——`rd_burst_addr` 在帧起始由 `frame_fifo_read` 的 S_ACK 状态从 `read_addr_0/1`（准静态 `camera_rd_addr`）经 MUX 锁存；`camera_rd_addr` 是帧基址，PS 初始化写一次后稳定。工具把低 3 位识别为“MUX hold”、高位识别为“时钟使能”，本质同属 2.3 的准静态配置。**豁免（2.3）。**

### 2.7 CRITICAL WARNING [Vivado 12-4739 / 12-627] —— PS7 PJTAG_TCK 无时钟对象
**是什么**：综合/实现日志各出现 4 条 `CRITICAL WARNING [Vivado 12-4739] set_output_delay: No valid object(s) found for '-clock [get_clocks PJTAG_TCK]'` 及 4 条 `WARNING [Vivado 12-627] No clocks matched 'PJTAG_TCK'`。

**来源**：官方 PS7 IP 自动生成的约束文件 `fpga/bd/ps_ai/ip/ps_ai_processing_system7_0_0/ps_ai_processing_system7_0_0.xdc` 第 18~23 行（约束语句在第 20~23 行）**无条件**对 `PJTAG_TDO` 端口发出 4 条 `set_output_delay -clock [get_clocks PJTAG_TCK] -clock_fall ...`。这是 IP 封装自带的固定内容，与顶层用法无关。

**为什么安全**：本设计**不使用 PS 私有 JTAG**——顶层 `hdmi_framebuffer_720p_top.sv`（第 401~405 行）把 `PJTAG_TCK/TMS/TDI` 固定接 `1'b0`、`PJTAG_TDO` 悬空，配置只用标准 JTAG/BSCAN。因此网表中**不存在** `PJTAG_TCK` 时钟，`get_clocks PJTAG_TCK` 匹配不到对象，约束被工具置为“无对象”。该警告不指向任何真实时序路径（`PJTAG_TDO` 已 tie off），不影响布局布线、时序收敛与 DRC（DRC 仍 0 Error）。

**豁免依据**：PS7 IP 自带 XDC 属官方冻结资产，**不得修改**（复用官方配置红线，同 2.2）。此 Critical Warning 是官方 PS7 IP 的固有行为（无论是否使用 PS JTAG 都发该约束），色条位流（同源同款）已真实构建通过。**豁免。**

---

## 3. 验证方法（重建后核对）

1. `report_methodology`（`routed_methodology.rpt`）：TIMING-10、TIMING-28 **消失**；剩余 11 条（TIMING-9×1、TIMING-24×4、TIMING-27×1、LUTAR-1×1、PDRC-190×4）**均已在上文逐条豁免**。
2. `report_cdc`（`routed_report_cdc.rpt`）：CDC-2/CDC-5 **消失**（1-bit → CDC-3 Info，已带 ASYNC_REG），**CDC-6 消失**（缓冲选择 1.3 修正后不再多 bit 跨域）；CDC-1/CDC-7/CDC-13/CDC-10/CDC-15/CDC-17 仍列出但属上文已豁免类别。
3. `report_clock_interaction`：6 条跨组路径仍 `Ignored / Asynchronous Groups`，时序 WNS/WHS ≥ 0。
4. DRC 仍 0 Error。
