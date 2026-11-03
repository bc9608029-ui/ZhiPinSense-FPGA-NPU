`timescale 1ns/1ps
// Real vendor FFT verification: drives smart_scan_top (Hann framer -> Xilinx
// XFFT 9.1 behavioural sim netlist -> u54 magnitude-square -> fftshift double
// buffer) with deterministic int16 IQ frames and checks the fftshift PSD against
// NumPy-computed peak bins. The FFT direction contract is the core check:
//   +37-bin tone -> natural bin 37  -> fftshift bin 549
//   -37-bin tone -> natural bin 987 -> fftshift bin 475
// a mirrored result (549<->475 swapped) means the transform ran inverse.
//
// Clean cases (with a PSD dump for the NumPy tolerance cross-check):
//   tone_pos37 / tone_neg37 / tone_dc / tone_bin511 / dual_tone / random /
//   multi_frame (3 frames) / zero / pulse
// Fault cases (latched into status_overflow via fft data_halt):
//   short_frame (early tlast -> event_tlast_unexpected)
//   bubble      (mid-frame valid drop -> event_data_in_channel_halt, i.e.
//                INPUT starvation, not "output too slow")
//   reset_recovery (mid-frame reset, then a clean frame must still pass)
//
// Stimulus is read from ASCII hex files in the current working directory
// (copied there by scripts/simulate_real_fft.ps1); the full PSD of every frame
// is dumped to psd_<case>.hex for the NumPy tolerance cross-check.
module tb_smart_scan_real_fft;
    reg clk = 0; always #5 clk = ~clk;          // 100 MHz
    reg rst_n = 0;
    reg [31:0] iq = 0;
    reg valid = 0, last = 0;
    wire ready;
    reg bank = 0;
    reg [9:0] addr = 0;
    wire [63:0] data;
    wire [7:0] version;
    wire [31:0] dut_frame_id;
    wire proto, overflow, committed, committed_bank;

    smart_scan_top dut (
        .clk(clk), .rst_n(rst_n),
        .s_axis_iq_tdata(iq), .s_axis_iq_tvalid(valid), .s_axis_iq_tready(ready),
        .s_axis_iq_tlast(last), .rd_bank(bank), .rd_addr(addr), .rd_data(data),
        .version(version), .status_frame_id(dut_frame_id),
        .status_protocol_error(proto), .status_overflow(overflow),
        .committed_valid(committed), .committed_bank(committed_bank));

    reg [31:0] stim [0:4095];
    integer npass, nfail, tone_count, fault_count;

    task do_reset;
        begin
            valid = 0; last = 0; iq = 32'd0;
            bank = 0; addr = 0;
            rst_n = 0;
            repeat (8) @(posedge clk);
            rst_n = 1;
            repeat (8) @(posedge clk);
        end
    endtask

    task load_stim(input string casename);
        begin
            $readmemh($sformatf("%s.stim.hex", casename), stim);
        end
    endtask

    // Drive exactly frame_len samples from stim[offset], asserting tlast on the
    // last sample, then deassert valid. Handshakes on `ready`.
    task drive_frame(input integer offset, input integer frame_len);
        integer n;
        begin
            n = 0;
            @(negedge clk);
            iq = stim[offset];
            valid = 1;
            last = (frame_len == 1);
            while (n < frame_len) begin
                @(posedge clk);
                if (ready) begin
                    n = n + 1;
                    @(negedge clk);
                    if (n < frame_len) begin
                        iq = stim[offset + n];
                        last = (n == frame_len - 1);
                    end else begin
                        valid = 0; last = 0;
                    end
                end else begin
                    @(negedge clk);
                end
            end
        end
    endtask

    // Drive nsamples WITHOUT tlast, then deassert valid (abandoned partial frame).
    task drive_partial(input integer offset, input integer nsamples);
        integer n;
        begin
            n = 0;
            @(negedge clk);
            iq = stim[offset];
            valid = 1; last = 0;
            while (n < nsamples) begin
                @(posedge clk);
                if (ready) begin
                    n = n + 1;
                    @(negedge clk);
                    if (n < nsamples) iq = stim[offset + n];
                end else begin
                    @(negedge clk);
                end
            end
            @(negedge clk);
            valid = 0; last = 0;
        end
    endtask

    // Read the currently-selected committed bank into an open file descriptor,
    // returning the peak bin/power and the second bin for diagnostics.
    task read_bank_fd(input integer fd, output integer peak_bin,
                      output reg [63:0] peak, output integer top2b);
        integer k;
        reg [63:0] word, max1, max2;
        integer max1_bin, max2_bin;
        begin
            max1 = 64'd0; max2 = 64'd0; max1_bin = -1; max2_bin = -1;
            for (k = 0; k < 1024; k = k + 1) begin
                addr = k; #1;
                word = data;
                $fwrite(fd, "%h\n", word);
                if (word > max1) begin
                    max2 = max1; max2_bin = max1_bin;
                    max1 = word; max1_bin = k;
                end else if (word > max2) begin
                    max2 = word; max2_bin = k;
                end
                @(negedge clk);
            end
            peak_bin = max1_bin; peak = max1; top2b = max2_bin;
        end
    endtask

    // Wait for frame `expect_frame` (1-based) to commit, then read its bank.
    task read_committed(input string dumpfile, input integer expect_frame,
                        output integer peak_bin, output reg [63:0] peak,
                        output integer top2b);
        integer fd;
        begin
            wait (dut_frame_id >= expect_frame);
            @(negedge clk);
            bank = committed_bank;
            fd = $fopen(dumpfile, "w");
            read_bank_fd(fd, peak_bin, peak, top2b);
            $fclose(fd);
        end
    endtask

    task check_clean(input string casename, input integer peak_bin);
        begin
            if (proto || overflow) begin
                $display("REAL_FFT_CASE FAIL case=%s proto=%0b overflow=%0b",
                         casename, proto, overflow);
                $fatal(1, "REAL_FFT protocol/overflow fault on clean frame");
            end
            npass = npass + 1;
            $display("REAL_FFT_CASE PASS case=%s peak_bin=%0d", casename, peak_bin);
        end
    endtask

    // Single clean frame with an exact expected fftshift peak bin.
    task run_peak(input string casename, input integer expect_peak);
        integer peak_bin, t2b;
        reg [63:0] peak;
        begin
            load_stim(casename);
            do_reset;
            drive_frame(0, 1024);
            read_committed($sformatf("psd_%s.hex", casename), 1, peak_bin, peak, t2b);
            if (peak_bin != expect_peak) begin
                $display("REAL_FFT_CASE FAIL case=%s expect_peak=%0d got=%0d peak=%h",
                         casename, expect_peak, peak_bin, peak);
                $fatal(1, "REAL_FFT peak bin mismatch");
            end
            check_clean(casename, peak_bin);
            if (casename == "tone_pos37" || casename == "tone_neg37")
                tone_count = tone_count + 1;
        end
    endtask

    // Single clean frame whose peak must be one of two equal-magnitude bins
    // (dual tone: +37 and -37 both present).
    task run_peak_any(input string casename, input integer a, input integer b);
        integer peak_bin, t2b;
        reg [63:0] peak;
        begin
            load_stim(casename);
            do_reset;
            drive_frame(0, 1024);
            read_committed($sformatf("psd_%s.hex", casename), 1, peak_bin, peak, t2b);
            if (peak_bin != a && peak_bin != b) begin
                $display("REAL_FFT_CASE FAIL case=%s expect={%0d,%0d} got=%0d peak=%h",
                         casename, a, b, peak_bin, peak);
                $fatal(1, "REAL_FFT peak bin mismatch (any-of)");
            end
            check_clean(casename, peak_bin);
        end
    endtask

    // Clean frame with no meaningful unique peak (flat or all-zero spectrum):
    // dump only, require no fault.
    task run_flat(input string casename);
        integer peak_bin, t2b;
        reg [63:0] peak;
        begin
            load_stim(casename);
            do_reset;
            drive_frame(0, 1024);
            read_committed($sformatf("psd_%s.hex", casename), 1, peak_bin, peak, t2b);
            check_clean(casename, peak_bin);
        end
    endtask

    // Multiple back-to-back frames through one FFT instance (no reset between),
    // reading each committed bank before the next frame overwrites the other
    // bank. Every frame must land on the same peak bin.
    task run_multi(input string casename, input integer frames,
                   input integer expect_peak);
        integer fd, f, peak_bin, t2b;
        reg [63:0] peak;
        begin
            load_stim(casename);
            do_reset;
            fd = $fopen($sformatf("psd_%s.hex", casename), "w");
            for (f = 0; f < frames; f = f + 1) begin
                drive_frame(f * 1024, 1024);
                wait (dut_frame_id >= f + 1);
                @(negedge clk);
                bank = committed_bank;
                read_bank_fd(fd, peak_bin, peak, t2b);
                if (peak_bin != expect_peak) begin
                    $display("REAL_FFT_CASE FAIL case=%s frame=%0d expect_peak=%0d got=%0d peak=%h",
                             casename, f, expect_peak, peak_bin, peak);
                    $fatal(1, "REAL_FFT multi-frame peak bin mismatch");
                end
                $display("REAL_FFT_CASE PASS case=%s frame=%0d peak_bin=%0d",
                         casename, f, peak_bin);
                npass = npass + 1;
            end
            $fclose(fd);
            if (proto || overflow) begin
                $display("REAL_FFT_CASE FAIL case=%s proto=%0b overflow=%0b",
                         casename, proto, overflow);
                $fatal(1, "REAL_FFT protocol/overflow fault on multi-frame");
            end
        end
    endtask

    // Early tlast on a 100-sample frame -> event_tlast_unexpected -> overflow.
    task run_short_frame;
        begin
            load_stim("tone_pos37");
            do_reset;
            drive_frame(0, 100);                 // tlast asserted on sample 100
            repeat (2000) @(posedge clk);
            if (!overflow) begin
                $display("REAL_FFT_FAULT FAIL case=short_frame overflow=%0b", overflow);
                $fatal(1, "short frame did not latch tlast-unexpected fault");
            end
            $display("REAL_FFT_FAULT PASS case=short_frame overflow=%0b", overflow);
            fault_count = fault_count + 1;
        end
    endtask

    // Mid-frame valid bubble -> event_data_in_channel_halt (INPUT starvation)
    // -> overflow.  Distinct from any output-side term.
    task run_bubble;
        begin
            load_stim("tone_pos37");
            do_reset;
            drive_partial(0, 500);               // 500 samples, no tlast
            @(negedge clk); valid = 0;           // starve the input
            repeat (32) @(posedge clk);
            repeat (2000) @(posedge clk);
            if (!overflow) begin
                $display("REAL_FFT_FAULT FAIL case=bubble overflow=%0b", overflow);
                $fatal(1, "input bubble did not latch channel-halt fault");
            end
            $display("REAL_FFT_FAULT PASS case=bubble overflow=%0b", overflow);
            fault_count = fault_count + 1;
        end
    endtask

    // Reset mid-frame, then a clean full frame must still pass (recovery +
    // config re-application after reset).
    task run_reset_recovery;
        integer peak_bin, t2b;
        reg [63:0] peak;
        begin
            load_stim("tone_pos37");
            do_reset;
            drive_partial(0, 300);               // abandoned partial frame
            rst_n = 0;
            repeat (8) @(posedge clk);
            rst_n = 1;
            repeat (8) @(posedge clk);
            drive_frame(0, 1024);                // clean frame after reset
            read_committed("psd_reset_recovery.hex", 1, peak_bin, peak, t2b);
            if (peak_bin != 549 || proto || overflow) begin
                $display("REAL_FFT_FAULT FAIL case=reset_recovery peak=%0d proto=%0b overflow=%0b",
                         peak_bin, proto, overflow);
                $fatal(1, "reset recovery failed");
            end
            $display("REAL_FFT_FAULT PASS case=reset_recovery peak_bin=%0d", peak_bin);
            fault_count = fault_count + 1;
            npass = npass + 1;
        end
    endtask

    initial begin : main
        npass = 0; nfail = 0; tone_count = 0; fault_count = 0;

        // --- direction contract (the two bins that must not mirror) ---------
        run_peak("tone_pos37", 549);
        run_peak("tone_neg37", 475);
        if (tone_count != 2) $fatal(1, "tone cases did not both run");

        // --- more clean cases -----------------------------------------------
        run_peak("tone_dc", 512);
        run_peak("tone_bin511", 1023);           // natural bin 511 -> fftshift 1023
        run_peak_any("dual_tone", 549, 475);
        run_peak("random", 835);
        run_multi("multi_frame", 3, 549);
        run_flat("zero");
        run_flat("pulse");

        // --- fault cases ----------------------------------------------------
        run_short_frame;
        run_bubble;
        run_reset_recovery;

        if (fault_count != 3) $fatal(1, "fault cases did not all run");
        $display("TB_SMART_SCAN_REAL_FFT PASS tones=2 cases=%0d faults=%0d",
                 npass, fault_count);
        $finish;
    end

    initial begin
        #20000000;
        $fatal(1, "real FFT timeout (20000000 ns)");
    end
endmodule
