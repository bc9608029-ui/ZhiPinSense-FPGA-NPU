`timescale 1ns/1ps
`default_nettype none

// Full functional chain used before Vivado integration:
// PL-DDR model -> input adapter -> frozen Mandatory Core -> output adapter -> PL-DDR model.
module tb_pl_ddr_mandatory_core_e2e;
    localparam integer FRAME_LENGTH = 1024;
    localparam integer FRAME_COUNT = 19;
    localparam integer TOTAL_SAMPLES = FRAME_COUNT * FRAME_LENGTH;
    localparam integer INPUT_BEATS = TOTAL_SAMPLES / 16;
    localparam integer INPUT_BYTES = TOTAL_SAMPLES * 4;
    localparam integer FRAME_BYTES = FRAME_LENGTH * 5;
    localparam integer OUTPUT_BEATS = FRAME_COUNT * (FRAME_LENGTH/64) * 5;
    localparam integer OUTPUT_BYTES = FRAME_COUNT * FRAME_BYTES;
    localparam [31:0] INPUT_BASE = 32'h8100_0000;
    localparam [31:0] OUTPUT_BASE = 32'h8200_0000;

    reg ddr_clk = 1'b0;
    reg core_clk = 1'b0;
    always #2.5 ddr_clk = ~ddr_clk; // 200 MHz PL-DDR domain
    always #10 core_clk = ~core_clk; // 50 MHz verified Mandatory Core domain

    reg ddr_rst_n = 1'b0;
    reg core_rst_n = 1'b0;
    reg input_ddr_start = 1'b0;
    reg output_ddr_start = 1'b0;
    reg output_core_start = 1'b0;

    reg [31:0] iq_words [0:TOTAL_SAMPLES-1];
    reg [7:0] expected_bytes [0:OUTPUT_BYTES-1];
    reg [7:0] captured_bytes [0:OUTPUT_BYTES-1];

    wire input_ddr_busy, input_ddr_done, input_ddr_error;
    wire [31:0] araddr, arinfo;
    wire arvalid;
    reg arready = 1'b0;
    reg [511:0] rdata = 512'd0;
    reg rvalid = 1'b0;
    reg [31:0] rinfo = 32'd1;
    wire rready;
    wire signed [15:0] core_i, core_q;
    wire input_core_valid, input_core_ready;
    wire [31:0] input_accepted_samples;

    wire core_write_valid, core_write_ready;
    wire core_buffer_id;
    wire [31:0] core_frame_id;
    wire [9:0] core_sample_index;
    wire [10:0] core_iq_i_addr, core_iq_q_addr;
    wire [11:0] core_power_addr, core_lag_re_addr, core_lag_im_addr;
    wire signed [7:0] core_iq_i_data, core_iq_q_data;
    wire signed [7:0] core_power_data, core_lag_re_data, core_lag_im_data;
    wire core_frame_start, core_frame_done, core_frame_error;
    wire core_frame_valid, core_irq;
    wire [1:0] core_buffer_busy, core_buffer_release;
    wire [31:0] overflow_count;
    wire [31:0] saturation_count_i, saturation_count_q;
    wire [31:0] saturation_count_power, saturation_count_lag_re;
    wire [31:0] saturation_count_lag_im;

    wire output_core_active, output_all_frames_enqueued;
    wire output_core_protocol_error;
    wire [31:0] output_core_accepted_samples, output_core_enqueued_beats;
    wire output_ddr_busy, output_ddr_done, output_ddr_error;
    wire [31:0] output_ddr_accepted_beats;
    wire [31:0] awwaddr;
    wire [511:0] awwdata;
    wire [71:0] awwinfo;
    wire awwvalid;
    reg awwready = 1'b0;

    integer pending_beat = 0;
    integer response_delay = 0;
    reg read_pending = 1'b0;
    reg [15:0] read_prng = 16'h1ace;
    integer ddr_cycles = 0;
    integer captured_beats = 0;
    integer release_count = 0;
    integer relative_addr;
    integer lane;
    integer byte_index;
    integer output_file;
    integer dump_index;
    reg [511:0] response_value;

    pl_ddr_iq_input_adapter #(.FIFO_ADDR_WIDTH(4)) input_adapter (
        .ddr_clk(ddr_clk), .ddr_rst_n(ddr_rst_n), .ddr_start(input_ddr_start),
        .iq_base_addr(INPUT_BASE), .iq_byte_count(INPUT_BYTES),
        .ddr_busy(input_ddr_busy), .ddr_done(input_ddr_done),
        .ddr_error(input_ddr_error), .User_Ddr_araddr(araddr),
        .User_Ddr_arvalid(arvalid), .User_Ddr_arinfo(arinfo),
        .User_Ddr_arready(arready), .User_Ddr_rdata(rdata),
        .User_Ddr_rvalid(rvalid), .User_Ddr_rinfo(rinfo),
        .User_Ddr_rready(rready), .core_clk(core_clk),
        .core_rst_n(core_rst_n), .core_i(core_i), .core_q(core_q),
        .core_valid(input_core_valid), .core_ready(input_core_ready),
        .core_accepted_samples(input_accepted_samples)
    );

    mandatory_core_path #(.FRAME_LENGTH(FRAME_LENGTH), .FRAME_ID_WIDTH(32)) frozen_core (
        .clk(core_clk), .rst_n(core_rst_n), .s_i(core_i), .s_q(core_q),
        .s_error(1'b0), .s_valid(input_core_valid), .s_ready(input_core_ready),
        .s_overflow_event(1'b0), .cfg_iq_multiplier(32'd127),
        .cfg_iq_shift(8'd15), .cfg_power_multiplier(32'd127),
        .cfg_power_shift(8'd31), .cfg_lag_multiplier(32'd127),
        .cfg_lag_shift(8'd31), .clear_counters(1'b0),
        .buffer_release(core_buffer_release), .m_write_valid(core_write_valid),
        .m_write_ready(core_write_ready), .m_buffer_id(core_buffer_id),
        .m_frame_id(core_frame_id), .m_sample_index(core_sample_index),
        .m_iq_i_addr(core_iq_i_addr), .m_iq_q_addr(core_iq_q_addr),
        .m_power_addr(core_power_addr), .m_lag_re_addr(core_lag_re_addr),
        .m_lag_im_addr(core_lag_im_addr), .m_iq_i_data(core_iq_i_data),
        .m_iq_q_data(core_iq_q_data), .m_power_data(core_power_data),
        .m_lag_re_data(core_lag_re_data), .m_lag_im_data(core_lag_im_data),
        .m_frame_valid(core_frame_valid), .m_frame_start(core_frame_start),
        .m_frame_done(core_frame_done), .m_frame_error(core_frame_error),
        .m_irq(core_irq), .buffer_busy(core_buffer_busy),
        .overflow_count(overflow_count), .saturation_count_i(saturation_count_i),
        .saturation_count_q(saturation_count_q),
        .saturation_count_power(saturation_count_power),
        .saturation_count_lag_re(saturation_count_lag_re),
        .saturation_count_lag_im(saturation_count_lag_im)
    );

    pl_ddr_tensor_output_adapter #(
        .FRAME_LENGTH(FRAME_LENGTH), .FRAME_COUNT(FRAME_COUNT),
        .FIFO_ADDR_WIDTH(4)
    ) output_adapter (
        .core_clk(core_clk), .core_rst_n(core_rst_n),
        .core_start(output_core_start), .output_base_addr(OUTPUT_BASE),
        .core_write_valid(core_write_valid), .core_write_ready(core_write_ready),
        .core_buffer_id(core_buffer_id), .core_frame_id(core_frame_id),
        .core_sample_index(core_sample_index), .core_iq_i_addr(core_iq_i_addr),
        .core_iq_q_addr(core_iq_q_addr), .core_power_addr(core_power_addr),
        .core_lag_re_addr(core_lag_re_addr), .core_lag_im_addr(core_lag_im_addr),
        .core_iq_i_data(core_iq_i_data), .core_iq_q_data(core_iq_q_data),
        .core_power_data(core_power_data), .core_lag_re_data(core_lag_re_data),
        .core_lag_im_data(core_lag_im_data), .core_frame_start(core_frame_start),
        .core_frame_done(core_frame_done), .core_frame_error(core_frame_error),
        .core_buffer_release(core_buffer_release), .core_active(output_core_active),
        .core_all_frames_enqueued(output_all_frames_enqueued),
        .core_protocol_error(output_core_protocol_error),
        .core_accepted_samples(output_core_accepted_samples),
        .core_enqueued_beats(output_core_enqueued_beats),
        .ddr_clk(ddr_clk), .ddr_rst_n(ddr_rst_n),
        .ddr_start(output_ddr_start), .ddr_busy(output_ddr_busy),
        .ddr_done(output_ddr_done), .ddr_error(output_ddr_error),
        .ddr_accepted_beats(output_ddr_accepted_beats),
        .User_Ddr_awwaddr(awwaddr), .User_Ddr_awwdata(awwdata),
        .User_Ddr_awwinfo(awwinfo), .User_Ddr_awwvalid(awwvalid),
        .User_Ddr_awwready(awwready)
    );

    // Conservative single-outstanding-beat read response model.
    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            arready <= 1'b0;
            rvalid <= 1'b0;
            read_pending <= 1'b0;
            response_delay <= 0;
            read_prng <= 16'h1ace;
        end else begin
            read_prng <= {read_prng[14:0], read_prng[15] ^ read_prng[13] ^ read_prng[12] ^ read_prng[10]};
            arready <= !read_pending && !rvalid && read_prng[0];
            if (arvalid && arready) begin
                if (arinfo !== 32'd1 || araddr[5:0] != 0 || araddr < INPUT_BASE ||
                    ((araddr - INPUT_BASE) >> 6) >= INPUT_BEATS)
                    $fatal(1, "Invalid DDR read request addr=%h info=%h", araddr, arinfo);
                pending_beat <= (araddr - INPUT_BASE) >> 6;
                response_delay <= read_prng[2:1];
                read_pending <= 1'b1;
            end
            if (read_pending && !rvalid) begin
                if (response_delay == 0) begin
                    response_value = 512'd0;
                    for (lane = 0; lane < 16; lane = lane + 1)
                        response_value[lane*32 +: 32] = iq_words[pending_beat*16 + lane];
                    rdata <= response_value;
                    rinfo <= 32'd1;
                    rvalid <= 1'b1;
                    read_pending <= 1'b0;
                end else begin
                    response_delay <= response_delay - 1;
                end
            end
            if (rvalid && rready)
                rvalid <= 1'b0;
        end
    end

    // Full-beat write sink with deterministic backpressure and byte-accurate
    // comparison against the pre-existing Golden-derived DDR payload.
    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            awwready <= 1'b0;
            ddr_cycles <= 0;
            captured_beats <= 0;
        end else begin
            ddr_cycles <= ddr_cycles + 1;
            awwready <= ((ddr_cycles % 9) != 3) && ((ddr_cycles % 13) != 8);
            if (awwvalid && awwready) begin
                if (awwinfo !== {1'b0, {64{1'b1}}, 6'b0, 1'b1} ||
                    awwaddr[5:0] != 0 || awwaddr < OUTPUT_BASE ||
                    awwaddr >= OUTPUT_BASE + OUTPUT_BYTES)
                    $fatal(1, "Invalid DDR write request addr=%h info=%h", awwaddr, awwinfo);
                relative_addr = awwaddr - OUTPUT_BASE;
                for (lane = 0; lane < 64; lane = lane + 1) begin
                    byte_index = relative_addr + lane;
                    captured_bytes[byte_index] = awwdata[lane*8 +: 8];
                    if (awwdata[lane*8 +: 8] !== expected_bytes[byte_index])
                        $fatal(1, "Golden mismatch byte=%0d got=%h expected=%h",
                            byte_index, awwdata[lane*8 +: 8], expected_bytes[byte_index]);
                end
                captured_beats <= captured_beats + 1;
            end
        end
    end

    always @(posedge core_clk) begin
        if (!core_rst_n)
            release_count <= 0;
        else if (core_buffer_release != 0)
            release_count <= release_count + 1;
    end

    initial begin
        $readmemh("../rf_cognitive_system/hardware/fpga/vectors/iq_input.hex", iq_words);
        $readmemh("generated/expected_tensor_plddr.hex", expected_bytes);
        #75;
        ddr_rst_n = 1'b1;
        core_rst_n = 1'b1;

        @(negedge core_clk);
        output_core_start = 1'b1;
        @(negedge core_clk);
        output_core_start = 1'b0;

        @(negedge ddr_clk);
        input_ddr_start = 1'b1;
        output_ddr_start = 1'b1;
        @(negedge ddr_clk);
        input_ddr_start = 1'b0;
        output_ddr_start = 1'b0;

        wait (output_ddr_done);
        repeat (10) @(posedge ddr_clk);
        if (input_ddr_error || output_ddr_error || output_core_protocol_error ||
            input_accepted_samples != TOTAL_SAMPLES ||
            output_core_accepted_samples != TOTAL_SAMPLES ||
            output_core_enqueued_beats != OUTPUT_BEATS ||
            output_ddr_accepted_beats != OUTPUT_BEATS ||
            captured_beats != OUTPUT_BEATS || release_count != FRAME_COUNT ||
            overflow_count != 0)
            $fatal(1, "E2E status mismatch inerr=%b outerr=%b proto=%b in=%0d out=%0d enq=%0d ddr=%0d cap=%0d rel=%0d ovf=%0d",
                input_ddr_error, output_ddr_error, output_core_protocol_error,
                input_accepted_samples, output_core_accepted_samples,
                output_core_enqueued_beats, output_ddr_accepted_beats,
                captured_beats, release_count, overflow_count);

        output_file = $fopen("generated/e2e_tensor_plddr.hex", "w");
        if (output_file == 0)
            $fatal(1, "Cannot open E2E output hex");
        for (dump_index = 0; dump_index < OUTPUT_BYTES; dump_index = dump_index + 1)
            $fdisplay(output_file, "%02x", captured_bytes[dump_index]);
        $fclose(output_file);
        $display("PL_DDR_MANDATORY_CORE_E2E_PASS samples=%0d frames=%0d beats=%0d golden_byte_mismatches=0",
            output_core_accepted_samples, FRAME_COUNT, captured_beats);
        $finish;
    end

    initial begin
        #20000000;
        $fatal(1, "E2E simulation timeout in=%0d out=%0d beats=%0d",
            input_accepted_samples, output_core_accepted_samples, captured_beats);
    end
endmodule

`default_nettype wire
