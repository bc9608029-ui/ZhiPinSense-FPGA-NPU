`timescale 1ns/1ps

// Board-independent mandatory path:
// FIFO -> framing -> exact Power/Lag -> configurable INT8 -> tensor write bundle.
// No vendor IP, pin, address map or board clock is embedded here.
module mandatory_core_path #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer FIFO_DEPTH = 16,
    parameter integer INDEX_WIDTH = $clog2(FRAME_LENGTH)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire signed [15:0]            s_i,
    input  wire signed [15:0]            s_q,
    input  wire                          s_error,
    input  wire                          s_valid,
    output wire                          s_ready,
    input  wire                          s_overflow_event,
    input  wire [31:0]                   cfg_iq_multiplier,
    input  wire [7:0]                    cfg_iq_shift,
    input  wire [31:0]                   cfg_power_multiplier,
    input  wire [7:0]                    cfg_power_shift,
    input  wire [31:0]                   cfg_lag_multiplier,
    input  wire [7:0]                    cfg_lag_shift,
    input  wire                          clear_counters,
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
    output wire [31:0]                   saturation_count_lag_im
);
    assign m_frame_valid = m_write_valid;
    wire signed [15:0] fifo_i, fifo_q;
    wire fifo_error, fifo_valid, fifo_ready;
    wire [$clog2(FIFO_DEPTH+1)-1:0] fifo_occupancy;

    iq_stream_fifo #(.DEPTH(FIFO_DEPTH)) input_fifo (
        .clk(clk), .rst_n(rst_n), .s_i(s_i), .s_q(s_q), .s_error(s_error),
        .s_valid(s_valid), .s_ready(s_ready), .s_overflow_event(s_overflow_event),
        .m_i(fifo_i), .m_q(fifo_q), .m_error(fifo_error), .m_valid(fifo_valid),
        .m_ready(fifo_ready), .occupancy(fifo_occupancy), .overflow_count(overflow_count)
    );

    wire signed [15:0] frame_i, frame_q;
    wire frame_error, frame_valid, frame_ready;
    wire [INDEX_WIDTH-1:0] frame_sample_index;
    wire [FRAME_ID_WIDTH-1:0] frame_id;
    wire frame_start, frame_end, frame_valid_sideband;

    iq_frame_controller #(.FRAME_LENGTH(FRAME_LENGTH), .FRAME_ID_WIDTH(FRAME_ID_WIDTH)) framer (
        .clk(clk), .rst_n(rst_n), .s_i(fifo_i), .s_q(fifo_q), .s_error(fifo_error),
        .s_valid(fifo_valid), .s_ready(fifo_ready), .m_i(frame_i), .m_q(frame_q),
        .m_error(frame_error), .m_valid(frame_valid), .m_ready(frame_ready),
        .m_sample_index(frame_sample_index), .m_frame_id(frame_id),
        .m_frame_start(frame_start), .m_frame_end(frame_end), .m_frame_valid(frame_valid_sideband)
    );

    wire signed [15:0] feature_i, feature_q;
    wire [31:0] feature_power;
    wire signed [32:0] feature_lag_re, feature_lag_im;
    wire feature_valid, feature_ready;
    wire [INDEX_WIDTH-1:0] feature_sample_index;
    wire [FRAME_ID_WIDTH-1:0] feature_frame_id;
    wire feature_frame_start, feature_frame_end, feature_error;

    qam_feature_pipeline #(.FRAME_ID_WIDTH(FRAME_ID_WIDTH), .INDEX_WIDTH(INDEX_WIDTH)) features (
        .clk(clk), .rst_n(rst_n), .s_i(frame_i), .s_q(frame_q), .s_valid(frame_valid),
        .s_ready(frame_ready), .s_sample_index(frame_sample_index), .s_frame_id(frame_id),
        .s_frame_start(frame_start), .s_frame_end(frame_end), .s_error(frame_error),
        .m_i(feature_i), .m_q(feature_q), .m_power(feature_power),
        .m_lag_re(feature_lag_re), .m_lag_im(feature_lag_im), .m_valid(feature_valid),
        .m_ready(feature_ready), .m_sample_index(feature_sample_index),
        .m_frame_id(feature_frame_id), .m_frame_start(feature_frame_start),
        .m_frame_end(feature_frame_end), .m_error(feature_error)
    );

    wire qi_s_ready, qq_s_ready, qp_s_ready, qr_s_ready, qm_s_ready;
    wire qi_valid, qq_valid, qp_valid, qr_valid, qm_valid;
    wire signed [7:0] qi_data, qq_data, qp_data, qr_data, qm_data;
    wire qi_sat, qq_sat, qp_sat, qr_sat, qm_sat;
    reg meta_valid;
    reg [INDEX_WIDTH-1:0] meta_sample_index;
    reg [FRAME_ID_WIDTH-1:0] meta_frame_id;
    reg meta_frame_start, meta_frame_end, meta_error;
    wire bundle_valid = meta_valid && qi_valid && qq_valid && qp_valid && qr_valid && qm_valid;
    wire packer_ready;
    wire bundle_consume = bundle_valid && packer_ready;
    wire meta_ready = !meta_valid || bundle_consume;
    wire all_quantizers_ready = qi_s_ready && qq_s_ready && qp_s_ready && qr_s_ready && qm_s_ready;
    wire quantizer_bundle_ready = meta_ready && all_quantizers_ready;
    wire quantizer_input_valid = feature_valid && quantizer_bundle_ready;
    assign feature_ready = quantizer_bundle_ready;

    feature_quantizer #(.INPUT_WIDTH(16), .SIGNED_INPUT(1)) quant_i (
        .clk(clk), .rst_n(rst_n), .s_data(feature_i), .s_valid(quantizer_input_valid),
        .s_ready(qi_s_ready), .cfg_multiplier(cfg_iq_multiplier), .cfg_shift(cfg_iq_shift),
        .clear_saturation_count(clear_counters), .m_data(qi_data), .m_saturated(qi_sat),
        .m_valid(qi_valid), .m_ready(bundle_consume), .saturation_count(saturation_count_i)
    );
    feature_quantizer #(.INPUT_WIDTH(16), .SIGNED_INPUT(1)) quant_q (
        .clk(clk), .rst_n(rst_n), .s_data(feature_q), .s_valid(quantizer_input_valid),
        .s_ready(qq_s_ready), .cfg_multiplier(cfg_iq_multiplier), .cfg_shift(cfg_iq_shift),
        .clear_saturation_count(clear_counters), .m_data(qq_data), .m_saturated(qq_sat),
        .m_valid(qq_valid), .m_ready(bundle_consume), .saturation_count(saturation_count_q)
    );
    feature_quantizer #(.INPUT_WIDTH(32), .SIGNED_INPUT(0)) quant_power (
        .clk(clk), .rst_n(rst_n), .s_data(feature_power), .s_valid(quantizer_input_valid),
        .s_ready(qp_s_ready), .cfg_multiplier(cfg_power_multiplier), .cfg_shift(cfg_power_shift),
        .clear_saturation_count(clear_counters), .m_data(qp_data), .m_saturated(qp_sat),
        .m_valid(qp_valid), .m_ready(bundle_consume), .saturation_count(saturation_count_power)
    );
    feature_quantizer #(.INPUT_WIDTH(33), .SIGNED_INPUT(1)) quant_lag_re (
        .clk(clk), .rst_n(rst_n), .s_data(feature_lag_re), .s_valid(quantizer_input_valid),
        .s_ready(qr_s_ready), .cfg_multiplier(cfg_lag_multiplier), .cfg_shift(cfg_lag_shift),
        .clear_saturation_count(clear_counters), .m_data(qr_data), .m_saturated(qr_sat),
        .m_valid(qr_valid), .m_ready(bundle_consume), .saturation_count(saturation_count_lag_re)
    );
    feature_quantizer #(.INPUT_WIDTH(33), .SIGNED_INPUT(1)) quant_lag_im (
        .clk(clk), .rst_n(rst_n), .s_data(feature_lag_im), .s_valid(quantizer_input_valid),
        .s_ready(qm_s_ready), .cfg_multiplier(cfg_lag_multiplier), .cfg_shift(cfg_lag_shift),
        .clear_saturation_count(clear_counters), .m_data(qm_data), .m_saturated(qm_sat),
        .m_valid(qm_valid), .m_ready(bundle_consume), .saturation_count(saturation_count_lag_im)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            meta_valid <= 1'b0;
        end else if (meta_ready) begin
            meta_valid <= quantizer_input_valid;
            if (quantizer_input_valid) begin
                meta_sample_index <= feature_sample_index;
                meta_frame_id <= feature_frame_id;
                meta_frame_start <= feature_frame_start;
                meta_frame_end <= feature_frame_end;
                meta_error <= feature_error;
            end
        end
    end

    tensor_packer #(.FRAME_LENGTH(FRAME_LENGTH), .FRAME_ID_WIDTH(FRAME_ID_WIDTH)) packer (
        .clk(clk), .rst_n(rst_n), .s_iq_i(qi_data), .s_iq_q(qq_data),
        .s_power(qp_data), .s_lag_re(qr_data), .s_lag_im(qm_data),
        .s_sample_index(meta_sample_index), .s_frame_id(meta_frame_id),
        .s_frame_start(meta_frame_start), .s_frame_end(meta_frame_end), .s_error(meta_error),
        .s_valid(bundle_valid), .s_ready(packer_ready), .buffer_release(buffer_release),
        .m_write_valid(m_write_valid), .m_write_ready(m_write_ready),
        .m_buffer_id(m_buffer_id), .m_frame_id(m_frame_id), .m_sample_index(m_sample_index),
        .m_iq_i_addr(m_iq_i_addr), .m_iq_q_addr(m_iq_q_addr),
        .m_power_addr(m_power_addr), .m_lag_re_addr(m_lag_re_addr), .m_lag_im_addr(m_lag_im_addr),
        .m_iq_i_data(m_iq_i_data), .m_iq_q_data(m_iq_q_data),
        .m_power_data(m_power_data), .m_lag_re_data(m_lag_re_data), .m_lag_im_data(m_lag_im_data),
        .m_frame_start(m_frame_start), .m_frame_done(m_frame_done),
        .m_frame_error(m_frame_error), .m_irq(m_irq), .buffer_busy(buffer_busy)
    );
endmodule
