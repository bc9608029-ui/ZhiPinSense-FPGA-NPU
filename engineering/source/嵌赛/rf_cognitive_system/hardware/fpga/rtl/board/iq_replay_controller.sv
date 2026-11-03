`timescale 1ns/1ps
`default_nettype none

// One-shot replay of the fixed IQ corpus.  Address and data advance only on
// an accepted ready/valid transfer.  ST_WAIT guarantees a complete clock of
// reset-released idle time before sample zero is offered.
module iq_replay_controller #(
    parameter integer TOTAL_SAMPLES = 19456,
    parameter integer ADDR_WIDTH = $clog2(TOTAL_SAMPLES),
    parameter integer COUNT_WIDTH = $clog2(TOTAL_SAMPLES + 1)
) (
    input  wire                     clk,
    input  wire                     rst_n,
    output wire [ADDR_WIDTH-1:0]    rom_address,
    input  wire [31:0]              rom_data,
    output wire signed [15:0]       s_i,
    output wire signed [15:0]       s_q,
    output wire                     s_valid,
    input  wire                     s_ready,
    output wire                     running,
    output wire                     done,
    output wire [COUNT_WIDTH-1:0]   accepted_count
);
    localparam [1:0] ST_WAIT = 2'd0;
    localparam [1:0] ST_RUN  = 2'd1;
    localparam [1:0] ST_DONE = 2'd2;

    reg [1:0] state;
    reg [ADDR_WIDTH-1:0] address_reg;
    reg [COUNT_WIDTH-1:0] accepted_count_reg;

    wire transfer = s_valid && s_ready;

    assign rom_address = address_reg;
    assign s_i = rom_data[15:0];
    assign s_q = rom_data[31:16];
    assign s_valid = (state == ST_RUN);
    assign running = (state == ST_RUN);
    assign done = (state == ST_DONE);
    assign accepted_count = accepted_count_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= ST_WAIT;
            address_reg <= {ADDR_WIDTH{1'b0}};
            accepted_count_reg <= {COUNT_WIDTH{1'b0}};
        end else begin
            case (state)
                ST_WAIT: begin
                    state <= ST_RUN;
                end

                ST_RUN: begin
                    if (transfer) begin
                        accepted_count_reg <= accepted_count_reg + 1'b1;
                        if (address_reg == TOTAL_SAMPLES - 1) begin
                            state <= ST_DONE;
                        end else begin
                            address_reg <= address_reg + 1'b1;
                        end
                    end
                end

                default: begin
                    state <= ST_DONE;
                end
            endcase
        end
    end
endmodule

`default_nettype wire
