// Copyright 1986-2018 Xilinx, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2018.3 (win64) Build 2405991 Thu Dec  6 23:38:27 MST 2018
// Date        : Tue Sep 29 18:15:54 2026
// Host        : colorfulshadow running 64-bit major release  (build 9200)
// Command     : write_verilog -force -mode synth_stub
//               F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/rtl/ip/windex_buf_2b_16w/windex_buf_2b_16w_stub.v
// Design      : windex_buf_2b_16w
// Purpose     : Stub declaration of top-level module interface
// Device      : xc7z030ffg676-2
// --------------------------------------------------------------------------------

// This empty module with port declaration file causes synthesis tools to infer a black box for IP.
// The synthesis directives are for Synopsys Synplify support to prevent IO buffer insertion.
// Please paste the declaration into a Verilog source file or add the file as an additional source.
(* x_core_info = "fifo_generator_v13_2_3,Vivado 2018.3" *)
module windex_buf_2b_16w(rst, wr_clk, rd_clk, din, wr_en, rd_en, dout, full, 
  empty)
/* synthesis syn_black_box black_box_pad_pin="rst,wr_clk,rd_clk,din[1:0],wr_en,rd_en,dout[1:0],full,empty" */;
  input rst;
  input wr_clk;
  input rd_clk;
  input [1:0]din;
  input wr_en;
  input rd_en;
  output [1:0]dout;
  output full;
  output empty;
endmodule
