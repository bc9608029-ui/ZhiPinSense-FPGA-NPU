`timescale 1ns / 1ps

module led_tb;

    localparam integer TEST_CLK_FREQ_HZ = 20;
    localparam integer TEST_STEP_HZ     = 2;
    localparam integer STEP_CYCLES      = TEST_CLK_FREQ_HZ / TEST_STEP_HZ;

    reg        clk;
    reg        rst_n;
    wire [3:0] led;

    led #(
        .CLK_FREQ_HZ(TEST_CLK_FREQ_HZ),
        .STEP_HZ(TEST_STEP_HZ),
        .LED_ACTIVE_LOW(1'b0)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .led(led)
    );

    initial clk = 1'b0;
    always #5 clk = ~clk;

    task check_led;
        input [3:0] expected;
        begin
            if (led !== expected) begin
                $display("FAIL: expected led=%b, actual led=%b", expected, led);
                $fatal(1);
            end
        end
    endtask

    initial begin
        rst_n = 1'b0;
        repeat (2) @(posedge clk);
        #1 check_led(4'b0001);

        rst_n = 1'b1;
        repeat (STEP_CYCLES) @(posedge clk);
        #1 check_led(4'b0010);
        repeat (STEP_CYCLES) @(posedge clk);
        #1 check_led(4'b0100);
        repeat (STEP_CYCLES) @(posedge clk);
        #1 check_led(4'b1000);
        repeat (STEP_CYCLES) @(posedge clk);
        #1 check_led(4'b0001);

        // 异步复位应立即恢复第一盏灯。
        rst_n = 1'b0;
        #1 check_led(4'b0001);

        $display("PASS: led running-light sequence and reset behavior verified");
        $finish;
    end

endmodule
