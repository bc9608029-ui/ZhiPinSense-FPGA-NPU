`timescale 1ns/1ps
// Double-buffer PSD storage + status test: write two full frames (one per bank)
// with a known power pattern, verify readback of each bank, and verify the
// committed/status/overflow/protocol_error contract the PS relies on.
module tb_smart_scan_psd_buffers;
    reg clk = 0; always #5 clk = ~clk;
    reg rst_n = 0;

    reg        wr_valid = 0, wr_bank = 0;
    reg [9:0]  wr_addr = 0;
    reg [53:0] wr_power = 0;
    reg [31:0] frame_id = 0;
    reg        protocol_error = 0, overflow = 0;

    reg        rd_bank = 0;
    reg [9:0]  rd_addr = 0;
    wire [63:0] rd_data;

    wire [7:0]  version;
    wire [31:0] status_frame_id;
    wire        status_protocol_error, status_overflow;
    wire        committed_valid, committed_bank;

    smart_scan_psd_buffers dut (
        .clk(clk), .rst_n(rst_n),
        .wr_valid(wr_valid), .wr_bank(wr_bank), .wr_addr(wr_addr), .wr_power(wr_power),
        .frame_id(frame_id), .protocol_error(protocol_error), .overflow(overflow),
        .rd_bank(rd_bank), .rd_addr(rd_addr), .rd_data(rd_data),
        .version(version), .status_frame_id(status_frame_id),
        .status_protocol_error(status_protocol_error), .status_overflow(status_overflow),
        .committed_valid(committed_valid), .committed_bank(committed_bank)
    );

    integer i;

    task write_bank(input integer bank);
        integer k;
        begin
            for (k = 0; k < 1024; k = k + 1) begin
                @(negedge clk);
                wr_valid = 1; wr_bank = bank[0]; wr_addr = k[9:0];
                wr_power = (bank * 1024) + k;   // unique 54-bit pattern per (bank,addr)
            end
            @(negedge clk); wr_valid = 0;
        end
    endtask

    task check_bank(input integer bank);
        integer k;
        begin
            rd_bank = bank[0];
            for (k = 0; k < 1024; k = k + 1) begin
                rd_addr = k[9:0];
                #1;   // combinational read settle
                if (rd_data !== {10'b0, (54'd0 + (bank * 1024) + k)}) begin
                    $display("BUFFER_MISMATCH bank=%0d addr=%0d got=%0d exp=%0d",
                             bank, k, rd_data, {10'b0, (54'd0 + (bank * 1024) + k)});
                    $fatal(1, "readback mismatch");
                end
                @(negedge clk);
            end
        end
    endtask

    initial begin
        repeat (4) @(posedge clk);
        rst_n <= 1;
        @(negedge clk);

        // Reset state: no committed frame, clean status, version 1.
        if (version !== 8'h01) $fatal(1, "version");
        if (committed_valid !== 1'b0) $fatal(1, "committed_valid should be 0 at reset");
        if (status_frame_id !== 32'd0) $fatal(1, "status_frame_id should be 0 at reset");
        if (status_protocol_error || status_overflow) $fatal(1, "sticky flags should be 0");

        // Frame 0 into bank 0; mid-frame, frame_id still 0 -> not committed.
        write_bank(0);
        frame_id = 32'd0;
        @(negedge clk);
        if (committed_valid !== 1'b0) $fatal(1, "committed_valid must be 0 mid-frame-0");

        // Frame 0 completes -> frame_id 1 -> committed_bank 0.
        frame_id = 32'd1;
        @(negedge clk);
        if (committed_valid !== 1'b1) $fatal(1, "committed_valid should be 1");
        if (committed_bank !== 1'b0) $fatal(1, "committed_bank should be 0 after frame 0");
        check_bank(0);

        // Frame 1 into bank 1; completes -> frame_id 2 -> committed_bank 1.
        write_bank(1);
        frame_id = 32'd2;
        @(negedge clk);
        if (committed_bank !== 1'b1) $fatal(1, "committed_bank should be 1 after frame 1");
        check_bank(1);

        // Sticky protocol_error and overflow.
        protocol_error = 1'b1; overflow = 1'b1;
        @(negedge clk);
        protocol_error = 1'b0; overflow = 1'b0;
        @(negedge clk); @(negedge clk);
        if (!status_protocol_error) $fatal(1, "protocol_error should be sticky");
        if (!status_overflow) $fatal(1, "overflow should be sticky");

        $display("TB_SMART_SCAN_PSD_BUFFERS PASS banks=2 words=2048 committed_ok=YES sticky_ok=YES");
        $finish;
    end
endmodule
