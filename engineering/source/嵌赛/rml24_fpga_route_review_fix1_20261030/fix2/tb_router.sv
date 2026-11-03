`timescale 1ns/1ps
module tb_router;
reg clk=0; always #5 clk=~clk;
reg rst_n=0;
reg [31:0] awwaddr=0,awwdata=32'h13579bdf,araddr=0;
reg awwvalid=1,arvalid=0,rready=0;
wire awwready,arready,rvalid; wire [31:0] rdata;
wire [31:0] e0_awwaddr,e1_awwaddr,e0_awwdata,e1_awwdata,e0_araddr,e1_araddr;
wire e0_awwvalid,e1_awwvalid,e0_arvalid,e1_arvalid,e0_rready,e1_rready;
reg e0_awwready=1,e1_awwready=0,e0_arready=1,e1_arready=1;
reg e0_rvalid=0,e1_rvalid=0;
user_reg_router dut(.*,.e0_rdata(32'h01234567),.e1_rdata(32'h89abcdef));
integer a; reg expected;
initial begin
 #12; rst_n=1;
 // Exhaustive 18-bit decode checks read+write, including both window edges.
 for(a=0;a<262144;a=a+1) begin
  awwaddr=a; araddr=a; arvalid=1; #1;
  expected=(a>=65536 && a<69632);
  if(e1_awwvalid!==expected || e0_awwvalid!==!expected ||
     e1_arvalid!==expected || e0_arvalid!==!expected) $fatal(1,"DECODE address=%h",a);
  if(expected && (e1_awwaddr!==a-65536 || e1_araddr!==a-65536)) $fatal(1,"REMAP");
  if(!expected && (e0_awwaddr!==a || e0_araddr!==a)) $fatal(1,"NPU_ADDR");
  if(awwready!==!expected) $fatal(1,"WRITE_BACKPRESSURE");
 end
 arvalid=0; awwvalid=0;
 @(negedge clk); araddr=32'h1000c; arvalid=1;
 @(posedge clk); #1; arvalid=0; e1_rvalid=1; rready=0; araddr=0;
 repeat(3) begin @(negedge clk); if(rdata!==32'h89abcdef || !rvalid || e1_rready) $fatal(1,"SS_RESPONSE"); end
 rready=1; #1; if(!e1_rready || e0_rready) $fatal(1,"SS_READY");
 @(negedge clk); e1_rvalid=0; rready=0; araddr=32'hc; arvalid=1;
 @(posedge clk); #1; arvalid=0; e0_rvalid=1;
 #1; if(rdata!==32'h01234567 || !rvalid) $fatal(1,"NPU_RESPONSE");
 rready=1; #1; if(!e0_rready || e1_rready) $fatal(1,"NPU_READY");
 $display("ROUTER_TEST_PASS addresses=262144 read_write=1 responses=2"); $finish;
end
endmodule
