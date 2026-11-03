// axi3_to_axilite_bridge.sv — AXI3 (12-bit ID) -> AXI-Lite (no ID, no B) bridge.
//
// NEW file.  Bridges the PS7 User_GP0 master port (AXI3, 12-bit ID, 32-bit data)
// to frame_ctrl, which is an AXI-Lite slave with two quirks:
//   1) it has NO write-response (B) channel — writes are fire-and-forget;
//   2) it is always-ready (AWREADY/WREADY/ARREADY = 1) and captures a write
//      combinationally when AWVALID & WVALID are asserted in the SAME cycle.
//
// This bridge therefore:
//   * aligns AW and W (accepts both in the same cycle) so frame_ctrl captures
//     the write correctly;
//   * synthesizes the B response (BRESP=OKAY) that frame_ctrl never sends;
//   * forwards the read channel and echoes back the ARID as RID.
//
// Assumption (documented): transactions are single-beat 32-bit register
// accesses (AWLEN/ARLEN == 0), which is what iCraft / Linux register writes
// issue.  Burst support is NOT implemented; this is sufficient for the
// frame_ctrl control register path in Phase 1A.
`timescale 1ns / 1ps

module axi3_to_axilite_bridge (
    input  wire        gp_clk,
    input  wire        gp_rst_n,       // active-low

    // ---- AXI3 master side (User_GP0 from PS7), 12-bit ID, 32-bit data ----
    // write address
    input  wire        m_awvalid,
    input  wire [31:0] m_awaddr,
    input  wire [11:0] m_awid,
    input  wire [2:0]  m_awprot,
    output wire        m_awready,
    // write data
    input  wire        m_wvalid,
    input  wire [31:0] m_wdata,
    input  wire [3:0]  m_wstrb,
    input  wire        m_wlast,
    output wire        m_wready,
    // write response
    output wire        m_bvalid,
    output wire [1:0]  m_bresp,
    output wire [11:0] m_bid,
    input  wire        m_bready,
    // read address
    input  wire        m_arvalid,
    input  wire [31:0] m_araddr,
    input  wire [11:0] m_arid,
    input  wire [2:0]  m_arprot,
    output wire        m_arready,
    // read data
    output wire        m_rvalid,
    output wire [31:0] m_rdata,
    output wire [1:0]  m_rresp,
    output wire        m_rlast,
    output wire [11:0] m_rid,
    input  wire        m_rready,

    // ---- AXI-Lite slave side (frame_ctrl), no ID, no B channel ----
    output wire        s_awvalid,
    output wire [8:0]  s_awaddr,
    output wire [2:0]  s_awprot,
    output wire        s_wvalid,
    output wire [31:0] s_wdata,
    output wire [3:0]  s_wstrb,
    output wire        s_arvalid,
    output wire [8:0]  s_araddr,
    output wire [2:0]  s_arprot,
    input  wire        s_rvalid,
    input  wire [31:0] s_rdata,
    input  wire [1:0]  s_rresp,
    output wire        s_rready
);

    // =======================================================================
    // Write path: align AW & W so frame_ctrl sees AWVALID & WVALID together.
    // =======================================================================
    assign m_awready = m_wvalid;      // accept AW only once W is also present
    assign m_wready = m_awvalid;      // accept W only once AW is also present

    assign s_awvalid = m_awvalid;
    assign s_awaddr  = m_awaddr[8:0];
    assign s_awprot  = m_awprot;
    assign s_wvalid  = m_wvalid;
    assign s_wdata   = m_wdata;
    assign s_wstrb   = m_wstrb;

    // Synthesize write response (frame_ctrl has no B channel).
    wire wr_accept = m_awvalid & m_wvalid & m_wlast;

    reg        wr_pending;
    reg [11:0] wr_bid;
    always @(posedge gp_clk or negedge gp_rst_n) begin
        if (!gp_rst_n) begin
            wr_pending <= 1'b0;
            wr_bid     <= 12'd0;
        end else begin
            if (wr_accept) begin
                wr_pending <= 1'b1;
                wr_bid     <= m_awid;
            end
            if (wr_pending && m_bready)
                wr_pending <= 1'b0;
        end
    end
    assign m_bvalid = wr_pending;
    assign m_bresp  = 2'b00;          // OKAY
    assign m_bid    = wr_bid;

    // =======================================================================
    // Read path: forward AR/R; frame_ctrl is always ready, 1-cycle read latency.
    // =======================================================================
    assign m_arready = 1'b1;
    assign s_arvalid = m_arvalid;
    assign s_araddr  = m_araddr[8:0];
    assign s_arprot  = m_arprot;
    assign s_rready  = m_rready;

    assign m_rvalid  = s_rvalid;
    assign m_rdata   = s_rdata;
    assign m_rresp   = s_rresp;
    assign m_rlast   = s_rvalid;      // single-beat read
    assign m_rid     = rd_id;

    reg [11:0] rd_id;
    always @(posedge gp_clk or negedge gp_rst_n) begin
        if (!gp_rst_n)
            rd_id <= 12'd0;
        else if (m_arvalid)
            rd_id <= m_arid;
    end

endmodule
