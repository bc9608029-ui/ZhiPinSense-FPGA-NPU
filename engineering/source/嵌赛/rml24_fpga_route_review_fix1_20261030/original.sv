`timescale 1ns/1ps
// Double-buffer PSD storage and PS readback. Two 1024x64 banks hold the u54
// magnitude-square in fftshift order; the high 10 bits of each 64-bit word are
// zero (the frozen 54-bit power contract). The writer owns one bank per frame
// and flips on completion; the PS reads the other (committed) bank.
//
// The two banks are explicit single-dimension arrays (not a 2D `mem[0:1][...]`
// with a dynamic first index) so the synthesizer infers one block RAM per bank
// instead of flattening the whole thing into flip-flops plus a 2048:1 read mux.
//
// Bank ownership is derived from the writer's monotonically increasing frame_id:
// after frame N completes, frame_id == N+1 and frame N resides in bank (N mod 2),
// so committed_bank == ~frame_id[0] once frame_id >= 1. This avoids depending on
// the writer's internal flip timing.
module smart_scan_psd_buffers (
    input  wire        clk,
    input  wire        rst_n,
    // write port (driven by fft_psd_stream_writer)
    input  wire        wr_valid,
    input  wire        wr_bank,
    input  wire [9:0]  wr_addr,
    input  wire [53:0] wr_power,
    input  wire [31:0] frame_id,
    input  wire        protocol_error,
    input  wire        overflow,
    // read port (PS reads the committed bank)
    input  wire        rd_bank,
    input  wire [9:0]  rd_addr,
    output wire [63:0] rd_data,
    // status
    output wire [7:0]  version,
    output wire [31:0] status_frame_id,
    output wire        status_protocol_error,
    output wire        status_overflow,
    output wire        committed_valid,
    output wire        committed_bank
);
    localparam [7:0] VERSION = 8'h01;

    reg [63:0] mem0 [0:1023];
    reg [63:0] mem1 [0:1023];

    always @(posedge clk) begin
        if (wr_valid) begin
            if (wr_bank) mem1[wr_addr] <= {10'b0, wr_power};
            else         mem0[wr_addr] <= {10'b0, wr_power};
        end
    end

    reg [31:0] frame_id_r;
    reg        proto_err_r;
    reg        overflow_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_id_r  <= 32'd0;
            proto_err_r <= 1'b0;
            overflow_r  <= 1'b0;
        end else begin
            frame_id_r  <= frame_id;
            if (protocol_error) proto_err_r <= 1'b1;
            if (overflow)       overflow_r  <= 1'b1;
        end
    end

    assign rd_data             = rd_bank ? mem1[rd_addr] : mem0[rd_addr];
    assign version             = VERSION;
    assign status_frame_id     = frame_id_r;
    assign status_protocol_error = proto_err_r;
    assign status_overflow     = overflow_r;
    assign committed_valid     = (frame_id_r != 32'd0);
    assign committed_bank      = ~frame_id_r[0];
endmodule
