`timescale 1ns/1ps

module tb_tensor_packer;
    reg clk = 0;
    reg rst_n = 0;
    reg signed [7:0] s_iq_i = 1, s_iq_q = 2, s_power = 3, s_lag_re = 4, s_lag_im = 5;
    reg [1:0] s_sample_index = 0;
    reg [7:0] s_frame_id = 0;
    reg s_frame_start = 0, s_frame_end = 0, s_error = 0, s_valid = 0;
    wire s_ready;
    reg [1:0] buffer_release = 0;
    wire m_write_valid, m_buffer_id;
    reg m_write_ready = 1;
    wire [7:0] m_frame_id;
    wire [1:0] m_sample_index;
    wire [2:0] m_iq_i_addr, m_iq_q_addr;
    wire [3:0] m_power_addr, m_lag_re_addr, m_lag_im_addr;
    wire signed [7:0] m_iq_i_data, m_iq_q_data, m_power_data, m_lag_re_data, m_lag_im_data;
    wire m_frame_start, m_frame_done, m_frame_error, m_irq;
    wire [1:0] buffer_busy;
    integer sample = 0;
    wire [2:0] extended_iq_index = {1'b0, m_sample_index};
    wire [3:0] extended_physical_index = {2'b00, m_sample_index};

    always #5 clk = ~clk;

    tensor_packer #(.FRAME_LENGTH(4), .FRAME_ID_WIDTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .s_iq_i(s_iq_i), .s_iq_q(s_iq_q), .s_power(s_power),
        .s_lag_re(s_lag_re), .s_lag_im(s_lag_im), .s_sample_index(s_sample_index),
        .s_frame_id(s_frame_id), .s_frame_start(s_frame_start), .s_frame_end(s_frame_end),
        .s_error(s_error), .s_valid(s_valid), .s_ready(s_ready), .buffer_release(buffer_release),
        .m_write_valid(m_write_valid), .m_write_ready(m_write_ready), .m_buffer_id(m_buffer_id),
        .m_frame_id(m_frame_id), .m_sample_index(m_sample_index), .m_iq_i_addr(m_iq_i_addr),
        .m_iq_q_addr(m_iq_q_addr), .m_power_addr(m_power_addr), .m_lag_re_addr(m_lag_re_addr),
        .m_lag_im_addr(m_lag_im_addr), .m_iq_i_data(m_iq_i_data), .m_iq_q_data(m_iq_q_data),
        .m_power_data(m_power_data), .m_lag_re_data(m_lag_re_data), .m_lag_im_data(m_lag_im_data),
        .m_frame_start(m_frame_start), .m_frame_done(m_frame_done), .m_frame_error(m_frame_error),
        .m_irq(m_irq), .buffer_busy(buffer_busy)
    );

    always @(negedge clk) begin
        if (rst_n && sample < 8 && s_ready) begin
            s_valid <= 1'b1;
            s_sample_index <= 2'(sample % 4);
            s_frame_id <= 8'(sample / 4);
            s_frame_start <= ((sample % 4) == 0);
            s_frame_end <= ((sample % 4) == 3);
            sample <= sample + 1;
        end else if (sample >= 8) begin
            s_valid <= 1'b0;
        end
    end

    always @(posedge clk) begin
        if (rst_n && m_write_valid && m_write_ready) begin
            if (m_iq_q_addr !== 3'd4 + extended_iq_index) $fatal(1, "IQ Q address mismatch");
            if (m_lag_re_addr !== 4'd4 + extended_physical_index) $fatal(1, "LagRe address mismatch");
            if (m_lag_im_addr !== 4'd8 + extended_physical_index) $fatal(1, "LagIm address mismatch");
            if (m_buffer_id !== m_frame_id[0]) $fatal(1, "buffer alternation mismatch");
            if (m_irq) buffer_release[m_buffer_id] <= 1'b1;
            else buffer_release <= 2'b00;
            if (m_frame_id == 1 && m_frame_done) begin
                $display("PASS tb_tensor_packer");
                $finish;
            end
        end else begin
            buffer_release <= 2'b00;
        end
    end

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        #2000 $fatal(1, "timeout");
    end
endmodule
