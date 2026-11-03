`timescale 1ns / 1ps
`default_nettype none

// Wujing Lite board bring-up design.
//
// The board provides a 200 MHz differential PL clock on C8/C7. Four
// active-high PL LED drivers are connected to J1, M6, H7, and J8. The
// illuminated LED advances every 0.5 seconds.
module led_flow_top (
    input  wire       sys_clk_p,
    input  wire       sys_clk_n,
    output wire [3:0] led
);

    localparam integer STEP_CYCLES = 100_000_000;

    wire clk_200m;

    IBUFDS #(
        .DIFF_TERM    ("FALSE"),
        .IBUF_LOW_PWR ("TRUE"),
        .IOSTANDARD   ("DIFF_SSTL15")
    ) u_sys_clk_ibufds (
        .I  (sys_clk_p),
        .IB (sys_clk_n),
        .O  (clk_200m)
    );

    reg [26:0] cycle_count = 27'd0;
    reg [1:0]  led_index   = 2'd0;

    always @(posedge clk_200m) begin
        if (cycle_count == STEP_CYCLES - 1) begin
            cycle_count <= 27'd0;
            led_index   <= led_index + 2'd1;
        end else begin
            cycle_count <= cycle_count + 27'd1;
        end
    end

    assign led = 4'b0001 << led_index;

endmodule

`default_nettype wire
