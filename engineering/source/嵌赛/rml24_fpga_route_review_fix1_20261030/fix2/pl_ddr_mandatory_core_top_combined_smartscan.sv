`timescale 1ns/1ps
`default_nettype none

// Combined NPU + smart-scan board top (candidate build, copy of the board
// project -- never in-place on the frozen project/bitstream).
//
// Based on pl_ddr_mandatory_core_top_combined.sv.  Adds the smart-scan PS/PL
// engine on the same platform channels:
//   - User_Reg_*:  user_reg_router splits the single 32-bit register channel.
//                  NPU keeps 0x00000-0x00028; the SS window moves to 0x10000
//                  and the router remaps it to offset 0 before forwarding, so
//                  smart_scan_pspl_regs keeps its frozen 0-based decode.
//   - User_Ddr_*:  the write channel stays NPU-only.  The read channel is
//                  shared through user_ddr_read_arbiter (NPU fixed priority,
//                  per-beat interleave, owner-latched return).
//
// The smart-scan datapath (Hann + migrated XFFT 9.1 + u54 + fftshift double
// buffer) runs in the existing 50 MHz core_clk; its PSD readback is over the
// register channel.  HDMI/clock/reset logic is unchanged from the frozen top.
module pl_ddr_mandatory_core_top_combined_smartscan (
    inout  wire [53:0] FIXED_IO_0_mio,
    inout  wire [14:0] DDR_0_addr,
    inout  wire [2:0]  DDR_0_ba,
    inout  wire        DDR_0_cas_n,
    inout  wire        DDR_0_ck_n,
    inout  wire        DDR_0_ck_p,
    inout  wire        DDR_0_cke,
    inout  wire        DDR_0_cs_n,
    inout  wire [3:0]  DDR_0_dm,
    inout  wire [31:0] DDR_0_dq,
    inout  wire [3:0]  DDR_0_dqs_n,
    inout  wire [3:0]  DDR_0_dqs_p,
    inout  wire        DDR_0_odt,
    inout  wire        DDR_0_ras_n,
    inout  wire        DDR_0_reset_n,
    inout  wire        DDR_0_we_n,
    inout  wire        FIXED_IO_0_ddr_vrn,
    inout  wire        FIXED_IO_0_ddr_vrp,
    inout  wire        FIXED_IO_0_ps_clk,
    inout  wire        FIXED_IO_0_ps_porb,
    inout  wire        FIXED_IO_0_ps_srstb,

    inout  wire [63:0] ddr3_dq,
    inout  wire [7:0]  ddr3_dqs_n,
    inout  wire [7:0]  ddr3_dqs_p,
    output wire [7:0]  ddr3_dm,
    output wire [14:0] ddr3_addr,
    output wire [2:0]  ddr3_ba,
    output wire        ddr3_ras_n,
    output wire        ddr3_cas_n,
    output wire        ddr3_we_n,
    output wire        ddr3_reset_n,
    output wire [0:0]  ddr3_ck_p,
    output wire [0:0]  ddr3_ck_n,
    output wire [0:0]  ddr3_cke,
    output wire [0:0]  ddr3_cs_n,
    output wire [0:0]  ddr3_odt,

    input  wire        sys_rst,
    input  wire        sys_clk_p,
    input  wire        sys_clk_n,
    output wire        HDMI_CLK_P,
    output wire        HDMI_CLK_N,
    output wire [2:0]  HDMI_TX_P,
    output wire [2:0]  HDMI_TX_N,
    output wire [1:0]  led,
    input  wire        PJTAG_TCK,
    input  wire        PJTAG_TMS,
    input  wire        PJTAG_TDI,
    output wire        PJTAG_TDO
);
    wire gp_clk;
    wire hp_clk;
    wire gp_clk_rst;
    wire hp_clk_rst;
    wire core_clk;
    wire core_clk_locked;

    // ---- HDMI display clock chain (unchanged from the frozen combined top) --
    wire clk_74m25, clk_74m25_bufg, clk_371m25, clk_371m25_bufg;
    wire clkfb_hdmi, mmcm_hdmi_locked;

    wire [31:0] User_Reg_awwaddr;
    wire [31:0] User_Reg_awwdata;
    wire User_Reg_awwvalid;
    wire User_Reg_awwready;
    wire [31:0] User_Reg_araddr;
    wire User_Reg_arvalid;
    wire User_Reg_arready;
    wire [31:0] User_Reg_rdata;
    wire User_Reg_rvalid;
    wire User_Reg_rready;

    wire [31:0] User_Ddr_awwaddr;
    wire [511:0] User_Ddr_awwdata;
    wire [71:0] User_Ddr_awwinfo;
    wire User_Ddr_awwvalid;
    wire User_Ddr_awwready;
    wire [31:0] User_Ddr_araddr;
    wire User_Ddr_arvalid;
    wire [31:0] User_Ddr_arinfo;
    wire User_Ddr_arready;
    wire [511:0] User_Ddr_rdata;
    wire User_Ddr_rvalid;
    wire [31:0] User_Ddr_rinfo;
    wire User_Ddr_rready;

    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (37.125),      // VCO = 100 * 37.125 / 5 = 742.5 MHz
        .CLKIN1_PERIOD   (10.000),      // 100 MHz gp_clk
        .CLKOUT0_DIVIDE_F(10.0),        // 74.25 MHz (pixel)
        .CLKOUT1_DIVIDE  (2),           // 371.25 MHz (TMDS x5)
        .DIVCLK_DIVIDE   (5)
    ) u_mmcm_hdmi (
        .CLKIN1  (gp_clk),
        .CLKOUT0 (clk_74m25),
        .CLKOUT1 (clk_371m25),
        .CLKFBOUT(clkfb_hdmi),
        .CLKFBIN (clkfb_hdmi),
        .LOCKED  (mmcm_hdmi_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    BUFG u_bufg_74  (.I(clk_74m25),  .O(clk_74m25_bufg));
    BUFG u_bufg_371 (.I(clk_371m25), .O(clk_371m25_bufg));

    ps_ai_peripheral_combined u_ps_ai_peripheral (
        .FIXED_IO_0_mio(FIXED_IO_0_mio),
        .DDR_0_addr(DDR_0_addr), .DDR_0_ba(DDR_0_ba),
        .DDR_0_cas_n(DDR_0_cas_n), .DDR_0_ck_n(DDR_0_ck_n),
        .DDR_0_ck_p(DDR_0_ck_p), .DDR_0_cke(DDR_0_cke),
        .DDR_0_cs_n(DDR_0_cs_n), .DDR_0_dm(DDR_0_dm),
        .DDR_0_dq(DDR_0_dq), .DDR_0_dqs_n(DDR_0_dqs_n),
        .DDR_0_dqs_p(DDR_0_dqs_p), .DDR_0_odt(DDR_0_odt),
        .DDR_0_ras_n(DDR_0_ras_n), .DDR_0_reset_n(DDR_0_reset_n),
        .DDR_0_we_n(DDR_0_we_n), .FIXED_IO_0_ddr_vrn(FIXED_IO_0_ddr_vrn),
        .FIXED_IO_0_ddr_vrp(FIXED_IO_0_ddr_vrp),
        .FIXED_IO_0_ps_clk(FIXED_IO_0_ps_clk),
        .FIXED_IO_0_ps_porb(FIXED_IO_0_ps_porb),
        .FIXED_IO_0_ps_srstb(FIXED_IO_0_ps_srstb),
        .ddr3_dq(ddr3_dq), .ddr3_dqs_n(ddr3_dqs_n),
        .ddr3_dqs_p(ddr3_dqs_p), .ddr3_dm(ddr3_dm),
        .ddr3_addr(ddr3_addr), .ddr3_ba(ddr3_ba),
        .ddr3_ras_n(ddr3_ras_n), .ddr3_cas_n(ddr3_cas_n),
        .ddr3_we_n(ddr3_we_n), .ddr3_reset_n(ddr3_reset_n),
        .ddr3_ck_p(ddr3_ck_p), .ddr3_ck_n(ddr3_ck_n),
        .ddr3_cke(ddr3_cke), .ddr3_cs_n(ddr3_cs_n),
        .ddr3_odt(ddr3_odt), .sys_rst(sys_rst),
        .sys_clk_p(sys_clk_p), .sys_clk_n(sys_clk_n),
        .cam_vs(1'b0), .cam_rgb(24'd0), .cam_clk(clk_74m25_bufg),
        .cam_data_en(1'b0), .clk_371m25(clk_371m25_bufg), .HDMI_CLK_P(HDMI_CLK_P),
        .HDMI_CLK_N(HDMI_CLK_N), .HDMI_TX_P(HDMI_TX_P),
        .HDMI_TX_N(HDMI_TX_N), .led(led), .led3(1'b0),
        .PJTAG_TCK(PJTAG_TCK), .PJTAG_TMS(PJTAG_TMS),
        .PJTAG_TDI(PJTAG_TDI), .PJTAG_TDO(PJTAG_TDO),
        .gp_clk(gp_clk), .hp_clk(hp_clk),
        .gp_clk_rst(gp_clk_rst), .hp_clk_rst(hp_clk_rst),
        .User_Reg_awwaddr(User_Reg_awwaddr),
        .User_Reg_awwdata(User_Reg_awwdata),
        .User_Reg_awwvalid(User_Reg_awwvalid),
        .User_Reg_awwready(User_Reg_awwready),
        .User_Reg_araddr(User_Reg_araddr),
        .User_Reg_arvalid(User_Reg_arvalid),
        .User_Reg_arready(User_Reg_arready),
        .User_Reg_rdata(User_Reg_rdata),
        .User_Reg_rvalid(User_Reg_rvalid),
        .User_Reg_rready(User_Reg_rready),
        .User_Ddr_awwaddr(User_Ddr_awwaddr),
        .User_Ddr_awwdata(User_Ddr_awwdata),
        .User_Ddr_awwinfo(User_Ddr_awwinfo),
        .User_Ddr_awwvalid(User_Ddr_awwvalid),
        .User_Ddr_awwready(User_Ddr_awwready),
        .User_Ddr_araddr(User_Ddr_araddr),
        .User_Ddr_arvalid(User_Ddr_arvalid),
        .User_Ddr_arinfo(User_Ddr_arinfo),
        .User_Ddr_arready(User_Ddr_arready),
        .User_Ddr_rdata(User_Ddr_rdata),
        .User_Ddr_rvalid(User_Ddr_rvalid),
        .User_Ddr_rinfo(User_Ddr_rinfo),
        .User_Ddr_rready(User_Ddr_rready)
    );

    clk_wiz_core_50 u_clk_wiz_core_50 (
        .clk_out1(core_clk),
        .reset(hp_clk_rst),
        .locked(core_clk_locked),
        .clk_in1(hp_clk)
    );

    wire core_reset_async = hp_clk_rst | ~core_clk_locked;
    (* ASYNC_REG = "TRUE" *) reg [2:0] core_reset_sync;
    always @(posedge core_clk or posedge core_reset_async) begin
        if (core_reset_async)
            core_reset_sync <= 3'b111;
        else
            core_reset_sync <= {core_reset_sync[1:0], 1'b0};
    end
    wire core_global_rst_n = ~core_reset_sync[2];

    // ------------------------------------------------------------------
    // Register channel split: NPU (e0) vs smart-scan (e1 @ 0x10000).
    // ------------------------------------------------------------------
    wire [31:0] nreg_awwaddr, nreg_awwdata; wire nreg_awwvalid, nreg_awwready;
    wire [31:0] nreg_araddr; wire nreg_arvalid, nreg_arready;
    wire [31:0] nreg_rdata; wire nreg_rvalid, nreg_rready;
    wire [31:0] sreg_awwaddr, sreg_awwdata; wire sreg_awwvalid, sreg_awwready;
    wire [31:0] sreg_araddr; wire sreg_arvalid, sreg_arready;
    wire [31:0] sreg_rdata; wire sreg_rvalid, sreg_rready;

    user_reg_router #(
        .SS_BASE(18'h10000),
        .SS_MASK(18'h3F000)
    ) u_reg_router (
        .clk(gp_clk), .rst_n(~gp_clk_rst),
        .awwaddr(User_Reg_awwaddr), .awwdata(User_Reg_awwdata),
        .awwvalid(User_Reg_awwvalid), .awwready(User_Reg_awwready),
        .araddr(User_Reg_araddr), .arvalid(User_Reg_arvalid),
        .arready(User_Reg_arready),
        .rdata(User_Reg_rdata), .rvalid(User_Reg_rvalid), .rready(User_Reg_rready),
        .e0_awwaddr(nreg_awwaddr), .e0_awwdata(nreg_awwdata),
        .e0_awwvalid(nreg_awwvalid), .e0_awwready(nreg_awwready),
        .e0_araddr(nreg_araddr), .e0_arvalid(nreg_arvalid),
        .e0_arready(nreg_arready),
        .e0_rdata(nreg_rdata), .e0_rvalid(nreg_rvalid), .e0_rready(nreg_rready),
        .e1_awwaddr(sreg_awwaddr), .e1_awwdata(sreg_awwdata),
        .e1_awwvalid(sreg_awwvalid), .e1_awwready(sreg_awwready),
        .e1_araddr(sreg_araddr), .e1_arvalid(sreg_arvalid),
        .e1_arready(sreg_arready),
        .e1_rdata(sreg_rdata), .e1_rvalid(sreg_rvalid), .e1_rready(sreg_rready)
    );

    // ------------------------------------------------------------------
    // DDR read channel split: NPU (r0, fixed priority) vs smart-scan (r1).
    // The write channel (User_Ddr_aww*) is wired to the NPU engine only.
    // ------------------------------------------------------------------
    wire [31:0]  nar_araddr;  wire nar_arvalid;  wire [31:0] nar_arinfo;  wire nar_arready;
    wire [511:0] nar_rdata;   wire nar_rvalid;   wire [31:0] nar_rinfo;   wire nar_rready;
    wire [31:0]  sar_araddr;  wire sar_arvalid;  wire [31:0] sar_arinfo;  wire sar_arready;
    wire [511:0] sar_rdata;   wire sar_rvalid;   wire [31:0] sar_rinfo;   wire sar_rready;

    user_ddr_read_arbiter u_ddr_rd_arb (
        .clk(hp_clk), .rst_n(~hp_clk_rst),
        .ar_araddr(User_Ddr_araddr), .ar_arvalid(User_Ddr_arvalid),
        .ar_arinfo(User_Ddr_arinfo), .ar_arready(User_Ddr_arready),
        .ar_rdata(User_Ddr_rdata), .ar_rvalid(User_Ddr_rvalid),
        .ar_rinfo(User_Ddr_rinfo), .ar_rready(User_Ddr_rready),
        .r0_araddr(nar_araddr), .r0_arvalid(nar_arvalid), .r0_arinfo(nar_arinfo),
        .r0_arready(nar_arready),
        .r0_rdata(nar_rdata), .r0_rvalid(nar_rvalid), .r0_rinfo(nar_rinfo),
        .r0_rready(nar_rready),
        .r1_araddr(sar_araddr), .r1_arvalid(sar_arvalid), .r1_arinfo(sar_arinfo),
        .r1_arready(sar_arready),
        .r1_rdata(sar_rdata), .r1_rvalid(sar_rvalid), .r1_rinfo(sar_rinfo),
        .r1_rready(sar_rready)
    );

    pl_ddr_mandatory_core_engine u_engine (
        .gp_clk(gp_clk), .gp_rst_n(~gp_clk_rst),
        .ddr_clk(hp_clk), .ddr_global_rst_n(~hp_clk_rst),
        .core_clk(core_clk),
        .core_global_rst_n(core_global_rst_n),
        .User_Reg_awwaddr(nreg_awwaddr),
        .User_Reg_awwdata(nreg_awwdata),
        .User_Reg_awwvalid(nreg_awwvalid),
        .User_Reg_awwready(nreg_awwready),
        .User_Reg_araddr(nreg_araddr),
        .User_Reg_arvalid(nreg_arvalid),
        .User_Reg_arready(nreg_arready),
        .User_Reg_rdata(nreg_rdata),
        .User_Reg_rvalid(nreg_rvalid),
        .User_Reg_rready(nreg_rready),
        .User_Ddr_awwaddr(User_Ddr_awwaddr),
        .User_Ddr_awwdata(User_Ddr_awwdata),
        .User_Ddr_awwinfo(User_Ddr_awwinfo),
        .User_Ddr_awwvalid(User_Ddr_awwvalid),
        .User_Ddr_awwready(User_Ddr_awwready),
        .User_Ddr_araddr(nar_araddr),
        .User_Ddr_arvalid(nar_arvalid),
        .User_Ddr_arinfo(nar_arinfo),
        .User_Ddr_arready(nar_arready),
        .User_Ddr_rdata(nar_rdata),
        .User_Ddr_rvalid(nar_rvalid),
        .User_Ddr_rinfo(nar_rinfo),
        .User_Ddr_rready(nar_rready)
    );

    smart_scan_pspl_engine u_smart_scan (
        .gp_clk(gp_clk), .gp_rst_n(~gp_clk_rst),
        .ddr_clk(hp_clk), .ddr_global_rst_n(~hp_clk_rst),
        .core_clk(core_clk), .core_global_rst_n(core_global_rst_n),
        .User_Reg_awwaddr(sreg_awwaddr),
        .User_Reg_awwdata(sreg_awwdata),
        .User_Reg_awwvalid(sreg_awwvalid),
        .User_Reg_awwready(sreg_awwready),
        .User_Reg_araddr(sreg_araddr),
        .User_Reg_arvalid(sreg_arvalid),
        .User_Reg_arready(sreg_arready),
        .User_Reg_rdata(sreg_rdata),
        .User_Reg_rvalid(sreg_rvalid),
        .User_Reg_rready(sreg_rready),
        // Smart-scan never writes DDR; its aww outputs are driven to 0 and left
        // unconnected here (the platform write channel is NPU-only).
        .User_Ddr_awwaddr(),
        .User_Ddr_awwdata(),
        .User_Ddr_awwinfo(),
        .User_Ddr_awwvalid(),
        .User_Ddr_awwready(1'b0),
        .User_Ddr_araddr(sar_araddr),
        .User_Ddr_arvalid(sar_arvalid),
        .User_Ddr_arinfo(sar_arinfo),
        .User_Ddr_arready(sar_arready),
        .User_Ddr_rdata(sar_rdata),
        .User_Ddr_rvalid(sar_rvalid),
        .User_Ddr_rinfo(sar_rinfo),
        .User_Ddr_rready(sar_rready)
    );
endmodule

`default_nettype wire
