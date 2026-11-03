// M26-B.3  fftshift — pure address remap, no arithmetic (contract §9).
//
//   out[k] = in[(k + N/2) mod N],  N = 1024   (moves DC to the bin-512 centre)
//
// Frame-based: buffer the 1024 input samples in natural order, then stream them out
// in the rotated order [512..1023, 0..511].  Bit width is unchanged (16-bit Q1.15).
// Latency = 1024 cycles in + 1024 cycles out.
module m26_fftshift (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // {I[15:0], Q[15:0]}
    input  logic        s_axis_tlast,
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tlast
);
  localparam int N = 1024;

  typedef enum logic { S_INPUT, S_OUTPUT } state_t;
  state_t state;

  logic [31:0] mem [0:N-1];
  logic [9:0]  in_cnt, out_cnt;

  assign s_axis_tready = (state == S_INPUT);
  assign m_axis_tvalid = (state == S_OUTPUT);
  assign m_axis_tdata  = mem[out_cnt + 10'd512];   // (out_cnt + N/2) mod N
  assign m_axis_tlast  = (state == S_OUTPUT) && (out_cnt == 10'd1023);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state   <= S_INPUT;
      in_cnt  <= 10'd0;
      out_cnt <= 10'd0;
    end else begin
      case (state)
        S_INPUT: begin
          if (s_axis_tvalid) begin
            mem[in_cnt] <= s_axis_tdata;
            if (s_axis_tlast) begin
              in_cnt <= 10'd0;
              out_cnt <= 10'd0;
              state   <= S_OUTPUT;
            end else begin
              in_cnt <= in_cnt + 10'd1;
            end
          end
        end
        S_OUTPUT: begin
          if (m_axis_tready) begin
            if (out_cnt == 10'd1023) begin
              out_cnt <= 10'd0;
              state   <= S_INPUT;
            end else begin
              out_cnt <= out_cnt + 10'd1;
            end
          end
        end
        default: state <= S_INPUT;
      endcase
    end
  end

endmodule
