`timescale 1ns/1ps
module window_mul_q15(
 input wire clk,input wire rst_n,
 input wire signed [15:0] s_i,input wire signed [15:0] s_q,input wire signed [15:0] s_w,
 input wire s_valid,output wire s_ready,
 output reg signed [15:0] m_i,output reg signed [15:0] m_q,output reg m_valid,input wire m_ready
);
 wire free=!m_valid||m_ready; assign s_ready=free;
 wire signed [31:0] pi=s_i*s_w,pq=s_q*s_w;
 function automatic signed [31:0] round15(input signed [31:0] v);
   reg signed [32:0] mag; begin
     mag = v<0 ? -$signed({v[31],v}) : $signed({1'b0,v});
     mag = (mag + 33'sd16384) >>> 15;
     round15 = v<0 ? -mag[31:0] : mag[31:0];
   end
 endfunction
 function automatic signed [15:0] sat16(input signed [31:0] v);
   begin if(v>32767) sat16=16'sd32767; else if(v< -32768) sat16=-16'sd32768; else sat16=v[15:0]; end
 endfunction
 always @(posedge clk or negedge rst_n) begin
   if(!rst_n) m_valid<=0; else if(free) begin m_valid<=s_valid; if(s_valid) begin m_i<=sat16(round15(pi)); m_q<=sat16(round15(pq)); end end
 end
endmodule
