`timescale 1ns/1ps
module tb_smart_scan_boundary;
 reg clk=0,rst_n=0; always #5 clk=~clk;
 reg signed [15:0] wi=0,wq=0,ww=0; reg wv=0; wire wr;
 wire signed [15:0] wo_i,wo_q; wire wo_v;
 window_mul_q15 u_win(.clk(clk),.rst_n(rst_n),.s_i(wi),.s_q(wq),.s_w(ww),.s_valid(wv),.s_ready(wr),.m_i(wo_i),.m_q(wo_q),.m_valid(wo_v),.m_ready(1'b1));
 reg signed [25:0] fr=0,fi=0; reg fv=0; wire fready; wire [51:0] power; wire pv;
 fft_magnitude_square_u52 u_pow(.clk(clk),.rst_n(rst_n),.s_re(fr),.s_im(fi),.s_valid(fv),.s_ready(fready),.m_power(power),.m_valid(pv),.m_ready(1'b1));
 initial begin
   repeat(2) @(negedge clk); rst_n=1;
   @(negedge clk); wi=1000; wq=-1000; ww=32767; wv=1; fr=-(1<<<25); fi=-(1<<<25); fv=1;
   @(negedge clk); wv=0; fv=0;
   wait(wo_v&&pv);
   if(wo_i!==1000 || wo_q!==-1000) $fatal(1,"window rounding");
   if(power!==52'd2251799813685248) $fatal(1,"u52 extreme");
   $display("TB_SMART_SCAN_BOUNDARY PASS"); $finish;
 end
endmodule
