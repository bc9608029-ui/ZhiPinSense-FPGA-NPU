// hdmi_framebuffer_720p_top.sv — Phase 1A top: PS DDR framebuffer -> 720p HDMI.
//
// NEW file.  Instantiates the reused official ps_ai_wrapper (PS7 + DDR3 + HP/GP)
// verbatim, plus the read path (fb_read_720p), the control register (frame_ctrl)
// reached over User_GP0 through a small AXI3->AXI-Lite bridge, and the 720p HDMI
// clock/TMDS chain.  No NPU/SDI/MIG/PL-DDR is instantiated; every unused
// ps_ai_wrapper port is tied off.
//
// Clock tree:
//   200 MHz crystal -> MMCM1 27 MHz -> MMCM2 74.25 MHz (pixel) + 371.25 MHz (TMDS)
//                   -> MMCM3 100 MHz  (hp_clk, HP2_1 read clock, independent of PS7)
//   PS7 FCLK_CLK0 (50 MHz) -> clk_wiz_0 (inside ps_ai_wrapper) -> ps_clk_out 100 MHz
//                              = gp_clk (frame_ctrl + GP bridge clock)
`timescale 1ns / 1ps

module hdmi_framebuffer_720p_top (
    // ---- board clock / reset ----
    input  wire        sys_clk_p,          // 200 MHz diff (C8/C7)
    input  wire        sys_clk_n,
    input  wire        sys_rst,            // active-high reset button (F8)

    // ---- PS DDR3 (reused PS7 controller pins) ----
    inout  wire [14:0] DDR_addr,
    inout  wire [2:0]  DDR_ba,
    inout  wire        DDR_cas_n,
    inout  wire        DDR_ck_n,
    inout  wire        DDR_ck_p,
    inout  wire        DDR_cke,
    inout  wire        DDR_cs_n,
    inout  wire [3:0]  DDR_dm,
    inout  wire [31:0] DDR_dq,
    inout  wire [3:0]  DDR_dqs_n,
    inout  wire [3:0]  DDR_dqs_p,
    inout  wire        DDR_odt,
    inout  wire        DDR_ras_n,
    inout  wire        DDR_reset_n,
    inout  wire        DDR_we_n,

    // ---- FIXED_IO (MIO) ----
    inout  wire        FIXED_IO_ddr_vrn,
    inout  wire        FIXED_IO_ddr_vrp,
    inout  wire [53:0] FIXED_IO_mio,
    inout  wire        FIXED_IO_ps_clk,
    inout  wire        FIXED_IO_ps_porb,
    inout  wire        FIXED_IO_ps_srstb,

    // ---- HDMI ----
    output wire        HDMI_CLK_P,         // AC17
    output wire        HDMI_CLK_N,
    output wire [2:0]  HDMI_TX_P,          // AA15/Y16/W16
    output wire [2:0]  HDMI_TX_N,

    // ---- LED ----
    output wire [1:0]  led                 // J1 / M6
);

    // =======================================================================
    // Internal nets (ALL declared up front — avoid implicit-net width hazards)
    // =======================================================================

    // ---- clock / MMCM ----
    wire        clk_200m, clk_27m, clk_27m_bufg, clkfb1, mmcm1_locked;
    wire        clk_74m25, clk_371m25, clkfb2, mmcm2_locked;
    wire        clk_74m25_bufg, clk_371m25_bufg;
    wire        clk_100m, clkfb3, mmcm3_locked;
    wire        hp_clk;

    // ---- PS7 ----
    wire        gp_clk;                 // = ps_clk_out = 100 MHz
    wire        pll_lock;
    wire        FCLK_RESET0_N;
    wire        clk_200mhz;             // unused (200 MHz from PS7)
    wire        sys_rst_n = ~sys_rst;
    wire        soft_rst;               // from frame_ctrl (default 0)

    // ---- reset ----
    wire        reset_or = sys_rst | soft_rst;
    reg         rst_gp_d1, rst_gp_d2;
    wire        gp_rst = rst_gp_d2;
    reg         rst_hp_d1, rst_hp_d2;
    wire        hp_rst = rst_hp_d2;
    reg  [3:0]  rst_sr = 4'hF;
    wire        cam_rst = sys_rst | (|rst_sr);

    // ---- User_GP0 (AXI3 master -> bridge) ----
    wire        user_gp0_awvalid, user_gp0_wvalid, user_gp0_bready;
    wire [31:0] user_gp0_awaddr, user_gp0_wdata;
    wire [11:0] user_gp0_awid;
    wire [ 2:0] user_gp0_awprot;
    wire [ 3:0] user_gp0_wstrb;
    wire        user_gp0_wlast;
    wire        user_gp0_awready, user_gp0_wready;
    wire        user_gp0_bvalid;
    wire [ 1:0] user_gp0_bresp;
    wire [11:0] user_gp0_bid;
    wire        user_gp0_arvalid;
    wire [31:0] user_gp0_araddr;
    wire [11:0] user_gp0_arid;
    wire [ 2:0] user_gp0_arprot;
    wire        user_gp0_arready;
    wire        user_gp0_rvalid, user_gp0_rready;
    wire [31:0] user_gp0_rdata;
    wire [ 1:0] user_gp0_rresp;
    wire        user_gp0_rlast;
    wire [11:0] user_gp0_rid;

    // ---- frame_ctrl AXI-Lite side ----
    wire        frame_ctrl_awvalid, frame_ctrl_wvalid, frame_ctrl_arvalid;
    wire [ 8:0] frame_ctrl_awaddr, frame_ctrl_araddr;
    wire [ 2:0] frame_ctrl_awprot, frame_ctrl_arprot;
    wire [31:0] frame_ctrl_wdata;
    wire [ 3:0] frame_ctrl_wstrb;
    wire        frame_ctrl_rvalid, frame_ctrl_rready;
    wire [31:0] frame_ctrl_rdata;
    wire [ 1:0] frame_ctrl_rresp;
    wire [31:0] camera_rd_addr;
    wire        display_en;

    // ---- HP2_1 AXI (fb_read_720p <-> ps_ai_wrapper) ----
    wire [4:0]  m00_axi_arid, m00_axi_awid, m00_axi_rid, m00_axi_bid, m00_axi_wid;
    wire [31:0] m00_axi_araddr, m00_axi_awaddr;
    wire [3:0]  m00_axi_arlen, m00_axi_awlen;
    wire [2:0]  m00_axi_arsize, m00_axi_awsize, m00_axi_arprot, m00_axi_awprot;
    wire [1:0]  m00_axi_arburst, m00_axi_awburst, m00_axi_arlock, m00_axi_awlock;
    wire [3:0]  m00_axi_arcache, m00_axi_awcache, m00_axi_arqos, m00_axi_awqos;
    wire        m00_axi_arvalid, m00_axi_arready;
    wire        m00_axi_awvalid, m00_axi_awready;
    wire [63:0] m00_axi_wdata, m00_axi_rdata;
    wire [7:0]  m00_axi_wstrb;
    wire        m00_axi_wlast, m00_axi_wvalid, m00_axi_wready;
    wire [1:0]  m00_axi_bresp, m00_axi_rresp;
    wire        m00_axi_bvalid, m00_axi_bready;
    wire        m00_axi_rlast, m00_axi_rvalid, m00_axi_rready;

    // ---- LED ----
    reg  [26:0] blink_cnt = 0;

    // =======================================================================
    // Input clock / MMCMs (reuse colorbar clock scheme + new hp_clk MMCM)
    // =======================================================================
    IBUFDS #(
        .DIFF_TERM("TRUE"),
        .IOSTANDARD("DIFF_SSTL15")
    ) u_ibufds_sysclk (
        .I  (sys_clk_p),
        .IB (sys_clk_n),
        .O  (clk_200m)
    );

    // MMCM1: 200 MHz -> 27 MHz
    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (27.0),
        .CLKIN1_PERIOD   (5.000),
        .CLKOUT0_DIVIDE_F(40.0),
        .DIVCLK_DIVIDE   (5)
    ) u_mmcm_200_27 (
        .CLKIN1  (clk_200m),
        .CLKOUT0 (clk_27m),
        .CLKFBOUT(clkfb1),
        .CLKFBIN (clkfb1),
        .LOCKED  (mmcm1_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    BUFG u_bufg_27 (.I(clk_27m), .O(clk_27m_bufg));

    // MMCM2: 27 MHz -> 74.25 MHz (pixel) + 371.25 MHz (TMDS x5)
    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (55.0),
        .CLKIN1_PERIOD   (37.037),
        .CLKOUT0_DIVIDE_F(10.0),
        .CLKOUT1_DIVIDE  (2),
        .DIVCLK_DIVIDE   (2)
    ) u_mmcm_27_742 (
        .CLKIN1  (clk_27m_bufg),
        .CLKOUT0 (clk_74m25),
        .CLKOUT1 (clk_371m25),
        .CLKFBOUT(clkfb2),
        .CLKFBIN (clkfb2),
        .LOCKED  (mmcm2_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    BUFG u_bufg_74  (.I(clk_74m25),  .O(clk_74m25_bufg));
    BUFG u_bufg_371 (.I(clk_371m25), .O(clk_371m25_bufg));

    // MMCM3: 200 MHz -> 100 MHz (hp_clk, HP2_1 read clock, independent of PS7)
    MMCME2_BASE #(
        .CLKFBOUT_MULT_F (5.0),
        .CLKIN1_PERIOD   (5.000),
        .CLKOUT0_DIVIDE_F(10.0),
        .DIVCLK_DIVIDE   (1)
    ) u_mmcm_200_100 (
        .CLKIN1  (clk_200m),
        .CLKOUT0 (clk_100m),
        .CLKFBOUT(clkfb3),
        .CLKFBIN (clkfb3),
        .LOCKED  (mmcm3_locked),
        .PWRDWN  (1'b0),
        .RST     (1'b0)
    );
    BUFG u_bufg_100 (.I(clk_100m), .O(hp_clk));

    // =======================================================================
    // PS7 wrapper (reused verbatim; unused ports tied off)
    // =======================================================================
    ps_ai_wrapper u_ps_ai_wrapper (
        // ---- DDR ----
        .DDR_addr      (DDR_addr),
        .DDR_ba        (DDR_ba),
        .DDR_cas_n     (DDR_cas_n),
        .DDR_ck_n      (DDR_ck_n),
        .DDR_ck_p      (DDR_ck_p),
        .DDR_cke       (DDR_cke),
        .DDR_cs_n      (DDR_cs_n),
        .DDR_dm        (DDR_dm),
        .DDR_dq        (DDR_dq),
        .DDR_dqs_n     (DDR_dqs_n),
        .DDR_dqs_p     (DDR_dqs_p),
        .DDR_odt       (DDR_odt),
        .DDR_ras_n     (DDR_ras_n),
        .DDR_reset_n   (DDR_reset_n),
        .DDR_we_n      (DDR_we_n),
        // ---- FIXED_IO ----
        .FIXED_IO_ddr_vrn (FIXED_IO_ddr_vrn),
        .FIXED_IO_ddr_vrp (FIXED_IO_ddr_vrp),
        .FIXED_IO_mio   (FIXED_IO_mio),
        .FIXED_IO_ps_clk(FIXED_IO_ps_clk),
        .FIXED_IO_ps_porb(FIXED_IO_ps_porb),
        .FIXED_IO_ps_srstb(FIXED_IO_ps_srstb),
        // ---- reset / clock ----
        .reset_n       (sys_rst_n & FCLK_RESET0_N),
        .FCLK_RESET0_N (FCLK_RESET0_N),
        .soft_rst_n    (~soft_rst),
        .hp_axi_aclk   (hp_clk),
        .ps_clk_out    (gp_clk),
        .pll_lock      (pll_lock),
        .clk_200mhz    (clk_200mhz),

        // ---- BYolo_GP0 (unused master) ----
        .BYolo_GP0_ARVALID(),
        .BYolo_GP0_AWVALID(),
        .BYolo_GP0_BREADY (),
        .BYolo_GP0_RREADY (),
        .BYolo_GP0_WLAST  (),
        .BYolo_GP0_WVALID (),
        .BYolo_GP0_ARID   (),
        .BYolo_GP0_AWID   (),
        .BYolo_GP0_WID    (),
        .BYolo_GP0_ARBURST(),
        .BYolo_GP0_ARLOCK (),
        .BYolo_GP0_ARSIZE (),
        .BYolo_GP0_AWBURST(),
        .BYolo_GP0_AWLOCK (),
        .BYolo_GP0_AWSIZE (),
        .BYolo_GP0_ARPROT (),
        .BYolo_GP0_AWPROT (),
        .BYolo_GP0_ARADDR (),
        .BYolo_GP0_AWADDR (),
        .BYolo_GP0_WDATA  (),
        .BYolo_GP0_ARCACHE(),
        .BYolo_GP0_ARLEN  (),
        .BYolo_GP0_ARQOS  (),
        .BYolo_GP0_AWCACHE(),
        .BYolo_GP0_AWLEN  (),
        .BYolo_GP0_AWQOS  (),
        .BYolo_GP0_WSTRB  (),
        .BYolo_GP0_ARREADY(1'b0),
        .BYolo_GP0_AWREADY(1'b0),
        .BYolo_GP0_BVALID (1'b0),
        .BYolo_GP0_RLAST  (1'b0),
        .BYolo_GP0_RVALID (1'b0),
        .BYolo_GP0_WREADY (1'b0),
        .BYolo_GP0_BID    (12'd0),
        .BYolo_GP0_RID    (12'd0),
        .BYolo_GP0_BRESP  (2'd0),
        .BYolo_GP0_RRESP  (2'd0),
        .BYolo_GP0_RDATA  (32'd0),

        // ---- BYolo_GP1 (unused master) ----
        .BYolo_GP1_ARVALID(),
        .BYolo_GP1_AWVALID(),
        .BYolo_GP1_BREADY (),
        .BYolo_GP1_RREADY (),
        .BYolo_GP1_WLAST  (),
        .BYolo_GP1_WVALID (),
        .BYolo_GP1_ARID   (),
        .BYolo_GP1_AWID   (),
        .BYolo_GP1_WID    (),
        .BYolo_GP1_ARBURST(),
        .BYolo_GP1_ARLOCK (),
        .BYolo_GP1_ARSIZE (),
        .BYolo_GP1_AWBURST(),
        .BYolo_GP1_AWLOCK (),
        .BYolo_GP1_AWSIZE (),
        .BYolo_GP1_ARPROT (),
        .BYolo_GP1_AWPROT (),
        .BYolo_GP1_ARADDR (),
        .BYolo_GP1_AWADDR (),
        .BYolo_GP1_WDATA  (),
        .BYolo_GP1_ARCACHE(),
        .BYolo_GP1_ARLEN  (),
        .BYolo_GP1_ARQOS  (),
        .BYolo_GP1_AWCACHE(),
        .BYolo_GP1_AWLEN  (),
        .BYolo_GP1_AWQOS  (),
        .BYolo_GP1_WSTRB  (),
        .BYolo_GP1_ARREADY(1'b0),
        .BYolo_GP1_AWREADY(1'b0),
        .BYolo_GP1_BVALID (1'b0),
        .BYolo_GP1_RLAST  (1'b0),
        .BYolo_GP1_RVALID (1'b0),
        .BYolo_GP1_WREADY (1'b0),
        .BYolo_GP1_BID    (12'd0),
        .BYolo_GP1_RID    (12'd0),
        .BYolo_GP1_BRESP  (2'd0),
        .BYolo_GP1_RRESP  (2'd0),
        .BYolo_GP1_RDATA  (32'd0),

        // ---- User_GP0 (-> frame_ctrl via bridge) ----
        .User_GP0_ARVALID(user_gp0_arvalid),
        .User_GP0_AWVALID(user_gp0_awvalid),
        .User_GP0_BREADY (user_gp0_bready),
        .User_GP0_RREADY (user_gp0_rready),
        .User_GP0_WLAST  (user_gp0_wlast),
        .User_GP0_WVALID (user_gp0_wvalid),
        .User_GP0_ARID   (user_gp0_arid),
        .User_GP0_AWID   (user_gp0_awid),
        .User_GP0_WID    (),
        .User_GP0_ARBURST(),
        .User_GP0_ARLOCK (),
        .User_GP0_ARSIZE (),
        .User_GP0_AWBURST(),
        .User_GP0_AWLOCK (),
        .User_GP0_AWSIZE (),
        .User_GP0_ARPROT (user_gp0_arprot),
        .User_GP0_AWPROT (user_gp0_awprot),
        .User_GP0_ARADDR (user_gp0_araddr),
        .User_GP0_AWADDR (user_gp0_awaddr),
        .User_GP0_WDATA  (user_gp0_wdata),
        .User_GP0_ARCACHE(),
        .User_GP0_ARLEN  (),
        .User_GP0_ARQOS  (),
        .User_GP0_AWCACHE(),
        .User_GP0_AWLEN  (),
        .User_GP0_AWQOS  (),
        .User_GP0_WSTRB  (user_gp0_wstrb),
        .User_GP0_ARREADY(user_gp0_arready),
        .User_GP0_AWREADY(user_gp0_awready),
        .User_GP0_BVALID (user_gp0_bvalid),
        .User_GP0_RLAST  (user_gp0_rlast),
        .User_GP0_RVALID (user_gp0_rvalid),
        .User_GP0_WREADY (user_gp0_wready),
        .User_GP0_BID    (user_gp0_bid),
        .User_GP0_RID    (user_gp0_rid),
        .User_GP0_BRESP  (user_gp0_bresp),
        .User_GP0_RRESP  (user_gp0_rresp),
        .User_GP0_RDATA  (user_gp0_rdata),

        // ---- User_GP1 (unused master) ----
        .User_GP1_ARVALID(),
        .User_GP1_AWVALID(),
        .User_GP1_BREADY (),
        .User_GP1_RREADY (),
        .User_GP1_WLAST  (),
        .User_GP1_WVALID (),
        .User_GP1_ARID   (),
        .User_GP1_AWID   (),
        .User_GP1_WID    (),
        .User_GP1_ARBURST(),
        .User_GP1_ARLOCK (),
        .User_GP1_ARSIZE (),
        .User_GP1_AWBURST(),
        .User_GP1_AWLOCK (),
        .User_GP1_AWSIZE (),
        .User_GP1_ARPROT (),
        .User_GP1_AWPROT (),
        .User_GP1_ARADDR (),
        .User_GP1_AWADDR (),
        .User_GP1_WDATA  (),
        .User_GP1_ARCACHE(),
        .User_GP1_ARLEN  (),
        .User_GP1_ARQOS  (),
        .User_GP1_AWCACHE(),
        .User_GP1_AWLEN  (),
        .User_GP1_AWQOS  (),
        .User_GP1_WSTRB  (),
        .User_GP1_ARREADY(1'b0),
        .User_GP1_AWREADY(1'b0),
        .User_GP1_BVALID (1'b0),
        .User_GP1_RLAST  (1'b0),
        .User_GP1_RVALID (1'b0),
        .User_GP1_WREADY (1'b0),
        .User_GP1_BID    (12'd0),
        .User_GP1_RID    (12'd0),
        .User_GP1_BRESP  (2'd0),
        .User_GP1_RRESP  (2'd0),
        .User_GP1_RDATA  (32'd0),

        // ---- PJTAG (unused) ----
        .PJTAG_TCK (1'b0),
        .PJTAG_TMS (1'b0),
        .PJTAG_TDI (1'b0),
        .PJTAG_TDO (),

        // ---- S_AXI_HP0 (unused slave) ----
        .S_AXI_HP0_ARADDR (32'd0),
        .S_AXI_HP0_ARBURST(2'd0),
        .S_AXI_HP0_ARCACHE(4'd0),
        .S_AXI_HP0_ARID   (5'd0),
        .S_AXI_HP0_ARLEN  (4'd0),
        .S_AXI_HP0_ARLOCK (2'd0),
        .S_AXI_HP0_ARPROT (3'd0),
        .S_AXI_HP0_ARQOS  (4'd0),
        .S_AXI_HP0_ARREADY(),
        .S_AXI_HP0_ARSIZE (3'd0),
        .S_AXI_HP0_ARVALID(1'b0),
        .S_AXI_HP0_AWADDR (32'd0),
        .S_AXI_HP0_AWBURST(2'd0),
        .S_AXI_HP0_AWCACHE(4'd0),
        .S_AXI_HP0_AWID   (5'd0),
        .S_AXI_HP0_AWLEN  (4'd0),
        .S_AXI_HP0_AWLOCK (2'd0),
        .S_AXI_HP0_AWPROT (3'd0),
        .S_AXI_HP0_AWQOS  (4'd0),
        .S_AXI_HP0_AWREADY(),
        .S_AXI_HP0_AWSIZE (3'd0),
        .S_AXI_HP0_AWVALID(1'b0),
        .S_AXI_HP0_BID    (),
        .S_AXI_HP0_BREADY (1'b0),
        .S_AXI_HP0_BRESP  (),
        .S_AXI_HP0_BVALID (),
        .S_AXI_HP0_RDATA  (),
        .S_AXI_HP0_RID    (),
        .S_AXI_HP0_RLAST  (),
        .S_AXI_HP0_RREADY (1'b0),
        .S_AXI_HP0_RRESP  (),
        .S_AXI_HP0_RVALID (),
        .S_AXI_HP0_WDATA  (64'd0),
        .S_AXI_HP0_WID    (5'd0),
        .S_AXI_HP0_WLAST  (1'b0),
        .S_AXI_HP0_WREADY (),
        .S_AXI_HP0_WSTRB  (8'd0),
        .S_AXI_HP0_WVALID (1'b0),
        .S_AXI_HP0_RACOUNT(),
        .S_AXI_HP0_RCOUNT (),
        .S_AXI_HP0_RDISSUECAP1_EN(1'b0),
        .S_AXI_HP0_WACOUNT(),
        .S_AXI_HP0_WCOUNT (),
        .S_AXI_HP0_WRISSUECAP1_EN(1'b0),

        // ---- S_AXI_HP1 (unused slave) ----
        .S_AXI_HP1_ARADDR (32'd0),
        .S_AXI_HP1_ARBURST(2'd0),
        .S_AXI_HP1_ARCACHE(4'd0),
        .S_AXI_HP1_ARID   (5'd0),
        .S_AXI_HP1_ARLEN  (4'd0),
        .S_AXI_HP1_ARLOCK (2'd0),
        .S_AXI_HP1_ARPROT (3'd0),
        .S_AXI_HP1_ARQOS  (4'd0),
        .S_AXI_HP1_ARREADY(),
        .S_AXI_HP1_ARSIZE (3'd0),
        .S_AXI_HP1_ARVALID(1'b0),
        .S_AXI_HP1_AWADDR (32'd0),
        .S_AXI_HP1_AWBURST(2'd0),
        .S_AXI_HP1_AWCACHE(4'd0),
        .S_AXI_HP1_AWID   (5'd0),
        .S_AXI_HP1_AWLEN  (4'd0),
        .S_AXI_HP1_AWLOCK (2'd0),
        .S_AXI_HP1_AWPROT (3'd0),
        .S_AXI_HP1_AWQOS  (4'd0),
        .S_AXI_HP1_AWREADY(),
        .S_AXI_HP1_AWSIZE (3'd0),
        .S_AXI_HP1_AWVALID(1'b0),
        .S_AXI_HP1_BID    (),
        .S_AXI_HP1_BREADY (1'b0),
        .S_AXI_HP1_BRESP  (),
        .S_AXI_HP1_BVALID (),
        .S_AXI_HP1_RDATA  (),
        .S_AXI_HP1_RID    (),
        .S_AXI_HP1_RLAST  (),
        .S_AXI_HP1_RREADY (1'b0),
        .S_AXI_HP1_RRESP  (),
        .S_AXI_HP1_RVALID (),
        .S_AXI_HP1_WDATA  (64'd0),
        .S_AXI_HP1_WID    (5'd0),
        .S_AXI_HP1_WLAST  (1'b0),
        .S_AXI_HP1_WREADY (),
        .S_AXI_HP1_WSTRB  (8'd0),
        .S_AXI_HP1_WVALID (1'b0),
        .S_AXI_HP1_RACOUNT(),
        .S_AXI_HP1_RCOUNT (),
        .S_AXI_HP1_RDISSUECAP1_EN(1'b0),
        .S_AXI_HP1_WACOUNT(),
        .S_AXI_HP1_WCOUNT (),
        .S_AXI_HP1_WRISSUECAP1_EN(1'b0),

        // ---- S_AXI_HP2 (unused slave) ----
        .S_AXI_HP2_ARADDR (32'd0),
        .S_AXI_HP2_ARBURST(2'd0),
        .S_AXI_HP2_ARCACHE(4'd0),
        .S_AXI_HP2_ARID   (5'd0),
        .S_AXI_HP2_ARLEN  (4'd0),
        .S_AXI_HP2_ARLOCK (2'd0),
        .S_AXI_HP2_ARPROT (3'd0),
        .S_AXI_HP2_ARQOS  (4'd0),
        .S_AXI_HP2_ARREADY(),
        .S_AXI_HP2_ARSIZE (3'd0),
        .S_AXI_HP2_ARVALID(1'b0),
        .S_AXI_HP2_AWADDR (32'd0),
        .S_AXI_HP2_AWBURST(2'd0),
        .S_AXI_HP2_AWCACHE(4'd0),
        .S_AXI_HP2_AWID   (5'd0),
        .S_AXI_HP2_AWLEN  (4'd0),
        .S_AXI_HP2_AWLOCK (2'd0),
        .S_AXI_HP2_AWPROT (3'd0),
        .S_AXI_HP2_AWQOS  (4'd0),
        .S_AXI_HP2_AWREADY(),
        .S_AXI_HP2_AWSIZE (3'd0),
        .S_AXI_HP2_AWVALID(1'b0),
        .S_AXI_HP2_BID    (),
        .S_AXI_HP2_BREADY (1'b0),
        .S_AXI_HP2_BRESP  (),
        .S_AXI_HP2_BVALID (),
        .S_AXI_HP2_RDATA  (),
        .S_AXI_HP2_RID    (),
        .S_AXI_HP2_RLAST  (),
        .S_AXI_HP2_RREADY (1'b0),
        .S_AXI_HP2_RRESP  (),
        .S_AXI_HP2_RVALID (),
        .S_AXI_HP2_WDATA  (64'd0),
        .S_AXI_HP2_WID    (5'd0),
        .S_AXI_HP2_WLAST  (1'b0),
        .S_AXI_HP2_WREADY (),
        .S_AXI_HP2_WSTRB  (8'd0),
        .S_AXI_HP2_WVALID (1'b0),

        // ---- S_AXI_HP2_1 (connected to fb_read_720p) ----
        .S_AXI_HP2_1_ARADDR (m00_axi_araddr),
        .S_AXI_HP2_1_ARBURST(m00_axi_arburst),
        .S_AXI_HP2_1_ARCACHE(m00_axi_arcache),
        .S_AXI_HP2_1_ARID   (m00_axi_arid),
        .S_AXI_HP2_1_ARLEN  (m00_axi_arlen),
        .S_AXI_HP2_1_ARLOCK (m00_axi_arlock),
        .S_AXI_HP2_1_ARPROT (m00_axi_arprot),
        .S_AXI_HP2_1_ARQOS  (m00_axi_arqos),
        .S_AXI_HP2_1_ARREADY(m00_axi_arready),
        .S_AXI_HP2_1_ARSIZE (m00_axi_arsize),
        .S_AXI_HP2_1_ARVALID(m00_axi_arvalid),
        .S_AXI_HP2_1_AWADDR (m00_axi_awaddr),
        .S_AXI_HP2_1_AWBURST(m00_axi_awburst),
        .S_AXI_HP2_1_AWCACHE(m00_axi_awcache),
        .S_AXI_HP2_1_AWID   (m00_axi_awid),
        .S_AXI_HP2_1_AWLEN  (m00_axi_awlen),
        .S_AXI_HP2_1_AWLOCK (m00_axi_awlock),
        .S_AXI_HP2_1_AWPROT (m00_axi_awprot),
        .S_AXI_HP2_1_AWQOS  (m00_axi_awqos),
        .S_AXI_HP2_1_AWREADY(m00_axi_awready),
        .S_AXI_HP2_1_AWSIZE (m00_axi_awsize),
        .S_AXI_HP2_1_AWVALID(m00_axi_awvalid),
        .S_AXI_HP2_1_BID    (m00_axi_bid),
        .S_AXI_HP2_1_BREADY (m00_axi_bready),
        .S_AXI_HP2_1_BRESP  (m00_axi_bresp),
        .S_AXI_HP2_1_BVALID (m00_axi_bvalid),
        .S_AXI_HP2_1_RDATA  (m00_axi_rdata),
        .S_AXI_HP2_1_RID    (m00_axi_rid),
        .S_AXI_HP2_1_RLAST  (m00_axi_rlast),
        .S_AXI_HP2_1_RREADY (m00_axi_rready),
        .S_AXI_HP2_1_RRESP  (m00_axi_rresp),
        .S_AXI_HP2_1_RVALID (m00_axi_rvalid),
        .S_AXI_HP2_1_WDATA  (m00_axi_wdata),
        .S_AXI_HP2_1_WID    (m00_axi_wid),
        .S_AXI_HP2_1_WLAST  (m00_axi_wlast),
        .S_AXI_HP2_1_WREADY (m00_axi_wready),
        .S_AXI_HP2_1_WSTRB  (m00_axi_wstrb),
        .S_AXI_HP2_1_WVALID (m00_axi_wvalid),

        // ---- S_AXI_HP2 FIFO ctrl (unused) ----
        .S_AXI_HP2_RACOUNT(),
        .S_AXI_HP2_RCOUNT (),
        .S_AXI_HP2_RDISSUECAP1_EN(1'b0),
        .S_AXI_HP2_WACOUNT(),
        .S_AXI_HP2_WCOUNT (),
        .S_AXI_HP2_WRISSUECAP1_EN(1'b0),

        // ---- S_AXI_HP3 (unused slave) ----
        .S_AXI_HP3_ARADDR (32'd0),
        .S_AXI_HP3_ARBURST(2'd0),
        .S_AXI_HP3_ARCACHE(4'd0),
        .S_AXI_HP3_ARID   (5'd0),
        .S_AXI_HP3_ARLEN  (4'd0),
        .S_AXI_HP3_ARLOCK (2'd0),
        .S_AXI_HP3_ARPROT (3'd0),
        .S_AXI_HP3_ARQOS  (4'd0),
        .S_AXI_HP3_ARREADY(),
        .S_AXI_HP3_ARSIZE (3'd0),
        .S_AXI_HP3_ARVALID(1'b0),
        .S_AXI_HP3_AWADDR (32'd0),
        .S_AXI_HP3_AWBURST(2'd0),
        .S_AXI_HP3_AWCACHE(4'd0),
        .S_AXI_HP3_AWID   (5'd0),
        .S_AXI_HP3_AWLEN  (4'd0),
        .S_AXI_HP3_AWLOCK (2'd0),
        .S_AXI_HP3_AWPROT (3'd0),
        .S_AXI_HP3_AWQOS  (4'd0),
        .S_AXI_HP3_AWREADY(),
        .S_AXI_HP3_AWSIZE (3'd0),
        .S_AXI_HP3_AWVALID(1'b0),
        .S_AXI_HP3_BID    (),
        .S_AXI_HP3_BREADY (1'b0),
        .S_AXI_HP3_BRESP  (),
        .S_AXI_HP3_BVALID (),
        .S_AXI_HP3_RDATA  (),
        .S_AXI_HP3_RID    (),
        .S_AXI_HP3_RLAST  (),
        .S_AXI_HP3_RREADY (1'b0),
        .S_AXI_HP3_RRESP  (),
        .S_AXI_HP3_RVALID (),
        .S_AXI_HP3_WDATA  (64'd0),
        .S_AXI_HP3_WID    (5'd0),
        .S_AXI_HP3_WLAST  (1'b0),
        .S_AXI_HP3_WREADY (),
        .S_AXI_HP3_WSTRB  (8'd0),
        .S_AXI_HP3_WVALID (1'b0),
        .S_AXI_HP3_RACOUNT(),
        .S_AXI_HP3_RCOUNT (),
        .S_AXI_HP3_RDISSUECAP1_EN(1'b0),
        .S_AXI_HP3_WACOUNT(),
        .S_AXI_HP3_WCOUNT (),
        .S_AXI_HP3_WRISSUECAP1_EN(1'b0),

        // ---- pl_* AI ports (unused) ----
        .pl_araddr      (),
        .pl_arinfo      (),
        .pl_arlast      (),
        .pl_arready     (1'b0),
        .pl_arvalid     (),
        .pl_awaddr      (),
        .pl_awdata      (),
        .pl_awen        (),
        .pl_awinfo      (),
        .pl_awlast      (),
        .pl_awready     (1'b0),
        .pl_awvalid     (),
        .pl_bvalid      (1'b0),
        .pl_bready      (),
        .pl_bist_clk    (1'b0),
        .pl_bist_rstn   (1'b0),
        .pl_bist_en     (1'b0),
        .pl_bist_done   (),
        .pl_bist_err    (),
        .pl_bist_err_inv(),
        .pl_clk_div_out (),
        .pl_clk_en_b    (1'b0),
        .pl_int_info    (),
        .pl_int_valid   (),
        .pl_int_ready   (1'b0),
        .pl_itf_clk     (1'b0),
        .pl_ra_araddr   (16'd0),
        .pl_ra_arready  (),
        .pl_ra_arvalid  (1'b0),
        .pl_ra_awaddr   (16'd0),
        .pl_ra_awdata   (32'd0),
        .pl_ra_awready  (),
        .pl_ra_awvalid  (1'b0),
        .pl_ra_clk      (1'b0),
        .pl_ra_rdata    (),
        .pl_ra_rready   (1'b0),
        .pl_ra_rvalid   (),
        .pl_rdata       (512'd0),
        .pl_repair_done (),
        .pl_repair_fail (),
        .pl_rlast       (1'b0),
        .pl_rready      (),
        .pl_rst_n       (1'b0),
        .pl_rvalid      (1'b0),
        .pl_scan_clk    (1'b0),
        .pl_scan_en     (1'b0),
        .pl_scan_i      (64'd0),
        .pl_scan_mode_b (1'b0),
        .pl_scan_o      (),
        .pl_scan_rst_n  (1'b0),

        // ---- interrupts (unused) ----
        .test_irq    (1'b0),
        .customop_irq(1'b0),
        .ai_irq      (1'b0)
    );

    // =======================================================================
    // Reset synchronizers (gp_clk / hp_clk domains)
    // =======================================================================
    always @(posedge gp_clk) begin
        rst_gp_d1 <= reset_or;
        rst_gp_d2 <= rst_gp_d1;
    end
    always @(posedge hp_clk) begin
        rst_hp_d1 <= reset_or;
        rst_hp_d2 <= rst_hp_d1;
    end
    // cam domain reset: assert until MMCM1+MMCM2 lock, then 4 px clocks
    always @(posedge clk_74m25_bufg)
        rst_sr <= {rst_sr[2:0], ~(mmcm1_locked & mmcm2_locked)};

    // =======================================================================
    // frame_ctrl (AXI-Lite control registers @0x40080000, gp_clk domain)
    // =======================================================================
    frame_ctrl u_frame_ctrl (
        .S_AXI_ACLK    (gp_clk),
        .S_AXI_ARESETN (~gp_rst),
        .S_AXI_AWADDR  (frame_ctrl_awaddr),
        .S_AXI_AWPROT  (frame_ctrl_awprot),
        .S_AXI_AWVALID (frame_ctrl_awvalid),
        .S_AXI_AWREADY (),
        .S_AXI_WDATA   (frame_ctrl_wdata),
        .S_AXI_WSTRB   (frame_ctrl_wstrb),
        .S_AXI_WVALID  (frame_ctrl_wvalid),
        .S_AXI_WREADY  (),
        .S_AXI_ARADDR  (frame_ctrl_araddr),
        .S_AXI_ARPROT  (frame_ctrl_arprot),
        .S_AXI_ARVALID (frame_ctrl_arvalid),
        .S_AXI_ARREADY (),
        .S_AXI_RDATA   (frame_ctrl_rdata),
        .S_AXI_RRESP   (frame_ctrl_rresp),
        .S_AXI_RVALID  (frame_ctrl_rvalid),
        .S_AXI_RREADY  (frame_ctrl_rready),

        .dvp_pclk     (clk_74m25_bufg),
        .dvp_prst_n   (~cam_rst),
        .dvp_vsync_in (1'b0),
        .dvp_href_in  (1'b0),
        .dvp_db_in    (24'd0),
        .vsync_out    (),
        .href_out     (),
        .db_out       (),

        .x0_pos_num  (),
        .y0_pos_num  (),
        .x1_pos_num  (),
        .y1_pos_num  (),
        .x_len_num   (),
        .y_len_num   (),
        .hresize_num (),
        .vresize_num (),

        .ps_x0_pos   (),
        .ps_y0_pos   (),
        .ps_x1_pos   (),
        .ps_y1_pos   (),
        .ps_x_leng   (),
        .ps_y_leng   (),
        .ps_hstride  (),
        .ps_vstride  (),
        .resize_pix_len(),
        .write_ps_size (),

        .H_SYNC       (),
        .H_BACK_PORCH (),
        .H_ACTIVE     (),
        .H_FRONT_PORCH(),
        .V_SYNC       (),
        .V_BACK_PORCH (),
        .V_ACTIVE     (),
        .V_FRONT_PORCH(),
        .vtc_enable   (),

        .camera_wr_addr (),
        .camera_rd_addr (camera_rd_addr),
        .wr_wfifo_err   (1'b0),
        .rd_rfifo_err   (1'b0),
        .wr_done_pulse  (1'b0),

        .irq_test       (),
        .network_running(1'b0),
        .wr_buf_index   (2'd0),
        .rd_buf_index   (2'd0),
        .img_en_sync    (),
        .dvp_ov         (1'b0),
        .cnt_clr        (),
        .continuous_en  (),
        .display_en     (display_en),
        .frame_debug_en (),

        .M01_AXI_ACLK   (clk_74m25_bufg),
        .M01_AXI_ARESETN(~cam_rst),
        .sys_rst_n      (sys_rst_n & FCLK_RESET0_N),
        .soft_rst       (soft_rst)
    );

    // =======================================================================
    // User_GP0 <-> frame_ctrl bridge (AXI3 -> AXI-Lite, B synthesized)
    // =======================================================================
    axi3_to_axilite_bridge u_gp_bridge (
        .gp_clk   (gp_clk),
        .gp_rst_n (~gp_rst),

        .m_awvalid(user_gp0_awvalid),
        .m_awaddr (user_gp0_awaddr),
        .m_awid   (user_gp0_awid),
        .m_awprot (user_gp0_awprot),
        .m_awready(user_gp0_awready),
        .m_wvalid (user_gp0_wvalid),
        .m_wdata  (user_gp0_wdata),
        .m_wstrb  (user_gp0_wstrb),
        .m_wlast  (user_gp0_wlast),
        .m_wready (user_gp0_wready),
        .m_bvalid (user_gp0_bvalid),
        .m_bresp  (user_gp0_bresp),
        .m_bid    (user_gp0_bid),
        .m_bready (user_gp0_bready),
        .m_arvalid(user_gp0_arvalid),
        .m_araddr (user_gp0_araddr),
        .m_arid   (user_gp0_arid),
        .m_arprot (user_gp0_arprot),
        .m_arready(user_gp0_arready),
        .m_rvalid (user_gp0_rvalid),
        .m_rdata  (user_gp0_rdata),
        .m_rresp  (user_gp0_rresp),
        .m_rlast  (user_gp0_rlast),
        .m_rid    (user_gp0_rid),
        .m_rready (user_gp0_rready),

        .s_awvalid(frame_ctrl_awvalid),
        .s_awaddr (frame_ctrl_awaddr),
        .s_awprot (frame_ctrl_awprot),
        .s_wvalid (frame_ctrl_wvalid),
        .s_wdata  (frame_ctrl_wdata),
        .s_wstrb  (frame_ctrl_wstrb),
        .s_arvalid(frame_ctrl_arvalid),
        .s_araddr (frame_ctrl_araddr),
        .s_arprot (frame_ctrl_arprot),
        .s_rvalid (frame_ctrl_rvalid),
        .s_rdata  (frame_ctrl_rdata),
        .s_rresp  (frame_ctrl_rresp),
        .s_rready (frame_ctrl_rready)
    );

    // =======================================================================
    // FB read path (DDR -> HDMI), 720p
    // =======================================================================
    fb_read_720p u_fb_read_720p (
        .cam_clk        (clk_74m25_bufg),
        .clk_371m25     (clk_371m25_bufg),
        .rst_cam        (cam_rst),
        .display_en     (display_en),
        .camera_rd_addr (camera_rd_addr[26:0]),
        .hp_clk         (hp_clk),
        .rst_hp         (hp_rst),

        .m00_axi_arid   (m00_axi_arid),
        .m00_axi_araddr (m00_axi_araddr),
        .m00_axi_arlen  (m00_axi_arlen),
        .m00_axi_arsize (m00_axi_arsize),
        .m00_axi_arburst(m00_axi_arburst),
        .m00_axi_arlock (m00_axi_arlock),
        .m00_axi_arcache(m00_axi_arcache),
        .m00_axi_arprot (m00_axi_arprot),
        .m00_axi_arqos  (m00_axi_arqos),
        .m00_axi_arvalid(m00_axi_arvalid),
        .m00_axi_arready(m00_axi_arready),
        .m00_axi_rid    (m00_axi_rid),
        .m00_axi_rdata  (m00_axi_rdata),
        .m00_axi_rresp  (m00_axi_rresp),
        .m00_axi_rlast  (m00_axi_rlast),
        .m00_axi_rvalid (m00_axi_rvalid),
        .m00_axi_rready (m00_axi_rready),
        .m00_axi_awid   (m00_axi_awid),
        .m00_axi_awaddr (m00_axi_awaddr),
        .m00_axi_awlen  (m00_axi_awlen),
        .m00_axi_awsize (m00_axi_awsize),
        .m00_axi_awburst(m00_axi_awburst),
        .m00_axi_awlock (m00_axi_awlock),
        .m00_axi_awcache(m00_axi_awcache),
        .m00_axi_awprot (m00_axi_awprot),
        .m00_axi_awqos  (m00_axi_awqos),
        .m00_axi_awvalid(m00_axi_awvalid),
        .m00_axi_awready(m00_axi_awready),
        .m00_axi_wdata  (m00_axi_wdata),
        .m00_axi_wstrb  (m00_axi_wstrb),
        .m00_axi_wlast  (m00_axi_wlast),
        .m00_axi_wid    (m00_axi_wid),
        .m00_axi_wvalid (m00_axi_wvalid),
        .m00_axi_wready (m00_axi_wready),
        .m00_axi_bid    (m00_axi_bid),
        .m00_axi_bresp  (m00_axi_bresp),
        .m00_axi_bvalid (m00_axi_bvalid),
        .m00_axi_bready (m00_axi_bready),

        .hdmi_clk_p     (HDMI_CLK_P),
        .hdmi_clk_n     (HDMI_CLK_N),
        .hdmi_tx_p      (HDMI_TX_P),
        .hdmi_tx_n      (HDMI_TX_N)
    );

    // =======================================================================
    // Status LED: [0] = all clocks/PS7 locked, [1] = ~1 Hz blink
    // =======================================================================
    assign led[0] = mmcm1_locked & mmcm2_locked & mmcm3_locked & pll_lock;
    always @(posedge clk_74m25_bufg)
        blink_cnt <= blink_cnt + 1'b1;
    assign led[1] = blink_cnt[26];

endmodule
