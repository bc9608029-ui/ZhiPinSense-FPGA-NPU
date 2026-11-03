`timescale 1ns/1ps
`default_nettype none

// Two-way router for the platform's single User_Reg_* 32-bit register channel.
//
// The combined NPU+smart-scan top has two register banks on one channel:
//   - engine 0 (NPU, pl_ddr_mandatory_core_regs): owns 0x00000-0x00028
//   - engine 1 (smart-scan, smart_scan_pspl_regs): SS window [SS_BASE, ...]
//     (default 0x10000-0x10FFF, remapped so the SS_ contract offsets stay a
//     relative layout while the board base moves).
//
// The platform protocol is single-outstanding read (arready = !rvalid on each
// bank).  The write channel is routed combinationally by the decoded byte
// address (awwaddr is held stable while awwvalid is asserted).  The read owner
// is latched at the ar handshake and steers the rdata/rvalid/rready return; no
// read can be issued while another is outstanding, so the latch is unambiguous.
module user_reg_router #(
    parameter [17:0] SS_BASE = 18'h10000,
    parameter [17:0] SS_MASK = 18'h0F000   // 4 KiB window: 0x10000-0x10FFF
) (
    input  wire        clk,
    input  wire        rst_n,

    // platform (single register channel)
    input  wire [31:0] awwaddr,
    input  wire [31:0] awwdata,
    input  wire        awwvalid,
    output wire        awwready,
    input  wire [31:0] araddr,
    input  wire        arvalid,
    output wire        arready,
    output wire [31:0] rdata,
    output wire        rvalid,
    input  wire        rready,

    // engine 0 (NPU): everything outside the SS window
    output wire [31:0] e0_awwaddr,
    output wire [31:0] e0_awwdata,
    output wire        e0_awwvalid,
    input  wire        e0_awwready,
    output wire [31:0] e0_araddr,
    output wire        e0_arvalid,
    input  wire        e0_arready,
    input  wire [31:0] e0_rdata,
    input  wire        e0_rvalid,
    output wire        e0_rready,

    // engine 1 (smart-scan): SS window
    output wire [31:0] e1_awwaddr,
    output wire [31:0] e1_awwdata,
    output wire        e1_awwvalid,
    input  wire        e1_awwready,
    output wire [31:0] e1_araddr,
    output wire        e1_arvalid,
    input  wire        e1_arready,
    input  wire [31:0] e1_rdata,
    input  wire        e1_rvalid,
    output wire        e1_rready
);
    wire ss_sel_w = ((awwaddr[17:0] & SS_MASK) == SS_BASE);
    wire ss_sel_r = ((araddr[17:0]  & SS_MASK) == SS_BASE);

    // Relocate the SS window to offset 0 before forwarding, so the SS register
    // bank keeps its frozen 0-based ADDR_* decode (byte-identical to the
    // standalone-TB version).  The NPU bank sees the address unchanged.
    wire [17:0] e1_addr_w = awwaddr[17:0] - SS_BASE;
    wire [17:0] e1_addr_r = araddr[17:0]  - SS_BASE;

    // ---- write channel: route by decoded address -------------------------
    assign e0_awwvalid = awwvalid && !ss_sel_w;
    assign e1_awwvalid = awwvalid &&  ss_sel_w;
    assign e0_awwaddr  = awwaddr;
    assign e1_awwaddr  = {14'd0, e1_addr_w};
    assign e0_awwdata  = awwdata;
    assign e1_awwdata  = awwdata;
    assign awwready    = ss_sel_w ? e1_awwready : e0_awwready;

    // ---- read channel: route by decoded address, latch owner for return --
    reg owner_ss;
    wire rd_accept = arvalid && arready;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)           owner_ss <= 1'b0;
        else if (rd_accept)   owner_ss <= ss_sel_r;
    end

    assign e0_arvalid = arvalid && !ss_sel_r;
    assign e1_arvalid = arvalid &&  ss_sel_r;
    assign e0_araddr  = araddr;
    assign e1_araddr  = {14'd0, e1_addr_r};
    assign arready    = ss_sel_r ? e1_arready : e0_arready;

    assign rdata     = owner_ss ? e1_rdata : e0_rdata;
    assign rvalid    = owner_ss ? e1_rvalid : e0_rvalid;
    assign e0_rready = (!owner_ss) && rready;
    assign e1_rready = ( owner_ss) && rready;
endmodule

`default_nettype wire
