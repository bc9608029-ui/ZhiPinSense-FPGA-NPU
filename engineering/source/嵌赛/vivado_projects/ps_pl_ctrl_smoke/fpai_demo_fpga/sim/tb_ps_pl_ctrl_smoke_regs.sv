`timescale 1ns/1ps

module tb_ps_pl_ctrl_smoke_regs;
    localparam [31:0] BASE = 32'h400c0000;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg [31:0] awaddr = 32'h0;
    reg [31:0] awdata = 32'h0;
    reg awvalid = 1'b0;
    wire awready;
    reg [31:0] araddr = 32'h0;
    reg arvalid = 1'b0;
    wire arready;
    wire [31:0] rdata;
    wire rvalid;
    reg rready = 1'b0;

    ps_pl_ctrl_smoke_regs #(.ACTION_CYCLES(4)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .User_Reg_awwaddr(awaddr),
        .User_Reg_awwdata(awdata),
        .User_Reg_awwvalid(awvalid),
        .User_Reg_awwready(awready),
        .User_Reg_araddr(araddr),
        .User_Reg_arvalid(arvalid),
        .User_Reg_arready(arready),
        .User_Reg_rdata(rdata),
        .User_Reg_rvalid(rvalid),
        .User_Reg_rready(rready)
    );

    always #5 clk = ~clk;

    task reg_write(input [31:0] addr, input [31:0] data);
        begin
            @(negedge clk);
            awaddr  <= addr;
            awdata  <= data;
            awvalid <= 1'b1;
            do @(posedge clk); while (!awready);
            @(negedge clk);
            awvalid <= 1'b0;
        end
    endtask

    task reg_read(input [31:0] addr, output [31:0] data);
        begin
            @(negedge clk);
            araddr  <= addr;
            arvalid <= 1'b1;
            do @(posedge clk); while (!arready);
            @(negedge clk);
            arvalid <= 1'b0;
            wait (rvalid);
            data = rdata;
            @(negedge clk);
            rready <= 1'b1;
            @(negedge clk);
            rready <= 1'b0;
        end
    endtask

    reg [31:0] value;
    reg [31:0] held_value;

    initial begin
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (2) @(posedge clk);

        reg_read(BASE + 32'h00, value);
        if (value !== 32'h20260927) $fatal(1, "VERSION mismatch: %08x", value);

        reg_write(BASE + 32'h04, 32'h12345678);
        reg_read(BASE + 32'h04, value);
        if (value !== 32'h12345678) $fatal(1, "SCRATCH mismatch: %08x", value);

        reg_write(BASE + 32'h08, 32'h00000001);
        reg_read(BASE + 32'h0c, value);
        if (value[0] !== 1'b1 || value[1] !== 1'b0)
            $fatal(1, "STATUS did not enter BUSY: %08x", value);

        repeat (6) @(posedge clk);
        reg_read(BASE + 32'h0c, value);
        if (value[0] !== 1'b0 || value[1] !== 1'b1)
            $fatal(1, "STATUS did not reach DONE: %08x", value);

        reg_read(BASE + 32'h10, value);
        if (value !== 32'h00000001) $fatal(1, "RUN_COUNT mismatch: %08x", value);

        // Hold read backpressure and require response/data stability.
        @(negedge clk);
        araddr  <= BASE + 32'h04;
        arvalid <= 1'b1;
        @(posedge clk);
        @(negedge clk);
        arvalid <= 1'b0;
        wait (rvalid);
        held_value = rdata;
        repeat (3) begin
            @(posedge clk);
            if (!rvalid || rdata !== held_value)
                $fatal(1, "Read response changed under backpressure");
        end
        @(negedge clk);
        rready <= 1'b1;
        @(negedge clk);
        rready <= 1'b0;

        $display("PS_PL_CTRL_SMOKE_RTL_PASS");
        $finish;
    end
endmodule
