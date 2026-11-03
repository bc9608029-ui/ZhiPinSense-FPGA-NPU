`timescale 1ns/1ps

// Test-only AXI3 register-window terminator for official BD regions that are
// intentionally absent from the PS->PL control smoke design. It accepts one
// transaction at a time and returns zero/OKAY. No NPU, DMA, memory, or
// algorithm behavior is implemented.
module axi_gp_rfu_responder #(
    parameter integer ID_WIDTH = 12,
    parameter integer DATA_WIDTH = 32,
    parameter [DATA_WIDTH-1:0] READ_DATA = {DATA_WIDTH{1'b0}}
) (
    input  wire                    clk,
    input  wire                    rst,

    input  wire                    s_arvalid,
    input  wire [ID_WIDTH-1:0]     s_arid,
    input  wire [3:0]              s_arlen,
    output wire                    s_arready,
    output reg                     s_rvalid,
    input  wire                    s_rready,
    output reg                     s_rlast,
    output reg  [ID_WIDTH-1:0]     s_rid,
    output wire [1:0]              s_rresp,
    output wire [DATA_WIDTH-1:0]   s_rdata,

    input  wire                    s_awvalid,
    input  wire [ID_WIDTH-1:0]     s_awid,
    output wire                    s_awready,
    input  wire                    s_wvalid,
    input  wire                    s_wlast,
    output wire                    s_wready,
    output reg                     s_bvalid,
    input  wire                    s_bready,
    output reg  [ID_WIDTH-1:0]     s_bid,
    output wire [1:0]              s_bresp
);

    reg [3:0] read_beats_left;
    reg       aw_seen;
    reg       wlast_seen;
    reg [ID_WIDTH-1:0] awid_hold;

    wire ar_fire = s_arvalid && s_arready;
    wire aw_fire = s_awvalid && s_awready;
    wire w_fire  = s_wvalid  && s_wready;
    wire write_complete = (aw_seen || aw_fire) &&
                          (wlast_seen || (w_fire && s_wlast));

    assign s_arready = !s_rvalid;
    assign s_rresp   = 2'b00;
    assign s_rdata   = READ_DATA;
    assign s_awready = !s_bvalid && !aw_seen;
    assign s_wready  = !s_bvalid && !wlast_seen;
    assign s_bresp   = 2'b00;

    always @(posedge clk) begin
        if (rst) begin
            s_rvalid        <= 1'b0;
            s_rlast         <= 1'b0;
            s_rid           <= {ID_WIDTH{1'b0}};
            read_beats_left <= 4'h0;
        end else if (ar_fire) begin
            s_rvalid        <= 1'b1;
            s_rid           <= s_arid;
            read_beats_left <= s_arlen;
            s_rlast         <= (s_arlen == 4'h0);
        end else if (s_rvalid && s_rready) begin
            if (s_rlast) begin
                s_rvalid <= 1'b0;
                s_rlast  <= 1'b0;
            end else begin
                read_beats_left <= read_beats_left - 1'b1;
                s_rlast <= (read_beats_left == 4'h1);
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            aw_seen    <= 1'b0;
            wlast_seen <= 1'b0;
            awid_hold  <= {ID_WIDTH{1'b0}};
            s_bvalid   <= 1'b0;
            s_bid      <= {ID_WIDTH{1'b0}};
        end else begin
            if (s_bvalid && s_bready)
                s_bvalid <= 1'b0;

            if (aw_fire) begin
                aw_seen   <= 1'b1;
                awid_hold <= s_awid;
            end

            if (w_fire && s_wlast)
                wlast_seen <= 1'b1;

            if (!s_bvalid && write_complete) begin
                s_bvalid   <= 1'b1;
                s_bid      <= aw_fire ? s_awid : awid_hold;
                aw_seen    <= 1'b0;
                wlast_seen <= 1'b0;
            end
        end
    end

endmodule
