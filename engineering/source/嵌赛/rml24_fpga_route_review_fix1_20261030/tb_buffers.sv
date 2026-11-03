`timescale 1ns/1ps
module tb_buffers;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,wr_valid=0,wr_bank=0,rd_bank=0;
reg [9:0] wr_addr=0,rd_addr=0;
reg [53:0] wr_power=0;
reg [31:0] frame_id=0;
wire [63:0] rd_data;
wire [7:0] version;wire [31:0] fid;wire pe,ov,cv,cb;
smart_scan_psd_buffers dut(clk,rst_n,wr_valid,wr_bank,wr_addr,wr_power,frame_id,
  1'b0,1'b0,rd_bank,rd_addr,rd_data,version,fid,pe,ov,cv,cb);
integer b,i;
initial begin
 repeat(3)@(negedge clk);rst_n=1;
 for(b=0;b<2;b=b+1)for(i=0;i<1024;i=i+1)begin
   @(negedge clk);wr_valid=1;wr_bank=b;wr_addr=i;wr_power=b*1024+i+7;
 end
 @(negedge clk);wr_valid=0;frame_id=2;
 for(b=0;b<2;b=b+1)for(i=0;i<1024;i=i+1)begin
   @(negedge clk);rd_bank=b;rd_addr=i;
   @(posedge clk);#1;
   if(rd_data!==b*1024+i+7)$fatal(1,"bad data bank=%d addr=%d data=%d",b,i,rd_data);
 end
 if(!cv || cb!==1'b1 || fid!==2)$fatal(1,"bad status");
 $display("BRAM_SYNC_SIM PASS reads=2048 banks=2 latency=1");$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
