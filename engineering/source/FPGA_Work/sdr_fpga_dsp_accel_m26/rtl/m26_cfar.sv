// M26-B.6  Cell-Averaging CFAR detector (frame-based, 1024 bins).
//
// Per M26_FIXED_POINT_CONTRACT.md §12: for each bin k the threshold is
//   thr[k] = T * mean(reference window),  reference = bins k-G-R .. k-G-1 and
//   k+G+1 .. k+G+R (guard cells and the cell-under-test excluded; truncated at
//   the spectrum edges, mirroring m26fixed::cfar).
//
// The decision `P[k] > thr[k]` is computed WITHOUT a divider, using the exact
// integer identity  (a > floor(x/b))  <=>  (a*b > x)  for b>0:
//   mask[k] = (cnt != 0) && ( P[k] * (cnt<<14) > T_q214 * sum )
// which is bit-identical to the C++ u64  T_q214*sum/(cnt<<14)  comparison.
// cnt is the number of reference cells actually summed (<= 2R), sum their Q0.30
// total.  All products are kept in 64-bit so the legal range (G+R < 512) cannot
// overflow (mirrors the C++ u64 accumulator).
//
// The power spectrum is buffered in a distributed register array (1024 x 32) so
// both reference cells are readable in the same cycle; one bin is resolved per
// R cycles (plus one judge cycle).  Illegal parameters (2R+2G >= N) raise
// `cfg_error` and halt output (fail-closed, §17).  The 1024-bit mask is emitted
// once per frame with a one-cycle `mask_valid` pulse.
module m26_cfar (
    input  logic          clk,
    input  logic          rst_n,            // async, active-low
    // CFAR configuration (runtime)
    input  logic [9:0]    guard,            // G guard cells each side
    input  logic [9:0]    ref,              // R reference cells each side
    input  logic [15:0]   threshold_scale_q214, // T in Q2.14 (unsigned)
    // AXI-Stream slave (power spectrum, one frame = 1024 x Q0.30)
    input  logic          s_axis_tvalid,
    output logic          s_axis_tready,
    input  logic [31:0]   s_axis_tdata,     // P[k] Q0.30
    input  logic          s_axis_tlast,
    // detection mask (frame statistic)
    output logic          mask_valid,       // one-cycle pulse when mask is ready
    output logic [1023:0] mask,             // 1 = detected
    output logic          cfg_error         // fail-closed: 2R+2G >= N
);
  localparam int N = 1024;

  typedef enum logic [1:0] { S_INPUT, S_REF, S_JUDGE, S_OUTPUT } state_t;
  state_t state;

  logic [31:0]   p [0:N-1];
  logic [1023:0] mask_r;

  logic [9:0]   in_cnt;
  logic [9:0]   k;                          // bin under test
  logic [9:0]   g;                          // reference offset 1..R
  logic [63:0]  sum;                        // Q0.30 sum of reference cells
  logic [10:0]  cnt;                        // number of reference cells summed

  // ---- position-derived values (stable while k,g are stable)
  wire signed [11:0] lo = $signed({2'b00, k}) - $signed({2'b00, guard}) - $signed({2'b00, g});
  wire [11:0]        hi = ({2'b00, k}) + ({2'b00, guard}) + ({2'b00, g});

  wire [9:0]  lo_addr = (lo >= 12'sd0) ? lo[9:0] : 10'd0;
  wire [9:0]  hi_addr = (hi < 12'(N))  ? hi[9:0] : 10'd0;
  wire [31:0] p_lo = p[lo_addr];
  wire [31:0] p_hi = p[hi_addr];

  // cross-multiplied decision (no divider): P[k]*(cnt<<14) > T_q214*sum
  wire [63:0] lhs = 64'(p[k]) * (64'(cnt) << 14);
  wire [63:0] rhs = 64'(threshold_scale_q214) * sum;

  assign cfg_error    = ({1'b0, guard} + {1'b0, ref}) >= 11'(N / 2);
  assign s_axis_tready = (state == S_INPUT) && !cfg_error;
  assign mask         = mask_r;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state      <= S_INPUT;
      in_cnt     <= 10'd0;
      k          <= 10'd0;
      g          <= 10'd0;
      sum        <= 64'd0;
      cnt        <= 11'd0;
      mask_r     <= '0;
      mask_valid <= 1'b0;
    end else begin
      mask_valid <= 1'b0;                    // pulse for a single cycle
      case (state)
        S_INPUT: begin
          if (s_axis_tvalid && s_axis_tready) begin
            p[in_cnt] <= s_axis_tdata;
            if (s_axis_tlast) begin
              in_cnt <= 10'd0;
              k      <= 10'd0;
              g      <= 10'd1;
              sum    <= 64'd0;
              cnt    <= 11'd0;
              state  <= S_REF;
            end else begin
              in_cnt <= in_cnt + 10'd1;
            end
          end
        end

        S_REF: begin
          if (g <= ref) begin
            sum <= sum + ((lo >= 12'sd0) ? 64'(p_lo) : 64'd0)
                       + ((hi < 12'(N)) ? 64'(p_hi) : 64'd0);
            cnt <= cnt + ((lo >= 12'sd0) ? 11'd1 : 11'd0)
                       + ((hi < 12'(N)) ? 11'd1 : 11'd0);
          end
          if (g >= ref)        state <= S_JUDGE;   // ref==0 handled here
          else                 g <= g + 10'd1;
        end

        S_JUDGE: begin
          mask_r[k] <= (cnt != 11'd0) && (lhs > rhs);
          if (k == 10'(N - 1)) begin
            state <= S_OUTPUT;
          end else begin
            k     <= k + 10'd1;
            g     <= 10'd1;
            sum   <= 64'd0;
            cnt   <= 11'd0;
            state <= S_REF;
          end
        end

        S_OUTPUT: begin
          mask_valid <= 1'b1;
          state      <= S_INPUT;
        end

        default: state <= S_INPUT;
      endcase
    end
  end

endmodule
