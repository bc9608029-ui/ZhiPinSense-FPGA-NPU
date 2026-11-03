`timescale 1ns/1ps
`default_nettype none

// Minimal Lite-board validation system:
// 200 MHz differential PL clock -> fixed IQ replay -> frozen Mandatory Core.
// This top intentionally contains no SDR, PS/Linux, DDR, DMA, or NPU logic.
module board_mandatory_core_test_top #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_COUNT = 19,
    parameter integer TOTAL_SAMPLES = FRAME_LENGTH * FRAME_COUNT,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer FIFO_DEPTH = 16,
    parameter integer INDEX_WIDTH = $clog2(FRAME_LENGTH),
    parameter integer ROM_ADDR_WIDTH = $clog2(TOTAL_SAMPLES),
    parameter ROM_INIT_FILE = "vectors/iq_input.hex"
) (
    input  wire       sys_clk_p,
    input  wire       sys_clk_n,
    input  wire       pl_key1_reset,
    output wire [3:0] led
);
    wire clk_200m_ibuf;
    wire core_clk;
    wire mmcm_locked;

    // Matches the successfully implemented LED baseline clock input.  The
    // baseline implementation contains the same IBUFDS -> global BUFG path.
    IBUFDS #(
        .DIFF_TERM    ("FALSE"),
        .IBUF_LOW_PWR ("TRUE"),
        .IOSTANDARD   ("DIFF_SSTL15")
    ) u_sys_clk_ibufds (
        .I  (sys_clk_p),
        .IB (sys_clk_n),
        .O  (clk_200m_ibuf)
    );

    // Clocking Wizard 6.0 is configured for a 200 MHz single-ended input
    // (after IBUFDS), an MMCM primitive, and a BUFG-driven 50 MHz output.
    clk_wiz_0 u_core_clk_wiz (
        .clk_out1 (core_clk),
        // Keep the 50 MHz clock running while PL_KEY1 resets the test logic.
        // The ILA and Debug Hub share core_clk and must remain clocked while
        // the reset request is asserted so that an armed capture survives the
        // press/release sequence.
        .reset    (1'b0),
        .locked   (mmcm_locked),
        .clk_in1  (clk_200m_ibuf)
    );

    // PL_KEY1 is active high.  Assertion is asynchronous; deassertion reaches
    // core_rst_n only after MMCM lock and three rising edges in the actual
    // 50 MHz core clock domain.
    (* ASYNC_REG = "TRUE" *) reg [2:0] reset_release_pipe;
    wire core_rst_n = reset_release_pipe[2];
    wire core_reset_async = pl_key1_reset | ~mmcm_locked;

    always @(posedge core_clk or posedge core_reset_async) begin
        if (core_reset_async)
            reset_release_pipe <= 3'b000;
        else
            reset_release_pipe <= {reset_release_pipe[1:0], 1'b1};
    end

    (* mark_debug = "true" *) wire [ROM_ADDR_WIDTH-1:0] rom_address;
    wire [31:0] rom_data;
    wire signed [15:0] replay_i;
    wire signed [15:0] replay_q;
    (* mark_debug = "true" *) wire replay_valid;
    (* mark_debug = "true" *) wire replay_ready;
    wire replay_running;
    wire replay_done;
    wire [$clog2(TOTAL_SAMPLES+1)-1:0] replay_accepted_count;

    fixed_iq_rom #(
        .DEPTH(TOTAL_SAMPLES),
        .ADDR_WIDTH(ROM_ADDR_WIDTH),
        .INIT_FILE(ROM_INIT_FILE)
    ) iq_rom (
        .address(rom_address),
        .data(rom_data)
    );

    iq_replay_controller #(
        .TOTAL_SAMPLES(TOTAL_SAMPLES),
        .ADDR_WIDTH(ROM_ADDR_WIDTH)
    ) replay (
        .clk(core_clk),
        .rst_n(core_rst_n),
        .rom_address(rom_address),
        .rom_data(rom_data),
        .s_i(replay_i),
        .s_q(replay_q),
        .s_valid(replay_valid),
        .s_ready(replay_ready),
        .running(replay_running),
        .done(replay_done),
        .accepted_count(replay_accepted_count)
    );

    (* mark_debug = "true" *) wire m_write_valid;
    (* mark_debug = "true" *) wire m_write_ready = 1'b1;
    (* mark_debug = "true" *) wire m_buffer_id;
    (* mark_debug = "true" *) wire [FRAME_ID_WIDTH-1:0] m_frame_id;
    (* mark_debug = "true" *) wire [INDEX_WIDTH-1:0] m_sample_index;
    (* mark_debug = "true" *) wire [INDEX_WIDTH:0] m_iq_i_addr;
    (* mark_debug = "true" *) wire [INDEX_WIDTH:0] m_iq_q_addr;
    (* mark_debug = "true" *) wire [INDEX_WIDTH+1:0] m_power_addr;
    (* mark_debug = "true" *) wire [INDEX_WIDTH+1:0] m_lag_re_addr;
    (* mark_debug = "true" *) wire [INDEX_WIDTH+1:0] m_lag_im_addr;
    (* mark_debug = "true" *) wire signed [7:0] m_iq_i_data;
    (* mark_debug = "true" *) wire signed [7:0] m_iq_q_data;
    (* mark_debug = "true" *) wire signed [7:0] m_power_data;
    (* mark_debug = "true" *) wire signed [7:0] m_lag_re_data;
    (* mark_debug = "true" *) wire signed [7:0] m_lag_im_data;
    (* mark_debug = "true" *) wire m_frame_valid;
    (* mark_debug = "true" *) wire m_frame_start;
    (* mark_debug = "true" *) wire m_frame_done;
    (* mark_debug = "true" *) wire m_frame_error;
    (* mark_debug = "true" *) wire m_irq;
    (* mark_debug = "true" *) wire [1:0] buffer_busy;
    wire [31:0] overflow_count;
    wire [31:0] saturation_count_i;
    wire [31:0] saturation_count_q;
    wire [31:0] saturation_count_power;
    wire [31:0] saturation_count_lag_re;
    wire [31:0] saturation_count_lag_im;
    wire output_transfer = m_write_valid && m_write_ready;

    // The test capture consumes every accepted tensor bundle immediately.
    // Release is intentionally delayed to the following cycle: on the final
    // transfer tensor_packer first marks the completed buffer busy, and only a
    // later release may return its ownership to the producer.
    (* mark_debug = "true" *) reg [1:0] buffer_release_reg;
    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            buffer_release_reg <= 2'b00;
        end else begin
            buffer_release_reg <= 2'b00;
            if (output_transfer && m_frame_done)
                buffer_release_reg[m_buffer_id] <= 1'b1;
        end
    end

    mandatory_core_path #(
        .FRAME_LENGTH(FRAME_LENGTH),
        .FRAME_ID_WIDTH(FRAME_ID_WIDTH),
        .FIFO_DEPTH(FIFO_DEPTH),
        .INDEX_WIDTH(INDEX_WIDTH)
    ) core (
        .clk(core_clk),
        .rst_n(core_rst_n),
        .s_i(replay_i),
        .s_q(replay_q),
        .s_error(1'b0),
        .s_valid(replay_valid),
        .s_ready(replay_ready),
        .s_overflow_event(1'b0),
        .cfg_iq_multiplier(32'd127),
        .cfg_iq_shift(8'd15),
        .cfg_power_multiplier(32'd127),
        .cfg_power_shift(8'd31),
        .cfg_lag_multiplier(32'd127),
        .cfg_lag_shift(8'd31),
        .clear_counters(1'b0),
        .buffer_release(buffer_release_reg),
        .m_write_valid(m_write_valid),
        .m_write_ready(m_write_ready),
        .m_buffer_id(m_buffer_id),
        .m_frame_id(m_frame_id),
        .m_sample_index(m_sample_index),
        .m_iq_i_addr(m_iq_i_addr),
        .m_iq_q_addr(m_iq_q_addr),
        .m_power_addr(m_power_addr),
        .m_lag_re_addr(m_lag_re_addr),
        .m_lag_im_addr(m_lag_im_addr),
        .m_iq_i_data(m_iq_i_data),
        .m_iq_q_data(m_iq_q_data),
        .m_power_data(m_power_data),
        .m_lag_re_data(m_lag_re_data),
        .m_lag_im_data(m_lag_im_data),
        .m_frame_valid(m_frame_valid),
        .m_frame_start(m_frame_start),
        .m_frame_done(m_frame_done),
        .m_frame_error(m_frame_error),
        .m_irq(m_irq),
        .buffer_busy(buffer_busy),
        .overflow_count(overflow_count),
        .saturation_count_i(saturation_count_i),
        .saturation_count_q(saturation_count_q),
        .saturation_count_power(saturation_count_power),
        .saturation_count_lag_re(saturation_count_lag_re),
        .saturation_count_lag_im(saturation_count_lag_im)
    );

    reg [5:0] completed_frame_count;
    reg sticky_error;
    wire all_frames_done = (completed_frame_count == FRAME_COUNT);

    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            completed_frame_count <= 6'd0;
            sticky_error <= 1'b0;
        end else begin
            if (m_irq && completed_frame_count < FRAME_COUNT)
                completed_frame_count <= completed_frame_count + 1'b1;
            if ((output_transfer && m_frame_error) || (overflow_count != 0))
                sticky_error <= 1'b1;
        end
    end

    // Active-high Lite-board LEDs: reset released, replay active, at least one
    // frame complete, and terminal success/error attention.
    assign led[0] = core_rst_n;
    assign led[1] = replay_running;
    assign led[2] = (completed_frame_count != 0);
    assign led[3] = all_frames_done || sticky_error;

    // Minimal future ILA observation set.  The simulation testbench also uses
    // these internal nets without adding unconnected physical top-level pins.
    (* mark_debug = "true" *) wire dbg_replay_transfer = replay_valid && replay_ready;
    (* mark_debug = "true" *) wire dbg_tensor_transfer = output_transfer;
    (* mark_debug = "true" *) wire dbg_all_frames_done = all_frames_done;
    (* mark_debug = "true" *) wire dbg_sticky_error = sticky_error;
endmodule

`default_nettype wire
