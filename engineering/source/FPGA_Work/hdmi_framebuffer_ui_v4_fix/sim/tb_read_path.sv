// tb_read_path.sv — Verilator red/green testbench for the HDMI DDR read path.
//
// Replicates the READ side of fb_read_720p.sv exactly (same module instances and
// same wiring), minus the HDMI TX and minus the HP2 width adaptation — aq_axi_master
// is connected straight to the AXI memory model (1-bit ID / 8-bit LEN).
//
// Test image (axi_mem_model): buffer 0 has x=0..39 = pixel index 0..39, buffer 1
// has x=0..39 = 0x00FF, the rest 0x0000, on every line.  The buffer-0 marker is
// deliberately sensitive to the 64->16 word-slicing order: correct LSB-first order
// shows value x, a wrong MSB-first order shows a reversed 4-pixel group.  A correct
// read path yields:
//   * exactly 230400 AXI beats per frame (230400 x 64-bit words), for both buffers
//   * 921600 valid pixels / 720 lines per frame
//   * 0 FIFO underflows, 0 pixel mismatches
//   * buffer 0/1 switch reads a full 230400-word frame from the other buffer
//
// The bug exposed here is the 64->16 word-slicing order: the Xilinx asymmetric
// FIFO (afifo_64i_16o_128) reads MSB-first (big-endian), but the design assumed
// LSB-first, so each 4-pixel group came out reversed.  RED (unmodified
// aq_axi_master) must FAIL; GREEN (the RD_FIFO_DATA half-word reversal) must PASS.
`timescale 1ns/1ps

module tb_read_path;

    // ------------------------------------------------------------------ clock
    reg hp_clk  = 1'b0;
    reg cam_clk = 1'b0;
    always #5.0   hp_clk  = ~hp_clk;    // 100  MHz
    always #6.734 cam_clk = ~cam_clk;   //  74.25 MHz (period 13.468 ns)

    reg rst_hp  = 1'b1;
    reg rst_cam = 1'b1;

    // ----------------------------------------------------------- test stimulus
    wire        display_en     = 1'b1;
    wire [26:0] camera_rd_addr = 27'd0;
    reg         read_buf_sel   = 1'b0;   // 0 -> buffer 0, 1 -> buffer 1 (flips mid-test)

    // =====================================================================
    // 1) timing generator (color_bar) — only hs/vs/de used
    // =====================================================================
    wire       cb_hs, cb_vs, cb_de;
    wire [7:0] cb_r, cb_g, cb_b;      // unused
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

    wire timing_hs = cb_hs & display_en;
    wire timing_vs = cb_vs & display_en;
    wire timing_de = cb_de & display_en;

    // =====================================================================
    // 2) video rectangle read controller
    // =====================================================================
    wire        ch0_read_req;
    wire        ch0_read_req_ack_sync;
    wire        ch0_read_en;
    wire [15:0] ch0_read_data;
    wire        hs, vs, de;
    wire [15:0] vout_data;

    video_rect_read_data #(.DATA_WIDTH(16)) u_video_rect_read_data (
        .video_clk        (cam_clk),
        .rst              (rst_cam),
        .video_left_offset(12'd0),
        .video_top_offset (12'd0),
        .video_width      (12'd1280),
        .video_height     (12'd720),
        .read_req         (ch0_read_req),
        .read_req_ack     (ch0_read_req_ack_sync),
        .read_en          (ch0_read_en),
        .read_data        (ch0_read_data),
        .timing_hs        (timing_hs),
        .timing_vs        (timing_vs),
        .timing_de        (timing_de),
        .timing_data      (16'd0),
        .hs               (hs),
        .vs               (vs),
        .de               (de),
        .vout_data        (vout_data)
    );

    // =====================================================================
    // 3) read_req / read_req_ack clock-domain crossing
    // =====================================================================
    wire ch0_read_req_sync;
    wire ch0_read_req_ack;

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

    // =====================================================================
    // 3b) double-buffer select CDC (read_buf_sel=0 -> buf_sel_sync2=0)
    // =====================================================================
    reg buf_sel_sync1;
    reg buf_sel_sync2;
    always @(posedge hp_clk or posedge rst_hp) begin
        if (rst_hp) begin
            buf_sel_sync1 <= 1'b0;
            buf_sel_sync2 <= 1'b0;
        end else begin
            buf_sel_sync1 <= read_buf_sel;
            buf_sel_sync2 <= buf_sel_sync1;
        end
    end

    // =====================================================================
    // 4) frame read/write large buffer (read-only)
    // =====================================================================
    wire        rd_burst_req;
    wire [ 9:0] rd_burst_len;
    wire [26:0] rd_burst_addr;
    wire        rd_burst_data_valid;
    wire [63:0] rd_burst_data;
    wire        rd_burst_finish;
    wire        rfifo_full;
    wire        read_finish_w;
    wire        rd_rfifo_err_w;

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
        .read_finish       (read_finish_w),
        .read_addr_0       (camera_rd_addr),
        .read_addr_1       (camera_rd_addr + 27'd230400),
        .read_addr_2       (camera_rd_addr),
        .read_addr_3       (camera_rd_addr),
        .read_addr_index   ({1'b0, buf_sel_sync2}),
        .read_len          (27'd230400),
        .read_en           (ch0_read_en),
        .read_data         (ch0_read_data),

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
        .rd_rfifo_err      (rd_rfifo_err_w),
        .wfifo_empty       (),
        .rfifo_full        (rfifo_full)
    );

    // =====================================================================
    // 5) aq_axi_master (native 1-bit ID / 8-bit LEN)
    // =====================================================================
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

    // write channel tie-off (no writes in this test)
    assign aq_m_awready = 1'b0;
    assign aq_m_wready  = 1'b0;
    assign aq_s_bid     = 1'b0;
    assign aq_s_bresp   = 2'b00;
    assign aq_s_bvalid  = 1'b0;

    // =====================================================================
    // 6) AXI read-slave memory model
    // =====================================================================
    axi_mem_model u_mem (
        .clk     (hp_clk),
        .rst     (rst_hp),
        .arid    (aq_m_arid),
        .araddr  (aq_m_araddr),
        .arlen   (aq_m_arlen),
        .arsize  (aq_m_arsize),
        .arburst (aq_m_arburst),
        .arvalid (aq_m_arvalid),
        .arready (aq_m_arready),
        .rid     (aq_s_rid),
        .rdata   (aq_s_rdata),
        .rresp   (aq_s_rresp),
        .rlast   (aq_s_rlast),
        .rvalid  (aq_s_rvalid),
        .rready  (aq_m_rready)
    );

    // =====================================================================
    // monitor — hp_clk domain: per-frame AXI beat count
    // =====================================================================
    reg        prev_read_finish;
    integer    rfin_cnt = 0;
    reg [31:0] beat_frame = 32'd0;
    reg [31:0] frame_beat [0:3];

    // FIFO-full diagnostics (hp_clk domain)
    reg        prev_rfifo_full;
    integer    full_event  = 0;   // rising edges of rfifo_full
    integer    full_cycles  = 0;  // total cycles rfifo_full asserted
    integer    drop_we      = 0;  // RD_FIFO_WE=1 while full (dropped writes)

    always @(posedge hp_clk) begin
        prev_read_finish <= read_finish_w;
        if (read_finish_w && !prev_read_finish) begin
            frame_beat[rfin_cnt] <= beat_frame;
            rfin_cnt <= rfin_cnt + 1;
            beat_frame <= 32'd0;
            // After frame #2 finishes, switch to buffer 1 so frame #3/#4 read
            // from read_addr_1 (= base + 230400 words).  Verifies the double
            // buffer select actually moves the read window by a full frame.
            if (rfin_cnt == 1) read_buf_sel <= 1'b1;
        end
        if (aq_s_rvalid && aq_m_rready) begin
            beat_frame <= beat_frame + 32'd1;
        end

        prev_rfifo_full <= rfifo_full;
        if (rfifo_full && !prev_rfifo_full) full_event <= full_event + 1;
        if (rfifo_full)                       full_cycles <= full_cycles + 1;
        if (rd_burst_data_valid && rfifo_full) drop_we <= drop_we + 1;
    end

    // =====================================================================
    // monitor — cam_clk domain: pixel mismatch / valid count / lines / underflow
    // =====================================================================
    reg        prev_read_req;
    integer    rreq_cnt = 0;
    reg        measuring = 1'b0;
    reg        cur_buf1  = 1'b0;   // 1 while measuring a buffer-1 frame
    reg [31:0] mismatch_buf0 = 32'd0;
    reg [31:0] mismatch_buf1 = 32'd0;
    reg [31:0] valid_px_cnt  = 32'd0;
    reg [31:0] line_cnt      = 32'd0;
    reg [31:0] underflow_cnt = 32'd0;
    reg [11:0] px_in_line = 12'd0;
    reg        prev_de;
    integer    first_mm_x = -1;
    integer    first_mm_y = -1;

    always @(posedge cam_clk) begin
        prev_read_req <= ch0_read_req;
        if (ch0_read_req && !prev_read_req) begin
            case (rreq_cnt)
                1: begin  // frame #2 starts (buffer 0) -> measure buf0
                    measuring     <= 1'b1;
                    cur_buf1      <= 1'b0;
                    mismatch_buf0 <= 32'd0;
                    valid_px_cnt  <= 32'd0;
                    line_cnt      <= 32'd0;
                    underflow_cnt <= 32'd0;
                    px_in_line    <= 12'd0;
                    first_mm_x    <= -1;
                    first_mm_y    <= -1;
                end
                2: measuring <= 1'b0;   // frame #3 starts (buffer 1) -> settle
                3: begin  // frame #4 starts (buffer 1) -> measure buf1
                    measuring     <= 1'b1;
                    cur_buf1      <= 1'b1;
                    mismatch_buf1 <= 32'd0;
                    px_in_line    <= 12'd0;
                end
                4: measuring <= 1'b0;   // frame #5 -> stop
            endcase
            rreq_cnt <= rreq_cnt + 1;
        end

        prev_de <= de;
        if (de && !prev_de) begin
            if (measuring && !cur_buf1) line_cnt <= line_cnt + 32'd1;
        end

        if (measuring) begin
            if (de) begin
                if (!cur_buf1) valid_px_cnt <= valid_px_cnt + 32'd1;
                if (px_in_line < 12'd40) begin
                    if (cur_buf1) begin
                        // buffer 1 marker: first 40 px = 0x00FF
                        if (vout_data != 16'h00FF) begin
                            mismatch_buf1 <= mismatch_buf1 + 32'd1;
                            if (first_mm_x == -1) begin first_mm_x <= px_in_line; first_mm_y <= line_cnt; end
                        end
                    end else begin
                        // expect pixel value == pixel index (0..39), i.e. the
                        // 64->16 word-slicing order is LSB-first and correct.
                        if (vout_data != {4'd0, px_in_line}) begin
                            mismatch_buf0 <= mismatch_buf0 + 32'd1;
                            if (first_mm_x == -1) begin first_mm_x <= px_in_line; first_mm_y <= line_cnt; end
                        end
                    end
                end else begin
                    if (vout_data != 16'h0000) begin
                        if (cur_buf1) begin
                            mismatch_buf1 <= mismatch_buf1 + 32'd1;
                            if (first_mm_x == -1) begin first_mm_x <= px_in_line; first_mm_y <= line_cnt; end
                        end else begin
                            mismatch_buf0 <= mismatch_buf0 + 32'd1;
                            if (first_mm_x == -1) begin first_mm_x <= px_in_line; first_mm_y <= line_cnt; end
                        end
                    end
                end
                px_in_line <= px_in_line + 12'd1;
            end else begin
                px_in_line <= 12'd0;
            end
        end
        if (rd_rfifo_err_w && measuring) underflow_cnt <= underflow_cnt + 32'd1;
    end

    // =====================================================================
    // run + verdict
    // =====================================================================
    initial begin
        rst_hp  = 1'b1;
        rst_cam = 1'b1;
        #300;
        rst_hp  = 1'b0;
        rst_cam = 1'b0;

        // 5 full frames (~83 ms) + margin.  Frame #2 (buffer 0) and frame #4
        // (buffer 1) are the measurement windows; read_buf_sel flips after
        // frame #2 finishes (see the hp_clk monitor).
        #80_000_000;

        $display("================ READ-PATH RESULT ================");
        $display("frame_beat[0] = %0d  (expect 230400)", frame_beat[0]);
        $display("frame_beat[1] = %0d  (expect 230400, buf0)", frame_beat[1]);
        $display("frame_beat[2] = %0d  (expect 230400)", frame_beat[2]);
        $display("frame_beat[3] = %0d  (expect 230400, buf1)", frame_beat[3]);
        $display("valid_px_cnt  = %0d  (expect 921600)",  valid_px_cnt);
        $display("line_cnt      = %0d  (expect 720)",    line_cnt);
        $display("mismatch_buf0 = %0d  (expect 0)",      mismatch_buf0);
        $display("mismatch_buf1 = %0d  (expect 0)",      mismatch_buf1);
        $display("underflow_cnt = %0d  (expect 0)",      underflow_cnt);
        $display("--- diagnostics ---");
        $display("full_event    = %0d  (FIFO-full rising edges)", full_event);
        $display("full_cycles   = %0d  (cycles FIFO full)", full_cycles);
        $display("drop_we       = %0d  (RD_FIFO_WE while full)", drop_we);
        $display("first_mismatch@ (x=%0d, y=%0d)", first_mm_x, first_mm_y);

        if (frame_beat[1] == 32'd230400 && frame_beat[3] == 32'd230400
            && valid_px_cnt == 32'd921600 && line_cnt == 32'd720
            && mismatch_buf0 == 32'd0 && mismatch_buf1 == 32'd0
            && underflow_cnt == 32'd0) begin
            $display("VERDICT: PASS");
        end else begin
            $display("VERDICT: FAIL");
        end
        $finish;
    end

endmodule
