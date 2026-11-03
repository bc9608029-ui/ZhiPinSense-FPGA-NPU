`timescale 1ns/1ps

// Abstract command/completion boundary for a future BRAM/DDR/DMA adapter.
// Addresses are byte addresses, lengths are bytes, and no bus protocol is
// implied. The board wrapper owns coherency and physical address translation.
interface buffer_transfer_if #(
    parameter integer ADDRESS_WIDTH = 64,
    parameter integer LENGTH_WIDTH = 32,
    parameter integer FRAME_ID_WIDTH = 32
) (input wire clk);
    logic request_valid;
    logic request_ready;
    logic write_not_read;
    logic buffer_id;
    logic [ADDRESS_WIDTH-1:0] buffer_address;
    logic [LENGTH_WIDTH-1:0] buffer_length;
    logic [FRAME_ID_WIDTH-1:0] frame_id;
    logic done;
    logic error;
    logic irq;

    modport requester (
        output request_valid, write_not_read, buffer_id, buffer_address, buffer_length, frame_id,
        input request_ready, done, error, irq
    );
    modport adapter (
        input request_valid, write_not_read, buffer_id, buffer_address, buffer_length, frame_id,
        output request_ready, done, error, irq
    );
endinterface
