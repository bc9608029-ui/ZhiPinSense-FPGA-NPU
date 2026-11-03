// M26-B.6  self-checking testbench: CA-CFAR detector.
//
//   frame : two strong bins at 12 and 56 (power 1e6) over noise floor (power 100)
//           guard=4, ref=8, T=8 (Q2.14)  -> mask must be exactly {12,56}
//   illegal params (guard+ref >= 512)    -> cfg_error=1, no output
//
// Run via synth/run_sim.tcl.
`timescale 1ns / 1ps

module m26_tb_cfar;

  logic clk = 0, rst_n = 0;
  always #5 clk = ~clk;

  logic [9:0]  guard, ref;
  logic [15:0] thr_q214;
  logic        tvalid, tready, tlast;
  logic [31:0] tdata;
  logic        mask_valid, cfg_error;
  logic [1023:0] mask;

  m26_cfar dut (
    .clk(clk), .rst_n(rst_n),
    .guard(guard), .ref(ref), .threshold_scale_q214(thr_q214),
    .s_axis_tvalid(tvalid), .s_axis_tready(tready),
    .s_axis_tdata(tdata), .s_axis_tlast(tlast),
    .mask_valid(mask_valid), .mask(mask), .cfg_error(cfg_error)
  );

  int errs = 0;
  task automatic check(input logic ok, input string what);
    if (!ok) begin $display("FAIL: %s", what); errs++; end
    else $display("PASS: %s", what);
  endtask

  initial begin
    guard = 10'd4; ref = 10'd8; thr_q214 = 16'(8 << 14);
    tvalid = 0; tdata = 0; tlast = 0;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);

    check(!cfg_error, "legal params -> no cfg_error");

    // feed a 1024-bin power spectrum: noise 100, strong 1_000_000 at bins 12 and 56
    for (int i = 0; i < 1024; i++) begin
      tvalid <= 1'b1;
      if (i == 12 || i == 56) tdata <= 32'd1000000;
      else                     tdata <= 32'd100;
      tlast <= (i == 1023);
      @(posedge clk);
      while (!tready) @(posedge clk);
    end
    tvalid <= 1'b0;
    @(posedge clk);

    while (!mask_valid) @(posedge clk);

    check(mask[12] == 1'b1, "mask[12] detected");
    check(mask[56] == 1'b1, "mask[56] detected");

    // count set bits: must be exactly 2
    int cnt = 0;
    for (int i = 0; i < 1024; i++) if (mask[i]) cnt++;
    check(cnt == 2, "exactly 2 detections (no false alarm)");
    @(posedge clk);

    // illegal params -> fail-closed
    guard = 10'd256; ref = 10'd256;
    @(posedge clk);
    check(cfg_error == 1'b1, "illegal params -> cfg_error");
    check(tready == 1'b0, "illegal params -> tready deasserted");

    if (errs == 0) $display("== m26_tb_cfar PASS ==");
    else           $display("== m26_tb_cfar FAIL (%0d) ==", errs);
    $finish;
  end

  initial begin
    #3000000;
    $display("== m26_tb_cfar TIMEOUT ==");
    $finish;
  end

endmodule
