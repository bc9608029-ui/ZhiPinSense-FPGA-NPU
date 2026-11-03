`timescale 1ns/1ps

// Behavioral FWFT model for the vendor FIFO used by axi_to_mna.
// Simulation-only: synthesis continues to use the official XCI.
module mna_idfifo_w12 (
    input  wire        clk,
    input  wire        srst,
    input  wire [11:0] din,
    input  wire        wr_en,
    input  wire        rd_en,
    output wire [11:0] dout,
    output wire        full,
    output wire        empty,
    output wire        prog_full
);
    reg [11:0] mem [0:7];
    reg [2:0] wr_ptr;
    reg [2:0] rd_ptr;
    reg [3:0] count;

    assign dout = mem[rd_ptr];
    assign full = (count == 8);
    assign empty = (count == 0);
    assign prog_full = (count >= 6);

    always @(posedge clk) begin
        if (srst) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            count <= 0;
        end else begin
            case ({wr_en && !full, rd_en && !empty})
                2'b10: begin
                    mem[wr_ptr] <= din;
                    wr_ptr <= wr_ptr + 1'b1;
                    count <= count + 1'b1;
                end
                2'b01: begin
                    rd_ptr <= rd_ptr + 1'b1;
                    count <= count - 1'b1;
                end
                2'b11: begin
                    mem[wr_ptr] <= din;
                    wr_ptr <= wr_ptr + 1'b1;
                    rd_ptr <= rd_ptr + 1'b1;
                end
                default: begin end
            endcase
        end
    end
endmodule
