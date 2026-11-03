`timescale 1ns / 1ps

// Running-light hardware check for the Wujing Lite board.
//
// This top level deliberately uses the device's internal configuration clock
// (BOOTUPE2.CFGMCLK), so it does not depend on an unverified external clock
// package pin.  The exact blink rate is therefore not a precision time base;
// it is only intended for a visible board/JTAG/PL/LED health check.
module lite_led_flow (
    output reg [3:0] led = 4'b0001
);

    wire cfg_mclk;

    // BOOTUPE2 is provided by the Procise FMZ7/FMK7 device library.
    BOOTUPE2 u_bootup (
        .CFGCLK     (),
        .CFGMCLK    (cfg_mclk),
        .EOS        (),
        .PREQ       (),
        .CLK        (1'b0),
        .GSR        (1'b0),
        .GTS        (1'b0),
        .KEYCLEARB  (1'b1),
        .PACK       (1'b0),
        .USRCCLKO   (1'b0),
        .USRCCLKTS  (1'b1),
        .USRDONEO   (1'b1),
        .USRDONETS  (1'b1)
    );

    // The configuration clock is not specified as a precision clock.  Using
    // a high divider bit keeps the change slow enough to observe across its
    // expected frequency range.
    reg [26:0] divider = 27'd0;
    reg [1:0]  step    = 2'd0;

    always @(posedge cfg_mclk) begin
        divider <= divider + 1'b1;

        // Advance once for every 2^25 configuration-clock cycles.
        if (divider[24:0] == 25'h1ff_ffff) begin
            step <= step + 1'b1;
        end
    end

    always @* begin
        case (step)
            2'd0: led = 4'b0001;
            2'd1: led = 4'b0010;
            2'd2: led = 4'b0100;
            2'd3: led = 4'b1000;
            default: led = 4'b0001;
        endcase
    end

endmodule
