`timescale 1ns/1ps
`default_nettype none

module user_ddr_tensor_writer #(
    parameter integer EXPECTED_BEATS = 1520
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire [543:0] beat_command,
    input  wire         beat_valid,
    output wire         beat_ready,
    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [31:0]  accepted_beats,

    output wire [31:0]  User_Ddr_awwaddr,
    output wire [511:0] User_Ddr_awwdata,
    output wire [71:0]  User_Ddr_awwinfo,
    output wire         User_Ddr_awwvalid,
    input  wire         User_Ddr_awwready
);
    assign User_Ddr_awwaddr  = beat_command[543:512];
    assign User_Ddr_awwdata  = beat_command[511:0];
    // Official full 64-byte single-beat write encoding.
    assign User_Ddr_awwinfo  = {1'b0, {64{1'b1}}, 6'b0, 1'b1};
    assign User_Ddr_awwvalid = busy && beat_valid;
    assign beat_ready        = busy && User_Ddr_awwready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy           <= 1'b0;
            done           <= 1'b0;
            error          <= 1'b0;
            accepted_beats <= 32'd0;
        end else begin
            if (start && !busy) begin
                busy           <= (EXPECTED_BEATS != 0);
                done           <= (EXPECTED_BEATS == 0);
                error          <= (EXPECTED_BEATS == 0);
                accepted_beats <= 32'd0;
            end

            if (User_Ddr_awwvalid && User_Ddr_awwready) begin
                accepted_beats <= accepted_beats + 1'b1;
                if (accepted_beats + 1'b1 == EXPECTED_BEATS) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end else if (accepted_beats + 1'b1 > EXPECTED_BEATS) begin
                    error <= 1'b1;
                end
            end
        end
    end
endmodule

`default_nettype wire
