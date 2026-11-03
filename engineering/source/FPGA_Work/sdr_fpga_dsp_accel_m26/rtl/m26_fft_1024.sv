// M26-B.2  1024-point radix-2 DIT FFT, per-stage 1/2 scaling (single butterfly).
//
// Per M26_FIXED_POINT_CONTRACT.md §8: a memory-based in-place FFT.  Input samples are
// buffered in bit-reversed order (natural output order results), then 10 stages x 512
// butterflies are applied with one complex butterfly per 4 clocks.  Twiddle factors
// are a 1024x32 ROM (`m26_twiddle.mem`, {im[31:16],re[15:0]} = exp(-j2pi m/N),
// generated from m26fixed::build_twiddle).  Each butterfly halves the data:
//
//   A' = (A + B*W)/2,  B' = (A - B*W)/2     (=> total gain 1/1024)
//
// matching m26fixed::fft_radix2_inplace() bit-for-bit (the scaled-butterfly round+sat
// is identical: sat16(rshift_round((A<<15) +/- (B*W), 16))).
//
// bypass=1 -> frame passthrough: samples are buffered in natural order and replayed
// unchanged (same frame latency, order preserved; the butterfly stages are skipped).
//
// Frame latency: 1024 cycles in + 10*512*4 cycles compute + 1024 cycles out.
// The data memory is inferred distributed RAM (async read + sync write); a block-RAM
// / sync-read variant is the production path (see M26_RESOURCE_AND_TIMING_BUDGET.md).
module m26_fft_1024 (
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

  localparam int N = 1024;
  localparam int LOGN = 10;

  typedef enum logic [2:0] { S_INPUT, S_RD_A, S_RD_B, S_WR_A, S_WR_B, S_OUTPUT } state_t;
  state_t state;

  logic [31:0]        mem [0:N-1];
  logic signed [31:0] tw  [0:N-1];
  initial $readmemh("m26_twiddle.mem", tw);

  logic [9:0] in_cnt, out_cnt;          // input / output sample index
  logic [3:0] stage;                    // 0..9  (len = 2^(stage+1))
  logic [9:0] group;                    // 0..N/len-1
  logic [8:0] k;                        // 0..half-1 (<=511)

  logic [31:0] A, B;                    // butterfly operands (latched)

  // ---- position-derived values (stage/group/k are stable across one butterfly)
  wire [9:0] half   = 10'd1 << stage;                       // 2^stage
  wire [9:0] addr_a = (group << (stage + 4'd1)) + {1'b0, k};
  wire [9:0] addr_b = addr_a + half;
  wire [9:0] tw_idx = ({1'b0, k} << (9 - stage));           // k * 2^(9-stage) = k*N/len
  wire [8:0] k_last = half[8:0] - 9'd1;                     // half-1
  wire [9:0] group_last = (10'd512 >> stage) - 10'd1;       // N/len - 1

  // ---- memory read port (async)
  wire [31:0] rd_data;
  assign rd_data = mem[rd_addr];
  wire [9:0] rd_addr;
  assign rd_addr = (state == S_RD_A) ? addr_a :
                   (state == S_RD_B) ? addr_b : 10'd0;

  // ---- butterfly arithmetic (combinational from A, B, tw[tw_idx])
  wire signed [15:0] a_re = $signed(A[15:0]);
  wire signed [15:0] a_im = $signed(A[31:16]);
  wire signed [15:0] b_re = $signed(B[15:0]);
  wire signed [15:0] b_im = $signed(B[31:16]);
  wire signed [15:0] w_re = $signed(tw[tw_idx][15:0]);
  wire signed [15:0] w_im = $signed(tw[tw_idx][31:16]);

  wire signed [32:0] m_rr = $signed(b_re) * $signed(w_re);  // Q2.30 (sign-ext to 33)
  wire signed [32:0] m_ii = $signed(b_im) * $signed(w_im);
  wire signed [32:0] m_ri = $signed(b_re) * $signed(w_im);
  wire signed [32:0] m_ir = $signed(b_im) * $signed(w_re);
  wire signed [32:0] tre = m_rr - m_ii;
  wire signed [32:0] tim = m_ri + m_ir;

  wire signed [39:0] a_re_sc = {{24{a_re[15]}}, a_re, 15'b0};   // A.re << 15 (Q2.30)
  wire signed [39:0] a_im_sc = {{24{a_im[15]}}, a_im, 15'b0};

  wire [31:0] A_p = { rshift_round_sat16(a_im_sc + tim, 16),
                      rshift_round_sat16(a_re_sc + tre, 16) };
  wire [31:0] B_p = { rshift_round_sat16(a_im_sc - tim, 16),
                      rshift_round_sat16(a_re_sc - tre, 16) };

  // ---- memory write port (butterfly write-back)
  wire        wr_en;
  wire [9:0]  wr_addr;
  wire [31:0] wr_data;
  assign wr_en   = (state == S_WR_A) || (state == S_WR_B);
  assign wr_addr = (state == S_WR_A) ? addr_a :
                   (state == S_WR_B) ? addr_b : 10'd0;
  assign wr_data = (state == S_WR_A) ? A_p : B_p;

  // ---- unified write port (input buffering + butterfly write-back share the RAM)
  wire [9:0]  in_addr    = bypass ? in_cnt : bitrev10(in_cnt);
  wire        mem_wr_en   = ((state == S_INPUT) && s_axis_tvalid) || wr_en;
  wire [9:0]  mem_wr_addr = (state == S_INPUT) ? in_addr : wr_addr;
  wire [31:0] mem_wr_data = (state == S_INPUT) ? s_axis_tdata : wr_data;

  // ---- stream handshake
  assign s_axis_tready = (state == S_INPUT);
  assign m_axis_tvalid = (state == S_OUTPUT);
  assign m_axis_tdata  = mem[out_cnt];
  assign m_axis_tlast  = (state == S_OUTPUT) && (out_cnt == 10'd1023);

  // bit-reversal of a 10-bit index (for DIT input storage).
  function automatic logic [9:0] bitrev10(input logic [9:0] v);
    logic [9:0] r;
    for (int i = 0; i < LOGN; i++) r[i] = v[LOGN-1-i];
    return r;
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state   <= S_INPUT;
      in_cnt  <= 10'd0;
      out_cnt <= 10'd0;
      stage   <= 4'd0;
      group   <= 10'd0;
      k       <= 9'd0;
      A       <= 32'd0;
      B       <= 32'd0;
    end else begin
      if (mem_wr_en) mem[mem_wr_addr] <= mem_wr_data;

      case (state)
        S_INPUT: begin
          if (s_axis_tvalid) begin
            if (s_axis_tlast) begin
              in_cnt <= 10'd0;
              state  <= bypass ? S_OUTPUT : S_RD_A;
            end else begin
              in_cnt <= in_cnt + 10'd1;
            end
          end
        end

        S_RD_A: begin
          A     <= rd_data;             // mem[addr_a]
          state <= S_RD_B;
        end

        S_RD_B: begin
          B     <= rd_data;             // mem[addr_b]
          state <= S_WR_A;
        end

        S_WR_A: state <= S_WR_B;        // mem[addr_a] = A_p written this cycle

        S_WR_B: begin                   // mem[addr_b] = B_p written this cycle
          if (k == k_last) begin
            k <= 9'd0;
            if (group == group_last) begin
              group <= 10'd0;
              if (stage == 4'd9) begin
                out_cnt <= 10'd0;
                state   <= S_OUTPUT;
              end else begin
                stage <= stage + 4'd1;
              end
            end else begin
              group <= group + 10'd1;
            end
          end else begin
            k <= k + 9'd1;
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
