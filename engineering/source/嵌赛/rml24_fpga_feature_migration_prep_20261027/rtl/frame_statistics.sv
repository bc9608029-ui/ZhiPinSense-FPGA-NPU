`timescale 1ns/1ps

// Frame statistics sidecar for accepted int16 IQ samples.
// It does not modify or delay the model IQ stream. RMS is intentionally
// derived in software as sqrt(energy/sample_count), avoiding an unnecessary
// FPGA square-root block while preserving the exact accumulated statistic.
module frame_statistics #(
    parameter integer COUNT_WIDTH = 11,
    parameter integer ENERGY_WIDTH = 42
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire signed [15:0]         s_i,
    input  wire signed [15:0]         s_q,
    input  wire                       s_valid,
    output wire                       s_ready,
    input  wire                       s_frame_start,
    input  wire                       s_frame_end,
    output reg                        m_stats_valid,
    input  wire                       m_stats_ready,
    output reg [COUNT_WIDTH-1:0]      m_sample_count,
    output reg [ENERGY_WIDTH-1:0]     m_energy,
    output reg [31:0]                 m_peak_power
);
    reg [COUNT_WIDTH-1:0] count_acc;
    reg [ENERGY_WIDTH-1:0] energy_acc;
    reg [31:0] peak_acc;

    wire signed [31:0] i_square_s = s_i * s_i;
    wire signed [31:0] q_square_s = s_q * s_q;
    wire [31:0] power_now = $unsigned(i_square_s) + $unsigned(q_square_s);
    wire output_free = !m_stats_valid || m_stats_ready;
    // Do not begin a later frame while the previous frame result is pending.
    assign s_ready = output_free;

    wire [COUNT_WIDTH-1:0] base_count = s_frame_start ? {COUNT_WIDTH{1'b0}} : count_acc;
    wire [ENERGY_WIDTH-1:0] base_energy = s_frame_start ? {ENERGY_WIDTH{1'b0}} : energy_acc;
    wire [31:0] base_peak = s_frame_start ? 32'd0 : peak_acc;
    wire [COUNT_WIDTH-1:0] next_count = base_count + {{(COUNT_WIDTH-1){1'b0}},1'b1};
    wire [ENERGY_WIDTH-1:0] next_energy = base_energy + {{(ENERGY_WIDTH-32){1'b0}},power_now};
    wire [31:0] next_peak = (power_now > base_peak) ? power_now : base_peak;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count_acc <= 0;
            energy_acc <= 0;
            peak_acc <= 0;
            m_stats_valid <= 1'b0;
            m_sample_count <= 0;
            m_energy <= 0;
            m_peak_power <= 0;
        end else begin
            if (m_stats_valid && m_stats_ready)
                m_stats_valid <= 1'b0;

            if (s_valid && s_ready) begin
                if (s_frame_end) begin
                    m_sample_count <= next_count;
                    m_energy <= next_energy;
                    m_peak_power <= next_peak;
                    m_stats_valid <= 1'b1;
                    count_acc <= 0;
                    energy_acc <= 0;
                    peak_acc <= 0;
                end else begin
                    count_acc <= next_count;
                    energy_acc <= next_energy;
                    peak_acc <= next_peak;
                end
            end
        end
    end
endmodule
