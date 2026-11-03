// M26-A.2  Energy / RMS statistics (observer tap on the IQ stream).
//
// Per M26_FIXED_POINT_CONTRACT.md §2, over a frame of N=1024 samples (frame delimited
// by s_axis_tlast):
//   power[n] = I[n]^2 + Q[n]^2          (unsigned 32-bit Q0.30)
//   energy   = sum power[n]             (unsigned 48-bit Q0.30)
//   rms      = round(sqrt(energy/N))    (unsigned 16-bit Q0.15)
//   peak     = max power[n]
//
// The sqrt is a bit-exact integer sqrt (binary search) of mean power = energy>>10,
// followed by round-half-away-from-zero.  Stats are emitted at each frame end with a
// `stats_valid` pulse.  `enable=0` freezes accumulation (stats stay 0) but the pulse
// still fires, so the frame boundary is always observable.
module m26_energy_rms (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,          // bypass/enable gate (0 = no accumulation)
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,    // {I[15:0], Q[15:0]}
    input  logic        s_axis_tlast,
    // frame-end statistics
    output logic        stats_valid,
    output logic [47:0] energy,          // Q0.30
    output logic [15:0] rms,             // Q0.15 (unsigned)
    output logic [31:0] peak             // Q0.30
);
  logic [31:0] p;
  logic [47:0] acc;
  logic [31:0] peak_r;
  logic [47:0] acc_next;
  logic [31:0] peak_next;

  // I^2 + Q^2 (unsigned, Q0.30)
  assign p = (16'(signed'(s_axis_tdata[15:0])) * 16'(signed'(s_axis_tdata[15:0])))
           + (16'(signed'(s_axis_tdata[31:16])) * 16'(signed'(s_axis_tdata[31:16])));

  // monitor consumes the stream immediately (no backpressure) — always ready.
  assign s_axis_tready = 1'b1;

  assign acc_next  = enable ? (acc + 48'(p)) : acc;
  assign peak_next = enable ? ((p > peak_r) ? p : peak_r) : peak_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      acc    <= 48'd0;
      peak_r <= 32'd0;
      stats_valid <= 1'b0;
    end else begin
      if (s_axis_tvalid) begin
        if (s_axis_tlast) begin
          energy      <= acc_next;            // whole frame, incl. last sample
          peak        <= peak_next;
          rms         <= rms_q(acc_next);
          acc         <= 48'd0;               // start next frame
          peak_r      <= 32'd0;
        end else begin
          acc    <= acc_next;
          peak_r <= peak_next;
        end
      end
      stats_valid <= s_axis_tvalid && s_axis_tlast;
    end
  end

  // round-half-away-from-zero sqrt of (energy/N), energy in Q0.30, N=1024=2^10.
  function automatic logic [15:0] rms_q(input logic [47:0] energy48);
    logic [31:0] v;
    logic [15:0] r;
    v = energy48[41:10];                 // energy >> 10  = mean power (Q0.30, <2^31)
    r = isqrt(v);                        // floor(sqrt(v)), 16-bit
    // round up when the remainder exceeds r  (i.e. v >= (r+0.5)^2)
    return (v - (32'(r) * 32'(r)) > 32'(r)) ? r + 16'd1 : r;
  endfunction

  // integer sqrt (floor) by binary search; v < 2^31 -> r < 2^16.
  function automatic logic [15:0] isqrt(input logic [31:0] v);
    logic [15:0] lo, hi, mid;
    lo = 16'd0; hi = 16'hFFFF;
    for (int i = 0; i < 16; i++) begin
      mid = (lo + hi + 1) >> 1;
      if (32'(mid) * 32'(mid) <= v) lo = mid;
      else                          hi = mid - 1;
    end
    return lo;
  endfunction

endmodule
