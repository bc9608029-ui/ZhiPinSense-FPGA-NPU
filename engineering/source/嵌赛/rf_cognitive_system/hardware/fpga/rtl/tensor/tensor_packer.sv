`timescale 1ns/1ps

// Logical NCL tensor packer with ping-pong ownership. It emits five parallel
// byte writes and channel-major byte offsets; the future board adapter may map
// them to banked BRAM or serialize them into DDR bursts.
module tensor_packer #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = $clog2(FRAME_LENGTH),
    parameter integer IQ_ADDR_WIDTH = $clog2(2*FRAME_LENGTH),
    parameter integer PHYS_ADDR_WIDTH = $clog2(3*FRAME_LENGTH)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire signed [7:0]             s_iq_i,
    input  wire signed [7:0]             s_iq_q,
    input  wire signed [7:0]             s_power,
    input  wire signed [7:0]             s_lag_re,
    input  wire signed [7:0]             s_lag_im,
    input  wire [INDEX_WIDTH-1:0]        s_sample_index,
    input  wire [FRAME_ID_WIDTH-1:0]     s_frame_id,
    input  wire                          s_frame_start,
    input  wire                          s_frame_end,
    input  wire                          s_error,
    input  wire                          s_valid,
    output wire                          s_ready,
    input  wire [1:0]                    buffer_release,
    output wire                          m_write_valid,
    input  wire                          m_write_ready,
    output wire                          m_buffer_id,
    output wire [FRAME_ID_WIDTH-1:0]     m_frame_id,
    output wire [INDEX_WIDTH-1:0]        m_sample_index,
    output wire [IQ_ADDR_WIDTH-1:0]      m_iq_i_addr,
    output wire [IQ_ADDR_WIDTH-1:0]      m_iq_q_addr,
    output wire [PHYS_ADDR_WIDTH-1:0]    m_power_addr,
    output wire [PHYS_ADDR_WIDTH-1:0]    m_lag_re_addr,
    output wire [PHYS_ADDR_WIDTH-1:0]    m_lag_im_addr,
    output wire signed [7:0]             m_iq_i_data,
    output wire signed [7:0]             m_iq_q_data,
    output wire signed [7:0]             m_power_data,
    output wire signed [7:0]             m_lag_re_data,
    output wire signed [7:0]             m_lag_im_data,
    output wire                          m_frame_start,
    output wire                          m_frame_done,
    output wire                          m_frame_error,
    output wire                          m_irq,
    output reg  [1:0]                    buffer_busy
);
    reg fill_buffer;
    wire selected_buffer_available = !buffer_busy[fill_buffer] || buffer_release[fill_buffer];
    wire transfer;

    assign s_ready = m_write_ready && selected_buffer_available;
    assign m_write_valid = s_valid && selected_buffer_available;
    assign transfer = m_write_valid && m_write_ready;
    assign m_buffer_id = fill_buffer;
    assign m_frame_id = s_frame_id;
    assign m_sample_index = s_sample_index;

    // Byte offsets for contiguous NCL planes.
    assign m_iq_i_addr = IQ_ADDR_WIDTH'(s_sample_index);
    assign m_iq_q_addr = IQ_ADDR_WIDTH'(FRAME_LENGTH) + IQ_ADDR_WIDTH'(s_sample_index);
    assign m_power_addr = PHYS_ADDR_WIDTH'(s_sample_index);
    assign m_lag_re_addr = PHYS_ADDR_WIDTH'(FRAME_LENGTH) + PHYS_ADDR_WIDTH'(s_sample_index);
    assign m_lag_im_addr = PHYS_ADDR_WIDTH'(2*FRAME_LENGTH) + PHYS_ADDR_WIDTH'(s_sample_index);

    assign m_iq_i_data = s_iq_i;
    assign m_iq_q_data = s_iq_q;
    assign m_power_data = s_power;
    assign m_lag_re_data = s_lag_re;
    assign m_lag_im_data = s_lag_im;
    assign m_frame_start = m_write_valid && s_frame_start;
    assign m_frame_done = m_write_valid && s_frame_end;
    assign m_frame_error = s_error;
    assign m_irq = transfer && s_frame_end;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fill_buffer <= 1'b0;
            buffer_busy <= 2'b00;
        end else begin
            if (buffer_release[0])
                buffer_busy[0] <= 1'b0;
            if (buffer_release[1])
                buffer_busy[1] <= 1'b0;

            if (transfer && s_frame_end) begin
                buffer_busy[fill_buffer] <= 1'b1;
                fill_buffer <= ~fill_buffer;
            end
        end
    end
endmodule
