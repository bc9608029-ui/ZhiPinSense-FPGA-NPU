`timescale 1ns/1ps

// Board-independent 1024-point frame marker. Sidebands remain stable while
// downstream backpressure holds m_valid high.
module iq_frame_controller #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = $clog2(FRAME_LENGTH)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire signed [15:0]            s_i,
    input  wire signed [15:0]            s_q,
    input  wire                          s_error,
    input  wire                          s_valid,
    output wire                          s_ready,
    output wire signed [15:0]            m_i,
    output wire signed [15:0]            m_q,
    output wire                          m_error,
    output wire                          m_valid,
    input  wire                          m_ready,
    output wire [INDEX_WIDTH-1:0]        m_sample_index,
    output wire [FRAME_ID_WIDTH-1:0]     m_frame_id,
    output wire                          m_frame_start,
    output wire                          m_frame_end,
    output wire                          m_frame_valid
);
    localparam logic [INDEX_WIDTH-1:0] LAST_SAMPLE = INDEX_WIDTH'(FRAME_LENGTH-1);

    reg [INDEX_WIDTH-1:0] sample_index;
    reg [FRAME_ID_WIDTH-1:0] frame_id;
    reg frame_error_sticky;
    wire transfer = s_valid && s_ready;

    assign s_ready = m_ready;
    assign m_valid = s_valid;
    assign m_i = s_i;
    assign m_q = s_q;
    assign m_sample_index = sample_index;
    assign m_frame_id = frame_id;
    assign m_frame_start = (sample_index == 0);
    assign m_frame_end = (sample_index == LAST_SAMPLE);
    assign m_frame_valid = m_valid;
    assign m_error = frame_error_sticky | s_error;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_index <= 0;
            frame_id <= 0;
            frame_error_sticky <= 1'b0;
        end else if (transfer) begin
            if (sample_index == LAST_SAMPLE) begin
                sample_index <= 0;
                frame_id <= frame_id + 1'b1;
                frame_error_sticky <= 1'b0;
            end else begin
                sample_index <= sample_index + 1'b1;
                frame_error_sticky <= frame_error_sticky | s_error;
            end
        end
    end
endmodule
