`timescale 1ns/1ps

// Conservative Lite-board wrapper for the verified Mandatory Core Path.
//
// This module deliberately contains no Procise/vendor IP and no physical pin
// constraints.  All IQ ingress and tensor egress signals are synchronous to
// pl_clk.  A future board adapter must provide CDC, DDR/DMA and PS/PL bridges.
// PL_KEY1 is documented as active high in the Lite manual; hold it high during
// reset and release it to obtain a two-clock synchronous reset release.
module top_lite #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer FIFO_DEPTH = 16,
    parameter integer INDEX_WIDTH = $clog2(FRAME_LENGTH)
) (
    input  wire                          pl_clk,
    input  wire                          pl_key1_reset,

    // Abstract, memory-fed or stream-fed signed-int16 IQ ingress.
    input  wire signed [15:0]            s_i,
    input  wire signed [15:0]            s_q,
    input  wire                          s_error,
    input  wire                          s_valid,
    output wire                          s_ready,
    input  wire                          s_overflow_event,

    // Runtime quantizer controls.  Reference values are documented, not tied.
    input  wire [31:0]                   cfg_iq_multiplier,
    input  wire [7:0]                    cfg_iq_shift,
    input  wire [31:0]                   cfg_power_multiplier,
    input  wire [7:0]                    cfg_power_shift,
    input  wire [31:0]                   cfg_lag_multiplier,
    input  wire [7:0]                    cfg_lag_shift,
    input  wire                          clear_counters,

    // Abstract ping-pong buffer ownership and tensor-write boundary.
    input  wire [1:0]                    buffer_release,
    output wire                          m_write_valid,
    input  wire                          m_write_ready,
    output wire                          m_buffer_id,
    output wire [FRAME_ID_WIDTH-1:0]     m_frame_id,
    output wire [INDEX_WIDTH-1:0]        m_sample_index,
    output wire [INDEX_WIDTH:0]          m_iq_i_addr,
    output wire [INDEX_WIDTH:0]          m_iq_q_addr,
    output wire [INDEX_WIDTH+1:0]        m_power_addr,
    output wire [INDEX_WIDTH+1:0]        m_lag_re_addr,
    output wire [INDEX_WIDTH+1:0]        m_lag_im_addr,
    output wire signed [7:0]             m_iq_i_data,
    output wire signed [7:0]             m_iq_q_data,
    output wire signed [7:0]             m_power_data,
    output wire signed [7:0]             m_lag_re_data,
    output wire signed [7:0]             m_lag_im_data,
    output wire                          m_frame_valid,
    output wire                          m_frame_start,
    output wire                          m_frame_done,
    output wire                          m_frame_error,
    output wire                          m_irq,
    output wire [1:0]                    buffer_busy,
    output wire [31:0]                   overflow_count,
    output wire [31:0]                   saturation_count_i,
    output wire [31:0]                   saturation_count_q,
    output wire [31:0]                   saturation_count_power,
    output wire [31:0]                   saturation_count_lag_re,
    output wire [31:0]                   saturation_count_lag_im,

    // Active-high PL LEDs: reset released, input activity, completed frame,
    // and sticky error/counter status.  Pin mapping belongs in Procise.
    output wire [3:0]                    pl_led
);
    reg [1:0] reset_release;
    wire core_rst_n = reset_release[1];

    reg input_activity_toggle;
    reg frame_complete_toggle;
    reg sticky_error;

    wire input_transfer = s_valid && s_ready;
    wire output_transfer = m_write_valid && m_write_ready;
    wire any_saturation = (saturation_count_i != 0)
                        || (saturation_count_q != 0)
                        || (saturation_count_power != 0)
                        || (saturation_count_lag_re != 0)
                        || (saturation_count_lag_im != 0);

    // Asynchronous assertion from the active-high key, synchronous release.
    always @(posedge pl_clk or posedge pl_key1_reset) begin
        if (pl_key1_reset)
            reset_release <= 2'b00;
        else
            reset_release <= {reset_release[0], 1'b1};
    end

    always @(posedge pl_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            input_activity_toggle <= 1'b0;
            frame_complete_toggle <= 1'b0;
            sticky_error <= 1'b0;
        end else begin
            if (input_transfer)
                input_activity_toggle <= ~input_activity_toggle;
            if (m_irq)
                frame_complete_toggle <= ~frame_complete_toggle;
            if (s_overflow_event || (output_transfer && m_frame_error))
                sticky_error <= 1'b1;
            if (clear_counters)
                sticky_error <= 1'b0;
        end
    end

    assign pl_led[0] = core_rst_n;
    assign pl_led[1] = input_activity_toggle;
    assign pl_led[2] = frame_complete_toggle;
    assign pl_led[3] = sticky_error || (overflow_count != 0) || any_saturation;

    mandatory_core_path #(
        .FRAME_LENGTH(FRAME_LENGTH),
        .FRAME_ID_WIDTH(FRAME_ID_WIDTH),
        .FIFO_DEPTH(FIFO_DEPTH),
        .INDEX_WIDTH(INDEX_WIDTH)
    ) core (
        .clk(pl_clk),
        .rst_n(core_rst_n),
        .s_i(s_i),
        .s_q(s_q),
        .s_error(s_error),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_overflow_event(s_overflow_event),
        .cfg_iq_multiplier(cfg_iq_multiplier),
        .cfg_iq_shift(cfg_iq_shift),
        .cfg_power_multiplier(cfg_power_multiplier),
        .cfg_power_shift(cfg_power_shift),
        .cfg_lag_multiplier(cfg_lag_multiplier),
        .cfg_lag_shift(cfg_lag_shift),
        .clear_counters(clear_counters),
        .buffer_release(buffer_release),
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

    // TODO-HARDWARE: bind pl_clk/reset/LED pins using the confirmed Lite
    // schematic and Procise constraints.  Add only confirmed PS-PL, DDR/DMA,
    // FFT and NPU adapters outside this module.
endmodule
