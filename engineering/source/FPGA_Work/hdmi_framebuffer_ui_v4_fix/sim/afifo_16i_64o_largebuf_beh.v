// afifo_16i_64o_largebuf_beh.v — write-side async FIFO stub for the read-path
// simulation.  The write path (WR_START) is tied low in the testbench, so this
// FIFO is never written or read: it just presents a benign idle state.
// Port list matches afifo_16i_64o_largebuf_stub.v EXACTLY.
`timescale 1ns/1ps

module afifo_16i_64o_largebuf (
    input  wire        rst,
    input  wire        wr_clk,
    input  wire        rd_clk,
    input  wire [15:0] din,
    input  wire        wr_en,
    input  wire        rd_en,
    output wire [63:0] dout,
    output wire        full,
    output wire        empty,
    output wire [11:0] rd_data_count,
    output wire [13:0] wr_data_count,
    output wire        wr_rst_busy,
    output wire        rd_rst_busy
);
    assign dout          = 64'd0;
    assign full          = 1'b0;
    assign empty         = 1'b1;
    assign rd_data_count = 12'd0;
    assign wr_data_count = 14'd0;
    assign wr_rst_busy   = 1'b0;
    assign rd_rst_busy   = 1'b0;
endmodule
