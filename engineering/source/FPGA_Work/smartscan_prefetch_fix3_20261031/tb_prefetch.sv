`timescale 1ns/1ps
module tb_prefetch;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0;reg [31:0] s_data=0;reg s_valid=0,s_last=0,m_ready=0;
 wire s_ready,m_valid,m_last,length_error;wire [31:0] m_data;
 fft_frame_prefetch dut(.*);
 integer sent=0,got=0,cycle=0;reg active=0;reg [31:0] held;reg stalled=0;
 always @(posedge clk) if(rst_n) begin
  cycle=cycle+1;
  if(s_valid && s_ready) sent=sent+1;
  if(m_valid && sent<1024) $fatal(1,"early output");
  if(stalled && (!m_valid || m_data!==held)) $fatal(1,"unstable stalled output");
  stalled=m_valid&&!m_ready;held=m_data;
  if(active && got%1024!=0 && !m_valid) $fatal(1,"output starvation");
  if(m_valid && m_ready) begin
   active=1;
   if(m_data!==got || m_last!==(got%1024==1023)) $fatal(1,"data/last mismatch %0d",got);
   got=got+1;
  end
  if(cycle>30000) $fatal(1,"timeout");
 end
 integer n;
 initial begin
  repeat(4) @(negedge clk);rst_n=1;
  for(n=0;n<2048;n=n+1) begin
   repeat((n*7)%11) begin @(negedge clk);s_valid=0;m_ready=($time%7!=0);end
   @(negedge clk);s_valid=1;s_data=n;s_last=(n%1024==1023);m_ready=1;
   while(!s_ready) @(negedge clk);
   @(negedge clk);s_valid=0;
  end
  m_ready=1;wait(got==2048);
  @(negedge clk);if(length_error) $fatal(1,"unexpected length error");
  // short TLAST must be reported; reset mid-capture must discard old contents.
  s_valid=1;s_last=1;s_data=0;@(negedge clk);s_valid=0;
  if(!length_error) $fatal(1,"missing length error");
  rst_n=0;@(negedge clk);rst_n=1;@(negedge clk);
  if(m_valid || length_error) $fatal(1,"reset failed");
  $display("PREFETCH_PASS two frames with input gaps, output continuity, data, last, fault, reset");$finish;
 end
endmodule
