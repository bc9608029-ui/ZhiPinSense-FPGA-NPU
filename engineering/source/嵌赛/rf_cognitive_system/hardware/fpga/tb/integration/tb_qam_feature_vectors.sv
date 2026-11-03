`timescale 1ns/1ps
`include "vector_params.svh"

module tb_qam_feature_vectors;
    localparam integer TOTAL = `FPGA_VECTOR_TOTAL_SAMPLES;
    reg [31:0] input_mem [0:TOTAL-1];
    reg clk = 0;
    reg rst_n = 0;
    reg signed [15:0] s_i = 0, s_q = 0;
    reg s_valid = 0;
    wire s_ready;
    reg [9:0] s_sample_index = 0;
    reg [31:0] s_frame_id = 0;
    reg s_frame_start = 0, s_frame_end = 0;
    wire signed [15:0] m_i, m_q;
    wire [31:0] m_power;
    wire signed [32:0] m_lag_re, m_lag_im;
    wire m_valid;
    reg m_ready = 1;
    wire [9:0] m_sample_index;
    wire [31:0] m_frame_id;
    wire m_frame_start, m_frame_end, m_error;
    integer input_index = 0;
    integer output_count = 0;
    integer output_file;

    always #5 clk = ~clk;

    qam_feature_pipeline dut (
        .clk(clk), .rst_n(rst_n), .s_i(s_i), .s_q(s_q), .s_valid(s_valid), .s_ready(s_ready),
        .s_sample_index(s_sample_index), .s_frame_id(s_frame_id), .s_frame_start(s_frame_start),
        .s_frame_end(s_frame_end), .s_error(1'b0), .m_i(m_i), .m_q(m_q), .m_power(m_power),
        .m_lag_re(m_lag_re), .m_lag_im(m_lag_im), .m_valid(m_valid), .m_ready(m_ready),
        .m_sample_index(m_sample_index), .m_frame_id(m_frame_id), .m_frame_start(m_frame_start),
        .m_frame_end(m_frame_end), .m_error(m_error)
    );

    always @(negedge clk) begin
        if (rst_n && input_index < TOTAL && s_ready) begin
            s_i <= input_mem[input_index][15:0];
            s_q <= input_mem[input_index][31:16];
            s_sample_index <= 10'(input_index % `FPGA_VECTOR_FRAME_LENGTH);
            s_frame_id <= 32'(input_index / `FPGA_VECTOR_FRAME_LENGTH);
            s_frame_start <= ((input_index % `FPGA_VECTOR_FRAME_LENGTH) == 0);
            s_frame_end <= ((input_index % `FPGA_VECTOR_FRAME_LENGTH) == `FPGA_VECTOR_FRAME_LENGTH-1);
            s_valid <= 1'b1;
            input_index <= input_index + 1;
        end else if (input_index >= TOTAL) begin
            s_valid <= 1'b0;
        end
    end

    always @(posedge clk) begin
        if (rst_n && m_valid && m_ready) begin
            $fwrite(output_file, "%0d,%0d,%0d,%0d,%0d\n", m_frame_id, m_sample_index,
                    $unsigned(m_power), $signed(m_lag_re), $signed(m_lag_im));
            output_count <= output_count + 1;
            if (output_count + 1 == TOTAL) begin
                $fclose(output_file);
                $display("PASS tb_qam_feature_vectors samples=%0d", TOTAL);
                $finish;
            end
        end
    end

    initial begin
        $readmemh("vectors/iq_input.hex", input_mem);
        output_file = $fopen("tb/results/rtl_features.csv", "w");
        $fwrite(output_file, "frame_id,sample_index,power,lag_re,lag_im\n");
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        #5000000 $fatal(1, "timeout");
    end
endmodule
