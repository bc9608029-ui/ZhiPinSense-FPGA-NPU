`timescale 1ns/1ps
`default_nettype none

// Behavioral simulation models for the two clock primitives used by the
// formal board top.  Synthesis uses the actual Xilinx UNISIM primitives.
module IBUFDS #(
    parameter DIFF_TERM = "FALSE",
    parameter IBUF_LOW_PWR = "TRUE",
    parameter IOSTANDARD = "DEFAULT"
) (
    input  wire I,
    input  wire IB,
    output wire O
);
    assign O = I;
endmodule

module BUFG (
    input  wire I,
    output wire O
);
    assign O = I;
endmodule

// Functional model of the 200 MHz -> 50 MHz Clocking Wizard used by the
// synthesizable board top.  The Vivado project supplies the generated IP;
// this test model only supplies divided-clock and LOCKED behavior.
module clk_wiz_0 (
    output wire clk_out1,
    output wire locked,
    input  wire reset,
    input  wire clk_in1
);
    reg clkout0_reg = 1'b0;
    reg locked_reg = 1'b0;
    reg [1:0] divide_count = 2'd0;
    reg [3:0] lock_count = 4'd0;

    assign clk_out1 = clkout0_reg;
    assign locked = locked_reg;

    always @(posedge clk_in1 or posedge reset) begin
        if (reset) begin
            clkout0_reg <= 1'b0;
            locked_reg <= 1'b0;
            divide_count <= 2'd0;
            lock_count <= 4'd0;
        end else begin
            if (divide_count == 2'd1) begin
                divide_count <= 2'd0;
                clkout0_reg <= ~clkout0_reg;
            end else begin
                divide_count <= divide_count + 1'b1;
            end
            if (!locked_reg) begin
                if (lock_count == 4'd7)
                    locked_reg <= 1'b1;
                else
                    lock_count <= lock_count + 1'b1;
            end
        end
    end
endmodule

module tb_board_mandatory_core_test_top;
    localparam integer FRAME_LENGTH = 1024;
    localparam integer FRAME_COUNT = 19;
    localparam integer TOTAL_SAMPLES = FRAME_LENGTH * FRAME_COUNT;

    reg sys_clk_p = 1'b0;
    wire sys_clk_n = ~sys_clk_p;
    reg pl_key1_reset = 1'b1;
    wire [3:0] led;

    reg [31:0] expected_iq [0:TOTAL_SAMPLES-1];
    integer tensor_file;
    integer input_count = 0;
    integer output_count = 0;
    integer completed_frames = 0;
    integer stall_cycles = 0;
    integer release_checks = 0;
    integer release_buffer = 0;
    reg release_expected = 1'b0;
    reg validation_active = 1'b0;
    reg stalled_last_check = 1'b0;
    reg [14:0] stalled_address = 15'd0;
    reg [31:0] stalled_data = 32'd0;
    reg saw_forced_stall = 1'b0;
    time last_clock_rise = 0;

    always #2.5 sys_clk_p = ~sys_clk_p;

    board_mandatory_core_test_top #(
        .ROM_INIT_FILE("vectors/iq_input.hex")
    ) dut (
        .sys_clk_p(sys_clk_p),
        .sys_clk_n(sys_clk_n),
        .pl_key1_reset(pl_key1_reset),
        .led(led)
    );

    always @(posedge dut.core_clk)
        last_clock_rise = $time;

    // A rising reset release is legal only on a core-clock edge.
    always @(posedge dut.core_rst_n) begin
        if ($time != last_clock_rise)
            $fatal(1, "core_rst_n deasserted asynchronously at time %0t", $time);
    end

    // Verify every accepted replay word.  This directly proves address zero,
    // source ordering, and absence of skipped or duplicated IQ samples.
    always @(posedge dut.core_clk) begin
        if (validation_active && dut.core_rst_n && dut.replay_valid && dut.replay_ready) begin
            if (input_count >= TOTAL_SAMPLES)
                $fatal(1, "extra replay transfer after sample %0d", TOTAL_SAMPLES - 1);
            if (dut.rom_address !== input_count[14:0])
                $fatal(1, "replay address mismatch got=%0d expected=%0d", dut.rom_address, input_count);
            if ({dut.replay_q, dut.replay_i} !== expected_iq[input_count])
                $fatal(1, "IQ mismatch at input row %0d", input_count);
            input_count = input_count + 1;
        end
    end

    // The complete tensor capture uses exactly the board-comparator schema.
    always @(posedge dut.core_clk) begin
        if (!dut.core_rst_n) begin
            release_expected = 1'b0;
            release_buffer = 0;
        end else if (validation_active) begin
            if (release_expected) begin
                if (dut.buffer_release_reg !== (2'b01 << release_buffer))
                    $fatal(1, "missing/wrong delayed buffer release for buffer %0d", release_buffer);
                release_checks = release_checks + 1;
            end else if (dut.buffer_release_reg !== 2'b00) begin
                $fatal(1, "unexpected buffer release pulse %b", dut.buffer_release_reg);
            end

            release_expected = dut.m_write_valid && dut.m_write_ready && dut.m_frame_done;
            release_buffer = dut.m_buffer_id;

            if (dut.m_write_valid && dut.m_write_ready) begin
                if (!dut.m_frame_valid)
                    $fatal(1, "frame_valid missing on accepted tensor sample");
                if (dut.m_frame_id !== (output_count / FRAME_LENGTH))
                    $fatal(1, "frame_id mismatch row=%0d got=%0d", output_count, dut.m_frame_id);
                if (dut.m_sample_index !== (output_count % FRAME_LENGTH))
                    $fatal(1, "sample_index mismatch row=%0d got=%0d", output_count, dut.m_sample_index);
                if (dut.m_buffer_id !== ((output_count / FRAME_LENGTH) & 1))
                    $fatal(1, "buffer_id mismatch row=%0d got=%0d", output_count, dut.m_buffer_id);
                if (dut.m_frame_start !== ((output_count % FRAME_LENGTH) == 0))
                    $fatal(1, "frame_start mismatch row=%0d", output_count);
                if (dut.m_frame_done !== ((output_count % FRAME_LENGTH) == FRAME_LENGTH - 1))
                    $fatal(1, "frame_done mismatch row=%0d", output_count);
                if (dut.m_irq !== dut.m_frame_done)
                    $fatal(1, "irq mismatch row=%0d", output_count);
                if (dut.m_frame_error)
                    $fatal(1, "unexpected frame_error row=%0d", output_count);

                $fwrite(tensor_file,
                    "%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                    dut.m_frame_id, dut.m_sample_index, dut.m_buffer_id,
                    $signed(dut.m_iq_i_data), $signed(dut.m_iq_q_data),
                    $signed(dut.m_power_data), $signed(dut.m_lag_re_data),
                    $signed(dut.m_lag_im_data), dut.m_iq_i_addr, dut.m_iq_q_addr,
                    dut.m_power_addr, dut.m_lag_re_addr, dut.m_lag_im_addr,
                    dut.m_frame_start, dut.m_frame_done, dut.m_frame_error, dut.m_irq);

                output_count = output_count + 1;
                if (dut.m_frame_done)
                    completed_frames = completed_frames + 1;
            end
        end
    end

    // Sample the replay interface away from the active clock edge.  Once
    // backpressured, valid, address, and data must remain stable.
    always @(negedge dut.core_clk) begin
        if (validation_active && dut.core_rst_n) begin
            if (stalled_last_check) begin
                if (!dut.replay_valid || dut.rom_address !== stalled_address ||
                    {dut.replay_q, dut.replay_i} !== stalled_data)
                    $fatal(1, "replay changed while stalled");
            end
            stalled_last_check = dut.replay_valid && !dut.replay_ready;
            stalled_address = dut.rom_address;
            stalled_data = {dut.replay_q, dut.replay_i};
            if (stalled_last_check) begin
                stall_cycles = stall_cycles + 1;
                saw_forced_stall = 1'b1;
            end
        end else begin
            stalled_last_check = 1'b0;
        end
    end

    initial begin
        $readmemh("vectors/iq_input.hex", expected_iq);
        tensor_file = $fopen("tb/results/board_top_tensor.csv", "w");
        if (tensor_file == 0)
            $fatal(1, "cannot open board_top_tensor.csv");
        $fwrite(tensor_file,
            "frame_id,sample_index,buffer_id,iq_i_int8,iq_q_int8,power_int8,lag_re_int8,lag_im_int8,iq_i_addr,iq_q_addr,power_addr,lag_re_addr,lag_im_addr,frame_start,frame_done,frame_error,irq\n");

        // Initial key assertion must hold the complete design in reset.
        repeat (3) @(posedge sys_clk_p);
        #0.5;
        if (dut.core_rst_n !== 1'b0 || dut.rom_address !== 0 || dut.replay_valid !== 1'b0)
            $fatal(1, "initial reset state is incorrect");

        // First short run is deliberately discarded, then PL_KEY1 is pressed
        // asynchronously to prove immediate reset and deterministic restart.
        @(negedge sys_clk_p);
        pl_key1_reset = 1'b0;
        wait (dut.mmcm_locked === 1'b1);
        wait (dut.core_rst_n === 1'b1);
        wait (dut.replay_accepted_count >= 37);
        #0.7 pl_key1_reset = 1'b1;
        #0.1;
        if (dut.core_rst_n !== 1'b0 || dut.rom_address !== 0 || dut.replay_valid !== 1'b0)
            $fatal(1, "asynchronous reset assertion failed");

        input_count = 0;
        output_count = 0;
        completed_frames = 0;
        release_checks = 0;
        validation_active = 1'b1;

        repeat (2) @(posedge sys_clk_p);
        @(negedge sys_clk_p);
        pl_key1_reset = 1'b0;

        wait (dut.mmcm_locked === 1'b1);

        // The three-stage synchronizer must hold reset for exactly the first
        // two rising edges, release it on the third, and the replay WAIT state
        // must keep valid low until one further complete clock has elapsed.
        repeat (2) begin
            @(posedge dut.core_clk);
            #0.1;
            if (dut.core_rst_n !== 1'b0 || dut.replay_valid !== 1'b0)
                $fatal(1, "reset released too early");
        end
        @(posedge dut.core_clk);
        #0.1;
        if (dut.core_rst_n !== 1'b1 || dut.replay_valid !== 1'b0)
            $fatal(1, "three-stage release or replay idle clock is incorrect");
        @(posedge dut.core_clk);
        #0.1;
        if (dut.replay_valid !== 1'b1 || dut.rom_address !== 0)
            $fatal(1, "first replay offer is not IQ sample zero");

        // Insert a real downstream stall after the second restart.  Force is
        // testbench-only and leaves the synthesizable board top tied ready.
        wait (input_count >= 500);
        force dut.m_write_ready = 1'b0;
        wait (dut.replay_valid && !dut.replay_ready);
        repeat (8) @(posedge dut.core_clk);
        release dut.m_write_ready;

        wait (dut.all_frames_done === 1'b1);
        repeat (4) @(posedge dut.core_clk);

        if (input_count != TOTAL_SAMPLES)
            $fatal(1, "input count mismatch got=%0d expected=%0d", input_count, TOTAL_SAMPLES);
        if (output_count != TOTAL_SAMPLES)
            $fatal(1, "output count mismatch got=%0d expected=%0d", output_count, TOTAL_SAMPLES);
        if (completed_frames != FRAME_COUNT)
            $fatal(1, "frame count mismatch got=%0d expected=%0d", completed_frames, FRAME_COUNT);
        if (release_checks != FRAME_COUNT)
            $fatal(1, "release count mismatch got=%0d expected=%0d", release_checks, FRAME_COUNT);
        if (!saw_forced_stall || stall_cycles < 2)
            $fatal(1, "downstream stall was not observed");
        if (!dut.replay_done || dut.replay_accepted_count != TOTAL_SAMPLES)
            $fatal(1, "replay did not terminate exactly at the final sample");
        if (dut.overflow_count != 0 || dut.sticky_error)
            $fatal(1, "unexpected overflow or sticky error");
        if (dut.buffer_busy != 2'b00)
            $fatal(1, "buffers were not released at end of run: %b", dut.buffer_busy);

        $fclose(tensor_file);
        $display("PASS tb_board_mandatory_core_test_top samples=%0d frames=%0d stall_cycles=%0d releases=%0d",
                 output_count, completed_frames, stall_cycles, release_checks);
        $finish;
    end

    initial begin
        #8000000;
        $fatal(1, "timeout/deadlock in board Mandatory Core test");
    end
endmodule

`default_nettype wire
