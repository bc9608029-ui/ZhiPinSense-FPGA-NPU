// fb_read_720p.sv — 720p display read path (Phase 1A).
//
// NEW file.  Replicates the READ side of the official frame_to_ps_largebuf.v
// verbatim, with only the resolution/read-length changed to 720p:
//   color_bar(720p timing) -> video_rect_read_data(1280x720)
//     -> frame_read_write_largebuf (read-only) -> aq_axi_master -> m00_axi (HP2_1)
//   plus uihdmitx/TMDS chain and RGB565->RGB888 glue.
//
// Reused verbatim (unchanged): frame_read_write_largebuf, aq_axi_master,
//   video_rect_read_data, timing_gen_xy, level_cross, color_bar, uihdmitx.
//
// Differences from the official frame_to_ps_largebuf.v read path:
//   1) read_len = 27'd230400  (1280*720*16/64), 1080p was 27'd518400.
//   2) video_width/video_height = 1280/720,     1080p was 1920/1080.
//   3) camera write path removed (Phase 1A is PS->DDR, PL reads only).
//   4) aq_axi_master's native M_AXI (1-bit ID / 8-bit LEN) is width-adapted
//      to the ps_ai_wrapper S_AXI_HP2_1 slave port (5-bit ID / 4-bit LEN).
`timescale 1ns / 1ps

module fb_read_720p (
    // ---- pixel-clock (cam) domain ----
    input  wire        cam_clk,          // 74.25 MHz pixel clock
    input  wire        clk_371m25,       // 371.25 MHz TMDS x5 clock
    input  wire        rst_cam,          // active-high reset, cam_clk domain
    input  wire        display_en,       // from frame_ctrl (default 1)
    input  wire [26:0] camera_rd_addr,   // from frame_ctrl (byte addr >> 3)
    input  wire        read_buf_sel,     // from frame_ctrl camera_wr_addr[0] (double-buffer select bit0, 0/1)

    // ---- HP memory domain ----
    input  wire        hp_clk,           // 100 MHz HP AXI clock
    input  wire        rst_hp,           // active-high reset, hp_clk domain

    // ---- AXI master (to ps_ai_wrapper S_AXI_HP2_1), 64-bit data ----
    // read address
    output wire [4:0]  m00_axi_arid,
    output wire [31:0] m00_axi_araddr,
    output wire [3:0]  m00_axi_arlen,
    output wire [2:0]  m00_axi_arsize,
    output wire [1:0]  m00_axi_arburst,
    output wire [1:0]  m00_axi_arlock,
    output wire [3:0]  m00_axi_arcache,
    output wire [2:0]  m00_axi_arprot,
    output wire [3:0]  m00_axi_arqos,
    output wire        m00_axi_arvalid,
    input  wire        m00_axi_arready,
    // read data
    input  wire [4:0]  m00_axi_rid,
    input  wire [63:0] m00_axi_rdata,
    input  wire [1:0]  m00_axi_rresp,
    input  wire        m00_axi_rlast,
    input  wire        m00_axi_rvalid,
    output wire        m00_axi_rready,
    // write address
    output wire [4:0]  m00_axi_awid,
    output wire [31:0] m00_axi_awaddr,
    output wire [3:0]  m00_axi_awlen,
    output wire [2:0]  m00_axi_awsize,
    output wire [1:0]  m00_axi_awburst,
    output wire [1:0]  m00_axi_awlock,
    output wire [3:0]  m00_axi_awcache,
    output wire [2:0]  m00_axi_awprot,
    output wire [3:0]  m00_axi_awqos,
    output wire        m00_axi_awvalid,
    input  wire        m00_axi_awready,
    // write data
    output wire [63:0] m00_axi_wdata,
    output wire [7:0]  m00_axi_wstrb,
    output wire        m00_axi_wlast,
    output wire [4:0]  m00_axi_wid,
    output wire        m00_axi_wvalid,
    input  wire        m00_axi_wready,
    // write response
    input  wire [4:0]  m00_axi_bid,
    input  wire [1:0]  m00_axi_bresp,
    input  wire        m00_axi_bvalid,
    output wire        m00_axi_bready,

    // ---- HDMI ----
    output wire        hdmi_clk_p,
    output wire        hdmi_clk_n,
    output wire [2:0]  hdmi_tx_p,
    output wire [2:0]  hdmi_tx_n
);

    // =======================================================================
    // 1) 720p timing generator (color_bar) — only hs/vs/de are used
    // =======================================================================
    wire cb_hs, cb_vs, cb_de;
    wire [7:0] cb_r, cb_g, cb_b;      // unused (data comes from DDR)
    color_bar u_color_bar (
        .clk  (cam_clk),
        .rst  (rst_cam),
        .hs   (cb_hs),
        .vs   (cb_vs),
        .de   (cb_de),
        .rgb_r(cb_r),
        .rgb_g(cb_g),
        .rgb_b(cb_b)
    );

    // gate timing with display_en (matches official frame_to_ps_largebuf)
    wire timing_hs = cb_hs & display_en;
    wire timing_vs = cb_vs & display_en;
    wire timing_de = cb_de & display_en;

    // =======================================================================
    // 2) video rectangle read controller (drives read_req/read_en, outputs hs/vs/de/data)
    // =======================================================================
    wire        ch0_read_req;
    wire        ch0_read_req_ack_sync;
    wire        ch0_read_en;
    wire [15:0] ch0_read_data;
    wire        hs, vs, de;
    wire [15:0] vout_data;             // RGB565

    video_rect_read_data #(.DATA_WIDTH(16)) u_video_rect_read_data (
        .video_clk       (cam_clk),
        .rst             (rst_cam),
        .video_left_offset(12'd0),
        .video_top_offset (12'd0),
        .video_width     (12'd1280),
        .video_height    (12'd720),
        .read_req        (ch0_read_req),
        .read_req_ack    (ch0_read_req_ack_sync),
        .read_en         (ch0_read_en),
        .read_data       (ch0_read_data),
        .timing_hs       (timing_hs),
        .timing_vs       (timing_vs),
        .timing_de       (timing_de),
        .timing_data     (16'd0),
        .hs              (hs),
        .vs              (vs),
        .de              (de),
        .vout_data       (vout_data)
    );

    // =======================================================================
    // 3) read_req / read_req_ack clock-domain crossing (cam_clk <-> hp_clk)
    //    (matches official frame_to_ps_largebuf level_cross usage)
    // =======================================================================
    wire ch0_read_req_sync;       // read_req re-timed to hp_clk domain
    wire ch0_read_req_ack;        // ack in hp_clk domain

    level_cross u_level_cross_req (
        .a2   (ch0_read_req_sync),
        .clk2 (hp_clk),
        .rst2 (rst_hp),
        .a1   (ch0_read_req),
        .clk1 (cam_clk),
        .rst1 (rst_cam)
    );
    level_cross u_level_cross_ack (
        .a2   (ch0_read_req_ack_sync),
        .clk2 (cam_clk),
        .rst2 (rst_cam),
        .a1   (ch0_read_req_ack),
        .clk1 (hp_clk),
        .rst1 (rst_hp)
    );

    // =======================================================================
    // 4) frame read/write large buffer (read-only; write side tied off)
    // =======================================================================
    wire        rd_burst_req;
    wire [ 9:0] rd_burst_len;
    wire [26:0] rd_burst_addr;
    wire        rd_burst_data_valid;
    wire [63:0] rd_burst_data;
    wire        rd_burst_finish;
    wire        rfifo_full;

    // =======================================================================
    // 3b) double-buffer select CDC (gp_clk -> hp_clk), 1-bit only.
    //     camera_wr_addr[0] selects read buffer 0/1 and is re-written by the PS
    //     EVERY frame (double-buffer ping-pong), so it is NOT quasi-static.
    //     Only bit0 crosses this boundary; bit1 is fixed to 0 (only 2 buffers
    //     exist).  buf_sel_sync1/buf_sel_sync2 form an explicit 2-FF
    //     synchronizer (ASYNC_REG-tagged in the XDC).  The synchronized value
    //     is latched at frame start by frame_fifo_read's S_ACK state
    //     (read_addr_index_d1 -> rd_burst_addr), so a mid-frame re-write cannot
    //     tear the in-flight frame.
    // =======================================================================
    reg        buf_sel_sync1;   // 1st FF of the 2-FF synchronizer (hp_clk)
    reg        buf_sel_sync2;   // 2nd FF, synchronized bit0 (hp_clk)
    always @(posedge hp_clk or posedge rst_hp) begin
        if (rst_hp) begin
            buf_sel_sync1 <= 1'b0;
            buf_sel_sync2 <= 1'b0;
        end else begin
            buf_sel_sync1 <= read_buf_sel;
            buf_sel_sync2 <= buf_sel_sync1;
        end
    end

    frame_read_write_largebuf #(
        .MEM_DATA_BITS   (64),
        .READ_DATA_BITS  (16),
        .WRITE_DATA_BITS (16),
        .ADDR_BITS       (27),
        .BUSRT_BITS      (10),
        .BURST_SIZE      (16)
    ) u_frame_read_write_largebuf (
        .rst               (rst_hp),
        .mem_clk           (hp_clk),
        .rd_burst_req      (rd_burst_req),
        .rd_burst_len      (rd_burst_len),
        .rd_burst_addr     (rd_burst_addr),
        .rd_burst_data_valid(rd_burst_data_valid),
        .rd_burst_data     (rd_burst_data),
        .rd_burst_finish   (rd_burst_finish),
        .read_clk          (cam_clk),
        .read_req          (ch0_read_req_sync),
        .read_req_ack      (ch0_read_req_ack),
        .read_finish       (),
        .read_addr_0       (camera_rd_addr),
        .read_addr_1       (camera_rd_addr + 27'd230400),   // buffer 1 = buffer 0 + one 720p frame (Phase 1B double buffer)
        .read_addr_2       (camera_rd_addr),
        .read_addr_3       (camera_rd_addr),
        .read_addr_index   ({1'b0, buf_sel_sync2}),   // bit0 = synchronized buffer select, bit1 = 0 (only 2 buffers)
        .read_len          (27'd230400),   // 1280*720*16/64
        .read_en           (ch0_read_en),
        .read_data         (ch0_read_data),

        // write side tied off (Phase 1A: PS writes DDR, PL reads only)
        .wr_burst_req      (),
        .wr_burst_len      (),
        .wr_burst_addr     (),
        .wr_burst_data_req (1'b0),
        .wr_burst_data     (),
        .wr_burst_finish   (1'b0),
        .write_clk         (cam_clk),
        .write_req         (1'b0),
        .write_req_ack     (),
        .write_finish      (),
        .write_addr_0      (27'd0),
        .write_addr_1      (27'd0),
        .write_addr_2      (27'd0),
        .write_addr_3      (27'd0),
        .write_addr_index  (2'd0),
        .write_len         (27'd0),
        .write_en          (1'b0),
        .write_data        (16'd0),
        .wr_wfifo_err      (),
        .rd_rfifo_err      (),
        .wfifo_empty       (),
        .rfifo_full        (rfifo_full)
    );

    // =======================================================================
    // 5) AQUAXIS AXI master (read DDR over HP2_1)
    // =======================================================================
    // aq_axi_master native M_AXI (1-bit ID, 8-bit LEN)
    wire [0:0]  aq_m_awid, aq_m_arid;
    wire [31:0] aq_m_awaddr, aq_m_araddr;
    wire [7:0]  aq_m_awlen, aq_m_arlen;
    wire [2:0]  aq_m_awsize, aq_m_arsize;
    wire [1:0]  aq_m_awburst, aq_m_arburst;
    wire        aq_m_awlock;
    wire [1:0]  aq_m_arlock;
    wire [3:0]  aq_m_awcache, aq_m_arcache;
    wire [2:0]  aq_m_awprot, aq_m_arprot;
    wire [3:0]  aq_m_awqos, aq_m_arqos;
    wire        aq_m_awvalid, aq_m_arvalid;
    wire        aq_m_awready, aq_m_arready;
    wire [63:0] aq_m_wdata;
    wire [7:0]  aq_m_wstrb;
    wire        aq_m_wlast, aq_m_wvalid, aq_m_wready;
    wire [0:0]  aq_s_bid, aq_s_rid;
    wire [1:0]  aq_s_bresp, aq_s_rresp;
    wire        aq_s_bvalid, aq_s_rvalid, aq_s_rlast;
    wire        aq_m_bready, aq_m_rready;
    wire [63:0] aq_s_rdata;
    wire        aq_m_awuser, aq_m_wuser, aq_m_aruser;

    aq_axi_master u_aq_axi_master (
        .ARESETN        (~rst_hp),
        .ACLK           (hp_clk),
        .MASTER_RST     (1'b0),

        .M_AXI_AWID     (aq_m_awid),
        .M_AXI_AWADDR   (aq_m_awaddr),
        .M_AXI_AWLEN    (aq_m_awlen),
        .M_AXI_AWSIZE   (aq_m_awsize),
        .M_AXI_AWBURST  (aq_m_awburst),
        .M_AXI_AWLOCK   (aq_m_awlock),
        .M_AXI_AWCACHE  (aq_m_awcache),
        .M_AXI_AWPROT   (aq_m_awprot),
        .M_AXI_AWQOS    (aq_m_awqos),
        .M_AXI_AWUSER   (aq_m_awuser),
        .M_AXI_AWVALID  (aq_m_awvalid),
        .M_AXI_AWREADY  (aq_m_awready),

        .M_AXI_WDATA    (aq_m_wdata),
        .M_AXI_WSTRB    (aq_m_wstrb),
        .M_AXI_WLAST    (aq_m_wlast),
        .M_AXI_WUSER    (aq_m_wuser),
        .M_AXI_WVALID   (aq_m_wvalid),
        .M_AXI_WREADY   (aq_m_wready),

        .M_AXI_BID      (aq_s_bid),
        .M_AXI_BRESP    (aq_s_bresp),
        .M_AXI_BUSER    (1'b0),
        .M_AXI_BVALID   (aq_s_bvalid),
        .M_AXI_BREADY   (aq_m_bready),

        .M_AXI_ARID     (aq_m_arid),
        .M_AXI_ARADDR   (aq_m_araddr),
        .M_AXI_ARLEN    (aq_m_arlen),
        .M_AXI_ARSIZE   (aq_m_arsize),
        .M_AXI_ARBURST  (aq_m_arburst),
        .M_AXI_ARLOCK   (aq_m_arlock),
        .M_AXI_ARCACHE  (aq_m_arcache),
        .M_AXI_ARPROT   (aq_m_arprot),
        .M_AXI_ARQOS    (aq_m_arqos),
        .M_AXI_ARUSER   (aq_m_aruser),
        .M_AXI_ARVALID  (aq_m_arvalid),
        .M_AXI_ARREADY  (aq_m_arready),

        .M_AXI_RID      (aq_s_rid),
        .M_AXI_RDATA    (aq_s_rdata),
        .M_AXI_RRESP    (aq_s_rresp),
        .M_AXI_RLAST    (aq_s_rlast),
        .M_AXI_RUSER    (1'b0),
        .M_AXI_RVALID   (aq_s_rvalid),
        .M_AXI_RREADY   (aq_m_rready),

        .WR_START       (1'b0),
        .WR_ADRS        (32'd0),
        .WR_LEN         (32'd0),
        .WR_READY       (),
        .WR_FIFO_RE     (),
        .WR_FIFO_EMPTY  (1'b0),
        .WR_FIFO_AEMPTY (1'b0),
        .WR_FIFO_DATA   (64'd0),
        .WR_DONE        (),

        .RD_START       (rd_burst_req),
        .RD_ADRS        ({rd_burst_addr, 3'd0}),
        .RD_LEN         ({rd_burst_len, 3'd0}),
        .RD_READY       (),
        .RD_FIFO_WE     (rd_burst_data_valid),
        .RD_FIFO_FULL   (rfifo_full),
        .RD_FIFO_AFULL  (1'b0),
        .RD_FIFO_DATA   (rd_burst_data),
        .RD_DONE        (rd_burst_finish),

        .DEBUG          ()
    );

    // =======================================================================
    // 6) Width adaptation: aq_axi_master M_AXI (1-bit ID/8-bit LEN)
    //    -> S_AXI_HP2_1 (5-bit ID/4-bit LEN).  USER signals dropped, WID = 0.
    // =======================================================================
    // write address
    assign m00_axi_awid    = {4'b0, aq_m_awid};
    assign m00_axi_awaddr  = aq_m_awaddr;
    assign m00_axi_awlen   = aq_m_awlen[3:0];
    assign m00_axi_awsize  = aq_m_awsize;
    assign m00_axi_awburst = aq_m_awburst;
    assign m00_axi_awlock  = {1'b0, aq_m_awlock};
    assign m00_axi_awcache = aq_m_awcache;
    assign m00_axi_awprot  = aq_m_awprot;
    assign m00_axi_awqos   = aq_m_awqos;
    assign m00_axi_awvalid = aq_m_awvalid;
    assign aq_m_awready    = m00_axi_awready;
    // write data
    assign m00_axi_wdata   = aq_m_wdata;
    assign m00_axi_wstrb   = aq_m_wstrb;
    assign m00_axi_wlast   = aq_m_wlast;
    assign m00_axi_wid     = 5'd0;
    assign m00_axi_wvalid  = aq_m_wvalid;
    assign aq_m_wready     = m00_axi_wready;
    // write response
    assign aq_s_bid        = m00_axi_bid[0];
    assign aq_s_bresp      = m00_axi_bresp;
    assign aq_s_bvalid     = m00_axi_bvalid;
    assign m00_axi_bready  = aq_m_bready;
    // read address
    assign m00_axi_arid    = {4'b0, aq_m_arid};
    assign m00_axi_araddr  = aq_m_araddr;
    assign m00_axi_arlen   = aq_m_arlen[3:0];
    assign m00_axi_arsize  = aq_m_arsize;
    assign m00_axi_arburst = aq_m_arburst;
    assign m00_axi_arlock  = aq_m_arlock;
    assign m00_axi_arcache = aq_m_arcache;
    assign m00_axi_arprot  = aq_m_arprot;
    assign m00_axi_arqos   = aq_m_arqos;
    assign m00_axi_arvalid = aq_m_arvalid;
    assign aq_m_arready    = m00_axi_arready;
    // read data
    assign aq_s_rid        = m00_axi_rid[0];
    assign aq_s_rdata      = m00_axi_rdata;
    assign aq_s_rresp      = m00_axi_rresp;
    assign aq_s_rlast      = m00_axi_rlast;
    assign aq_s_rvalid     = m00_axi_rvalid;
    assign m00_axi_rready  = aq_m_rready;

    // =======================================================================
    // 7) RGB565 -> RGB888 (replicate MSBs into LSBs)
    // =======================================================================
    wire [7:0] hdmi_r = {vout_data[15:11], vout_data[13:11]};
    wire [7:0] hdmi_g = {vout_data[10: 5], vout_data[ 6: 5]};
    wire [7:0] hdmi_b = {vout_data[ 4: 0], vout_data[ 2: 0]};

    // =======================================================================
    // 8) HDMI TX (7-series, TMDS_33)
    // =======================================================================
    uihdmitx #(.FAMILY("7FAMILY")) u_hdmitx (
        .RSTn_i        (~rst_cam),
        .HS_i          (hs),
        .VS_i          (vs),
        .VDE_i         (de),
        .RGB_i         ({hdmi_r, hdmi_g, hdmi_b}),
        .PCLKX1_i      (cam_clk),
        .PCLKX2_5_i    (1'b0),
        .PCLKX5_i      (clk_371m25),
        .TMDS_TX_CLK_P (hdmi_clk_p),
        .TMDS_TX_CLK_N (hdmi_clk_n),
        .TMDS_TX_P     (hdmi_tx_p),
        .TMDS_TX_N     (hdmi_tx_n)
    );

endmodule
