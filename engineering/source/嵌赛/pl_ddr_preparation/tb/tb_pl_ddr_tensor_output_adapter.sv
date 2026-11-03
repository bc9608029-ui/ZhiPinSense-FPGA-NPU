`timescale 1ns/1ps
`default_nettype none

module tb_pl_ddr_tensor_output_adapter;
    localparam integer FRAME_LENGTH = 1024;
    localparam integer FRAME_COUNT = 19;
    localparam integer FRAME_BYTES = 5 * FRAME_LENGTH;
    localparam integer TOTAL_SAMPLES = FRAME_COUNT * FRAME_LENGTH;
    localparam integer TOTAL_BEATS = FRAME_COUNT * (FRAME_LENGTH/64) * 5;
    localparam [31:0] OUTPUT_BASE = 32'h8200_0000; // simulation-only address

    reg core_clk = 1'b0;
    reg ddr_clk = 1'b0;
    always #10 core_clk = ~core_clk;
    always #2.5 ddr_clk = ~ddr_clk;

    reg core_rst_n = 1'b0;
    reg ddr_rst_n = 1'b0;
    reg core_start = 1'b0;
    reg ddr_start = 1'b0;

    reg core_write_valid = 1'b0;
    wire core_write_ready;
    reg core_buffer_id = 1'b0;
    reg [31:0] core_frame_id = 0;
    reg [9:0] core_sample_index = 0;
    reg [10:0] core_iq_i_addr = 0;
    reg [10:0] core_iq_q_addr = 0;
    reg [11:0] core_power_addr = 0;
    reg [11:0] core_lag_re_addr = 0;
    reg [11:0] core_lag_im_addr = 0;
    reg signed [7:0] core_iq_i_data = 0;
    reg signed [7:0] core_iq_q_data = 0;
    reg signed [7:0] core_power_data = 0;
    reg signed [7:0] core_lag_re_data = 0;
    reg signed [7:0] core_lag_im_data = 0;
    reg core_frame_start = 0;
    reg core_frame_done = 0;
    reg core_frame_error = 0;

    wire [1:0] core_buffer_release;
    wire core_active, core_all_frames_enqueued, core_protocol_error;
    wire [31:0] core_accepted_samples, core_enqueued_beats;
    wire ddr_busy, ddr_done, ddr_error;
    wire [31:0] ddr_accepted_beats;
    wire [31:0] awwaddr;
    wire [511:0] awwdata;
    wire [71:0] awwinfo;
    wire awwvalid;
    reg awwready = 1'b0;

    integer captured_beats = 0;
    integer release_count = 0;
    integer ddr_cycles = 0;
    integer relative_addr;
    integer decoded_frame;
    integer decoded_within_frame;
    integer decoded_plane;
    integer decoded_block;
    integer decoded_sample;
    integer lane;
    reg [7:0] expected_byte;

    function [7:0] tensor_value;
        input integer frame_number;
        input integer sample_number;
        input integer plane_number;
        begin
            tensor_value = (frame_number * 17 + sample_number * 3 + plane_number * 29) & 8'hff;
        end
    endfunction

    pl_ddr_tensor_output_adapter #(
        .FRAME_LENGTH(FRAME_LENGTH), .FRAME_COUNT(FRAME_COUNT),
        .FIFO_ADDR_WIDTH(4)
    ) dut (
        .core_clk(core_clk), .core_rst_n(core_rst_n), .core_start(core_start),
        .output_base_addr(OUTPUT_BASE), .core_write_valid(core_write_valid),
        .core_write_ready(core_write_ready), .core_buffer_id(core_buffer_id),
        .core_frame_id(core_frame_id), .core_sample_index(core_sample_index),
        .core_iq_i_addr(core_iq_i_addr), .core_iq_q_addr(core_iq_q_addr),
        .core_power_addr(core_power_addr), .core_lag_re_addr(core_lag_re_addr),
        .core_lag_im_addr(core_lag_im_addr), .core_iq_i_data(core_iq_i_data),
        .core_iq_q_data(core_iq_q_data), .core_power_data(core_power_data),
        .core_lag_re_data(core_lag_re_data), .core_lag_im_data(core_lag_im_data),
        .core_frame_start(core_frame_start), .core_frame_done(core_frame_done),
        .core_frame_error(core_frame_error), .core_buffer_release(core_buffer_release),
        .core_active(core_active), .core_all_frames_enqueued(core_all_frames_enqueued),
        .core_protocol_error(core_protocol_error),
        .core_accepted_samples(core_accepted_samples),
        .core_enqueued_beats(core_enqueued_beats),
        .ddr_clk(ddr_clk), .ddr_rst_n(ddr_rst_n), .ddr_start(ddr_start),
        .ddr_busy(ddr_busy), .ddr_done(ddr_done), .ddr_error(ddr_error),
        .ddr_accepted_beats(ddr_accepted_beats), .User_Ddr_awwaddr(awwaddr),
        .User_Ddr_awwdata(awwdata), .User_Ddr_awwinfo(awwinfo),
        .User_Ddr_awwvalid(awwvalid), .User_Ddr_awwready(awwready)
    );

    always @(posedge core_clk) begin
        if (!core_rst_n)
            release_count <= 0;
        else if (core_buffer_release != 0)
            release_count <= release_count + 1;
    end

    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            awwready <= 1'b0;
            ddr_cycles <= 0;
            captured_beats <= 0;
        end else begin
            ddr_cycles <= ddr_cycles + 1;
            awwready <= ((ddr_cycles % 9) != 3) && ((ddr_cycles % 13) != 8);
            if (awwvalid && awwready) begin
                if (awwinfo !== {1'b0, {64{1'b1}}, 6'b0, 1'b1})
                    $fatal(1, "Incorrect User_Ddr_awwinfo: %h", awwinfo);
                if (awwaddr[5:0] != 0 || awwaddr < OUTPUT_BASE ||
                    awwaddr >= OUTPUT_BASE + FRAME_COUNT*FRAME_BYTES)
                    $fatal(1, "Invalid output address %h", awwaddr);

                relative_addr = awwaddr - OUTPUT_BASE;
                decoded_frame = relative_addr / FRAME_BYTES;
                decoded_within_frame = relative_addr % FRAME_BYTES;
                decoded_plane = decoded_within_frame / FRAME_LENGTH;
                decoded_block = (decoded_within_frame % FRAME_LENGTH) / 64;
                for (lane = 0; lane < 64; lane = lane + 1) begin
                    decoded_sample = decoded_block * 64 + lane;
                    expected_byte = tensor_value(decoded_frame, decoded_sample, decoded_plane);
                    if (awwdata[(lane*8) +: 8] !== expected_byte)
                        $fatal(1, "Tensor mismatch frame=%0d plane=%0d sample=%0d got=%h expected=%h",
                            decoded_frame, decoded_plane, decoded_sample,
                            awwdata[(lane*8) +: 8], expected_byte);
                end
                captured_beats <= captured_beats + 1;
            end
        end
    end

    task send_sample;
        input integer frame_number;
        input integer sample_number;
        begin
            @(negedge core_clk);
            core_buffer_id = frame_number & 1;
            core_frame_id = frame_number;
            core_sample_index = sample_number;
            core_iq_i_addr = sample_number;
            core_iq_q_addr = FRAME_LENGTH + sample_number;
            core_power_addr = sample_number;
            core_lag_re_addr = FRAME_LENGTH + sample_number;
            core_lag_im_addr = 2*FRAME_LENGTH + sample_number;
            core_iq_i_data = tensor_value(frame_number, sample_number, 0);
            core_iq_q_data = tensor_value(frame_number, sample_number, 1);
            core_power_data = tensor_value(frame_number, sample_number, 2);
            core_lag_re_data = tensor_value(frame_number, sample_number, 3);
            core_lag_im_data = tensor_value(frame_number, sample_number, 4);
            core_frame_start = (sample_number == 0);
            core_frame_done = (sample_number == FRAME_LENGTH-1);
            core_frame_error = 1'b0;
            core_write_valid = 1'b1;
            @(posedge core_clk);
            while (!core_write_ready)
                @(posedge core_clk);
            @(negedge core_clk);
            core_write_valid = 1'b0;
        end
    endtask

    integer frame_number;
    integer sample_number;
    initial begin
        #75;
        core_rst_n = 1'b1;
        ddr_rst_n = 1'b1;

        @(negedge ddr_clk);
        ddr_start = 1'b1;
        @(negedge ddr_clk);
        ddr_start = 1'b0;

        @(negedge core_clk);
        core_start = 1'b1;
        @(negedge core_clk);
        core_start = 1'b0;

        for (frame_number = 0; frame_number < FRAME_COUNT; frame_number = frame_number + 1)
            for (sample_number = 0; sample_number < FRAME_LENGTH; sample_number = sample_number + 1)
                send_sample(frame_number, sample_number);

        wait (ddr_done);
        repeat (10) @(posedge ddr_clk);
        if (core_protocol_error || ddr_error ||
            core_accepted_samples != TOTAL_SAMPLES ||
            core_enqueued_beats != TOTAL_BEATS ||
            ddr_accepted_beats != TOTAL_BEATS ||
            captured_beats != TOTAL_BEATS || release_count != FRAME_COUNT)
            $fatal(1, "Output status mismatch proto=%b ddrerr=%b samples=%0d enq=%0d ddr=%0d cap=%0d rel=%0d",
                core_protocol_error, ddr_error, core_accepted_samples,
                core_enqueued_beats, ddr_accepted_beats, captured_beats, release_count);
        $display("PL_DDR_TENSOR_OUTPUT_ADAPTER_PASS samples=%0d beats=%0d releases=%0d",
            core_accepted_samples, captured_beats, release_count);
        $finish;
    end

    initial begin
        #10000000;
        $fatal(1, "Output adapter simulation timeout samples=%0d beats=%0d",
            core_accepted_samples, captured_beats);
    end
endmodule

`default_nettype wire
