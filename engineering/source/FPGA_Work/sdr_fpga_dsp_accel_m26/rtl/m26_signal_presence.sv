// M26-A.3  Signal-presence detector (hysteretic threshold + N/M frame hysteresis).
//
// Mirrors the host `signal_presence.hpp` state machine (and the C++ golden/fixed
// models): a 2-state detector NO_SIGNAL <-> SIGNAL_PRESENT with
//   * enter: rms >= thr_enter for `enter_m` consecutive frames
//   * exit : rms <= thr_exit  for `exit_n`  consecutive frames
// ACQUIRING / SIGNAL_LOST are reserved enum values (2'd1 / 2'd3) kept for host
// compatibility but not entered by this hysteresis engine.
//
// Thresholds are unsigned Q0.15 (16-bit); enter_m/exit_n are 4-bit (1..15, 0 means
// "immediate").  One evaluation per frame, gated by `frame_valid`.
module m26_signal_presence (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        frame_valid,     // frame boundary (== energy_rms.stats_valid)
    input  logic [15:0] rms,             // Q0.15 unsigned
    input  logic [15:0] thr_enter,       // Q0.15
    input  logic [15:0] thr_exit,        // Q0.15
    input  logic [3:0]  enter_m,         // 4-bit (0 => immediate enter)
    input  logic [3:0]  exit_n,          // 4-bit (0 => immediate exit)
    output logic [1:0]  presence,        // 2'd0 NO_SIGNAL, 2'd2 SIGNAL_PRESENT
    output logic        presence_changed // pulse at the frame the state flips
);
  localparam logic [1:0] NO_SIGNAL = 2'd0, SIGNAL_PRESENT = 2'd2;

  logic [1:0] state, state_prev;
  logic [3:0] above, below;

  logic [1:0] state_next;
  logic [3:0] above_next, below_next;

  always_comb begin
    state_next = state;
    above_next = above;
    below_next = below;
    case (state)
      NO_SIGNAL: begin
        if (rms >= thr_enter) begin
          if (above + 4'd1 >= enter_m) begin
            state_next = SIGNAL_PRESENT;
            above_next = 4'd0;
          end else begin
            above_next = above + 4'd1;
          end
        end else begin
          above_next = 4'd0;
        end
      end
      SIGNAL_PRESENT: begin
        if (rms <= thr_exit) begin
          if (below + 4'd1 >= exit_n) begin
            state_next = NO_SIGNAL;
            below_next = 4'd0;
          end else begin
            below_next = below + 4'd1;
          end
        end else begin
          below_next = 4'd0;
        end
      end
      default: state_next = NO_SIGNAL;   // reserved states -> fold to NO_SIGNAL
    endcase
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state            <= NO_SIGNAL;
      state_prev       <= NO_SIGNAL;
      above            <= 4'd0;
      below            <= 4'd0;
      presence_changed <= 1'b0;
    end else begin
      presence_changed <= 1'b0;
      if (frame_valid) begin
        state_prev       <= state;
        presence_changed <= (state_next != state);
        state            <= state_next;
        above            <= above_next;
        below            <= below_next;
      end
    end
  end

  assign presence = state;

endmodule
