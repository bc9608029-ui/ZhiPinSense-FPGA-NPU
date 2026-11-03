`timescale 1ns/1ps
// Explicit boundary around a Procise-generated FFT IP instance.
// There is deliberately no FFT implementation here: connect the generated
// vendor core to these ports and preserve the frozen scaling/order contract.
module procise_fft_axis_boundary(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire signed [15:0]   s_i,
    input  wire signed [15:0]   s_q,
    input  wire                 s_valid,
    output wire                 s_ready,
    input  wire                 s_last,

    output wire signed [15:0]   fft_s_i,
    output wire signed [15:0]   fft_s_q,
    output wire                 fft_s_valid,
    input  wire                 fft_s_ready,
    output wire                 fft_s_last,

    input  wire signed [26:0]   fft_m_re,
    input  wire signed [26:0]   fft_m_im,
    input  wire [9:0]           fft_m_index,
    input  wire                 fft_m_valid,
    output wire                 fft_m_ready,
    input  wire                 fft_m_last,

    output wire signed [26:0]   m_re,
    output wire signed [26:0]   m_im,
    output wire [9:0]           m_index,
    output wire                 m_valid,
    input  wire                 m_ready,
    output wire                 m_last
);
    assign fft_s_i = s_i;
    assign fft_s_q = s_q;
    assign fft_s_valid = s_valid;
    assign s_ready = fft_s_ready;
    assign fft_s_last = s_last;

    assign m_re = fft_m_re;
    assign m_im = fft_m_im;
    assign m_index = fft_m_index;
    assign m_valid = fft_m_valid;
    assign fft_m_ready = m_ready;
    assign m_last = fft_m_last;

    // rst_n is part of the frozen boundary even when the generated FFT exposes
    // its own reset/configuration ports at the integration layer.
    wire unused_rst_n = rst_n;
endmodule
