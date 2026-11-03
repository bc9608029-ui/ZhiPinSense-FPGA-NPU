`timescale 1ns/1ps

// Minimal PS -> PL control-only top.  The official ps_ai block design,
// processing_system7, M_AXI_GP0 interconnect, gp_io and clock/reset generation
// are retained.  PL DDR, DMA, IRQ, NPU and SDR datapaths are not instantiated.
module ps_pl_ctrl_smoke_top (
    inout [53:0] FIXED_IO_0_mio,
    inout [14:0] DDR_0_addr,
    inout [2:0]  DDR_0_ba,
    inout        DDR_0_cas_n,
    inout        DDR_0_ck_n,
    inout        DDR_0_ck_p,
    inout        DDR_0_cke,
    inout        DDR_0_cs_n,
    inout [3:0]  DDR_0_dm,
    inout [31:0] DDR_0_dq,
    inout [3:0]  DDR_0_dqs_n,
    inout [3:0]  DDR_0_dqs_p,
    inout        DDR_0_odt,
    inout        DDR_0_ras_n,
    inout        DDR_0_reset_n,
    inout        DDR_0_we_n,
    inout        FIXED_IO_0_ddr_vrn,
    inout        FIXED_IO_0_ddr_vrp,
    inout        FIXED_IO_0_ps_clk,
    inout        FIXED_IO_0_ps_porb,
    inout        FIXED_IO_0_ps_srstb
);

    wire gp_clk;
    wire fclk_reset0_n;
    wire pll_lock;
    wire gp_clk_rst;

    wire              User_GP0_ARVALID;
    wire              User_GP0_AWVALID;
    wire              User_GP0_BREADY;
    wire              User_GP0_RREADY;
    wire              User_GP0_WLAST;
    wire              User_GP0_WVALID;
    wire [11:0]       User_GP0_ARID;
    wire [11:0]       User_GP0_AWID;
    wire [11:0]       User_GP0_WID;
    wire [1:0]        User_GP0_ARBURST;
    wire [1:0]        User_GP0_ARLOCK;
    wire [2:0]        User_GP0_ARSIZE;
    wire [1:0]        User_GP0_AWBURST;
    wire [1:0]        User_GP0_AWLOCK;
    wire [2:0]        User_GP0_AWSIZE;
    wire [2:0]        User_GP0_ARPROT;
    wire [2:0]        User_GP0_AWPROT;
    wire [31:0]       User_GP0_ARADDR;
    wire [31:0]       User_GP0_AWADDR;
    wire [31:0]       User_GP0_WDATA;
    wire [3:0]        User_GP0_ARCACHE;
    wire [3:0]        User_GP0_ARLEN;
    wire [3:0]        User_GP0_ARQOS;
    wire [3:0]        User_GP0_AWCACHE;
    wire [3:0]        User_GP0_AWLEN;
    wire [3:0]        User_GP0_AWQOS;
    wire [3:0]        User_GP0_WSTRB;
    wire              User_GP0_ARREADY;
    wire              User_GP0_AWREADY;
    wire              User_GP0_BVALID;
    wire              User_GP0_RLAST;
    wire              User_GP0_RVALID;
    wire              User_GP0_WREADY;
    wire [11:0]       User_GP0_BID;
    wire [11:0]       User_GP0_RID;
    wire [1:0]        User_GP0_BRESP;
    wire [1:0]        User_GP0_RRESP;
    wire [31:0]       User_GP0_RDATA;

    wire [31:0] User_Reg_awwaddr;
    wire [31:0] User_Reg_awwdata;
    wire        User_Reg_awwvalid;
    wire        User_Reg_awwready;
    wire [31:0] User_Reg_araddr;
    wire        User_Reg_arvalid;
    wire        User_Reg_arready;
    wire [31:0] User_Reg_rdata;
    wire        User_Reg_rvalid;
    wire        User_Reg_rready;

    mna_gp_ww_itf gp0();
    mna_gp_ww_itf host_ctrl();
    mna_gp_ww_itf ai_ra();
    mna_gp_ww_itf cam();
    mna_gp_ww_itf user_op();

    ps_ai_wrapper u_ps_ai_wrapper (
        .FIXED_IO_mio       (FIXED_IO_0_mio),
        .FIXED_IO_ps_srstb  (FIXED_IO_0_ps_srstb),
        .FIXED_IO_ps_clk    (FIXED_IO_0_ps_clk),
        .FIXED_IO_ps_porb   (FIXED_IO_0_ps_porb),
        .DDR_ck_p           (DDR_0_ck_p),
        .DDR_ck_n           (DDR_0_ck_n),
        .DDR_cke            (DDR_0_cke),
        .DDR_cs_n           (DDR_0_cs_n),
        .DDR_ras_n          (DDR_0_ras_n),
        .DDR_cas_n          (DDR_0_cas_n),
        .DDR_we_n           (DDR_0_we_n),
        .DDR_ba             (DDR_0_ba),
        .DDR_addr           (DDR_0_addr),
        .DDR_odt            (DDR_0_odt),
        .DDR_reset_n        (DDR_0_reset_n),
        .DDR_dq             (DDR_0_dq),
        .DDR_dm             (DDR_0_dm),
        .DDR_dqs_p          (DDR_0_dqs_p),
        .DDR_dqs_n          (DDR_0_dqs_n),
        .FIXED_IO_ddr_vrn   (FIXED_IO_0_ddr_vrn),
        .FIXED_IO_ddr_vrp   (FIXED_IO_0_ddr_vrp),

        .reset_n            (fclk_reset0_n),
        .FCLK_RESET0_N      (fclk_reset0_n),
        .soft_rst_n         (1'b1),
        .hp_axi_aclk        (gp_clk),
        .ps_clk_out         (gp_clk),
        .pll_lock           (pll_lock),

        .User_GP0_ARVALID   (User_GP0_ARVALID),
        .User_GP0_AWVALID   (User_GP0_AWVALID),
        .User_GP0_BREADY    (User_GP0_BREADY),
        .User_GP0_RREADY    (User_GP0_RREADY),
        .User_GP0_WLAST     (User_GP0_WLAST),
        .User_GP0_WVALID    (User_GP0_WVALID),
        .User_GP0_ARID      (User_GP0_ARID),
        .User_GP0_AWID      (User_GP0_AWID),
        .User_GP0_WID       (User_GP0_WID),
        .User_GP0_ARBURST   (User_GP0_ARBURST),
        .User_GP0_ARLOCK    (User_GP0_ARLOCK),
        .User_GP0_ARSIZE    (User_GP0_ARSIZE),
        .User_GP0_AWBURST   (User_GP0_AWBURST),
        .User_GP0_AWLOCK    (User_GP0_AWLOCK),
        .User_GP0_AWSIZE    (User_GP0_AWSIZE),
        .User_GP0_ARPROT    (User_GP0_ARPROT),
        .User_GP0_AWPROT    (User_GP0_AWPROT),
        .User_GP0_ARADDR    (User_GP0_ARADDR),
        .User_GP0_AWADDR    (User_GP0_AWADDR),
        .User_GP0_WDATA     (User_GP0_WDATA),
        .User_GP0_ARCACHE   (User_GP0_ARCACHE),
        .User_GP0_ARLEN     (User_GP0_ARLEN),
        .User_GP0_ARQOS     (User_GP0_ARQOS),
        .User_GP0_AWCACHE   (User_GP0_AWCACHE),
        .User_GP0_AWLEN     (User_GP0_AWLEN),
        .User_GP0_AWQOS     (User_GP0_AWQOS),
        .User_GP0_WSTRB     (User_GP0_WSTRB),
        .User_GP0_ARREADY   (User_GP0_ARREADY),
        .User_GP0_AWREADY   (User_GP0_AWREADY),
        .User_GP0_BVALID    (User_GP0_BVALID),
        .User_GP0_RLAST     (User_GP0_RLAST),
        .User_GP0_RVALID    (User_GP0_RVALID),
        .User_GP0_WREADY    (User_GP0_WREADY),
        .User_GP0_BID       (User_GP0_BID),
        .User_GP0_RID       (User_GP0_RID),
        .User_GP0_BRESP     (User_GP0_BRESP),
        .User_GP0_RRESP     (User_GP0_RRESP),
        .User_GP0_RDATA     (User_GP0_RDATA),

        .BYolo_GP0_ARREADY  (1'b1),
        .BYolo_GP0_AWREADY  (1'b1),
        .BYolo_GP0_BVALID   (1'b0),
        .BYolo_GP0_RLAST    (1'b0),
        .BYolo_GP0_RVALID   (1'b0),
        .BYolo_GP0_WREADY   (1'b1),
        .BYolo_GP0_BID      (12'h0),
        .BYolo_GP0_RID      (12'h0),
        .BYolo_GP0_BRESP    (2'h0),
        .BYolo_GP0_RRESP    (2'h0),
        .BYolo_GP0_RDATA    (32'h0),
        .BYolo_GP1_ARREADY  (1'b1),
        .BYolo_GP1_AWREADY  (1'b1),
        .BYolo_GP1_BVALID   (1'b0),
        .BYolo_GP1_RLAST    (1'b0),
        .BYolo_GP1_RVALID   (1'b0),
        .BYolo_GP1_WREADY   (1'b1),
        .BYolo_GP1_BID      (12'h0),
        .BYolo_GP1_RID      (12'h0),
        .BYolo_GP1_BRESP    (2'h0),
        .BYolo_GP1_RRESP    (2'h0),
        .BYolo_GP1_RDATA    (32'h0),
        .User_GP1_ARREADY   (1'b1),
        .User_GP1_AWREADY   (1'b1),
        .User_GP1_BVALID    (1'b0),
        .User_GP1_RLAST     (1'b0),
        .User_GP1_RVALID    (1'b0),
        .User_GP1_WREADY    (1'b1),
        .User_GP1_BID       (12'h0),
        .User_GP1_RID       (12'h0),
        .User_GP1_BRESP     (2'h0),
        .User_GP1_RRESP     (2'h0),
        .User_GP1_RDATA     (32'h0),

        .PJTAG_TCK          (1'b0),
        .PJTAG_TMS          (1'b0),
        .PJTAG_TDI          (1'b0),
        .S_AXI_HP0_ARVALID  (1'b0),
        .S_AXI_HP0_AWVALID  (1'b0),
        .S_AXI_HP0_BREADY   (1'b0),
        .S_AXI_HP0_RREADY   (1'b0),
        .S_AXI_HP0_WVALID   (1'b0),
        .S_AXI_HP1_ARVALID  (1'b0),
        .S_AXI_HP1_AWVALID  (1'b0),
        .S_AXI_HP1_BREADY   (1'b0),
        .S_AXI_HP1_RREADY   (1'b0),
        .S_AXI_HP1_WVALID   (1'b0),
        .S_AXI_HP2_ARVALID  (1'b0),
        .S_AXI_HP2_AWVALID  (1'b0),
        .S_AXI_HP2_BREADY   (1'b0),
        .S_AXI_HP2_RREADY   (1'b0),
        .S_AXI_HP2_WVALID   (1'b0),
        .S_AXI_HP2_1_ARVALID(1'b0),
        .S_AXI_HP2_1_AWVALID(1'b0),
        .S_AXI_HP2_1_BREADY (1'b0),
        .S_AXI_HP2_1_RREADY (1'b0),
        .S_AXI_HP2_1_WVALID (1'b0),
        .S_AXI_HP3_ARVALID  (1'b0),
        .S_AXI_HP3_AWVALID  (1'b0),
        .S_AXI_HP3_BREADY   (1'b0),
        .S_AXI_HP3_RREADY   (1'b0),
        .S_AXI_HP3_WVALID   (1'b0),
        .pl_arready        (1'b0),
        .pl_awready        (1'b0),
        .pl_bvalid         (1'b0),
        .pl_rdata          (512'h0),
        .pl_rlast          (1'b0),
        .pl_rvalid         (1'b0),
        .pl_ra_araddr      (16'h0),
        .pl_ra_arvalid     (1'b0),
        .pl_ra_awaddr      (16'h0),
        .pl_ra_awdata      (32'h0),
        .pl_ra_awvalid     (1'b0),
        .pl_ra_rready      (1'b0),
        .pl_ra_clk         (gp_clk),
        .pl_itf_clk        (gp_clk),
        .pl_rst_n          (fclk_reset0_n),
        .pl_clk_en_b       (1'b1),
        .pl_bist_clk       (gp_clk),
        .pl_bist_rstn      (fclk_reset0_n),
        .pl_bist_en        (1'b0),
        .pl_int_ready      (1'b0),
        .pl_scan_clk       (gp_clk),
        .pl_scan_en        (1'b0),
        .pl_scan_i         (64'h0),
        .pl_scan_mode_b    (1'b1),
        .pl_scan_rst_n     (fclk_reset0_n),
        .customop_irq       (1'b0),
        .ai_irq             (1'b0),
        .test_irq           (1'b0)
    );

    // The GP0 datapath is clocked by the PS-derived gp_clk.  Match the
    // official demo_clkrst_wrapper behavior: its reset follows the PS fabric
    // reset, rather than an unrelated extra lock qualifier.
    async_to_sync_reset u_gp_reset_sync (
        .async_reset(~fclk_reset0_n),
        .clk        (gp_clk),
        .sync_reset (gp_clk_rst)
    );

    gp_io u_gp0_io (
        .M_AXI_GP_ARVALID (User_GP0_ARVALID),
        .M_AXI_GP_AWVALID (User_GP0_AWVALID),
        .M_AXI_GP_BREADY  (User_GP0_BREADY),
        .M_AXI_GP_RREADY  (User_GP0_RREADY),
        .M_AXI_GP_WLAST   (User_GP0_WLAST),
        .M_AXI_GP_WVALID  (User_GP0_WVALID),
        .M_AXI_GP_ARID    (User_GP0_ARID),
        .M_AXI_GP_AWID    (User_GP0_AWID),
        .M_AXI_GP_WID     (User_GP0_WID),
        .M_AXI_GP_ARBURST (User_GP0_ARBURST),
        .M_AXI_GP_ARLOCK  (User_GP0_ARLOCK),
        .M_AXI_GP_ARSIZE  (User_GP0_ARSIZE),
        .M_AXI_GP_AWBURST (User_GP0_AWBURST),
        .M_AXI_GP_AWLOCK  (User_GP0_AWLOCK),
        .M_AXI_GP_AWSIZE  (User_GP0_AWSIZE),
        .M_AXI_GP_ARPROT  (User_GP0_ARPROT),
        .M_AXI_GP_AWPROT  (User_GP0_AWPROT),
        .M_AXI_GP_ARADDR  (User_GP0_ARADDR),
        .M_AXI_GP_AWADDR  (User_GP0_AWADDR),
        .M_AXI_GP_WDATA   (User_GP0_WDATA),
        .M_AXI_GP_ARCACHE (User_GP0_ARCACHE),
        .M_AXI_GP_ARLEN   (User_GP0_ARLEN),
        .M_AXI_GP_ARQOS   (User_GP0_ARQOS),
        .M_AXI_GP_AWCACHE (User_GP0_AWCACHE),
        .M_AXI_GP_AWLEN   (User_GP0_AWLEN),
        .M_AXI_GP_AWQOS   (User_GP0_AWQOS),
        .M_AXI_GP_WSTRB   (User_GP0_WSTRB),
        .M_AXI_GP_ACLK    (),
        .M_AXI_GP_ARREADY (User_GP0_ARREADY),
        .M_AXI_GP_AWREADY (User_GP0_AWREADY),
        .M_AXI_GP_BVALID  (User_GP0_BVALID),
        .M_AXI_GP_RLAST   (User_GP0_RLAST),
        .M_AXI_GP_RVALID  (User_GP0_RVALID),
        .M_AXI_GP_WREADY  (User_GP0_WREADY),
        .M_AXI_GP_BID     (User_GP0_BID),
        .M_AXI_GP_RID     (User_GP0_RID),
        .M_AXI_GP_BRESP   (User_GP0_BRESP),
        .M_AXI_GP_RRESP   (User_GP0_RRESP),
        .M_AXI_GP_RDATA   (User_GP0_RDATA),
        .gp               (gp0.master),
        .gp_clk_rst       (gp_clk_rst),
        .gp_clk           (gp_clk)
    );

    gp0_manager #(.GP0_BASE(32'h40000000)) u_gp0_manager (
        .gpx       (gp0.slave),
        .host_ctrl (host_ctrl.master),
        .ai_ra     (ai_ra.master),
        .m2_gpx    (cam.master),
        .m3_gpx    (user_op.master),
        .gpx_rst   (gp_clk_rst),
        .gpx_clk   (gp_clk)
    );

    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_host_ctrl_rfu (
        .gpx(host_ctrl.slave), .gpx_rst(gp_clk_rst), .gpx_clk(gp_clk));
    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_ai_ra_rfu (
        .gpx(ai_ra.slave), .gpx_rst(gp_clk_rst), .gpx_clk(gp_clk));
    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_cam_rfu (
        .gpx(cam.slave), .gpx_rst(gp_clk_rst), .gpx_clk(gp_clk));

    assign User_Reg_araddr    = user_op.araddr;
    assign User_Reg_arvalid   = user_op.arvalid;
    assign User_Reg_rready    = user_op.rready;
    assign User_Reg_awwaddr   = user_op.awwaddr;
    assign User_Reg_awwdata   = user_op.awwdata;
    assign User_Reg_awwvalid  = user_op.awwvalid;
    assign user_op.arready    = User_Reg_arready;
    assign user_op.rdata      = User_Reg_rdata;
    assign user_op.rvalid     = User_Reg_rvalid;
    assign user_op.awwready   = User_Reg_awwready;

    ps_pl_ctrl_smoke_regs u_smoke_regs (
        .clk(gp_clk),
        .rst_n(~gp_clk_rst),
        .User_Reg_awwaddr(User_Reg_awwaddr),
        .User_Reg_awwdata(User_Reg_awwdata),
        .User_Reg_awwvalid(User_Reg_awwvalid),
        .User_Reg_awwready(User_Reg_awwready),
        .User_Reg_araddr(User_Reg_araddr),
        .User_Reg_arvalid(User_Reg_arvalid),
        .User_Reg_arready(User_Reg_arready),
        .User_Reg_rdata(User_Reg_rdata),
        .User_Reg_rvalid(User_Reg_rvalid),
        .User_Reg_rready(User_Reg_rready)
    );

endmodule
