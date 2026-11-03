// axi_mem_model.v — AXI4 read-slave memory model for the read-path testbench.
//
// Holds a 2-frame array (460800 x 64-bit = 2 x 230400 words).  Buffer 0
// (words 0..230399) has x=0..39 = pixel index 0..39 on every line; buffer 1
// (words 230400..460799) has x=0..39 = 0x00FF.  One line = 1280 px = 320
// x 64-bit words, so the first 10 words of each 320-word line carry the marker.
//
// The only behaviour that matters for reproducing the aq_axi_master bug is that
// the R channel is a *faithful* AXI slave: when RREADY is deasserted, RVALID /
// RDATA / RLAST must be HELD unchanged (the slave never drops a beat).  A real
// AXI slave pauses the burst on RREADY=0; this model does exactly that, so the
// DUT's premature RLAST/beat counting under FIFO-full is observable as dropped
// beats and misaligned data.
`timescale 1ns/1ps

module axi_mem_model (
    input  wire        clk,
    input  wire        rst,
    // AR channel
    input  wire [0:0]  arid,
    input  wire [31:0] araddr,
    input  wire [7:0]  arlen,
    input  wire [2:0]  arsize,
    input  wire [1:0]  arburst,
    input  wire        arvalid,
    output reg         arready,
    // R channel
    output reg  [0:0]  rid,
    output reg  [63:0] rdata,
    output reg  [1:0]  rresp,
    output reg         rlast,
    output reg         rvalid,
    input  wire        rready
);

    localparam DEPTH = 460800;   // 64-bit words (2 x 230400-word frames)
    reg [63:0] mem [0:DEPTH-1];

    integer y, i;
    initial begin
        for (i = 0; i < DEPTH; i = i + 1) mem[i] = 64'h0000_0000_0000_0000;
        // Test image: first 40 px of every line hold their PIXEL INDEX (0..39),
        // the rest are 0x0000.  This is deliberately sensitive to the 64->16
        // FIFO word-slicing order: with correct LSB-first order, screen x shows
        // value x; with a wrong MSB-first order, screen x shows 3-(x%4) etc.,
        // so a mis-order produces a mismatch instead of silently passing.
        //   word i = pixels 4i..4i+3, LSB 16-bit half = pixel 4i, MSB = 4i+3.
        //
        // Buffer 0 (words 0..230399): first 40 px = pixel index 0..39.
        for (y = 0; y < 720; y = y + 1) begin
            for (i = 0; i < 10; i = i + 1) begin  // 10 words = 40 px
                mem[y*320 + i] = {16'(4*i+3), 16'(4*i+2), 16'(4*i+1), 16'(4*i)};
            end
        end
        // Buffer 1 (words 230400..460799): first 40 px = 0x00FF (distinct marker).
        for (y = 0; y < 720; y = y + 1) begin
            for (i = 0; i < 10; i = i + 1) begin
                mem[230400 + y*320 + i] = 64'h00FF_00FF_00FF_00FF;
            end
        end
    end

    reg [31:0] cur_addr;
    reg [7:0]  remaining;   // beats left to send, including the current one
    reg        active;

    wire [31:0] next_addr = cur_addr + 32'd8;

    always @(posedge clk) begin
        if (rst) begin
            arready   <= 1'b1;
            active    <= 1'b0;
            rvalid    <= 1'b0;
            rlast     <= 1'b0;
            rdata     <= 64'd0;
            rid       <= 1'b0;
            rresp     <= 2'b00;
            cur_addr  <= 32'd0;
            remaining <= 8'd0;
        end else begin
            arready <= ~active;   // accept AR only when idle (single outstanding burst)

            if (!active && arvalid && arready) begin
                active    <= 1'b1;
                cur_addr  <= araddr;
                remaining <= arlen + 8'd1;
                rid       <= arid;
            end

            if (active) begin
                if (!rvalid) begin
                    // send the first (or next) beat
                    rvalid <= 1'b1;
                    rdata  <= mem[cur_addr[21:3]];
                    rlast  <= (remaining == 8'd1);
                end else if (rready) begin
                    // current beat accepted by the master
                    if (remaining == 8'd1) begin
                        // burst complete
                        rvalid <= 1'b0;
                        rlast  <= 1'b0;
                        active <= 1'b0;
                    end else begin
                        remaining <= remaining - 8'd1;
                        cur_addr  <= next_addr;
                        rdata     <= mem[next_addr[21:3]];
                        rlast     <= (remaining == 8'd2);
                    end
                end
                // else: rvalid=1 && rready=0 -> HOLD rvalid/rdata/rlast (AXI pause)
            end
        end
    end

endmodule
