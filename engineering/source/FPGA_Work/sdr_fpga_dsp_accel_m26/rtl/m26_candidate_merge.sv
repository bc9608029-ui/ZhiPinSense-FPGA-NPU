// M26-B.7  Candidate-band merge + 99%-power bandwidth (frame-based).
//
// Per M26_FIXED_POINT_CONTRACT.md §13/§14: group the CFAR detection mask into
// contiguous candidate bands (bridging gaps of <= merge_gap bins) and report, per
// candidate: bin_start/bin_end, peak bin, power sum, power-weighted centroid
// numerator (center = wsum/power), and the 99%-power bandwidth.
//
// The 99% bandwidth (occupied_bw_bins) grows from the peak bin by adding, in
// descending power order, the not-yet-added bins of the candidate until the
// accumulated power reaches 99% of the candidate total; the bandwidth is the
// span (hi-lo+1) of that set.  The 0.99 threshold is applied as the exact
// integer test  acc*100 >= power*99  (no divider).  Argmax ties break toward the
// lowest bin index.
//
// The power spectrum is buffered in a distributed register array (1024 x 32)
// and consumed together with the CFAR mask sideband (from m26_cfar); candidates
// are emitted one per cycle as cand_valid pulses, terminated by cand_done with
// cand_count.  Up to max_cand candidates are emitted in bin order (the fixed
// model's resize() semantics); any further candidate sets candidate_overflow.
//
// Structural only: the fixed-point arithmetic of this stage is integer-exact and
// matches m26fixed::candidate_merge / occupied_bw_bins (see the merge-gap fix in
// the golden/fixed models for the gap <= merge_gap semantics of §13).
module m26_candidate_merge (
    input  logic          clk,
    input  logic          rst_n,            // async, active-low
    // configuration
    input  logic [9:0]    merge_gap,        // max gap (bins) bridged between detections
    input  logic [4:0]    max_cand,         // candidate cap (legal 1..16, clamped)
    // power spectrum stream (one frame = 1024 x Q0.30)
    input  logic          s_axis_tvalid,
    output logic          s_axis_tready,
    input  logic [31:0]   s_axis_tdata,
    input  logic          s_axis_tlast,
    // CFAR mask sideband (from m26_cfar)
    input  logic          mask_valid,
    input  logic [1023:0] mask,
    // candidate list output
    output logic          cand_valid,       // one-cycle pulse per candidate
    output logic [9:0]    cand_start,
    output logic [9:0]    cand_end,
    output logic [9:0]    cand_peak,
    output logic [10:0]   cand_bw,          // 99% power bandwidth (bins)
    output logic [41:0]   cand_power,       // Q0.30 power sum within candidate
    output logic [51:0]   cand_wsum,        // sum p[k]*k (centroid numerator)
    output logic          cand_done,        // one-cycle pulse: list complete
    output logic [4:0]    cand_count,       // valid with cand_done
    output logic          candidate_overflow // valid with cand_done
);
  localparam int N = 1024;

  typedef enum logic [3:0] {
    S_INPUT, S_WAIT_MASK, S_FIND_START, S_MERGE, S_GAP, S_STATS, S_BW, S_EMIT, S_DONE
  } state_t;
  state_t state;

  logic [31:0]   p [0:N-1];
  logic [1023:0] mask_r;

  logic [10:0]  in_cnt;                     // input buffer index (0..1023)
  logic [10:0]  i;                          // candidate-search position (0..N)
  logic [10:0]  j, gpos;                    // merge / gap scan positions (0..N)
  logic [9:0]   start, end_, peak, s, b, best, lo, hi;
  logic [9:0]   gap;
  logic [47:0]  power;                      // candidate power sum Q0.30
  logic [63:0]  wsum;                       // sum p[k]*k
  logic [31:0]  pk, bestval;                // argmax trackers
  logic [47:0]  acc;                        // BW accumulated power
  logic [1023:0] added;                     // BW consumed-bin mask
  logic         found;
  logic [10:0]  bw;                         // 99% BW in bins
  logic [4:0]   cand_count_r;
  logic         overflow_r;

  wire [4:0] cap = (max_cand == 5'd0 || max_cand > 5'd16) ? 5'd16 : max_cand;

  // 99% threshold test without a divider: acc >= 0.99*power <=> acc*100 >= power*99
  wire [63:0] acc100  = acc * 64'd100;
  wire [63:0] power99 = power * 64'd99;

  assign s_axis_tready = (state == S_INPUT);

  // Candidate data is valid the same cycle cand_valid pulses: the internal
  // start/end_/peak/bw/power/wsum regs are finalised before entering S_EMIT, so they
  // are exposed combinationally and stay stable for the single-cycle emit pulse.
  assign cand_valid      = (state == S_EMIT);
  assign cand_done       = (state == S_DONE);
  assign cand_count      = cand_count_r;
  assign candidate_overflow = overflow_r;

  assign cand_start = start;
  assign cand_end   = end_;
  assign cand_peak  = peak;
  assign cand_bw    = bw;
  assign cand_power = power[41:0];
  assign cand_wsum  = wsum[51:0];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state        <= S_INPUT;
      in_cnt       <= 11'd0;
      i            <= 11'd0;
      j            <= 11'd0;
      gpos         <= 11'd0;
      start        <= 10'd0;
      end_         <= 10'd0;
      peak         <= 10'd0;
      s            <= 10'd0;
      b            <= 10'd0;
      best         <= 10'd0;
      lo           <= 10'd0;
      hi           <= 10'd0;
      gap          <= 10'd0;
      power        <= 48'd0;
      wsum         <= 64'd0;
      pk           <= 32'd0;
      bestval      <= 32'd0;
      acc          <= 48'd0;
      added        <= '0;
      found        <= 1'b0;
      bw           <= 11'd0;
      cand_count_r <= 5'd0;
      overflow_r   <= 1'b0;
      mask_r       <= '0;
    end else begin
      case (state)
        S_INPUT: begin
          if (s_axis_tvalid) begin
            p[in_cnt[9:0]] <= s_axis_tdata;
            if (s_axis_tlast) begin
              in_cnt <= 11'd0;
              i      <= 11'd0;
              state  <= S_WAIT_MASK;
            end else begin
              in_cnt <= in_cnt + 11'd1;
            end
          end
        end

        S_WAIT_MASK: begin
          if (mask_valid) begin
            mask_r       <= mask;
            i            <= 11'd0;
            cand_count_r <= 5'd0;
            overflow_r   <= 1'b0;
            state        <= S_FIND_START;
          end
        end

        S_FIND_START: begin
          if (i >= 11'(N)) begin
            state <= S_DONE;
          end else if (mask_r[i]) begin
            if (cand_count_r >= cap) begin
              overflow_r <= 1'b1;
              state      <= S_DONE;
            end else begin
              start <= i[9:0];
              end_  <= i[9:0];
              j     <= i + 11'd1;
              state <= S_MERGE;
            end
          end else begin
            i <= i + 11'd1;
          end
        end

        S_MERGE: begin
          if (j >= 11'(N)) begin
            s     <= start;
            power <= 48'd0;
            wsum  <= 64'd0;
            pk    <= 32'd0;
            peak  <= start;
            state <= S_STATS;
          end else if (mask_r[j]) begin
            end_ <= j[9:0];
            j    <= j + 11'd1;
          end else begin
            gap  <= 10'd0;
            gpos <= j;
            state <= S_GAP;
          end
        end

        S_GAP: begin
          if (gpos < 11'(N) && !mask_r[gpos]) begin
            gap  <= gap + 10'd1;
            gpos <= gpos + 11'd1;
          end else if (gpos >= 11'(N)) begin
            s     <= start;
            power <= 48'd0;
            wsum  <= 64'd0;
            pk    <= 32'd0;
            peak  <= start;
            state <= S_STATS;
          end else if (gap <= merge_gap) begin
            end_  <= gpos[9:0];
            j     <= gpos + 11'd1;
            state <= S_MERGE;
          end else begin
            s     <= start;
            power <= 48'd0;
            wsum  <= 64'd0;
            pk    <= 32'd0;
            peak  <= start;
            state <= S_STATS;
          end
        end

        S_STATS: begin
          if (s <= end_) begin
            power <= power + 48'(p[s]);
            wsum  <= wsum + 64'(p[s]) * 64'(s);
            if (p[s] > pk) begin
              peak <= s;
              pk   <= p[s];
            end
            s <= s + 10'd1;
          end else if (end_ == start || power == 48'd0) begin
            bw    <= 11'd1;
            state <= S_EMIT;
          end else begin
            lo      <= peak;
            hi      <= peak;
            acc     <= 48'd0;
            added   <= '0;
            b       <= start;
            bestval <= 32'd0;
            found   <= 1'b0;
            state   <= S_BW;
          end
        end

        S_BW: begin
          if (b <= end_) begin
            if (!added[b] && p[b] > bestval) begin
              bestval <= p[b];
              best    <= b;
              found   <= 1'b1;
            end
            b <= b + 10'd1;
          end else begin
            if (!found) begin
              bw    <= ({1'b0, hi} - {1'b0, lo}) + 11'd1;
              state <= S_EMIT;
            end else if (acc100 >= power99) begin
              bw    <= ({1'b0, hi} - {1'b0, lo}) + 11'd1;
              state <= S_EMIT;
            end else begin
              acc        <= acc + 48'(p[best]);
              lo         <= (best < lo) ? best : lo;
              hi         <= (best > hi) ? best : hi;
              added[best] <= 1'b1;
              b          <= start;
              bestval    <= 32'd0;
              found      <= 1'b0;
            end
          end
        end

        S_EMIT: begin
          cand_count_r <= cand_count_r + 5'd1;
          i            <= {1'b0, end_} + 11'd1;
          state        <= S_FIND_START;
        end

        S_DONE: begin
          state <= S_INPUT;
        end

        default: state <= S_INPUT;
      endcase
    end
  end

endmodule
