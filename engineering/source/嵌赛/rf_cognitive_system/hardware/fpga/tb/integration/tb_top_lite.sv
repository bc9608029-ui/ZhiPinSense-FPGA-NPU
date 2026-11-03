`timescale 1ns/1ps

module tb_top_lite;
    localparam integer FRAME_LENGTH = 4;
    localparam integer INDEX_WIDTH = 2;

    reg pl_clk = 0;
    reg pl_key1_reset = 1;
    reg signed [15:0] s_i = 0;
    reg signed [15:0] s_q = 0;
    reg s_error = 0;
    reg s_valid = 0;
    wire s_ready;
    reg [1:0] buffer_release = 0;
    wire m_write_valid;
    reg m_write_ready = 1;
    wire m_buffer_id;
    wire [7:0] m_frame_id;
    wire [INDEX_WIDTH-1:0] m_sample_index;
    wire [INDEX_WIDTH:0] m_iq_i_addr, m_iq_q_addr;
    wire [INDEX_WIDTH+1:0] m_power_addr, m_lag_re_addr, m_lag_im_addr;
    wire signed [7:0] m_iq_i_data, m_iq_q_data, m_power_data, m_lag_re_data, m_lag_im_data;
    wire m_frame_valid, m_frame_start, m_frame_done, m_frame_error, m_irq;
    wire [1:0] buffer_busy;
    wire [31:0] overflow_count, sat_i, sat_q, sat_power, sat_re, sat_im;
    wire [3:0] pl_led;
    integer sent = 0;
    integer received = 0;

    always #5 pl_clk = ~pl_clk;

    top_lite #(
        .FRAME_LENGTH(FRAME_LENGTH), .FRAME_ID_WIDTH(8), .FIFO_DEPTH(4),
        .INDEX_WIDTH(INDEX_WIDTH)
    ) dut (
        .pl_clk(pl_clk), .pl_key1_reset(pl_key1_reset),
        .s_i(s_i), .s_q(s_q), .s_error(s_error), .s_valid(s_valid), .s_ready(s_ready),
        .s_overflow_event(1'b0),
        .cfg_iq_multiplier(32'd127), .cfg_iq_shift(8'd15),
        .cfg_power_multiplier(32'd127), .cfg_power_shift(8'd31),
        .cfg_lag_multiplier(32'd127), .cfg_lag_shift(8'd31),
        .clear_counters(1'b0), .buffer_release(buffer_release),
        .m_write_valid(m_write_valid), .m_write_ready(m_write_ready),
        .m_buffer_id(m_buffer_id), .m_frame_id(m_frame_id), .m_sample_index(m_sample_index),
        .m_iq_i_addr(m_iq_i_addr), .m_iq_q_addr(m_iq_q_addr),
        .m_power_addr(m_power_addr), .m_lag_re_addr(m_lag_re_addr),
        .m_lag_im_addr(m_lag_im_addr), .m_iq_i_data(m_iq_i_data),
        .m_iq_q_data(m_iq_q_data), .m_power_data(m_power_data),
        .m_lag_re_data(m_lag_re_data), .m_lag_im_data(m_lag_im_data),
        .m_frame_valid(m_frame_valid), .m_frame_start(m_frame_start),
        .m_frame_done(m_frame_done), .m_frame_error(m_frame_error), .m_irq(m_irq),
        .buffer_busy(buffer_busy), .overflow_count(overflow_count),
        .saturation_count_i(sat_i), .saturation_count_q(sat_q),
        .saturation_count_power(sat_power), .saturation_count_lag_re(sat_re),
        .saturation_count_lag_im(sat_im), .pl_led(pl_led)
    );

    always @(negedge pl_clk) begin
        if (!pl_key1_reset && pl_led[0] && sent < FRAME_LENGTH && s_ready) begin
            s_i <= 16'(sent + 1);
            s_q <= 16'(-(sent + 1));
            s_valid <= 1'b1;
            sent <= sent + 1;
        end else if (sent >= FRAME_LENGTH) begin
            s_valid <= 1'b0;
        end
    end

    always @(posedge pl_clk) begin
        buffer_release <= 2'b00;
        if (m_write_valid && m_write_ready) begin
            if (!m_frame_valid) $fatal(1, "top_lite frame_valid missing");
            if (m_frame_start !== (m_sample_index == 0)) $fatal(1, "top_lite start mismatch");
            if (m_frame_done !== (m_sample_index == INDEX_WIDTH'(FRAME_LENGTH-1)))
                $fatal(1, "top_lite done mismatch");
            received <= received + 1;
            if (m_irq) begin
                buffer_release[m_buffer_id] <= 1'b1;
                if (received + 1 != FRAME_LENGTH) $fatal(1, "top_lite early IRQ");
                $display("PASS tb_top_lite samples=%0d", received + 1);
                $finish;
            end
        end
    end

    initial begin
        repeat (3) @(posedge pl_clk);
        @(negedge pl_clk);
        pl_key1_reset = 1'b0;
        #2000 $fatal(1, "top_lite timeout");
    end
endmodule
