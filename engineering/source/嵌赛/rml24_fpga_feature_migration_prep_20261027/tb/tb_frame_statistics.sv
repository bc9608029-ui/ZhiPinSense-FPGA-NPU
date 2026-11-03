`timescale 1ns/1ps
module tb_frame_statistics;
    reg clk=0, rst_n=0;
    reg signed [15:0] s_i=0, s_q=0;
    reg s_valid=0, s_frame_start=0, s_frame_end=0;
    wire s_ready;
    wire m_stats_valid;
    reg m_stats_ready=1;
    wire [10:0] m_sample_count;
    wire [41:0] m_energy;
    wire [31:0] m_peak_power;

    frame_statistics dut(.*);
    always #5 clk=~clk;

    task send(input signed [15:0] i, input signed [15:0] q, input fs, input fe);
      begin
        @(negedge clk); s_i=i; s_q=q; s_frame_start=fs; s_frame_end=fe; s_valid=1;
        while (!s_ready) @(negedge clk);
        @(negedge clk); s_valid=0; s_frame_start=0; s_frame_end=0;
      end
    endtask

    initial begin
      repeat(3) @(negedge clk); rst_n=1;
      send(16'sd3,16'sd4,1,0);       // power 25
      send(-16'sd5,16'sd12,0,0);     // power 169
      send(-16'sd32768,-16'sd32768,0,1); // power 2^31
      wait(m_stats_valid);
      if(m_sample_count !== 11'd3) $fatal(1,"count");
      if(m_energy !== (42'd2147483648+42'd194)) $fatal(1,"energy");
      if(m_peak_power !== 32'd2147483648) $fatal(1,"peak");
      @(negedge clk);
      send(16'sd0,16'sd0,1,1);
      wait(m_stats_valid);
      if(m_sample_count !== 11'd1 || m_energy !== 0 || m_peak_power !== 0) $fatal(1,"reset between frames");
      $display("TB_FRAME_STATISTICS PASS");
      $finish;
    end
endmodule
