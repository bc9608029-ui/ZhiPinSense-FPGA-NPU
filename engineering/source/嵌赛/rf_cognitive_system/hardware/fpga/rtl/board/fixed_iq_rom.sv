`timescale 1ns/1ps
`default_nettype none

// Fixed board-validation corpus.  Each word is exactly {Q[15:0], I[15:0]}
// from hardware/fpga/vectors/iq_input.hex; no numerical conversion occurs.
module fixed_iq_rom #(
    parameter integer DEPTH = 19456,
    parameter integer ADDR_WIDTH = $clog2(DEPTH),
    parameter INIT_FILE = "vectors/iq_input.hex"
) (
    input  wire [ADDR_WIDTH-1:0] address,
    output wire [31:0]           data
);
    (* rom_style = "block" *) reg [31:0] memory [0:DEPTH-1];

    initial begin
        $readmemh(INIT_FILE, memory);
    end

    assign data = memory[address];
endmodule

`default_nettype wire
