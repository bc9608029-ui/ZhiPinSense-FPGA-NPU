`timescale 1ns/1ps
module tb_qam_ooc_harness;
 reg clk=0,rst_n=0,serial_load=0,serial_in=0,sample_valid=0,result_ready=0,serial_read=0;
 wire sample_ready,result_valid,serial_out;
 qam_ooc_harness dut(.*);
 always #5 clk=~clk;
 reg signed[15:0] pi=0,pq=0;
 task one(input signed[15:0] iv,qv,input[31:0] fid,input[9:0] idx,input fs,fe,err);
  reg[76:0] inword;reg[174:0] got,want;reg[31:0] pw;reg[32:0] re,im;
  longint signed a,b,c,d;integer j;
  begin
   a=iv;b=qv;c=pi;d=pq;pw=a*a+b*b;re=fs?0:a*c+b*d;im=fs?0:b*c-a*d;
   inword={err,fe,fs,fid,idx,qv,iv};want={iv,qv,pw,re,im,idx,fid,fs,fe,err};
   for(j=76;j>=0;j=j-1)begin @(negedge clk);serial_load=1;serial_in=inword[j];end
   @(negedge clk);serial_load=0;sample_valid=1;
   @(posedge clk);while(!sample_ready)@(posedge clk);
   @(negedge clk);sample_valid=0;
   wait(result_valid);@(negedge clk);result_ready=1;@(posedge clk);@(negedge clk);result_ready=0;
   for(j=0;j<175;j=j+1)begin #1;got[j]=serial_out;serial_read=1;@(posedge clk);@(negedge clk);end
   serial_read=0;
   if(got!==want)$fatal(1,"OOC serial harness changed frozen output idx=%0d",idx);
   pi=iv;pq=qv;
  end
 endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  one(16'sh8000,16'sh8000,32'd0,10'd0,1,0,0);
  one(16'sh7fff,16'sh8000,32'd0,10'd1,0,0,0);
  one(0,0,32'd0,10'd2,0,1,0);
  one(3,4,32'd1,10'd0,1,1,1);
  $display("OOC_HARNESS_EQUIVALENCE_PASS samples=4 bits_per_output=175");$finish;
 end
 initial begin #100000;$fatal(1,"harness timeout");end
endmodule