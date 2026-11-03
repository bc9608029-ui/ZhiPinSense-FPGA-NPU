`timescale 1ns/1ps

module tb_axi_gp_rfu_responder;
    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    reg arvalid = 0;
    reg [11:0] arid = 0;
    reg [3:0] arlen = 0;
    wire arready;
    wire rvalid;
    reg rready = 0;
    wire rlast;
    wire [11:0] rid;
    wire [1:0] rresp;
    wire [31:0] rdata;

    reg awvalid = 0;
    reg [11:0] awid = 0;
    wire awready;
    reg wvalid = 0;
    reg wlast = 0;
    wire wready;
    wire bvalid;
    reg bready = 0;
    wire [11:0] bid;
    wire [1:0] bresp;
    integer beat;

    axi_gp_rfu_responder dut (
        .clk(clk), .rst(rst),
        .s_arvalid(arvalid), .s_arid(arid), .s_arlen(arlen),
        .s_arready(arready), .s_rvalid(rvalid), .s_rready(rready),
        .s_rlast(rlast), .s_rid(rid), .s_rresp(rresp), .s_rdata(rdata),
        .s_awvalid(awvalid), .s_awid(awid), .s_awready(awready),
        .s_wvalid(wvalid), .s_wlast(wlast), .s_wready(wready),
        .s_bvalid(bvalid), .s_bready(bready), .s_bid(bid), .s_bresp(bresp)
    );

    initial begin
        repeat (3) @(posedge clk);
        rst <= 0;

        @(posedge clk); arid <= 12'h123; arlen <= 0; arvalid <= 1;
        @(posedge clk); while (!arready) @(posedge clk); arvalid <= 0;
        repeat (2) begin
            @(posedge clk);
            if (!rvalid || !rlast || rid != 12'h123 || rresp != 0 || rdata != 0)
                $fatal(1, "single read response mismatch");
        end
        rready <= 1;
        @(posedge clk); rready <= 0;

        @(posedge clk); arid <= 12'h456; arlen <= 3; arvalid <= 1;
        @(posedge clk); while (!arready) @(posedge clk); arvalid <= 0; rready <= 1;
        for (beat = 0; beat < 4; beat = beat + 1) begin
            @(posedge clk);
            if (!rvalid || rid != 12'h456 || (rlast != (beat == 3)))
                $fatal(1, "burst read response mismatch at beat %0d", beat);
        end
        rready <= 0;

        @(posedge clk); wvalid <= 1; wlast <= 1;
        @(posedge clk); while (!wready) @(posedge clk); wvalid <= 0; wlast <= 0;
        repeat (2) @(posedge clk);
        if (bvalid) $fatal(1, "write response asserted before AW");
        awid <= 12'h789; awvalid <= 1;
        @(posedge clk); while (!awready) @(posedge clk); awvalid <= 0;
        @(posedge clk);
        if (!bvalid || bid != 12'h789 || bresp != 0)
            $fatal(1, "write response mismatch");
        repeat (2) begin
            @(posedge clk);
            if (!bvalid) $fatal(1, "BVALID not held under backpressure");
        end
        bready <= 1;
        @(posedge clk); bready <= 0;
        @(posedge clk);
        if (bvalid) $fatal(1, "BVALID did not clear");

        $display("AXI_GP_RFU_RESPONDER_PASS");
        $finish;
    end
endmodule
