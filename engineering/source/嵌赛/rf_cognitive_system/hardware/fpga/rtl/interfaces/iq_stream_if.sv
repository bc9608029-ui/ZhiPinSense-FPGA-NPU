`timescale 1ns/1ps

// Generic complex-sample boundary. A board adapter, not this interface,
// terminates DDR, USB/GigE or any future direct digital RF transport.
interface iq_stream_if (input wire clk);
    logic signed [15:0] i;
    logic signed [15:0] q;
    logic error;
    logic valid;
    logic ready;
    logic drop_event;

    modport source (output i, q, error, valid, drop_event, input ready);
    modport sink   (input i, q, error, valid, drop_event, output ready);
endinterface
