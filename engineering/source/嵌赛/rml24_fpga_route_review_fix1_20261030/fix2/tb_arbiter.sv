`timescale 1ns/1ps
module tb_arbiter;
reg clk=0;always #5 clk=~clk;
reg rst_n=0;
wire [31:0] ar_araddr,ar_arinfo;wire ar_arvalid,ar_rready;
reg ar_arready=1,ar_rvalid=0;reg [511:0] ar_rdata=512'h1234;reg [31:0] ar_rinfo=1;
reg [31:0] r0_araddr=32'h100,r1_araddr=32'h200,r0_arinfo=1,r1_arinfo=1;
reg r0_arvalid=0,r1_arvalid=0,r0_rready=0,r1_rready=0;
wire r0_arready,r1_arready,r0_rvalid,r1_rvalid;
wire [511:0] r0_rdata,r1_rdata;wire [31:0] r0_rinfo,r1_rinfo;
user_ddr_read_arbiter dut(.*);
initial begin
 #12;rst_n=1;
 @(negedge clk);r1_arvalid=1;
 @(posedge clk);#1;r1_arvalid=0;r0_arvalid=1;
 repeat(4) begin
  @(negedge clk);if(ar_arvalid || r0_arready || r1_arready) $fatal(1,"OVERLAPPING_OUTSTANDING");
 end
 ar_rvalid=1;
 #1;if(!r1_rvalid || r0_rvalid || ar_rready) $fatal(1,"OWNER_CHANGED");
 repeat(3) @(negedge clk);
 r1_rready=1;
 @(posedge clk);#1;ar_rvalid=0;r1_rready=0;
 @(negedge clk);if(!ar_arvalid || !r0_arready || ar_araddr!==32'h100) $fatal(1,"NPU_NOT_RESUMED");
 @(posedge clk);#1;r0_arvalid=0;ar_rvalid=1;r0_rready=1;
 #1;if(!r0_rvalid || r1_rvalid || r0_rdata!==512'h1234) $fatal(1,"NPU_RESPONSE");
 @(posedge clk);#1;ar_rvalid=0;r0_rready=0;
 @(negedge clk);r0_arvalid=1;r1_arvalid=1;
 #1;if(ar_araddr!==32'h100 || !r0_arready || r1_arready) $fatal(1,"PRIORITY");
 @(posedge clk);#1;r0_arvalid=0;r1_arvalid=0;rst_n=0;
 #2;if(r0_rvalid || r1_rvalid || ar_rready) $fatal(1,"RESET_OWNER");
 $display("DDR_ARBITER_PASS concurrent=1 delayed_response=1 backpressure=1 reset=1");$finish;
end
endmodule
