`timescale 1ns/1ps
`default_nettype none

// Generates the authoritative per-frame `tlast` for the smart-scan datapath.
//
// The PS->PL IQ stream from the DDR reader/unpacker carries no frame boundary:
// it is a flat sequence of {Q[15:0],I[15:0]} samples.  The Hann framer and the
// FFT writer both require an explicit `last` marker on sample index 1023 of
// every 1024-sample frame (the framer resets its window coefficient index on
// `last`; the writer checks `s_last == (s_index == 1023)` and flags a protocol
// error otherwise).  This module inserts that marker by counting accepted
// samples, so `tlast` stays aligned with the data even under backpressure.
//
// A byte count that is not an exact multiple of 4096 (== 1024 samples x 4
// bytes) is rejected at START time by the register bank (BAD_CONFIG); this
// module therefore never needs to emit a partial-frame `last`.
module smart_scan_iq_frame_marker #(
    parameter integer FRAME_LENGTH = 1024
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [31:0]  s_tdata,
    input  wire         s_tvalid,
    output wire         s_tready,
    output wire [31:0]  m_tdata,
    output wire         m_tvalid,
    output wire         m_tlast,
    input  wire         m_tready
);
    localparam integer COUNT_WIDTH = $clog2(FRAME_LENGTH);

    reg [COUNT_WIDTH-1:0] count;

    assign m_tdata  = s_tdata;
    assign m_tvalid = s_tvalid;
    assign s_tready = m_tready;
    assign m_tlast  = s_tvalid && (count == FRAME_LENGTH - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= {COUNT_WIDTH{1'b0}};
        else if (s_tvalid && m_tready)
            count <= (count == FRAME_LENGTH - 1) ? {COUNT_WIDTH{1'b0}} : count + 1'b1;
    end
endmodule

`default_nettype wire
