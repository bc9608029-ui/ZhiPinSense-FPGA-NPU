`timescale 1ns/1ps
`default_nettype none

module tb_pl_ddr_mandatory_core_engine;
    localparam integer TOTAL_SAMPLES = 19 * 1024;
    localparam integer INPUT_BEATS = TOTAL_SAMPLES / 16;
    localparam integer INPUT_BYTES = TOTAL_SAMPLES * 4;
    localparam integer OUTPUT_BEATS = 19 * 80;
    localparam integer OUTPUT_BYTES = TOTAL_SAMPLES * 5;
    localparam [31:0] INPUT_BASE = 32'h81000000;
    localparam [31:0] OUTPUT_BASE = INPUT_BASE + INPUT_BYTES;

    reg gp_clk = 0;
    reg ddr_clk = 0;
    reg core_clk = 0;
    always #5 gp_clk = ~gp_clk;
    always #2.5 ddr_clk = ~ddr_clk;
    always #10 core_clk = ~core_clk;

    reg gp_rst_n = 0;
    reg ddr_rst_n = 0;
    reg core_rst_n = 0;

    reg [31:0] reg_awaddr = 0;
    reg [31:0] reg_awdata = 0;
    reg reg_awvalid = 0;
    wire reg_awready;
    reg [31:0] reg_araddr = 0;
    reg reg_arvalid = 0;
    wire reg_arready;
    wire [31:0] reg_rdata;
    wire reg_rvalid;
    reg reg_rready = 1;

    wire [31:0] awwaddr;
    wire [511:0] awwdata;
    wire [71:0] awwinfo;
    wire awwvalid;
    reg awwready = 0;
    wire [31:0] araddr;
    wire arvalid;
    wire [31:0] arinfo;
    reg arready = 0;
    reg [511:0] rdata = 0;
    reg rvalid = 0;
    reg [31:0] rinfo = 1;
    wire rready;

    reg [31:0] iq_words [0:TOTAL_SAMPLES-1];
    reg [7:0] expected_bytes [0:OUTPUT_BYTES-1];
    integer pending_beat = 0;
    integer response_delay = 0;
    reg read_pending = 0;
    reg [15:0] read_prng = 16'h1ace;
    integer ddr_cycles = 0;
    integer captured_beats = 0;
    integer run_number = 0;
    integer lane;
    integer byte_index;
    integer relative_addr;
    reg [511:0] response_value;
    reg [31:0] rd_value;

    pl_ddr_mandatory_core_engine dut (
        .gp_clk(gp_clk), .gp_rst_n(gp_rst_n),
        .ddr_clk(ddr_clk), .ddr_global_rst_n(ddr_rst_n),
        .core_clk(core_clk), .core_global_rst_n(core_rst_n),
        .User_Reg_awwaddr(reg_awaddr), .User_Reg_awwdata(reg_awdata),
        .User_Reg_awwvalid(reg_awvalid), .User_Reg_awwready(reg_awready),
        .User_Reg_araddr(reg_araddr), .User_Reg_arvalid(reg_arvalid),
        .User_Reg_arready(reg_arready), .User_Reg_rdata(reg_rdata),
        .User_Reg_rvalid(reg_rvalid), .User_Reg_rready(reg_rready),
        .User_Ddr_awwaddr(awwaddr), .User_Ddr_awwdata(awwdata),
        .User_Ddr_awwinfo(awwinfo), .User_Ddr_awwvalid(awwvalid),
        .User_Ddr_awwready(awwready), .User_Ddr_araddr(araddr),
        .User_Ddr_arvalid(arvalid), .User_Ddr_arinfo(arinfo),
        .User_Ddr_arready(arready), .User_Ddr_rdata(rdata),
        .User_Ddr_rvalid(rvalid), .User_Ddr_rinfo(rinfo),
        .User_Ddr_rready(rready)
    );

    task write_reg;
        input [31:0] addr;
        input [31:0] data;
        begin
            @(negedge gp_clk);
            reg_awaddr = addr;
            reg_awdata = data;
            reg_awvalid = 1;
            while (!reg_awready) @(negedge gp_clk);
            @(negedge gp_clk);
            reg_awvalid = 0;
        end
    endtask

    task read_reg;
        input [31:0] addr;
        output [31:0] data;
        begin
            @(negedge gp_clk);
            reg_araddr = addr;
            reg_arvalid = 1;
            while (!reg_arready) @(negedge gp_clk);
            @(negedge gp_clk);
            reg_arvalid = 0;
            while (!reg_rvalid) @(negedge gp_clk);
            data = reg_rdata;
            @(negedge gp_clk);
        end
    endtask

    task run_one_job;
        integer wait_count;
        begin
            captured_beats = 0;
            write_reg(32'h04, 32'h2);
            write_reg(32'h0c, INPUT_BASE);
            write_reg(32'h10, INPUT_BYTES);
            write_reg(32'h14, OUTPUT_BASE);
            write_reg(32'h18, OUTPUT_BYTES);
            write_reg(32'h1c, 19);
            write_reg(32'h04, 32'h1);

            wait_count = 0;
            rd_value = 0;
            while ((rd_value & 32'h6) == 0 && wait_count < 1000000) begin
                read_reg(32'h08, rd_value);
                wait_count = wait_count + 1;
            end
            if (rd_value !== 32'h2) begin
                read_reg(32'h28, rd_value);
                $display("STATUS failure run=%0d error_code=%h beats=%0d", run_number, rd_value, captured_beats);
                read_reg(32'h20, rd_value);
                $display("failure IQ_ACCEPTED=%0d", rd_value);
                read_reg(32'h24, rd_value);
                $fatal(1, "failure TENSOR_ACCEPTED=%0d", rd_value);
            end
            read_reg(32'h20, rd_value);
            if (rd_value != TOTAL_SAMPLES)
                $fatal(1, "IQ accepted failure run=%0d got=%0d", run_number, rd_value);
            read_reg(32'h24, rd_value);
            if (rd_value != TOTAL_SAMPLES)
                $fatal(1, "Tensor accepted failure run=%0d got=%0d", run_number, rd_value);
            read_reg(32'h28, rd_value);
            if (rd_value != 0)
                $fatal(1, "Error code failure run=%0d code=%h", run_number, rd_value);
            if (captured_beats != OUTPUT_BEATS)
                $fatal(1, "DDR write count failure run=%0d got=%0d", run_number, captured_beats);
            $display("PL_DDR_ENGINE_RUN_PASS run=%0d iq=%0d tensor=%0d beats=%0d",
                     run_number, TOTAL_SAMPLES, TOTAL_SAMPLES, captured_beats);
            run_number = run_number + 1;
            repeat (20) @(posedge gp_clk);
        end
    endtask

    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            arready <= 0;
            rvalid <= 0;
            read_pending <= 0;
            response_delay <= 0;
            read_prng <= 16'h1ace;
        end else begin
            read_prng <= {read_prng[14:0], read_prng[15] ^ read_prng[13] ^ read_prng[12] ^ read_prng[10]};
            arready <= !read_pending && !rvalid && read_prng[0];
            if (arvalid && arready) begin
                if (arinfo !== 32'd1 || araddr[5:0] != 0 || araddr < INPUT_BASE ||
                    ((araddr - INPUT_BASE) >> 6) >= INPUT_BEATS)
                    $fatal(1, "Invalid read addr=%h info=%h", araddr, arinfo);
                pending_beat <= (araddr - INPUT_BASE) >> 6;
                response_delay <= read_prng[2:1];
                read_pending <= 1;
            end
            if (read_pending && !rvalid) begin
                if (response_delay == 0) begin
                    response_value = 0;
                    for (lane = 0; lane < 16; lane = lane + 1)
                        response_value[lane*32 +: 32] = iq_words[pending_beat*16 + lane];
                    rdata <= response_value;
                    rinfo <= 1;
                    rvalid <= 1;
                    read_pending <= 0;
                end else begin
                    response_delay <= response_delay - 1;
                end
            end
            if (rvalid && rready)
                rvalid <= 0;
        end
    end

    always @(posedge ddr_clk) begin
        if (ddr_rst_n && dut.output_ddr_done && !dut.output_done_d)
            $display("DDR_DONE_EDGE run=%0d started=%b in_sync=%0d out_sync=%0d beats=%0d time=%0t",
                     run_number, dut.job_started_ddr, dut.input_samples_ddr2,
                     dut.output_samples_ddr2, dut.output_ddr_accepted_beats, $time);
    end

    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            awwready <= 0;
            ddr_cycles <= 0;
        end else begin
            ddr_cycles <= ddr_cycles + 1;
            awwready <= ((ddr_cycles % 9) != 3) && ((ddr_cycles % 13) != 8);
            if (awwvalid && awwready) begin
                if (awwinfo !== {1'b0, {64{1'b1}}, 6'b0, 1'b1} ||
                    awwaddr[5:0] != 0 || awwaddr < OUTPUT_BASE ||
                    awwaddr >= OUTPUT_BASE + OUTPUT_BYTES)
                    $fatal(1, "Invalid write addr=%h info=%h", awwaddr, awwinfo);
                relative_addr = awwaddr - OUTPUT_BASE;
                for (lane = 0; lane < 64; lane = lane + 1) begin
                    byte_index = relative_addr + lane;
                    if (awwdata[lane*8 +: 8] !== expected_bytes[byte_index])
                        $fatal(1, "Golden mismatch run=%0d byte=%0d got=%h expected=%h",
                               run_number, byte_index, awwdata[lane*8 +: 8], expected_bytes[byte_index]);
                end
                captured_beats <= captured_beats + 1;
            end
        end
    end

    initial begin
        $readmemh("data/iq_input.hex", iq_words);
        $readmemh("data/expected_tensor_plddr.hex", expected_bytes);
        #100;
        gp_rst_n = 1;
        ddr_rst_n = 1;
        core_rst_n = 1;

        read_reg(32'h00, rd_value);
        if (rd_value !== 32'h20260929)
            $fatal(1, "VERSION failure got=%h", rd_value);

        run_one_job();
        run_one_job();
        $display("PL_DDR_MANDATORY_CORE_ENGINE_PASS runs=2 golden_byte_mismatches=0");
        $finish;
    end

    initial begin
        #50000000;
        $fatal(1, "Engine simulation timeout run=%0d beats=%0d", run_number, captured_beats);
    end
endmodule

`default_nettype wire
