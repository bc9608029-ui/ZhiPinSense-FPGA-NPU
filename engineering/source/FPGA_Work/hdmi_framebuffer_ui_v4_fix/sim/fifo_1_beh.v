// fifo_1_beh.v — synchronous write-side staging FIFO stub for the read-path
// simulation.  Unused in this test (write path idle).  Port list matches
// fifo_1_stub.v EXACTLY.
`timescale 1ns/1ps

module fifo_1 (
    input  wire        clk,
    input  wire        srst,
    input  wire [63:0] din,
    input  wire        wr_en,
    input  wire        rd_en,
    output wire [63:0] dout,
    output wire        full,
    output wire        almost_full,
    output wire        empty,
    output wire        almost_empty,
    output wire [11:0] data_count
);
    assign dout         = 64'd0;
    assign full         = 1'b0;
    assign almost_full  = 1'b0;
    assign empty        = 1'b1;
    assign almost_empty = 1'b1;
    assign data_count   = 12'd0;
endmodule
