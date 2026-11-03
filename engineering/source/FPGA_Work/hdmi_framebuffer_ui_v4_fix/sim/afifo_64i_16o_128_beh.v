// afifo_64i_16o_128_beh.v — functional (simulation-only) behavioural model of
// the Xilinx afifo_64i_16o_128 IP, for Verilator red/green verification of the
// aq_axi_master read-channel bug.
//
// Port list matches afifo_64i_16o_128_stub.v EXACTLY:
//   rst, wr_clk, rd_clk, din[63:0], wr_en, rd_en, dout[15:0], full, empty,
//   rd_data_count[16:0], wr_data_count[14:0], wr_rst_busy, rd_rst_busy
//
// Depth: 32768 x 64-bit on the write side == 131072 x 16-bit on the read side.
//
// This is an IDEALISED functional model: full / empty / *_data_count are
// computed combinationally from the raw write/read pointers with NO 2-FF
// synchroniser.  The consequence is that `full` asserts the *instant* the
// write pointer overtakes the read pointer by 32768 (rather than 2..3 clock
// cycles later as the real grey-coded FIFO does).  For the purpose of
// reproducing the aq_axi_master bug this is the correct, conservative choice:
// the bug is "RREADY drops while RD_FIFO_FULL=1 but the FSM keeps advancing",
// so an exact-on-time `full` reproduces it at least as faithfully as the real
// (slightly-late) full.
//
// Key Xilinx behaviour that MUST be modelled for the bug to reproduce:
//   * wr_data_count is 15-bit: at exactly 32768 used words it WRAPS to 0, so
//     frame_fifo_read (which tests `wrusedw < 32752`) sees 0 and keeps issuing
//     bursts even though the FIFO is physically full.  full stays asserted.
//   * A write while full is DROPPED (standard FIFO).  This is the actual data
//     loss the bug produces when RD_FIFO_WE is incorrectly held at 1.
`timescale 1ns/1ps

module afifo_64i_16o_128 (
    input  wire        rst,
    input  wire        wr_clk,
    input  wire        rd_clk,
    input  wire [63:0] din,
    input  wire        wr_en,
    input  wire        rd_en,
    output wire [15:0] dout,
    output wire        full,
    output wire        empty,
    output wire [16:0] rd_data_count,
    output wire [14:0] wr_data_count,
    output wire        wr_rst_busy,
    output wire        rd_rst_busy
);

    localparam WR_DEPTH = 32768;   // 64-bit words (2^15)

    reg [63:0] mem [0:WR_DEPTH-1];

    // 16-bit pointers so the "used" count can distinguish 32768 (full) from 0
    // (empty): wptr/rword wrap at 65536, so a difference of 32768 is visible.
    reg [15:0] wptr;      // write pointer (64-bit words), wr_clk domain
    reg [17:0] rptr;      // read pointer (16-bit words),  rd_clk domain

    wire [15:0] rword = rptr[17:2];   // read pointer in 64-bit words

    // Occupancy (combinational).  used==32768 => full (and wr_data_count wraps
    // to 0, exactly like the IP).
    wire [15:0] used = wptr - rword;

    assign full  = (used >= WR_DEPTH);
    assign empty = (rword == wptr);

    // Write side: drop writes while full (standard FIFO).
    always @(posedge wr_clk) begin
        if (rst) begin
            wptr <= 16'd0;
        end else if (wr_en && !full) begin
            mem[wptr[14:0]] <= din;
            wptr <= wptr + 16'd1;
        end
    end

    // Read side: 16-bit reads, 4 reads per 64-bit word.
    //
    // Xilinx FIFO Generator asymmetric FIFOs (write width > read width) read
    // MSB-FIRST (big-endian): the first read of a 64-bit word returns the most
    // significant 16-bit slice din[63:48], the last returns din[15:0].  (PG057
    // asymmetric-FIFO example: an 8-bit write `11_00_01_11` reads out `11`,
    // `00`, `01`, `11`.)  A design that assumes LSB-first will therefore emit
    // each 4-pixel group reversed.  This model reproduces the real IP.
    reg [15:0] dout_r;
    always @(posedge rd_clk) begin
        if (rst) begin
            rptr   <= 18'd0;
            dout_r <= 16'd0;
        end else if (rd_en && !empty) begin
            dout_r <= mem[rword[14:0]][(3 - rptr[1:0])*16 +: 16];
            rptr   <= rptr + 18'd1;
        end
    end
    assign dout = dout_r;

    assign wr_data_count = used[14:0];   // wraps to 0 at full
    assign rd_data_count = 17'd0;        // unconnected in DUT; keep deterministic
    assign wr_rst_busy    = 1'b0;
    assign rd_rst_busy    = 1'b0;

endmodule
