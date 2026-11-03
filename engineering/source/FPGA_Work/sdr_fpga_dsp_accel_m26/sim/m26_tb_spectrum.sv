// M26-B  self-checking testbench: spectrum chain (hann/fft bypassed to inject a
// synthetic power spectrum, exercising fftshift -> mag_sq -> {noise_floor, cfar,
// candidate_merge} end to end).
//
//   frame : I = 1000 at input bins 12,56 (=> power 1_000_000), I = 10 elsewhere
//           (=> power 100); Q = 0.  fftshift rotates +512, so the detections land
//           on output bins 524 and 568.
//   checks: median == 100, CFAR mask == {524,568} exactly, and candidate_merge
//           emits 2 single-bin candidates (99% BW == 1) with exact power/centroid.
//
// Run via synth/run_sim.tcl.
`timescale 1ns / 1ps

module m26_tb_spectrum;

  logic clk = 0, rst_n = 0;
  always #5 clk = ~clk;

  logic        bypass_hann, bypass_fft;
  logic [9:0]  cfar_guard, cfar_ref;
  logic [15:0] cfar_thr;
  logic [9:0]  merge_gap;
  logic [4:0]  max_cand;

  logic        tvalid, tready, tlast;
  logic [31:0] tdata;
  logic        n0_valid;
  logic [31:0] n0_data;
  logic        mask_valid;
  logic [1023:0] mask;
  logic        cand_valid;
  logic [9:0]  cand_start, cand_end, cand_peak;
  logic [10:0] cand_bw;
  logic [41:0] cand_power;
  logic [51:0] cand_wsum;
  logic        cand_done;
  logic [4:0]  cand_count;
  logic        candidate_overflow;
  logic        cfg_error;

  m26_spectrum_top dut (
    .clk, .rst_n,
    .bypass_hann(bypass_hann), .bypass_fft(bypass_fft),
    .cfar_guard(cfar_guard), .cfar_ref(cfar_ref),
    .cfar_threshold_scale_q214(cfar_thr),
    .merge_gap(merge_gap), .max_cand(max_cand),
    .s_axis_tvalid(tvalid), .s_axis_tready(tready),
    .s_axis_tdata(tdata), .s_axis_tlast(tlast),
    .n0_valid(n0_valid), .n0_data(n0_data),
    .mask_valid(mask_valid), .mask(mask),
    .cand_valid(cand_valid),
    .cand_start(cand_start), .cand_end(cand_end), .cand_peak(cand_peak),
    .cand_bw(cand_bw), .cand_power(cand_power), .cand_wsum(cand_wsum),
    .cand_done(cand_done), .cand_count(cand_count),
    .candidate_overflow(candidate_overflow),
    .cfg_error(cfg_error)
  );

  int errs = 0;
  task automatic check(input logic ok, input string what);
    if (!ok) begin $display("FAIL: %s", what); errs++; end
    else $display("PASS: %s", what);
  endtask

  // captured candidate fields (up to 4)
  logic [9:0]  cs [0:3], ce [0:3], cp [0:3];
  logic [10:0] cbw [0:3];
  logic [41:0] cpow [0:3];
  logic [51:0] cwsum [0:3];
  int ncap = 0;

  // drive one 1024-sample IQ frame; strong bins b0/b1 carry I=tone, rest I=noise
  task automatic drive_frame(input logic [9:0] b0, b1,
                             input logic [15:0] tone, noise);
    for (int i = 0; i < 1024; i++) begin
      tvalid <= 1'b1;
      if (i == b0 || i == b1) tdata <= {16'sd0, 16'(tone)};   // {Q=0, I=tone}
      else                    tdata <= {16'sd0, 16'(noise)};
      tlast <= (i == 1023);
      @(posedge clk);
      while (!tready) @(posedge clk);
    end
    tvalid <= 1'b0;
    @(posedge clk);
  endtask

  initial begin
    bypass_hann = 1'b1; bypass_fft = 1'b1;
    cfar_guard = 10'd4; cfar_ref = 10'd8; cfar_thr = 16'(8 << 14);
    merge_gap = 10'd2; max_cand = 5'd4;
    tvalid = 0; tdata = 0; tlast = 0;

    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);

    check(!cfg_error, "legal params -> no cfg_error");

    // ---- frame 1
    drive_frame(10'd12, 10'd56, 16'sd1000, 16'sd10);

    while (!n0_valid) @(posedge clk);
    check(n0_data == 32'd100, "median == 100");

    while (!mask_valid) @(posedge clk);
    int mcnt = 0;
    logic m12, m56, m524, m568;
    m12 = mask[12]; m56 = mask[56]; m524 = mask[524]; m568 = mask[568];
    for (int i = 0; i < 1024; i++) if (mask[i]) mcnt++;
    check(mcnt == 2, "exactly 2 detections");
    check(m524 == 1'b1 && m568 == 1'b1, "detections at fftshift bins 524/568");
    check(m12 == 1'b0 && m56 == 1'b0, "no detections at pre-shift bins 12/56");

    // capture candidates on each cand_valid pulse until cand_done
    ncap = 0;
    while (1) begin
      @(posedge clk);
      if (cand_valid) begin
        if (ncap < 4) begin
          cs[ncap] = cand_start; ce[ncap] = cand_end; cp[ncap] = cand_peak;
          cbw[ncap] = cand_bw; cpow[ncap] = cand_power; cwsum[ncap] = cand_wsum;
        end
        ncap++;
      end
      if (cand_done) break;
    end
    check(cand_count == 5'd2, "candidate list = 2");
    check(!candidate_overflow, "no candidate overflow");
    check(ncap == 2, "captured 2 candidates");

    if (ncap >= 2) begin
      check(cs[0] == 10'd524 && ce[0] == 10'd524, "cand0 span = {524}");
      check(cp[0] == 10'd524, "cand0 peak = 524");
      check(cs[1] == 10'd568 && ce[1] == 10'd568, "cand1 span = {568}");
      check(cp[1] == 10'd568, "cand1 peak = 568");
      check(cbw[0] == 11'd1 && cbw[1] == 11'd1, "99% BW == 1 bin (single-bin candidates)");
      check(cpow[0] == 42'd1000000 && cpow[1] == 42'd1000000, "candidate power == 1e6");
      check(cwsum[0] == 52'(1000000) * 52'd524, "cand0 centroid numerator");
      check(cwsum[1] == 52'(1000000) * 52'd568, "cand1 centroid numerator");
    end

    // ---- frame 2 (re-arm): same spectrum, prove the frame-based chain recovers
    drive_frame(10'd12, 10'd56, 16'sd1000, 16'sd10);
    while (!n0_valid) @(posedge clk);
    check(n0_data == 32'd100, "frame 2 median == 100 (re-arm)");
    while (!mask_valid) @(posedge clk);
    mcnt = 0;
    for (int i = 0; i < 1024; i++) if (mask[i]) mcnt++;
    check(mcnt == 2, "frame 2 exactly 2 detections (re-arm)");

    if (errs == 0) $display("== m26_tb_spectrum PASS ==");
    else           $display("== m26_tb_spectrum FAIL (%0d) ==", errs);
    $finish;
  end

  initial begin
    #8000000;
    $display("== m26_tb_spectrum TIMEOUT ==");
    $finish;
  end

endmodule
