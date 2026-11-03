`timescale 1ns/1ps
module fifo_case #(parameter W=512,parameter A=4,parameter real SH=3.5,parameter real MH=5.5)(output reg done=0);
reg s_clk=0,m_clk=0; always #(SH) s_clk=~s_clk; always #(MH) m_clk=~m_clk;
reg s_rst_n=0,m_rst_n=0; reg [W-1:0] s_data=0; reg s_valid=0,m_ready=0;
wire os_ready,ns_ready,ov,nv; wire [W-1:0] od,nd;
async_fifo_gray_original #(.DATA_WIDTH(W),.ADDR_WIDTH(A)) old_dut(
 .s_clk(s_clk),.s_rst_n(s_rst_n),.s_data(s_data),.s_valid(s_valid),.s_ready(os_ready),
 .m_clk(m_clk),.m_rst_n(m_rst_n),.m_data(od),.m_valid(ov),.m_ready(m_ready));
async_fifo_gray #(.DATA_WIDTH(W),.ADDR_WIDTH(A)) new_dut(
 .s_clk(s_clk),.s_rst_n(s_rst_n),.s_data(s_data),.s_valid(s_valid),.s_ready(ns_ready),
 .m_clk(m_clk),.m_rst_n(m_rst_n),.m_data(nd),.m_valid(nv),.m_ready(m_ready));
reg [W-1:0] expected[0:8191]; integer wr=0,rd=0,phase,i,j;
reg [31:0] sr=32'h18372895,mr=32'ha8f3d291;
function [31:0] step(input [31:0] x); step={x[30:0],x[31]^x[21]^x[1]^x[0]}; endfunction
always @(posedge s_clk) if(s_rst_n) begin
 if(os_ready!==ns_ready) $fatal(1,"READY W=%d",W);
 if(s_valid && ns_ready) begin expected[wr]=s_data; wr=wr+1; end
end
always @(posedge m_clk) if(m_rst_n) begin
 if(ov!==nv) $fatal(1,"VALID W=%d",W);
 if(nv && od!==nd) $fatal(1,"DATA W=%d",W);
 if(nv && m_ready) begin if(rd>=wr || nd!==expected[rd]) $fatal(1,"ORDER W=%d",W); rd=rd+1; end
end
initial begin
 for(phase=0;phase<3;phase=phase+1) begin
  @(negedge s_clk); s_rst_n=0; m_rst_n=0; s_valid=0; m_ready=0; wr=0;rd=0;
  #40; s_rst_n=1; m_rst_n=1;
  fork
   begin
    for(i=0;i<3500;i=i+1) begin
     @(negedge s_clk); sr=step(sr);
     if(!s_valid || ns_ready) begin
      s_valid=(sr[2:0]!=0);
      for(j=0;j<W;j=j+1) s_data[j]=sr[j%32] ^ ((wr>>(j%13))&1);
     end
    end
    @(negedge s_clk); s_valid=0;
   end
   begin repeat(2400) begin @(negedge m_clk); mr=step(mr); m_ready=(mr[3:0]>3); end end
  join
  @(negedge m_clk); m_ready=1;
  repeat(100) @(negedge m_clk);
  if(rd!=wr || nv) $fatal(1,"DRAIN W=%d wr=%d rd=%d",W,wr,rd);
 end
 $display("FIFO_EQUIVALENCE_PASS width=%d addr=%d resets=3",W,A);done=1;
end
endmodule
module tb_fifo;
wire d0,d1,d2,d3;
fifo_case #(.W(32),.A(2)) c0(d0);
fifo_case #(.W(512),.A(4)) c1(d1);
fifo_case #(.W(544),.A(4)) c2(d2);
fifo_case #(.W(512),.A(4),.SH(7.5),.MH(2.5)) c3(d3);
initial begin wait(d0&&d1&&d2&&d3); $display("ALL_FIFO_CASES_PASS");$finish;end
initial begin #1000000; $fatal(1,"TIMEOUT");end
endmodule
