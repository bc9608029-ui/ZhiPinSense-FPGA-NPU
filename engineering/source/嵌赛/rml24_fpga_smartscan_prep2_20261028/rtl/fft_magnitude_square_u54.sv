`timescale 1ns/1ps
module fft_magnitude_square_u54(
 input wire clk,input wire rst_n,input wire signed [26:0] s_re,input wire signed [26:0] s_im,
 input wire s_valid,output wire s_ready,output reg [53:0] m_power,output reg m_valid,input wire m_ready
);
 wire free=!m_valid||m_ready; assign s_ready=free;
 wire signed [53:0] re2=s_re*s_re, im2=s_im*s_im;
 always @(posedge clk or negedge rst_n) begin
   if(!rst_n) m_valid<=0; else if(free) begin m_valid<=s_valid; if(s_valid) m_power<=$unsigned(re2)+$unsigned(im2); end
 end
endmodule
