`timescale 1ns/1ps
`default_nettype none

// Collects 64 accepted Mandatory Core tensor writes and emits five complete
// 64-byte DDR beats in channel-major order:
//   IQ-I, IQ-Q, Power, Lag-Re, Lag-Im.
// A frame therefore occupies 5 * 1024 = 5120 bytes.
module tensor_plane_beat_packer #(
    parameter integer FRAME_LENGTH = 1024,
    parameter integer FRAME_COUNT = 19,
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = 10
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         start,
    input  wire [31:0]                  output_base_addr,

    input  wire                         s_write_valid,
    output wire                         s_write_ready,
    input  wire                         s_buffer_id,
    input  wire [FRAME_ID_WIDTH-1:0]    s_frame_id,
    input  wire [INDEX_WIDTH-1:0]       s_sample_index,
    input  wire [INDEX_WIDTH:0]         s_iq_i_addr,
    input  wire [INDEX_WIDTH:0]         s_iq_q_addr,
    input  wire [INDEX_WIDTH+1:0]       s_power_addr,
    input  wire [INDEX_WIDTH+1:0]       s_lag_re_addr,
    input  wire [INDEX_WIDTH+1:0]       s_lag_im_addr,
    input  wire signed [7:0]            s_iq_i_data,
    input  wire signed [7:0]            s_iq_q_data,
    input  wire signed [7:0]            s_power_data,
    input  wire signed [7:0]            s_lag_re_data,
    input  wire signed [7:0]            s_lag_im_data,
    input  wire                         s_frame_start,
    input  wire                         s_frame_done,
    input  wire                         s_frame_error,

    output reg  [1:0]                   buffer_release,
    output wire [543:0]                 beat_command,
    output wire                         beat_valid,
    input  wire                         beat_ready,
    output reg                          active,
    output reg                          all_frames_enqueued,
    output reg                          protocol_error,
    output reg  [31:0]                  accepted_samples,
    output reg  [31:0]                  enqueued_beats
);
    localparam integer FRAME_BYTES = 5 * FRAME_LENGTH;
    localparam [1:0] ST_IDLE    = 2'd0;
    localparam [1:0] ST_COLLECT = 2'd1;
    localparam [1:0] ST_EMIT    = 2'd2;

    reg [1:0] state;
    reg [511:0] plane_i;
    reg [511:0] plane_q;
    reg [511:0] plane_power;
    reg [511:0] plane_lag_re;
    reg [511:0] plane_lag_im;
    reg [2:0] emit_plane;
    reg [31:0] emit_frame_base;
    reg [31:0] emit_block_offset;
    reg emit_last_block;
    reg emit_last_frame;
    reg [FRAME_ID_WIDTH-1:0] expected_frame;
    reg [INDEX_WIDTH-1:0] expected_sample;
    reg [31:0] current_frame_base;

    wire input_transfer = s_write_valid && s_write_ready;
    wire beat_transfer = beat_valid && beat_ready;
    reg [511:0] selected_plane;

    assign s_write_ready = active && (state == ST_COLLECT);
    assign beat_valid = (state == ST_EMIT);
    assign beat_command = {
        emit_frame_base + (emit_plane * FRAME_LENGTH) + emit_block_offset,
        selected_plane
    };

    always @* begin
        case (emit_plane)
            3'd0: selected_plane = plane_i;
            3'd1: selected_plane = plane_q;
            3'd2: selected_plane = plane_power;
            3'd3: selected_plane = plane_lag_re;
            default: selected_plane = plane_lag_im;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state               <= ST_IDLE;
            plane_i             <= 512'd0;
            plane_q             <= 512'd0;
            plane_power         <= 512'd0;
            plane_lag_re        <= 512'd0;
            plane_lag_im        <= 512'd0;
            emit_plane          <= 3'd0;
            emit_frame_base     <= 32'd0;
            emit_block_offset   <= 32'd0;
            emit_last_block     <= 1'b0;
            emit_last_frame     <= 1'b0;
            expected_frame      <= {FRAME_ID_WIDTH{1'b0}};
            expected_sample     <= {INDEX_WIDTH{1'b0}};
            current_frame_base  <= 32'd0;
            buffer_release      <= 2'b00;
            active              <= 1'b0;
            all_frames_enqueued <= 1'b0;
            protocol_error      <= 1'b0;
            accepted_samples    <= 32'd0;
            enqueued_beats      <= 32'd0;
        end else begin
            buffer_release <= 2'b00;

            if (start && state == ST_IDLE) begin
                state               <= ST_COLLECT;
                expected_frame      <= {FRAME_ID_WIDTH{1'b0}};
                expected_sample     <= {INDEX_WIDTH{1'b0}};
                current_frame_base  <= output_base_addr;
                active              <= 1'b1;
                all_frames_enqueued <= 1'b0;
                protocol_error      <= 1'b0;
                accepted_samples    <= 32'd0;
                enqueued_beats      <= 32'd0;
            end

            if (input_transfer) begin
                plane_i[(s_sample_index[5:0] * 8) +: 8]      <= s_iq_i_data;
                plane_q[(s_sample_index[5:0] * 8) +: 8]      <= s_iq_q_data;
                plane_power[(s_sample_index[5:0] * 8) +: 8]  <= s_power_data;
                plane_lag_re[(s_sample_index[5:0] * 8) +: 8] <= s_lag_re_data;
                plane_lag_im[(s_sample_index[5:0] * 8) +: 8] <= s_lag_im_data;
                accepted_samples <= accepted_samples + 1'b1;

                if (s_frame_id != expected_frame ||
                    s_sample_index != expected_sample ||
                    s_buffer_id != expected_frame[0] ||
                    s_iq_i_addr != s_sample_index ||
                    s_iq_q_addr != FRAME_LENGTH + s_sample_index ||
                    s_power_addr != s_sample_index ||
                    s_lag_re_addr != FRAME_LENGTH + s_sample_index ||
                    s_lag_im_addr != (2*FRAME_LENGTH) + s_sample_index ||
                    s_frame_start != (s_sample_index == 0) ||
                    s_frame_done != (s_sample_index == FRAME_LENGTH-1) ||
                    s_frame_error)
                    protocol_error <= 1'b1;

                if (s_sample_index == FRAME_LENGTH-1) begin
                    buffer_release[s_buffer_id] <= 1'b1;
                    expected_sample <= {INDEX_WIDTH{1'b0}};
                    expected_frame <= expected_frame + 1'b1;
                    current_frame_base <= current_frame_base + FRAME_BYTES;
                end else begin
                    expected_sample <= expected_sample + 1'b1;
                end

                if (s_sample_index[5:0] == 6'd63) begin
                    emit_plane        <= 3'd0;
                    emit_frame_base   <= current_frame_base;
                    emit_block_offset <= {22'd0, s_sample_index[INDEX_WIDTH-1:6], 6'd0};
                    emit_last_block   <= (s_sample_index == FRAME_LENGTH-1);
                    emit_last_frame   <= (s_frame_id == FRAME_COUNT-1);
                    state             <= ST_EMIT;
                end
            end

            if (beat_transfer) begin
                enqueued_beats <= enqueued_beats + 1'b1;
                if (emit_plane == 3'd4) begin
                    emit_plane <= 3'd0;
                    if (emit_last_block && emit_last_frame) begin
                        all_frames_enqueued <= 1'b1;
                        active <= 1'b0;
                        state <= ST_IDLE;
                    end else begin
                        state <= ST_COLLECT;
                    end
                end else begin
                    emit_plane <= emit_plane + 1'b1;
                end
            end
        end
    end
endmodule

`default_nettype wire
