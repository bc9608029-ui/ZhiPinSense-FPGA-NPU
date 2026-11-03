`timescale 1ns/1ps
module tb_fft_psd_stream_writer;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0;
    reg signed [26:0] s_re=0,s_im=0;
    reg [9:0] s_index=0;
    reg s_valid=0,s_last=0;
    wire s_ready;
    wire m_write_valid,m_write_bank;
    reg m_write_ready=1;
    wire [9:0] m_write_addr;
    wire [53:0] m_write_power;
    wire frame_done;
    wire [31:0] frame_id;
    wire protocol_error;
    integer frame,idx,accepted,natural_index,stall_cycle;
    reg [53:0] expected_power;

    fft_psd_stream_writer dut(
      .clk(clk),.rst_n(rst_n),.s_re(s_re),.s_im(s_im),.s_index(s_index),
      .s_valid(s_valid),.s_ready(s_ready),.s_last(s_last),
      .m_write_valid(m_write_valid),.m_write_ready(m_write_ready),
      .m_write_bank(m_write_bank),.m_write_addr(m_write_addr),
      .m_write_power(m_write_power),.frame_done(frame_done),
      .frame_id(frame_id),.protocol_error(protocol_error));

    always @(negedge clk) begin
      if(!rst_n) begin stall_cycle=0; m_write_ready=1; end
      else begin
        stall_cycle=stall_cycle+1;
        m_write_ready=((stall_cycle%7)!=3);
      end
    end

    task send_sample(input integer value,input integer is_last);
      begin : SEND_ONE
        @(negedge clk);
        s_re=value; s_im=value; s_index=value[9:0];
        s_last=is_last; s_valid=1;
        while(1) begin
          @(posedge clk);
          if(s_ready) begin
            @(negedge clk); s_valid=0; s_last=0;
            disable SEND_ONE;
          end
        end
      end
    endtask

    always @(posedge clk) begin
      if (rst_n && m_write_valid && m_write_ready) begin
        natural_index = m_write_addr ^ 10'd512;
        expected_power = 2 * natural_index * natural_index;
        if (m_write_power !== expected_power) begin
          $display("POWER_DEBUG accepted=%0d addr=%0d natural=%0d got=%0d expected=%0d s_re=%0d s_im=%0d re2=%0d im2=%0d pu=%0d",accepted,m_write_addr,natural_index,m_write_power,expected_power,s_re,s_im,dut.re_square,dut.im_square,dut.power_u54);
          $fatal(1,"power mismatch");
        end
        if (m_write_bank !== ((accepted/1024)&1)) $fatal(1,"bank mismatch");
        accepted = accepted + 1;
      end
    end

    initial begin
      accepted=0;
      repeat(4) @(posedge clk); rst_n<=1;
      for(frame=0;frame<2;frame=frame+1) begin
        for(idx=0;idx<1024;idx=idx+1)
          send_sample(idx,(idx==1023));
      end
      wait(frame_id==2); repeat(4) @(posedge clk);
      if(accepted!=2048) $fatal(1,"accepted count mismatch");
      if(frame_id!=2) $fatal(1,"frame id mismatch");
      if(protocol_error) $fatal(1,"unexpected protocol error");
      $display("TB_FFT_PSD_STREAM_WRITER PASS accepted=%0d",accepted);
      $finish;
    end
endmodule
