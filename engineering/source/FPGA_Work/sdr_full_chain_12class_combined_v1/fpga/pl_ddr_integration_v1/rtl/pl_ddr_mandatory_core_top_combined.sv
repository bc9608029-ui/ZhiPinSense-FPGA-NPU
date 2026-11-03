`timescale 1ns/1ps
`default_nettype none

// Board top for the fixed-IQ Linux -> PL-DDR -> Mandatory Core -> PL-DDR
// validation.  It retains the official ps_ai_peripheral/AI_Mate/MIG shell and
// replaces only the example UserCustomOp logic.
module pl_ddr_mandatory_core_top_combined (
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

    // ---- HDMI display clock chain (100 MHz gp_clk -> 74.25 + 371.25 MHz) ----
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

    // =======================================================================
    // HDMI display clock chain.  The 200 MHz sys_clk crystal (C8/C7, DIFF_SSTL15)
    // is consumed by the MIG (mig_7series_0 buffers it internally; its in-context
    // XDC sets IO_BUFFER_TYPE=NONE on sys_clk_p/n), so it CANNOT also drive a
    // second IBUFDS at this level (that would be an illegal double-buffer).
    // The 74.25 MHz pixel clock and 371.25 MHz TMDS x5 clock are therefore derived
    // from the existing 100 MHz gp_clk (PS clk_wiz_0, clean PLL) with a single
    // MMCM -- the exact same output frequencies the standalone hdmi_framebuffer_720p
    // build produced through its 200->27->74.25/371.25 chain.  hp_clk stays the MIG
    // ui_clk (100 MHz), so fb_read_720p's HP AXI read runs in the existing HP domain
    // with no clock-crossing on the AXI bus itself.
    // =======================================================================
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
        // The display path remains functionally disabled (no valid pixels),
        // but its official clock wizard must not be fed a constant clock.
        // Reuse the shell's active PL-DDR clock; no SDR input is connected.
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

    // Unique instance/IP name avoids collision with the official ps_ai clock
    // wizard.  The project script creates this 200 MHz -> 50 MHz MMCM using
    // the same Vivado-2018.3 settings already proven by the board baseline.
    clk_wiz_core_50 u_clk_wiz_core_50 (
        .clk_out1(core_clk),
        .reset(hp_clk_rst),
        .locked(core_clk_locked),
        .clk_in1(hp_clk)
    );

    // The platform DDR reset is synchronous to hp_clk, not core_clk.  Convert
    // hp_clk_rst/MMCM-lock loss into an asynchronous reset request and release
    // it only after three complete 50 MHz core clock edges.
    wire core_reset_async = hp_clk_rst | ~core_clk_locked;
    (* ASYNC_REG = "TRUE" *) reg [2:0] core_reset_sync;
    always @(posedge core_clk or posedge core_reset_async) begin
        if (core_reset_async)
            core_reset_sync <= 3'b111;
        else
            core_reset_sync <= {core_reset_sync[1:0], 1'b0};
    end
    wire core_global_rst_n = ~core_reset_sync[2];

    pl_ddr_mandatory_core_engine u_engine (
        .gp_clk(gp_clk), .gp_rst_n(~gp_clk_rst),
        .ddr_clk(hp_clk), .ddr_global_rst_n(~hp_clk_rst),
        .core_clk(core_clk),
        .core_global_rst_n(core_global_rst_n),
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
endmodule

`default_nettype wire
