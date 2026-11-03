`timescale 1ns/1ps

module tb_iq_stream_fifo;
    reg clk = 0;
    reg rst_n = 0;
    reg signed [15:0] s_i = 0, s_q = 0;
    reg s_error = 0, s_valid = 0, s_overflow_event = 0;
    wire s_ready;
    wire signed [15:0] m_i, m_q;
    wire m_error, m_valid;
    reg m_ready = 0;
    wire [1:0] occupancy;
    wire [31:0] overflow_count;

    always #5 clk = ~clk;

    iq_stream_fifo #(.DEPTH(2)) dut (
        .clk(clk), .rst_n(rst_n), .s_i(s_i), .s_q(s_q), .s_error(s_error),
        .s_valid(s_valid), .s_ready(s_ready), .s_overflow_event(s_overflow_event),
        .m_i(m_i), .m_q(m_q), .m_error(m_error), .m_valid(m_valid),
        .m_ready(m_ready), .occupancy(occupancy), .overflow_count(overflow_count)
    );

    task automatic push;
        input integer value;
        begin
            @(negedge clk);
            if (!s_ready) $fatal(1, "FIFO unexpectedly full");
            s_i = 16'(value);
            s_q = 16'(-value);
            s_valid = 1'b1;
            @(posedge clk); #1;
            @(negedge clk);
            s_valid = 1'b0;
        end
    endtask

    task automatic pop_and_check;
        input integer expected;
        begin
            @(negedge clk);
            if (!m_valid || $signed(m_i) !== 16'(expected)) $fatal(1, "FIFO order mismatch");
            m_ready = 1'b1;
            @(posedge clk); #1;
            @(negedge clk);
            m_ready = 1'b0;
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        push(11);
        push(22);
        if (s_ready || occupancy !== 2) $fatal(1, "FIFO full state mismatch");

        // A full FIFO with no explicit drop event is ordinary backpressure.
        @(negedge clk); s_valid = 1'b1; s_i = 33; s_overflow_event = 1'b0;
        @(posedge clk); #1;
        if (overflow_count !== 0) $fatal(1, "Backpressure counted as overflow");

        // Only the adapter's explicit sample-drop event increments the counter.
        @(negedge clk); s_overflow_event = 1'b1;
        @(posedge clk); #1;
        @(negedge clk); s_overflow_event = 1'b0; s_valid = 1'b0;
        if (overflow_count !== 1) $fatal(1, "Explicit overflow was not counted");

        pop_and_check(11);
        pop_and_check(22);
        if (m_valid || occupancy !== 0) $fatal(1, "FIFO empty state mismatch");
        $display("PASS tb_iq_stream_fifo");
        $finish;
    end
endmodule
