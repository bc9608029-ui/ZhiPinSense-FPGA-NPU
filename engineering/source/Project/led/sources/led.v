`timescale 1ns / 1ps

module led #(
    // 悟净板 PL 侧时钟按硬件手册暂设为 200 MHz。
    // 上板前仍需在约束文件中绑定实际时钟引脚并确认频率。
    parameter integer CLK_FREQ_HZ    = 200_000_000,
    parameter integer STEP_HZ        = 2,
    // 若实板 LED 为低电平点亮，将此参数改为 1'b1。
    parameter         LED_ACTIVE_LOW = 1'b0
)(
    input  wire       clk,
    input  wire       rst_n,
    output wire [3:0] led
);

    // 默认每 0.5 秒移动一次。32 位计数器足以覆盖当前 200 MHz 配置。
    localparam integer STEP_CYCLES = CLK_FREQ_HZ / STEP_HZ;

    reg [31:0] divider_count;
    reg [3:0]  led_pattern;

    // 内部统一使用高电平表示“点亮”，通过参数适配实际 LED 极性。
    assign led = LED_ACTIVE_LOW ? ~led_pattern : led_pattern;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            divider_count <= 32'd0;
            led_pattern   <= 4'b0001;
        end else if (divider_count >= STEP_CYCLES - 1) begin
            divider_count <= 32'd0;
            led_pattern   <= {led_pattern[2:0], led_pattern[3]};
        end else begin
            divider_count <= divider_count + 1'b1;
        end
    end

endmodule
