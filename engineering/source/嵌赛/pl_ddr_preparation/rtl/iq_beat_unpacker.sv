`timescale 1ns/1ps
`default_nettype none

// Converts each 64-byte PL-DDR beat into sixteen sequential {Q[15:0],I[15:0]}
// IQ transfers.  It advances only on iq_valid && iq_ready.
module iq_beat_unpacker (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [511:0] beat_data,
    input  wire         beat_valid,
    output wire         beat_ready,
    output wire signed [15:0] iq_i,
    output wire signed [15:0] iq_q,
    output wire         iq_valid,
    input  wire         iq_ready,
    output reg  [31:0]  accepted_samples
);
    reg [511:0] held_beat;
    reg [3:0]   word_index;
    reg         have_beat;
    wire [31:0] iq_word = held_beat[(word_index * 32) +: 32];
    wire iq_transfer = iq_valid && iq_ready;
    wire finishing_beat = iq_transfer && (word_index == 4'd15);

    assign iq_i = iq_word[15:0];
    assign iq_q = iq_word[31:16];
    assign iq_valid = have_beat;
    assign beat_ready = !have_beat || finishing_beat;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            held_beat       <= 512'd0;
            word_index      <= 4'd0;
            have_beat       <= 1'b0;
            accepted_samples <= 32'd0;
        end else begin
            if (iq_transfer)
                accepted_samples <= accepted_samples + 1'b1;

            if (!have_beat) begin
                if (beat_valid && beat_ready) begin
                    held_beat  <= beat_data;
                    word_index <= 4'd0;
                    have_beat  <= 1'b1;
                end
            end else if (iq_transfer) begin
                if (word_index == 4'd15) begin
                    if (beat_valid) begin
                        held_beat  <= beat_data;
                        word_index <= 4'd0;
                        have_beat  <= 1'b1;
                    end else begin
                        have_beat <= 1'b0;
                    end
                end else begin
                    word_index <= word_index + 1'b1;
                end
            end
        end
    end
endmodule

`default_nettype wire
