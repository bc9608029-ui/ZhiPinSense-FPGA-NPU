`timescale 1ns/1ps
`include "vector_params.svh"
module tb_feature_stress;
 localparam TOTAL=`FPGA_VECTOR_TOTAL_SAMPLES, FRAMES=TOTAL/1024;
 reg clk=0,rst_n=0,phase=0;
 always #5 clk=~clk;
 reg [31:0] iq[0:TOTAL-1],ep[0:TOTAL-1];
 reg [32:0] er[0:TOTAL-1],ei[0:TOTAL-1];
 reg [41:0] ee[0:FRAMES-1];reg [31:0] ek[0:FRAMES-1];
 reg signed[15:0] si=0,sq=0;
 reg sv=0,fs=0,fe=0;
 reg[9:0] idx=0;reg[31:0] fid=0;
 wire qr,sr; wire common_ready=qr&&sr;
 wire signed[15:0] mi,mq;wire[31:0] mp;wire signed[32:0] mr,mim;
 wire mv;reg ready=1;wire[9:0] midx;wire[31:0] mfid;wire mfs,mfe,me;
 wire statv;reg statr=1;wire[10:0] count;wire[41:0] energy;wire[31:0] peak;
 qam_feature_pipeline q(.clk(clk),.rst_n(rst_n),.s_i(si),.s_q(sq),.s_valid(sv&&sr),.s_ready(qr),.s_sample_index(idx),.s_frame_id(fid),.s_frame_start(fs),.s_frame_end(fe),.s_error(1'b0),.m_i(mi),.m_q(mq),.m_power(mp),.m_lag_re(mr),.m_lag_im(mim),.m_valid(mv),.m_ready(ready),.m_sample_index(midx),.m_frame_id(mfid),.m_frame_start(mfs),.m_frame_end(mfe),.m_error(me));
 frame_statistics st(.clk(clk),.rst_n(rst_n),.s_i(si),.s_q(sq),.s_valid(sv&&qr),.s_ready(sr),.s_frame_start(fs),.s_frame_end(fe),.m_stats_valid(statv),.m_stats_ready(statr),.m_sample_count(count),.m_energy(energy),.m_peak_power(peak));
 integer sent=0,received=0,stats=0,cycles=0,input_stalls=0,output_stalls=0,stats_stalls=0;
 reg accepted=0;reg[31:0] lfsr=32'h12345678;
 reg prev_stall=0,prev_stats_stall=0;reg[179:0] held;reg[84:0] held_stats;
 wire[179:0] payload={mi,mq,mp,mr,mim,midx,mfid,mfs,mfe,me};
 always @(posedge clk) begin
  if(!rst_n)begin sent<=0;received<=0;stats<=0;accepted<=0;prev_stall<=0;prev_stats_stall<=0;lfsr<=32'h12345678;end
  else if(phase)begin
   cycles<=cycles+1;lfsr<={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
   accepted<=sv&&common_ready;
   if(sv&&common_ready)sent<=sent+1;
   if(sv&&!common_ready)input_stalls<=input_stalls+1;
   if(mv&&!ready)output_stalls<=output_stalls+1;
   if(statv&&!statr)stats_stalls<=stats_stalls+1;
   if(prev_stall&&(!mv||payload!==held))$fatal(1,"feature changed during stall");
   if(prev_stats_stall&&(!statv||{count,energy,peak}!==held_stats))$fatal(1,"statistics changed during stall");
   prev_stall<=mv&&!ready;held<=payload;prev_stats_stall<=statv&&!statr;held_stats<={count,energy,peak};
   if(mv&&ready)begin
    if(received>=TOTAL)$fatal(1,"extra output");
    if(mi!==iq[received][15:0]||mq!==iq[received][31:16])$fatal(1,"IQ mismatch %0d",received);
    if(mp!==ep[received]||mr!==er[received]||mim!==ei[received])$fatal(1,"feature mismatch %0d",received);
    if(midx!==10'(received%1024)||mfid!==32'(received/1024)||mfs!==(received%1024==0)||mfe!==(received%1024==1023)||me!==0)$fatal(1,"metadata mismatch %0d",received);
    received<=received+1;
   end
   if(statv&&statr)begin
    if(stats>=FRAMES)$fatal(1,"extra frame statistics");
    if(count!==1024||energy!==ee[stats]||peak!==ek[stats])$fatal(1,"frame statistics mismatch %0d",stats);
    stats<=stats+1;
   end
   if(received==TOTAL&&stats==FRAMES)begin
    if(input_stalls==0||output_stalls==0||stats_stalls==0)$fatal(1,"missing stall coverage");
    $display("FEATURE_STRESS_PASS samples=%0d frames=%0d input_stalls=%0d output_stalls=%0d stats_stalls=%0d partial_reset=1",received,stats,input_stalls,output_stalls,stats_stalls);$finish;
   end
  end
 end
 always @(negedge clk)if(rst_n&&phase)begin
  ready=lfsr[0]||lfsr[2];statr=lfsr[5];
  if(!sv||accepted)begin
   if(sent<TOTAL)begin
    sv=lfsr[1]||lfsr[3];si=iq[sent][15:0];sq=iq[sent][31:16];idx=sent%1024;fid=sent/1024;fs=sent%1024==0;fe=sent%1024==1023;
   end else begin sv=0;fs=0;fe=0;end
  end
 end
 integer k;
 initial begin
  $readmemh("vectors/iq_input.hex",iq);$readmemh("vectors/expected_power.hex",ep);$readmemh("vectors/expected_lag_re.hex",er);$readmemh("vectors/expected_lag_im.hex",ei);$readmemh("vectors/expected_energy.hex",ee);$readmemh("vectors/expected_peak.hex",ek);
  repeat(3)@(negedge clk);rst_n=1;
  for(k=0;k<17;k=k+1)begin
   @(negedge clk);si=16'sh8000;sq=16'sh8000;sv=1;fs=(k==0);fe=0;
   @(posedge clk);while(!common_ready)@(posedge clk);
  end
  @(negedge clk);sv=0;ready=0;statr=0;rst_n=0;
  #1;if(mv!==0||statv!==0)$fatal(1,"reset did not flush pending state");
  repeat(3)@(negedge clk);#1;rst_n=1;phase=1;
 end
 initial begin #5000000;$fatal(1,"stress timeout");end
endmodule