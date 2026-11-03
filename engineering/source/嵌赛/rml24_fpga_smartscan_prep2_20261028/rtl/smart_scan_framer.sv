`timescale 1ns/1ps
// Production framer: applies the frozen symmetric-Hann Q1.15 window to the
// PS->PL int16 I/Q stream and carries the frame `last` marker through the
// window pipeline so it stays aligned with the data under backpressure.
//
// Two registers keep the ROM read off the multiply critical path: the stage-1
// register captures (data, coefficient, valid, last) together, so the Hann ROM
// read (coeff_idx -> ROM -> w_r) is a separate reg-to-reg path from the
// multiply (i_r/q_r/w_r -> window -> m_q). `last` therefore has a 2-cycle
// latency, exactly matching `m_valid` (stage-1 + window).
//
// This supersedes the OOC smoke harness's unity window + naive 1-cycle
// `s_last_r` delay, which was documented as correct only under no-stall.
module smart_scan_framer (
    input  wire               clk,
    input  wire               rst_n,
    input  wire signed [15:0] s_i,
    input  wire signed [15:0] s_q,
    input  wire               s_valid,
    output wire               s_ready,
    input  wire               s_last,      // authoritative frame boundary from PS
    output wire signed [15:0] m_i,
    output wire signed [15:0] m_q,
    output wire               m_valid,
    input  wire               m_ready,
    output wire               m_last
);
    // --- stage 1: register data + coefficient + valid + last together ---
    reg signed [15:0] d_i, d_q, d_w;
    reg               d_valid, d_last;
    reg [9:0]         coeff_idx;

    wire signed [15:0] coeff;
    hann_coeff_rom u_rom (.addr(coeff_idx), .dout(coeff));

    wire win_ready;                       // window_mul_q15's s_ready (== its free)
    wire stg1_free = !d_valid || win_ready;
    assign s_ready = stg1_free;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            d_i <= 16'sd0; d_q <= 16'sd0; d_w <= 16'sd0;
            d_valid <= 1'b0; d_last <= 1'b0;
            coeff_idx <= 10'd0;
        end else if (stg1_free) begin
            d_valid <= s_valid;
            d_last  <= s_valid && s_last;
            d_i <= s_i;
            d_q <= s_q;
            d_w <= coeff;                     // coefficient for the accepted sample
            if (s_valid)
                coeff_idx <= s_last ? 10'd0 : coeff_idx + 1'b1;
        end
    end

    // --- stage 2: the frozen Q1.15 window multiply/round/sat ---
    window_mul_q15 u_window (
        .clk(clk), .rst_n(rst_n),
        .s_i(d_i), .s_q(d_q), .s_w(d_w),
        .s_valid(d_valid), .s_ready(win_ready),
        .m_i(m_i), .m_q(m_q), .m_valid(m_valid), .m_ready(m_ready)
    );

    // Carry `last` through the window's 1-cycle output register, advancing only
    // on the window's free condition so m_last stays aligned with m_valid.
    reg last_r;
    wire win_free = !m_valid || m_ready;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            last_r <= 1'b0;
        else if (win_free)
            last_r <= d_valid && d_last;
    end
    assign m_last = last_r;
endmodule
