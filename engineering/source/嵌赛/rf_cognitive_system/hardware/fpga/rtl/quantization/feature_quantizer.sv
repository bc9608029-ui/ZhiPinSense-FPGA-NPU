`timescale 1ns/1ps

// Configurable integer multiplier/shift quantizer.
// q = sat[-127,127](round_ties_away(raw * multiplier / 2^shift)).
// SIGNED_INPUT=0 is used for u32 Power; SIGNED_INPUT=1 for IQ/Lag.
module feature_quantizer #(
    parameter integer INPUT_WIDTH = 33,
    parameter integer MULTIPLIER_WIDTH = 32,
    parameter integer SIGNED_INPUT = 1,
    parameter integer COUNTER_WIDTH = 32,
    parameter integer PRODUCT_WIDTH = INPUT_WIDTH + MULTIPLIER_WIDTH
) (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire [INPUT_WIDTH-1:0]         s_data,
    input  wire                           s_valid,
    output wire                           s_ready,
    input  wire [MULTIPLIER_WIDTH-1:0]    cfg_multiplier,
    input  wire [7:0]                     cfg_shift,
    input  wire                           clear_saturation_count,
    output reg  signed [7:0]              m_data,
    output reg                            m_saturated,
    output reg                            m_valid,
    input  wire                           m_ready,
    output reg  [COUNTER_WIDTH-1:0]       saturation_count
);
    localparam logic [7:0] PRODUCT_WIDTH_VALUE = 8'(PRODUCT_WIDTH);

    reg input_negative;
    reg [INPUT_WIDTH-1:0] magnitude;
    reg [PRODUCT_WIDTH-1:0] product;
    reg [PRODUCT_WIDTH:0] adjusted;
    reg [PRODUCT_WIDTH:0] rounded_magnitude;
    reg signed [7:0] quantized_comb;
    reg saturated_comb;

    assign s_ready = !m_valid || m_ready;

    always @* begin
        input_negative = (SIGNED_INPUT != 0) && s_data[INPUT_WIDTH-1];
        magnitude = input_negative ? (~s_data + 1'b1) : s_data;
        product = magnitude * cfg_multiplier;
        adjusted = {1'b0, product};
        rounded_magnitude = 0;

        if (cfg_shift == 0) begin
            rounded_magnitude = {1'b0, product};
        end else if (cfg_shift <= PRODUCT_WIDTH_VALUE) begin
            adjusted = {1'b0, product}
                     + ({{PRODUCT_WIDTH{1'b0}}, 1'b1} << (cfg_shift - 1'b1));
            rounded_magnitude = adjusted >> cfg_shift;
        end

        saturated_comb = (rounded_magnitude > 127);
        if (saturated_comb)
            quantized_comb = input_negative ? -8'sd127 : 8'sd127;
        else if (input_negative)
            quantized_comb = -$signed({1'b0, rounded_magnitude[6:0]});
        else
            quantized_comb = $signed({1'b0, rounded_magnitude[6:0]});
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_valid <= 1'b0;
            m_data <= 0;
            m_saturated <= 1'b0;
            saturation_count <= 0;
        end else begin
            if (clear_saturation_count)
                saturation_count <= 0;
            else if (s_valid && s_ready && saturated_comb)
                saturation_count <= saturation_count + 1'b1;

            if (s_ready) begin
                m_valid <= s_valid;
                if (s_valid) begin
                    m_data <= quantized_comb;
                    m_saturated <= saturated_comb;
                end
            end
        end
    end
endmodule
