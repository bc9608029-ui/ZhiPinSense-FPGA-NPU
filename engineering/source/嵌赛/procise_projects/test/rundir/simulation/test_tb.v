`timescale 1ns / 1ps

module test_tb;
    wire [3:0] led;

    test dut (
        .led (led)
    );

    task expect_led;
        input [3:0] expected;
        begin
            #1;
            if (led !== expected) begin
                $display("FAIL: expected led=%b, got led=%b at t=%0t", expected, led, $time);
                $finish;
            end
        end
    endtask

    initial begin
        expect_led(4'b0001);

        // Move the divider near rollover so the sequence can be verified
        // without simulating tens of millions of clock cycles.
        force dut.divider = 27'h01ff_fffe;
        @(posedge dut.cfg_mclk);
        release dut.divider;
        @(posedge dut.cfg_mclk);
        expect_led(4'b0010);

        force dut.divider = 27'h01ff_ffff;
        @(posedge dut.cfg_mclk);
        release dut.divider;
        @(posedge dut.cfg_mclk);
        expect_led(4'b0100);

        force dut.divider = 27'h01ff_ffff;
        @(posedge dut.cfg_mclk);
        release dut.divider;
        @(posedge dut.cfg_mclk);
        expect_led(4'b1000);

        force dut.divider = 27'h01ff_ffff;
        @(posedge dut.cfg_mclk);
        release dut.divider;
        @(posedge dut.cfg_mclk);
        expect_led(4'b0001);

        $display("PASS: Lite LED sequence 0001 -> 0010 -> 0100 -> 1000 -> 0001");
        $finish;
    end
endmodule
