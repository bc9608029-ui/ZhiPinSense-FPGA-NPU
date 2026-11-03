`timescale 1ns/1ps
`default_nettype none

// Small dual-clock ready/valid FIFO.  The read pointer advances when a word
// is copied into the output holding register, so data remains stable under
// downstream backpressure while the corresponding RAM slot is released.
module async_fifo_gray_original #(
    parameter integer DATA_WIDTH = 512,
    parameter integer ADDR_WIDTH = 4
) (
    input  wire                  s_clk,
    input  wire                  s_rst_n,
    input  wire [DATA_WIDTH-1:0] s_data,
    input  wire                  s_valid,
    output wire                  s_ready,

    input  wire                  m_clk,
    input  wire                  m_rst_n,
    output reg  [DATA_WIDTH-1:0] m_data,
    output reg                   m_valid,
    input  wire                  m_ready
);
    localparam integer DEPTH = (1 << ADDR_WIDTH);
    localparam integer PTR_WIDTH = ADDR_WIDTH + 1;

    (* ram_style = "block" *) reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    reg [PTR_WIDTH-1:0] wr_bin;
    reg [PTR_WIDTH-1:0] wr_gray;
    reg                 wr_full;
    reg [PTR_WIDTH-1:0] rd_bin;
    reg [PTR_WIDTH-1:0] rd_gray;

    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] rd_gray_sync1;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] rd_gray_sync2;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] wr_gray_sync1;
    (* ASYNC_REG = "TRUE" *) reg [PTR_WIDTH-1:0] wr_gray_sync2;

    wire s_transfer = s_valid && s_ready;
    wire [PTR_WIDTH-1:0] wr_bin_next = wr_bin + s_transfer;
    wire [PTR_WIDTH-1:0] wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
    wire [PTR_WIDTH-1:0] rd_gray_full_compare = {
        ~rd_gray_sync2[PTR_WIDTH-1:PTR_WIDTH-2],
        rd_gray_sync2[PTR_WIDTH-3:0]
    };
    wire wr_full_next = (wr_gray_next == rd_gray_full_compare);
    wire fifo_empty = (rd_gray == wr_gray_sync2);
    wire load_output = !m_valid || m_ready;

    assign s_ready = !wr_full;

    always @(posedge s_clk or negedge s_rst_n) begin
        if (!s_rst_n) begin
            wr_bin  <= {PTR_WIDTH{1'b0}};
            wr_gray <= {PTR_WIDTH{1'b0}};
            wr_full <= 1'b0;
        end else begin
            if (s_transfer)
                mem[wr_bin[ADDR_WIDTH-1:0]] <= s_data;
            wr_bin  <= wr_bin_next;
            wr_gray <= wr_gray_next;
            wr_full <= wr_full_next;
        end
    end

    always @(posedge m_clk or negedge m_rst_n) begin
        if (!m_rst_n) begin
            rd_bin  <= {PTR_WIDTH{1'b0}};
            rd_gray <= {PTR_WIDTH{1'b0}};
            m_data  <= {DATA_WIDTH{1'b0}};
            m_valid <= 1'b0;
        end else if (load_output) begin
            if (!fifo_empty) begin
                m_data  <= mem[rd_bin[ADDR_WIDTH-1:0]];
                m_valid <= 1'b1;
                rd_bin  <= rd_bin + 1'b1;
                rd_gray <= ((rd_bin + 1'b1) >> 1) ^ (rd_bin + 1'b1);
            end else begin
                m_valid <= 1'b0;
            end
        end
    end

    always @(posedge s_clk or negedge s_rst_n) begin
        if (!s_rst_n) begin
            rd_gray_sync1 <= {PTR_WIDTH{1'b0}};
            rd_gray_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            rd_gray_sync1 <= rd_gray;
            rd_gray_sync2 <= rd_gray_sync1;
        end
    end

    always @(posedge m_clk or negedge m_rst_n) begin
        if (!m_rst_n) begin
            wr_gray_sync1 <= {PTR_WIDTH{1'b0}};
            wr_gray_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            wr_gray_sync1 <= wr_gray;
            wr_gray_sync2 <= wr_gray_sync1;
        end
    end
endmodule

`default_nettype wire

