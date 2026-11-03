`timescale 1ns/1ps
// Bit-exact framer test: drives the production Hann framer with full-range int16
// I/Q (vectors/framer_stim.hex) and compares every windowed output against the
// frozen Golden `window_iq` (vectors/framer_expect.hex). Also checks that the
// frame `last` marker stays aligned with `m_valid` under periodic backpressure
// (m_ready stalling), which is the one place the 2-stage `last` carry can break.
module tb_smart_scan_framer;
    reg clk = 0; always #5 clk = ~clk;
    reg rst_n = 0;

    reg  signed [15:0] s_i = 0, s_q = 0;
    reg  s_valid = 0, s_last = 0;
    wire s_ready;
    wire signed [15:0] m_i, m_q;
    wire m_valid, m_last;
    reg  m_ready;

    reg [31:0] stim  [0:4095];
    reg [31:0] expv[0:4095];
    integer idx, accepted, fired, frames_seen, last_expect;

    smart_scan_framer dut (
        .clk(clk), .rst_n(rst_n),
        .s_i(s_i), .s_q(s_q),
        .s_valid(s_valid), .s_ready(s_ready), .s_last(s_last),
        .m_i(m_i), .m_q(m_q), .m_valid(m_valid), .m_ready(m_ready), .m_last(m_last)
    );

    // Periodic backpressure on the downstream side to exercise the last carry.
    integer cyc;
    always @(negedge clk) begin
        if (!rst_n) begin cyc = 0; m_ready = 1; end
        else begin
            cyc = cyc + 1;
            m_ready = ((cyc % 11) != 4);
        end
    end

    // Feed one sample per accepted beat; hold the current sample stable until
    // s_ready asserts (standard valid/ready contract).
    task drive_sample(input integer n);
        begin : DRIVE
            @(negedge clk);
            s_i   = $signed(stim[n][15:0]);
            s_q   = $signed(stim[n][31:16]);
            s_last = (n % 1024 == 1023);
            s_valid = 1;
            while (1) begin
                @(posedge clk);
                if (s_ready) begin
                    @(negedge clk); s_valid = 0; s_last = 0;
                    disable DRIVE;
                end
            end
        end
    endtask

    // Check every windowed output, in order, bit-exactly; track last alignment.
    always @(posedge clk) begin
        if (rst_n && m_valid && m_ready) begin
            if (m_i !== $signed(expv[fired][15:0]) ||
                m_q !== $signed(expv[fired][31:16])) begin
                $display("FRAMER_MISMATCH idx=%0d got_i=%0d got_q=%0d exp_i=%0d exp_q=%0d",
                         fired, m_i, m_q,
                         $signed(expv[fired][15:0]), $signed(expv[fired][31:16]));
                $fatal(1, "window bit-exact mismatch");
            end
            last_expect = (fired % 1024 == 1023);
            if (m_last !== last_expect) begin
                $display("FRAMER_LAST_MISALIGN idx=%0d got_last=%0b exp_last=%0b",
                         fired, m_last, last_expect);
                $fatal(1, "last misaligned with valid");
            end
            fired = fired + 1;
        end
    end

    initial begin
        $readmemh("vectors/framer_stim.hex", stim);
        $readmemh("vectors/framer_expect.hex", expv);
        idx = 0; accepted = 0; fired = 0; frames_seen = 0;
        repeat (4) @(posedge clk);
        rst_n <= 1;
        repeat (2) @(posedge clk);
        // 4 frames x 1024 samples.
        for (idx = 0; idx < 4096; idx = idx + 1)
            drive_sample(idx);
        // Wait until the last output has fired and downstream drained.
        wait (fired == 4096);
        repeat (8) @(posedge clk);
        if (fired != 4096) $fatal(1, "fired count mismatch");
        $display("TB_SMART_SCAN_FRAMER PASS fired=%0d frames=4 last_aligned=YES", fired);
        $finish;
    end
endmodule
