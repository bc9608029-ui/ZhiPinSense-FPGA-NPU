// M26-A.6  Decimator (keep 1 of every D samples, phase-0 aligned).
//
// Per M26_FIXED_POINT_CONTRACT.md §6: legal factors are only {2,4,8}; any other
// value with bypass=0 asserts `cfg_error` and the stage fail-closes (deasserts
// s_axis_tready, produces no output).  bypass=1 is D=1 equivalent (passthrough).
//
// Phase-0 alignment: the first sample of each frame (counter == 0) is always kept,
// matching m26fixed::decimate() which keeps indices 0, D, 2D, ...
//
// tlast re-timing: a kept sample is emitted at the *last* sample of its D-group
// (counter == D-1), and the group's trailing tlast is attached there — so the output
// frame boundary lands on the last kept sample of each input frame.  This requires
// the input frame length N to be a multiple of D; guaranteed here (N = 1024 and
// D in {2,4,8} all divide 1024).  Output latency is D-1 cycles (1/3/7 for D=2/4/8).
module m26_decimator (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        bypass,
    input  logic [3:0]  decim,          // legal {2,4,8}; else cfg_error when !bypass
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // {I[15:0], Q[15:0]}
    input  logic        s_axis_tlast,
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tlast,
    output logic        cfg_error
);
  logic [2:0]  cnt;                     // 0 .. D-1 within each D-group
  logic [31:0] held;                    // kept sample, emitted at group end
  logic        out_valid;

  wire legal = (decim == 4'd2) || (decim == 4'd4) || (decim == 4'd8);
  assign cfg_error = !bypass && !legal;

  wire [3:0] d_minus_1 = decim - 4'd1;  // 2->1, 4->3, 8->7
  wire       keep      = (cnt == 3'd0);
  wire       emit      = ({1'b0, cnt} == d_minus_1);

  assign s_axis_tready = cfg_error ? 1'b0 : (!out_valid || m_axis_tready);
  assign m_axis_tvalid = out_valid;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cnt       <= 3'd0;
      held      <= 32'd0;
      out_valid <= 1'b0;
    end else begin
      // output consumed when downstream is ready (independent of input acceptance,
      // since the stage produces once every D samples).
      if (m_axis_tready && out_valid) out_valid <= 1'b0;

      if (s_axis_tready && s_axis_tvalid) begin
        if (bypass) begin
          m_axis_tdata <= s_axis_tdata;
          m_axis_tlast <= s_axis_tlast;
          out_valid    <= 1'b1;
        end else begin
          if (keep) held <= s_axis_tdata;
          if (emit) begin
            m_axis_tdata <= held;
            m_axis_tlast <= s_axis_tlast;
            out_valid    <= 1'b1;
          end
          cnt <= emit ? 3'd0 : cnt + 3'd1;
        end
      end
    end
  end

endmodule
