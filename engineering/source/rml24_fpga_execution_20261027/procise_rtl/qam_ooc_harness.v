`timescale 1ns/1ps
// Implementation-only serial register harness. Not a PS/PL runtime adapter.
// Keeps every frozen QAM input/output bit observable without 258 package pins.
module qam_ooc_harness(
 input wire clk,rst_n,serial_load,serial_in,sample_valid,result_ready,serial_read,
 output wire sample_ready,result_valid,serial_out);
 reg[76:0] input_shift;
 reg[174:0] output_shift;
 wire signed[15:0] mi,mq;wire[31:0] power;wire signed[32:0] re,im;
 wire[9:0] index;wire[31:0] fid;wire fs,fe,err;
 qam_feature_pipeline dut(.clk(clk),.rst_n(rst_n),
 .s_i(input_shift[15:0]),.s_q(input_shift[31:16]),
 .s_valid(sample_valid),.s_ready(sample_ready),
 .s_sample_index(input_shift[41:32]),.s_frame_id(input_shift[73:42]),
 .s_frame_start(input_shift[74]),.s_frame_end(input_shift[75]),.s_error(input_shift[76]),
 .m_i(mi),.m_q(mq),.m_power(power),.m_lag_re(re),.m_lag_im(im),
 .m_valid(result_valid),.m_ready(result_ready),.m_sample_index(index),
 .m_frame_id(fid),.m_frame_start(fs),.m_frame_end(fe),.m_error(err));
 always@(posedge clk or negedge rst_n)begin
  if(!rst_n)begin input_shift<=0;output_shift<=0;end
  else begin
   if(serial_load)input_shift<={input_shift[75:0],serial_in};
   if(result_valid&&result_ready)output_shift<={mi,mq,power,re,im,index,fid,fs,fe,err};
   else if(serial_read)output_shift<={1'b0,output_shift[174:1]};
  end
 end
 assign serial_out=output_shift[0];
endmodule