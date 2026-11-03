// M26-A.1  DC-offset removal (first-order high-pass).
//
//   y[n] = x[n] - x[n-1] + R*y[n-1],   R = 1 - 2^-7 = 127/128
//
// Implemented per M26_FIXED_POINT_CONTRACT.md §1: the feedback `y_d1 - (y_d1>>>7)`
// and the difference term are kept in a wide accumulator (Q9.30), so the >>>7
// truncation floor sits far below the Q1.15 output LSB; only the output is rounded
// (round-half-away-from-zero) and symmetrically saturated to Q1.15.
//
// bypass=1 -> output is the input sample, bit-for-bit, order unchanged (the 1-cycle
// pipeline latency is identical for both paths).
module m26_dc_removal (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        bypass,
    // AXI-Stream slave  (tdata = {I[15:0], Q[15:0]}, Q1.15)
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,
    input  logic        s_axis_tlast,
    // AXI-Stream master
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tlast
);
  import m26_fxp_pkg::*;

  logic        out_valid;
  logic [15:0] i_in, q_in;

  // Q9.30 state (mirrors the C++ i64 accumulator; 40-bit has ample headroom).
  logic signed [39:0] xd_re, xd_im, yd_re, yd_im;

  assign i_in = s_axis_tdata[15:0];
  assign q_in = s_axis_tdata[31:16];

  // ready to accept a new sample when the output register is free.
  assign s_axis_tready = !out_valid || m_axis_tready;
  assign m_axis_tvalid = out_valid;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      out_valid   <= 1'b0;
      xd_re <= 40'sd0; xd_im <= 40'sd0;
      yd_re <= 40'sd0; yd_im <= 40'sd0;
    end else begin
      if (s_axis_tready && s_axis_tvalid) begin
        automatic logic signed [39:0] x30_re, x30_im, re, im;
        x30_re = q15_to_q930(i_in);
        x30_im = q15_to_q930(q_in);
        re = x30_re - xd_re + (yd_re - (yd_re >>> 7));
        im = x30_im - xd_im + (yd_im - (yd_im >>> 7));

        if (bypass) begin
          m_axis_tdata <= s_axis_tdata;   // passthrough, bit-for-bit
        end else begin
          m_axis_tdata <= {rshift_round_sat16(im, 15), rshift_round_sat16(re, 15)};
        end
        m_axis_tlast <= s_axis_tlast;
        out_valid    <= 1'b1;

        // update state (Q9.30 held at full width, no truncation)
        xd_re <= x30_re; xd_im <= x30_im;
        yd_re <= re;     yd_im <= im;
      end else if (m_axis_tready && out_valid) begin
        out_valid <= 1'b0;
      end
    end
  end

endmodule
