`timescale 1ns / 1ps

// Wujing Lite PL running-light board check.
//
// No external clock pin is required. BOOTUPE2.CFGMCLK is an internal device
// clock exposed by the Procise FMK7/FMZ7 primitive library. The light-change
// interval is intentionally approximate and is not a calibrated time base.
module led (
    output reg [3:0] led = 4'b0001
);

    wire cfg_mclk;

    BOOTUPE2 #(
        // Enables a useful primitive clock in behavioral simulation. This
        // parameter does not define the physical CFGMCLK frequency on board.
        .SIM_CCLK_FREQ (50.0)
    ) u_bootup (
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

    reg [26:0] divider = 27'd0;
    reg [1:0]  step    = 2'd0;

    always @(posedge cfg_mclk) begin
        divider <= divider + 1'b1;
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
