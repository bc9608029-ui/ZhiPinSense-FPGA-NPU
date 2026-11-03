// M26-B.5  Noise-floor estimate = exact median of the 1024-bin power spectrum.
//
// Per M26_FIXED_POINT_CONTRACT.md §11 the noise floor is the median of the frame's
// power bins.  This is a bit-serial *exact* median (no approximation): for the
// fixed N = 1024, the fixed model returns s[512] of the ascending-sorted bins, i.e.
// the 513rd smallest (upper median).  Processing bits MSB -> LSB with a live
// "alive" mask selects that rank exactly:
//
//   alive = all, rank = 513, n = 1024
//   for b = 31 .. 0:
//       c     = #{ i : alive[i] & val[i][b] }        // ones at this bit
//       zeros = n - c
//       if (rank <= zeros): bit = 0, keep zeros, n = zeros          (rank unchanged)
//       else:               bit = 1, keep ones,  n = c, rank -= zeros
//
// The result is the exact 513rd-smallest value, matching m26fixed::noise_floor_median
// (std::sort + s[512]) bit-for-bit including ties.  The values are held in a
// distributed register array (1024 x 32) so all 1024 bits are readable in parallel
// for the population count; 32 compute cycles follow each buffered frame.  A BRAM +
// 32-pass variant is the production path (see M26_RESOURCE_AND_TIMING_BUDGET.md).
//
// Frame-based: buffer 1024 x Q0.30 power samples (s_axis_tlast ends the frame), then
// emit a single 32-bit median with a one-cycle n0_valid pulse.
module m26_noise_floor (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // power Q0.30
    input  logic        s_axis_tlast,
    // frame statistic
    output logic        n0_valid,       // one-cycle pulse when n0_data is valid
    output logic [31:0] n0_data         // median power Q0.30
);
  localparam int N    = 1024;
  localparam int W    = 32;
  localparam int RANK = 513;            // s[N/2] = s[512] (0-indexed) -> 513rd smallest

  typedef enum logic [1:0] { S_INPUT, S_COMPUTE, S_DONE } state_t;
  state_t state;

  logic [31:0]  val [0:N-1];
  logic [N-1:0] alive;
  logic [4:0]   bit_idx;                // 31 .. 0
  logic [10:0]  rank;                   // 1 .. 1024
  logic [10:0]  n_alive;                // 0 .. 1024
  logic [9:0]   in_cnt;
  logic [31:0]  result;

  // bit-slice vector: bitvec[i] = val[i][bit_idx]
  logic [N-1:0] bitvec;
  always_comb begin
    for (int i = 0; i < N; i++) bitvec[i] = val[i][bit_idx];
  end

  // count of alive values with the current bit set
  logic [10:0] c;
  always_comb begin
    c = 11'd0;
    for (int i = 0; i < N; i++) c = c + {{10{1'b0}}, (alive[i] & bitvec[i])};
  end

  assign s_axis_tready = (state == S_INPUT);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state    <= S_INPUT;
      in_cnt   <= 10'd0;
      bit_idx  <= 5'd0;
      rank     <= 11'd0;
      n_alive  <= 11'd0;
      alive    <= '0;
      result   <= 32'd0;
      n0_valid <= 1'b0;
    end else begin
      n0_valid <= 1'b0;                  // pulse for a single cycle
      case (state)
        S_INPUT: begin
          if (s_axis_tvalid) begin
            val[in_cnt] <= s_axis_tdata;
            if (s_axis_tlast) begin
              in_cnt   <= 10'd0;
              alive    <= {N{1'b1}};
              rank     <= 11'(RANK);
              n_alive  <= 11'(N);
              bit_idx  <= 5'(W - 1);
              result   <= 32'd0;
              state    <= S_COMPUTE;
            end else begin
              in_cnt <= in_cnt + 10'd1;
            end
          end
        end

        S_COMPUTE: begin
          if (rank <= (n_alive - c)) begin
            result[bit_idx] <= 1'b0;     // median bit = 0: keep zeros
            alive   <= alive & ~bitvec;
            n_alive <= n_alive - c;
            // rank unchanged
          end else begin
            result[bit_idx] <= 1'b1;     // median bit = 1: keep ones
            alive   <= alive & bitvec;
            n_alive <= c;
            rank    <= rank - (n_alive - c);
          end
          if (bit_idx == 5'd0)          state <= S_DONE;
          else                      bit_idx <= bit_idx - 5'd1;
        end

        S_DONE: begin
          n0_data  <= result;
          n0_valid <= 1'b1;
          state    <= S_INPUT;
        end

        default: state <= S_INPUT;
      endcase
    end
  end

endmodule
