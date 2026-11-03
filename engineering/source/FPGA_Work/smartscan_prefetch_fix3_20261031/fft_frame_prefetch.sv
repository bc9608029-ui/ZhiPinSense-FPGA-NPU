`timescale 1ns/1ps
// Independent candidate: capture a complete windowed frame before realtime FFT.
// Single buffer, backpressure between frames, no model/rounding/FFT config change.
module fft_frame_prefetch(
 input wire clk,rst_n, input wire [31:0] s_data,
 input wire s_valid,output wire s_ready,input wire s_last,
 output wire [31:0] m_data,output wire m_valid,input wire m_ready,
 output wire m_last,output reg length_error);
 (* ram_style="block" *) reg [31:0] mem [0:1023];
 reg [31:0] output_data;
 reg [9:0] wr,rd;
 reg draining;
 assign s_ready=!draining;
 assign m_valid=draining;
 assign m_data=output_data;
 assign m_last=draining && rd==1023;
 // RAM ports are synchronous and have no asynchronous reset.
 wire first_read=rst_n && s_valid && s_ready && wr==1023;
 wire next_read=rst_n && m_valid && m_ready && rd!=1023;
 wire [9:0] read_addr=first_read ? 10'd0 : rd+1'b1;
 always @(posedge clk) begin
  if(rst_n && s_valid && s_ready) mem[wr]<=s_data;
  if(first_read || next_read) output_data<=mem[read_addr];
 end
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin wr<=0;rd<=0;draining<=0;length_error<=0;end
  else begin
   if(s_valid && s_ready) begin
    if(s_last != (wr==1023)) length_error<=1;
    if(wr==1023) begin wr<=0;rd<=0;draining<=1;end
    else wr<=wr+1'b1;
   end
   if(m_valid && m_ready) begin
    if(rd==1023) begin rd<=0;draining<=0;end
    else rd<=rd+1'b1;
   end
  end
 end
endmodule
