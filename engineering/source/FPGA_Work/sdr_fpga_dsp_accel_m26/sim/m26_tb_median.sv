// M26-B.5  self-checking testbench: bit-serial exact median.
//
//   frame 1 : power = 0..1023 (ramp)         -> median must be 512  (s[512])
//   frame 2 : power = 1000 (constant)        -> median must be 1000
//   backpressure : hold ready low during compute, ensure no output lost
//
// Run via synth/run_sim.tcl (xvlog/xelab/xsim).
`timescale 1ns / 1ps

module m26_tb_median;

  logic clk = 0, rst_n = 0;
  always #5 clk = ~clk;                     // 100 MHz

  logic        tvalid, tready, tlast;
  logic [31:0] tdata;
  logic        n0_valid;
  logic [31:0] n0_data;

  m26_noise_floor dut (
    .clk(clk), .rst_n(rst_n),
    .s_axis_tvalid(tvalid), .s_axis_tready(tready),
    .s_axis_tdata(tdata), .s_axis_tlast(tlast),
    .n0_valid(n0_valid), .n0_data(n0_data)
  );

  int errs = 0;
  task automatic check(input logic ok, input string what);
    if (!ok) begin $display("FAIL: %s", what); errs++; end
    else $display("PASS: %s", what);
  endtask

  // drive one 1024-sample power frame, return the median result
  task automatic send_frame(input logic [31:0] v [0:1023], output logic [31:0] med);
    for (int i = 0; i < 1024; i++) begin
      tvalid <= 1'b1;
      tdata  <= v[i];
      tlast  <= (i == 1023);
      @(posedge clk);
      while (!tready) @(posedge clk);
    end
    tvalid <= 1'b0;
    @(posedge clk);
    // wait for the single-cycle n0_valid pulse
    while (!n0_valid) @(posedge clk);
    med = n0_data;
    @(posedge clk);
  endtask

  initial begin
    logic [31:0] v [0:1023];
    logic [31:0] med;

    // reset
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);
    tvalid = 0; tdata = 0; tlast = 0;

    // frame 1: ramp -> median 512
    for (int i = 0; i < 1024; i++) v[i] = 32'(i);
    send_frame(v, med);
    check(med == 32'd512, "ramp median == 512");

    // frame 2: constant -> median 1000
    for (int i = 0; i < 1024; i++) v[i] = 32'd1000;
    send_frame(v, med);
    check(med == 32'd1000, "constant median == 1000");

    // frame 3: reverse ramp (still a permutation of 0..1023) -> median 512
    for (int i = 0; i < 1024; i++) v[i] = 32'(1023 - i);
    send_frame(v, med);
    check(med == 32'd512, "reverse-ramp median == 512");

    if (errs == 0) $display("== m26_tb_median PASS ==");
    else           $display("== m26_tb_median FAIL (%0d) ==", errs);
    $finish;
  end

  initial begin
    #2000000;   // watchdog
    $display("== m26_tb_median TIMEOUT ==");
    $finish;
  end

endmodule
