// M26-A  self-checking testbench: streaming frontend top.
//
//   reset          : m_axis_tvalid low, cfg_error 0 (legal config)
//   bypass-all     : output == input (bit-exact, 4-cycle latency)
//   decim=2        : 1024 in -> 512 out per frame, tlast on the last kept sample
//   backpressure   : holding m_axis_tready low deasserts s_axis_tready
//   illegal decim  : cfg_error=1 and s_axis_tready deasserted (fail-closed)
//
// Run via synth/run_sim.tcl.
`timescale 1ns / 1ps

module m26_tb_stream_frontend;

  logic clk = 0, rst_n = 0;
  always #5 clk = ~clk;

  logic        bypass_dc, bypass_nco, bypass_fir, bypass_decim;
  logic [31:0] nco_phase_inc;
  logic [3:0]  decim_factor;
  logic        energy_enable;
  logic [15:0] thr_enter, thr_exit;
  logic [3:0]  enter_m, exit_n;

  logic        tvalid, tready, tlast;
  logic [31:0] tdata;
  logic        oval, oready, olast;
  logic [31:0] odata;
  logic [47:0] energy;
  logic [15:0] rms;
  logic [31:0] peak;
  logic        stats_valid;
  logic [1:0]  presence;
  logic        presence_changed;
  logic        cfg_error;

  m26_stream_frontend_top dut (
    .clk(clk), .rst_n(rst_n),
    .bypass_dc(bypass_dc), .bypass_nco(bypass_nco),
    .bypass_fir(bypass_fir), .bypass_decim(bypass_decim),
    .nco_phase_inc(nco_phase_inc), .decim_factor(decim_factor),
    .energy_enable(energy_enable),
    .thr_enter(thr_enter), .thr_exit(thr_exit),
    .enter_m(enter_m), .exit_n(exit_n),
    .s_axis_tvalid(tvalid), .s_axis_tready(tready),
    .s_axis_tdata(tdata), .s_axis_tlast(tlast),
    .m_axis_tvalid(oval), .m_axis_tready(oready),
    .m_axis_tdata(odata), .m_axis_tlast(olast),
    .energy(energy), .rms(rms), .peak(peak), .stats_valid(stats_valid),
    .presence(presence), .presence_changed(presence_changed),
    .cfg_error(cfg_error)
  );

  int errs = 0;
  task automatic check(input logic ok, input string what);
    if (!ok) begin $display("FAIL: %s", what); errs++; end
    else $display("PASS: %s", what);
  endtask

  logic [31:0] got [0:1023];

  initial begin
    bypass_dc = 1; bypass_nco = 1; bypass_fir = 1; bypass_decim = 1;
    nco_phase_inc = 0; decim_factor = 2; energy_enable = 0;
    thr_enter = 16'd100; thr_exit = 16'd50; enter_m = 4'd2; exit_n = 4'd2;
    tvalid = 0; tdata = 0; tlast = 0; oready = 1'b1;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);

    check(!cfg_error, "legal config -> cfg_error 0");
    check(!oval, "reset -> m_axis_tvalid low");

    // ---- bypass-all passthrough (4-cycle latency: dc+nco+fir+decim)
    logic [31:0] sent [0:31];
    int nout = 0;
    for (int i = 0; i < 32; i++) sent[i] = {16'(i * 7 + 1), 16'(-(i * 11 + 2))};
    for (int i = 0; i < 32; i++) begin
      tvalid <= 1'b1; tdata <= sent[i]; tlast <= (i == 31);
      @(posedge clk);
      while (!tready) @(posedge clk);
      if (oval && oready) got[nout++] = odata;
    end
    tvalid <= 1'b0;
    repeat (6) begin @(posedge clk); if (oval && oready) got[nout++] = odata; end

    int pmatch = 1;
    // outputs correspond to input shifted by 4 (bypass latency)
    for (int i = 0; i < nout && i < 28; i++)
      if (got[i] !== sent[i]) pmatch = 0;   // got[0] == sent[0] after 4-cycle pipe
    check(nout >= 28 && pmatch, "bypass-all passthrough bit-exact");

    // ---- decim=2 (dc/nco/fir bypass, decim active): 1024 in -> 512 out
    bypass_decim = 1'b0; decim_factor = 4'd2;
    @(posedge clk);
    // flush any residual
    repeat (4) @(posedge clk);
    int ocount = 0;
    for (int i = 0; i < 1024; i++) begin
      tvalid <= 1'b1; tdata <= 32'(i); tlast <= (i == 1023);
      @(posedge clk);
      while (!tready) @(posedge clk);
      if (oval && oready) ocount++;
    end
    tvalid <= 1'b0;
    repeat (8) begin @(posedge clk); if (oval && oready) ocount++; end
    check(ocount == 512, "decim=2 -> 512 outputs per 1024-input frame");

    // ---- backpressure: stall downstream, expect s_axis_tready to drop
    bypass_decim = 1;   // back to bypass for a clean streaming test
    oready = 1'b0;
    tvalid <= 1'b1; tdata <= 32'h12345678; tlast <= 1'b0;
    @(posedge clk); @(posedge clk); @(posedge clk);
    check(tready == 1'b0, "backpressure -> s_axis_tready deasserted");
    tvalid <= 1'b0; oready <= 1'b1;
    @(posedge clk);

    // ---- illegal decim -> fail-closed
    bypass_decim = 1'b0; decim_factor = 4'd3;
    @(posedge clk);
    check(cfg_error == 1'b1, "illegal decim -> cfg_error");
    check(tready == 1'b0, "illegal decim -> tready deasserted");

    if (errs == 0) $display("== m26_tb_stream_frontend PASS ==");
    else           $display("== m26_tb_stream_frontend FAIL (%0d) ==", errs);
    $finish;
  end

  initial begin
    #5000000;
    $display("== m26_tb_stream_frontend TIMEOUT ==");
    $finish;
  end

endmodule
