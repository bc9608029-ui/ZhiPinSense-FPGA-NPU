`timescale 1ns/1ps

// Abstract boundary only. No Procise, AXI, DMA or DDR IP is instantiated.
// The future board adapter consumes one five-lane write bundle per sample.
interface tensor_buffer_write_if #(
    parameter integer FRAME_ID_WIDTH = 32,
    parameter integer INDEX_WIDTH = 10
) (input wire clk);
    logic valid;
    logic ready;
    logic buffer_id;
    logic [FRAME_ID_WIDTH-1:0] frame_id;
    logic [INDEX_WIDTH-1:0] sample_index;
    logic signed [7:0] iq_i;
    logic signed [7:0] iq_q;
    logic signed [7:0] power;
    logic signed [7:0] lag_re;
    logic signed [7:0] lag_im;
    logic frame_start;
    logic frame_done;
    logic frame_error;
    logic irq;

    modport producer (
        input ready,
        output valid, buffer_id, frame_id, sample_index,
        output iq_i, iq_q, power, lag_re, lag_im,
        output frame_start, frame_done, frame_error, irq
    );
    modport consumer (
        output ready,
        input valid, buffer_id, frame_id, sample_index,
        input iq_i, iq_q, power, lag_re, lag_im,
        input frame_start, frame_done, frame_error, irq
    );
endinterface
