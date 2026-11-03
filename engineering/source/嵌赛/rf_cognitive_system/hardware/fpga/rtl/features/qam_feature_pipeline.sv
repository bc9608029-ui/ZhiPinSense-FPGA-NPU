`timescale 1ns/1ps

// Two-stage elastic pipeline for the frozen Power/Lag-1 numerical contract.
// Latency: 2 accepted pipeline clocks without stalls. Initiation interval: 1.
// Exact arithmetic widths: Power u32, LagRe/LagIm s33.
module qam_feature_pipeline #(
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = 10
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire signed [15:0]            s_i,
    input  wire signed [15:0]            s_q,
    input  wire                          s_valid,
    output wire                          s_ready,
    input  wire [INDEX_WIDTH-1:0]        s_sample_index,
    input  wire [FRAME_ID_WIDTH-1:0]     s_frame_id,
    input  wire                          s_frame_start,
    input  wire                          s_frame_end,
    input  wire                          s_error,
    output reg  signed [15:0]            m_i,
    output reg  signed [15:0]            m_q,
    output reg  [31:0]                   m_power,
    output reg  signed [32:0]            m_lag_re,
    output reg  signed [32:0]            m_lag_im,
    output reg                           m_valid,
    input  wire                          m_ready,
    output reg  [INDEX_WIDTH-1:0]        m_sample_index,
    output reg  [FRAME_ID_WIDTH-1:0]     m_frame_id,
    output reg                           m_frame_start,
    output reg                           m_frame_end,
    output reg                           m_error
);
    reg signed [15:0] previous_i;
    reg signed [15:0] previous_q;

    reg s1_valid;
    reg signed [15:0] s1_i;
    reg signed [15:0] s1_q;
    reg [31:0] s1_i_square;
    reg [31:0] s1_q_square;
    reg signed [31:0] s1_i_i_prev;
    reg signed [31:0] s1_q_q_prev;
    reg signed [31:0] s1_q_i_prev;
    reg signed [31:0] s1_i_q_prev;
    reg [INDEX_WIDTH-1:0] s1_sample_index;
    reg [FRAME_ID_WIDTH-1:0] s1_frame_id;
    reg s1_frame_start;
    reg s1_frame_end;
    reg s1_error;

    wire stage2_ready = !m_valid || m_ready;
    wire stage1_ready = !s1_valid || stage2_ready;
    assign s_ready = stage1_ready;

    wire signed [15:0] selected_previous_i = s_frame_start ? 16'sd0 : previous_i;
    wire signed [15:0] selected_previous_q = s_frame_start ? 16'sd0 : previous_q;
    wire signed [31:0] product_i_square = s_i * s_i;
    wire signed [31:0] product_q_square = s_q * s_q;
    wire signed [31:0] product_i_i_prev = s_i * selected_previous_i;
    wire signed [31:0] product_q_q_prev = s_q * selected_previous_q;
    wire signed [31:0] product_q_i_prev = s_q * selected_previous_i;
    wire signed [31:0] product_i_q_prev = s_i * selected_previous_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            previous_i <= 0;
            previous_q <= 0;
            s1_valid <= 1'b0;
            m_valid <= 1'b0;
        end else begin
            if (stage2_ready) begin
                m_valid <= s1_valid;
                if (s1_valid) begin
                    m_i <= s1_i;
                    m_q <= s1_q;
                    m_power <= s1_i_square + s1_q_square;
                    if (s1_frame_start) begin
                        m_lag_re <= 33'sd0;
                        m_lag_im <= 33'sd0;
                    end else begin
                        m_lag_re <= $signed({s1_i_i_prev[31], s1_i_i_prev})
                                  + $signed({s1_q_q_prev[31], s1_q_q_prev});
                        m_lag_im <= $signed({s1_q_i_prev[31], s1_q_i_prev})
                                  - $signed({s1_i_q_prev[31], s1_i_q_prev});
                    end
                    m_sample_index <= s1_sample_index;
                    m_frame_id <= s1_frame_id;
                    m_frame_start <= s1_frame_start;
                    m_frame_end <= s1_frame_end;
                    m_error <= s1_error;
                end
            end

            if (stage1_ready) begin
                s1_valid <= s_valid;
                if (s_valid) begin
                    s1_i <= s_i;
                    s1_q <= s_q;
                    s1_i_square <= $unsigned(product_i_square);
                    s1_q_square <= $unsigned(product_q_square);
                    s1_i_i_prev <= product_i_i_prev;
                    s1_q_q_prev <= product_q_q_prev;
                    s1_q_i_prev <= product_q_i_prev;
                    s1_i_q_prev <= product_i_q_prev;
                    s1_sample_index <= s_sample_index;
                    s1_frame_id <= s_frame_id;
                    s1_frame_start <= s_frame_start;
                    s1_frame_end <= s_frame_end;
                    s1_error <= s_error;

                    if (s_frame_end) begin
                        previous_i <= 0;
                        previous_q <= 0;
                    end else begin
                        previous_i <= s_i;
                        previous_q <= s_q;
                    end
                end
            end
        end
    end
endmodule
