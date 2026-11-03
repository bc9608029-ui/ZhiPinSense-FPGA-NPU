// M26-A.5  Symmetric (folded) FIR low-pass, anti-aliasing stage for decimation.
//
// A linear-phase FIR with TAPS=32 coefficients h[0..31] (symmetric: h[k]=h[31-k]),
// loaded from `m26_fir_coeff.mem` (Q1.15, generated from design_lowpass(32, 0.4)
// by scripts/gen_m26_roms.py).  The symmetric structure is folded so only the first
// HALF=16 taps are MAC'd against the sum of the two mirrored delay taps:
//
//   y[n] = sum_{k=0}^{15} ( x[n-k] + x[n-(31-k)] ) * h[k]
//
// Mirrors m26fixed::fir_sym() bit-for-bit: the folded sum is 17-bit signed, the
// product is 33-bit (17+16), accumulated in a 40-bit Q1.30 register, then rounded
// (round-half-away-from-zero) and symmetrically saturated to Q1.15.  Missing
// (pre-roll) taps contribute 0 because the delay line resets to zero.
//
// bypass=1 -> passthrough (1-cycle latency identical to the filtered path).
module m26_fir (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        bypass,
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // {I[15:0], Q[15:0]}
    input  logic        s_axis_tlast,
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tlast
);
  import m26_fxp_pkg::*;

  localparam int N    = 32;             // taps
  localparam int HALF = N / 2;          // folded MAC count

  logic signed [15:0] coeff [0:N-1];
  logic signed [15:0] delay_re [0:N-1];
  logic signed [15:0] delay_im [0:N-1];
  logic               out_valid;

  initial $readmemh("m26_fir_coeff.mem", coeff);

  // incoming sample, and the delay line as it will be AFTER this sample shifts in.
  wire signed [15:0] in_re = $signed(s_axis_tdata[15:0]);
  wire signed [15:0] in_im = $signed(s_axis_tdata[31:16]);
  wire signed [15:0] nd_re [0:N-1];
  wire signed [15:0] nd_im [0:N-1];
  genvar i;
  generate
    assign nd_re[0] = in_re;
    assign nd_im[0] = in_im;
    for (i = 1; i < N; i++) begin : gen_dly
      assign nd_re[i] = delay_re[i-1];
      assign nd_im[i] = delay_im[i-1];
    end
  endgenerate

  // folded sum x[n-k] + x[n-(31-k)]  (17-bit signed)
  wire signed [16:0] fold_re [0:HALF-1];
  wire signed [16:0] fold_im [0:HALF-1];
  generate
    for (i = 0; i < HALF; i++) begin : gen_fold
      assign fold_re[i] = $signed({nd_re[i][15], nd_re[i]})
                        + $signed({nd_re[N-1-i][15], nd_re[N-1-i]});
      assign fold_im[i] = $signed({nd_im[i][15], nd_im[i]})
                        + $signed({nd_im[N-1-i][15], nd_im[N-1-i]});
    end
  endgenerate

  // folded MAC accumulator (48-bit Q1.30, contract §5; T=32 needs only ~36 bits, the
  // extra headroom covers T<=64.  Sign-extends into the 64-bit package helpers.)
  logic signed [47:0] acc_re, acc_im;
  always_comb begin
    acc_re = 48'sd0;
    acc_im = 48'sd0;
    for (int k = 0; k < HALF; k++) begin
      acc_re = acc_re + $signed(fold_re[k]) * $signed(coeff[k]);
      acc_im = acc_im + $signed(fold_im[k]) * $signed(coeff[k]);
    end
  end

  assign s_axis_tready = !out_valid || m_axis_tready;
  assign m_axis_tvalid = out_valid;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      out_valid <= 1'b0;
      for (int j = 0; j < N; j++) begin
        delay_re[j] <= 16'sd0;
        delay_im[j] <= 16'sd0;
      end
    end else begin
      if (s_axis_tready && s_axis_tvalid) begin
        for (int j = 0; j < N; j++) begin
          delay_re[j] <= nd_re[j];
          delay_im[j] <= nd_im[j];
        end
        if (bypass)
          m_axis_tdata <= s_axis_tdata;
        else
          m_axis_tdata <= {rshift_round_sat16(acc_im, 15), rshift_round_sat16(acc_re, 15)};
        m_axis_tlast <= s_axis_tlast;
        out_valid    <= 1'b1;
      end else if (m_axis_tready && out_valid) begin
        out_valid <= 1'b0;
      end
    end
  end

endmodule
