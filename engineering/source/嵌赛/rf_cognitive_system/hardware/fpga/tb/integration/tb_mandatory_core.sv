`timescale 1ns/1ps
`include "vector_params.svh"

module tb_mandatory_core;
    localparam integer TOTAL = `FPGA_VECTOR_TOTAL_SAMPLES;
    reg [31:0] input_mem [0:TOTAL-1];
    reg clk = 0;
    reg rst_n = 0;
    reg signed [15:0] s_i = 0, s_q = 0;
    reg s_valid = 0, s_error = 0, s_overflow_event = 0;
    wire s_ready;
    reg [1:0] buffer_release = 0;
    wire m_write_valid;
    reg m_write_ready = 1;
    wire m_buffer_id;
    wire [31:0] m_frame_id;
    wire [9:0] m_sample_index;
    wire [10:0] m_iq_i_addr, m_iq_q_addr;
    wire [11:0] m_power_addr, m_lag_re_addr, m_lag_im_addr;
    wire signed [7:0] m_iq_i_data, m_iq_q_data, m_power_data, m_lag_re_data, m_lag_im_data;
    wire m_frame_valid, m_frame_start, m_frame_done, m_frame_error, m_irq;
    wire [1:0] buffer_busy;
    wire [31:0] overflow_count, sat_i, sat_q, sat_p, sat_re, sat_im;
    integer input_index = 0;
    integer output_count = 0;
    integer output_file;

    always #5 clk = ~clk;

    mandatory_core_path dut (
        .clk(clk), .rst_n(rst_n), .s_i(s_i), .s_q(s_q), .s_error(s_error),
        .s_valid(s_valid), .s_ready(s_ready), .s_overflow_event(s_overflow_event),
        .cfg_iq_multiplier(32'd127), .cfg_iq_shift(8'd15),
        .cfg_power_multiplier(32'd127), .cfg_power_shift(8'd31),
        .cfg_lag_multiplier(32'd127), .cfg_lag_shift(8'd31),
        .clear_counters(1'b0), .buffer_release(buffer_release),
        .m_write_valid(m_write_valid), .m_write_ready(m_write_ready), .m_buffer_id(m_buffer_id),
        .m_frame_id(m_frame_id), .m_sample_index(m_sample_index), .m_iq_i_addr(m_iq_i_addr),
        .m_iq_q_addr(m_iq_q_addr), .m_power_addr(m_power_addr), .m_lag_re_addr(m_lag_re_addr),
        .m_lag_im_addr(m_lag_im_addr), .m_iq_i_data(m_iq_i_data), .m_iq_q_data(m_iq_q_data),
        .m_power_data(m_power_data), .m_lag_re_data(m_lag_re_data), .m_lag_im_data(m_lag_im_data),
        .m_frame_valid(m_frame_valid), .m_frame_start(m_frame_start),
        .m_frame_done(m_frame_done), .m_frame_error(m_frame_error),
        .m_irq(m_irq), .buffer_busy(buffer_busy), .overflow_count(overflow_count),
        .saturation_count_i(sat_i), .saturation_count_q(sat_q), .saturation_count_power(sat_p),
        .saturation_count_lag_re(sat_re), .saturation_count_lag_im(sat_im)
    );

    always @(negedge clk) begin
        if (rst_n && input_index < TOTAL && s_ready) begin
            s_i <= input_mem[input_index][15:0];
            s_q <= input_mem[input_index][31:16];
            s_valid <= 1'b1;
            input_index <= input_index + 1;
        end else if (input_index >= TOTAL) begin
            s_valid <= 1'b0;
        end
    end

    always @(posedge clk) begin
        buffer_release <= 2'b00;
        if (rst_n && m_irq)
            buffer_release[m_buffer_id] <= 1'b1;
        if (rst_n && m_write_valid && m_write_ready) begin
            if (!m_frame_valid) $fatal(1, "frame_valid missing on accepted tensor sample");
            if (m_frame_start !== (m_sample_index == 10'd0))
                $fatal(1, "frame_start alignment mismatch");
            if (m_frame_done !== (m_sample_index == 10'd1023))
                $fatal(1, "frame_end alignment mismatch");
            if (m_frame_id !== 32'(output_count / `FPGA_VECTOR_FRAME_LENGTH))
                $fatal(1, "frame_id sequence mismatch");
            $fwrite(output_file, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                    m_frame_id, m_sample_index, m_buffer_id,
                    $signed(m_iq_i_data), $signed(m_iq_q_data), $signed(m_power_data),
                    $signed(m_lag_re_data), $signed(m_lag_im_data),
                    m_iq_i_addr, m_iq_q_addr, m_power_addr, m_lag_re_addr, m_lag_im_addr);
            output_count <= output_count + 1;
            if (output_count + 1 == TOTAL) begin
                $fclose(output_file);
                $display("PASS tb_mandatory_core samples=%0d", TOTAL);
                $finish;
            end
        end
    end

    initial begin
        $readmemh("vectors/iq_input.hex", input_mem);
        output_file = $fopen("tb/results/rtl_core.csv", "w");
        $fwrite(output_file, "frame_id,sample_index,buffer_id,iq_i_int8,iq_q_int8,power_int8,lag_re_int8,lag_im_int8,iq_i_addr,iq_q_addr,power_addr,lag_re_addr,lag_im_addr\n");
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        #5000000 $fatal(1, "timeout");
    end
endmodule
