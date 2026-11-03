`timescale 1ns/1ps
`default_nettype none

// Diagnostic-only testbench: drives the same two jobs as the release tb, but
// instruments the internal counters and per-job resets so the repeated-job
// data-loss root cause can be observed directly.  This file is throwaway
// diagnostic code; it does not alter any release source file.
module tb_diag;
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

    // ---- instrumentation ------------------------------------------------
    // Watch the two per-job reset sources for every assertion edge.
    reg prev_core_job_rst_n = 1;
    reg prev_ddr_job_rst_n  = 1;
    integer core_reset_asserts = 0;
    integer ddr_reset_asserts  = 0;
    always @(posedge core_clk) begin
        if (prev_core_job_rst_n && !dut.core_job_rst_n) begin
            core_reset_asserts = core_reset_asserts + 1;
            $display("DIAG [%0t] core_job_rst_n ASSERT (#%0d)", $time, core_reset_asserts);
        end else if (!prev_core_job_rst_n && dut.core_job_rst_n) begin
            $display("DIAG [%0t] core_job_rst_n RELEASE", $time);
        end
        prev_core_job_rst_n <= dut.core_job_rst_n;
    end
    always @(posedge ddr_clk) begin
        if (prev_ddr_job_rst_n && !dut.ddr_job_rst_n) begin
            ddr_reset_asserts = ddr_reset_asserts + 1;
            $display("DIAG [%0t] ddr_job_rst_n ASSERT (#%0d)", $time, ddr_reset_asserts);
        end else if (!prev_ddr_job_rst_n && dut.ddr_job_rst_n) begin
            $display("DIAG [%0t] ddr_job_rst_n RELEASE", $time);
        end
        prev_ddr_job_rst_n <= dut.ddr_job_rst_n;
    end

    // Watch the accepted-sample counters for any backward jump (a reset).
    reg [31:0] prev_in_ctr = 0;
    reg [31:0] prev_out_ctr = 0;
    always @(posedge core_clk) begin
        if (dut.input_accepted_samples < prev_in_ctr)
            $display("DIAG [%0t] INPUT  counter RESET: %0d -> %0d", $time,
                     prev_in_ctr, dut.input_accepted_samples);
        prev_in_ctr <= dut.input_accepted_samples;
        if (dut.output_core_accepted_samples < prev_out_ctr)
            $display("DIAG [%0t] OUTPUT counter RESET: %0d -> %0d", $time,
                     prev_out_ctr, dut.output_core_accepted_samples);
        prev_out_ctr <= dut.output_core_accepted_samples;
    end

    // ---- register access tasks ------------------------------------------
    task write_reg;
        input [31:0] addr;
        input [31:0] data;
        begin
            @(negedge gp_clk);
            reg_awaddr = addr; reg_awdata = data; reg_awvalid = 1;
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
            reg_araddr = addr; reg_arvalid = 1;
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
            read_reg(32'h20, rd_value);
            $display("DIAG run=%0d IQ_ACCEPTED=%0d", run_number, rd_value);
            read_reg(32'h24, rd_value);
            $display("DIAG run=%0d TENSOR_ACCEPTED=%0d", run_number, rd_value);
            read_reg(32'h28, rd_value);
            $display("DIAG run=%0d ERROR_CODE=%h beats=%0d", run_number, rd_value, captured_beats);
            $display("DIAG run=%0d core_reset_asserts=%0d ddr_reset_asserts=%0d",
                     run_number, core_reset_asserts, ddr_reset_asserts);
            run_number = run_number + 1;
            repeat (20) @(posedge gp_clk);
        end
    endtask

    // ---- DDR read responder ----------------------------------------------
    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            arready <= 0; rvalid <= 0; read_pending <= 0;
            response_delay <= 0; read_prng <= 16'h1ace;
        end else begin
            read_prng <= {read_prng[14:0], read_prng[15] ^ read_prng[13] ^ read_prng[12] ^ read_prng[10]};
            arready <= !read_pending && !rvalid && read_prng[0];
            if (arvalid && arready) begin
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

    // ---- DDR write responder (beat count only, no golden compare) -------
    always @(posedge ddr_clk) begin
        if (!ddr_rst_n) begin
            awwready <= 0; ddr_cycles <= 0;
        end else begin
            ddr_cycles <= ddr_cycles + 1;
            awwready <= ((ddr_cycles % 9) != 3) && ((ddr_cycles % 13) != 8);
            if (awwvalid && awwready)
                captured_beats <= captured_beats + 1;
        end
    end

    initial begin
        $readmemh("data/iq_input.hex", iq_words);
        $readmemh("data/expected_tensor_plddr.hex", expected_bytes);
        #100;
        gp_rst_n = 1; ddr_rst_n = 1; core_rst_n = 1;
        run_one_job();
        run_one_job();
        $display("DIAG DONE runs=2");
        $finish;
    end

    initial begin
        #50000000;
        $fatal(1, "diag timeout");
    end
endmodule

`default_nettype wire
