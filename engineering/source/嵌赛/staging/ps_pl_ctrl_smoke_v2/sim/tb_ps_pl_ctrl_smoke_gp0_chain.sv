`timescale 1ns/1ps

module tb_ps_pl_ctrl_smoke_gp0_chain;
    localparam [31:0] BASE = 32'h400c0000;

    reg clk = 1'b0;
    reg rst = 1'b1;
    always #5 clk = ~clk;

    reg arvalid = 0;
    reg awvalid = 0;
    reg bready = 0;
    reg rready = 0;
    reg wlast = 0;
    reg wvalid = 0;
    reg [11:0] arid = 0;
    reg [11:0] awid = 0;
    reg [11:0] wid = 0;
    reg [1:0] arburst = 1;
    reg [1:0] arlock = 0;
    reg [2:0] arsize = 2;
    reg [1:0] awburst = 1;
    reg [1:0] awlock = 0;
    reg [2:0] awsize = 2;
    reg [2:0] arprot = 0;
    reg [2:0] awprot = 0;
    reg [31:0] araddr = 0;
    reg [31:0] awaddr = 0;
    reg [31:0] wdata = 0;
    reg [3:0] arcache = 0;
    reg [3:0] arlen = 0;
    reg [3:0] arqos = 0;
    reg [3:0] awcache = 0;
    reg [3:0] awlen = 0;
    reg [3:0] awqos = 0;
    reg [3:0] wstrb = 4'hf;

    wire aclk;
    wire arready;
    wire awready;
    wire bvalid;
    wire rlast;
    wire rvalid;
    wire wready;
    wire [11:0] bid;
    wire [11:0] rid;
    wire [1:0] bresp;
    wire [1:0] rresp;
    wire [31:0] rdata;

    mna_gp_ww_itf gp0();
    mna_gp_ww_itf host_ctrl();
    mna_gp_ww_itf ai_ra();
    mna_gp_ww_itf cam();
    mna_gp_ww_itf user_op();

    wire [31:0] reg_awaddr = user_op.awwaddr;
    wire [31:0] reg_awdata = user_op.awwdata;
    wire reg_awvalid = user_op.awwvalid;
    wire reg_awready;
    wire [31:0] reg_araddr = user_op.araddr;
    wire reg_arvalid = user_op.arvalid;
    wire reg_arready;
    wire [31:0] reg_rdata;
    wire reg_rvalid;
    wire reg_rready = user_op.rready;

    assign user_op.awwready = reg_awready;
    assign user_op.arready = reg_arready;
    assign user_op.rdata = reg_rdata;
    assign user_op.rvalid = reg_rvalid;

    gp_io u_gp0_io (
        .M_AXI_GP_ARVALID(arvalid), .M_AXI_GP_AWVALID(awvalid),
        .M_AXI_GP_BREADY(bready), .M_AXI_GP_RREADY(rready),
        .M_AXI_GP_WLAST(wlast), .M_AXI_GP_WVALID(wvalid),
        .M_AXI_GP_ARID(arid), .M_AXI_GP_AWID(awid), .M_AXI_GP_WID(wid),
        .M_AXI_GP_ARBURST(arburst), .M_AXI_GP_ARLOCK(arlock),
        .M_AXI_GP_ARSIZE(arsize), .M_AXI_GP_AWBURST(awburst),
        .M_AXI_GP_AWLOCK(awlock), .M_AXI_GP_AWSIZE(awsize),
        .M_AXI_GP_ARPROT(arprot), .M_AXI_GP_AWPROT(awprot),
        .M_AXI_GP_ARADDR(araddr), .M_AXI_GP_AWADDR(awaddr),
        .M_AXI_GP_WDATA(wdata), .M_AXI_GP_ARCACHE(arcache),
        .M_AXI_GP_ARLEN(arlen), .M_AXI_GP_ARQOS(arqos),
        .M_AXI_GP_AWCACHE(awcache), .M_AXI_GP_AWLEN(awlen),
        .M_AXI_GP_AWQOS(awqos), .M_AXI_GP_WSTRB(wstrb),
        .M_AXI_GP_ACLK(aclk), .M_AXI_GP_ARREADY(arready),
        .M_AXI_GP_AWREADY(awready), .M_AXI_GP_BVALID(bvalid),
        .M_AXI_GP_RLAST(rlast), .M_AXI_GP_RVALID(rvalid),
        .M_AXI_GP_WREADY(wready), .M_AXI_GP_BID(bid),
        .M_AXI_GP_RID(rid), .M_AXI_GP_BRESP(bresp),
        .M_AXI_GP_RRESP(rresp), .M_AXI_GP_RDATA(rdata),
        .gp(gp0.master), .gp_clk_rst(rst), .gp_clk(clk)
    );

    gp0_manager #(.GP0_BASE(32'h40000000)) u_gp0_manager (
        .gpx(gp0.slave), .host_ctrl(host_ctrl.master),
        .ai_ra(ai_ra.master), .m2_gpx(cam.master),
        .m3_gpx(user_op.master), .gpx_rst(rst), .gpx_clk(clk)
    );

    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_host (
        .gpx(host_ctrl.slave), .gpx_rst(rst), .gpx_clk(clk));
    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_ai (
        .gpx(ai_ra.slave), .gpx_rst(rst), .gpx_clk(clk));
    gpx_RFU #(.ERR(32'hA0AAAAAA)) u_cam (
        .gpx(cam.slave), .gpx_rst(rst), .gpx_clk(clk));

    ps_pl_ctrl_smoke_regs #(.ACTION_CYCLES(4)) u_regs (
        .clk(clk), .rst_n(~rst),
        .User_Reg_awwaddr(reg_awaddr), .User_Reg_awwdata(reg_awdata),
        .User_Reg_awwvalid(reg_awvalid), .User_Reg_awwready(reg_awready),
        .User_Reg_araddr(reg_araddr), .User_Reg_arvalid(reg_arvalid),
        .User_Reg_arready(reg_arready), .User_Reg_rdata(reg_rdata),
        .User_Reg_rvalid(reg_rvalid), .User_Reg_rready(reg_rready)
    );

    task automatic axi_write(input [31:0] addr, input [31:0] data);
        integer timeout;
        begin
            @(negedge clk);
            awaddr = addr;
            awid = 12'h321;
            awvalid = 1;
            wdata = data;
            wid = 12'h321;
            wlast = 1;
            wvalid = 1;
            bready = 1;
            timeout = 0;
            while (!(awready && wready) && timeout < 40) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (timeout == 40) $fatal(1, "AXI write address/data handshake timeout");
            @(negedge clk);
            awvalid = 0;
            wvalid = 0;
            timeout = 0;
            while (!bvalid && timeout < 40) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (timeout == 40) $fatal(1, "AXI write response timeout");
            if (bid !== 12'h321 || bresp !== 2'b00)
                $fatal(1, "AXI write response mismatch");
            @(negedge clk);
            bready = 0;
        end
    endtask

    task automatic axi_read(input [31:0] addr, output [31:0] data);
        integer timeout;
        begin
            @(negedge clk);
            araddr = addr;
            arid = 12'h123;
            arvalid = 1;
            rready = 0;
            timeout = 0;
            while (!arready && timeout < 40) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (timeout == 40) $fatal(1, "AXI read address handshake timeout");
            @(negedge clk);
            arvalid = 0;
            timeout = 0;
            while (!rvalid && timeout < 40) begin
                @(posedge clk);
                timeout = timeout + 1;
            end
            if (timeout == 40) $fatal(1, "AXI read response timeout");
            data = rdata;
            if (rid !== 12'h123 || rresp !== 2'b00 || !rlast)
                $fatal(1, "AXI read response metadata mismatch");
            repeat (3) begin
                @(posedge clk);
                if (!rvalid || rdata !== data)
                    $fatal(1, "AXI read response not stable under backpressure");
            end
            @(negedge clk);
            rready = 1;
            @(negedge clk);
            rready = 0;
        end
    endtask

    reg [31:0] value;
    initial begin
        repeat (5) @(posedge clk);
        rst = 0;
        repeat (4) @(posedge clk);

        axi_read(BASE + 0, value);
        if (value !== 32'h20260927) $fatal(1, "VERSION mismatch %08x", value);

        axi_write(BASE + 4, 32'h12345678);
        axi_read(BASE + 4, value);
        if (value !== 32'h12345678) $fatal(1, "SCRATCH mismatch %08x", value);

        axi_write(BASE + 8, 32'h1);
        repeat (8) @(posedge clk);
        axi_read(BASE + 12, value);
        if (value[1:0] !== 2'b10) $fatal(1, "STATUS mismatch %08x", value);
        axi_read(BASE + 16, value);
        if (value !== 1) $fatal(1, "RUN_COUNT mismatch %08x", value);

        axi_read(32'h40080000, value);
        if (value !== 32'hA0AAAAAA) $fatal(1, "RFU routing mismatch %08x", value);

        $display("PS_PL_CTRL_SMOKE_GP0_CHAIN_PASS");
        $finish;
    end
endmodule
