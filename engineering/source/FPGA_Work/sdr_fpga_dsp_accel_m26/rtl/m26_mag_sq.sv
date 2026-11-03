// M26-B.4  Complex magnitude-squared (per-sample, streaming).
//
// Per M26_FIXED_POINT_CONTRACT.md §10:
//   |X|^2 = Re^2 + Im^2   -> unsigned 32-bit Q0.30
//
// The power expression is byte-identical to the energy/RMS tap (m26_energy_rms.sv)
// so the spectrum chain's power spectrum and the frontend observer agree: each
// 16x16 signed product is Q2.30 (value in [0, 2^30]) and their sum is Q0.30 in
// [0, 2^31], which fits the 32-bit unsigned output (mirrors m26fixed::mag_sq).
//
// Stream passthrough with one register of latency; tlast is forwarded unmodified.
// No bypass: the transform is essential (complex in -> real power out).
module m26_mag_sq (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // {I[15:0], Q[15:0]} Q1.15
    input  logic        s_axis_tlast,
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,   // |X|^2 Q0.30 (unsigned)
    output logic        m_axis_tlast
);
  logic        out_valid;
  logic [31:0] p;

  // I^2 + Q^2 (unsigned Q0.30), same expression as m26_energy_rms.sv.
  assign p = (16'(signed'(s_axis_tdata[15:0])) * 16'(signed'(s_axis_tdata[15:0])))
           + (16'(signed'(s_axis_tdata[31:16])) * 16'(signed'(s_axis_tdata[31:16])));

  assign s_axis_tready = !out_valid || m_axis_tready;
  assign m_axis_tvalid = out_valid;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      out_valid <= 1'b0;
    end else begin
      if (s_axis_tready && s_axis_tvalid) begin
        m_axis_tdata <= p;
        m_axis_tlast <= s_axis_tlast;
        out_valid    <= 1'b1;
      end else if (m_axis_tready && out_valid) begin
        out_valid <= 1'b0;
      end
    end
  end

endmodule
