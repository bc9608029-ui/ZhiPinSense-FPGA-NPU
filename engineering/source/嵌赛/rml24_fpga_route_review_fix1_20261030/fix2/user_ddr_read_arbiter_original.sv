`timescale 1ns/1ps
`default_nettype none

// Two-way arbiter for the platform's single User_Ddr_* 512-bit READ channel.
//
// The write channel (User_Ddr_aww*) is NOT arbitrated here: the NPU engine
// owns it exclusively (the smart-scan engine drives its aww outputs to 0 and
// never writes DDR -- PSD readback is over the register channel).
//
// Both requesters are single-outstanding-per-beat readers; beats from the two
// engines may interleave freely because the read owner is latched at the ar
// handshake and steers the rdata/rvalid/rready return.  NPU (r0) has fixed
// priority when both assert arvalid in the same cycle; the readers deassert
// arvalid for at least one cycle after each accepted beat, so the smart-scan
// (r1) reader is not starved.
module user_ddr_read_arbiter (
    input  wire         clk,
    input  wire         rst_n,

    // platform (single read channel)
    output wire [31:0]  ar_araddr,
    output wire         ar_arvalid,
    output wire [31:0]  ar_arinfo,
    input  wire         ar_arready,
    input  wire [511:0] ar_rdata,
    input  wire         ar_rvalid,
    input  wire [31:0]  ar_rinfo,
    output wire         ar_rready,

    // requester 0 (NPU) -- fixed priority
    input  wire [31:0]  r0_araddr,
    input  wire         r0_arvalid,
    input  wire [31:0]  r0_arinfo,
    output wire         r0_arready,
    output wire [511:0] r0_rdata,
    output wire         r0_rvalid,
    output wire [31:0]  r0_rinfo,
    input  wire         r0_rready,

    // requester 1 (smart-scan)
    input  wire [31:0]  r1_araddr,
    input  wire         r1_arvalid,
    input  wire [31:0]  r1_arinfo,
    output wire         r1_arready,
    output wire [511:0] r1_rdata,
    output wire         r1_rvalid,
    output wire [31:0]  r1_rinfo,
    input  wire         r1_rready
);
    wire req0   = r0_arvalid;
    wire req1   = r1_arvalid;
    wire grant1 = req1 && !req0;   // NPU (r0) has fixed priority

    assign ar_arvalid = req0 | req1;
    assign ar_araddr  = grant1 ? r1_araddr : r0_araddr;
    assign ar_arinfo  = grant1 ? r1_arinfo : r0_arinfo;
    assign r0_arready = ar_arready && !grant1;
    assign r1_arready = ar_arready &&  grant1;

    reg owner1;
    wire rd_accept = ar_arvalid && ar_arready;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)         owner1 <= 1'b0;
        else if (rd_accept) owner1 <= grant1;
    end

    assign r0_rvalid = ar_rvalid && !owner1;
    assign r1_rvalid = ar_rvalid &&  owner1;
    assign r0_rdata  = ar_rdata;
    assign r1_rdata  = ar_rdata;
    assign r0_rinfo  = ar_rinfo;
    assign r1_rinfo  = ar_rinfo;
    assign ar_rready = owner1 ? r1_rready : r0_rready;
endmodule

`default_nettype wire
