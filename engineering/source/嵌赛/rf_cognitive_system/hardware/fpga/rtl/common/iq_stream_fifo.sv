`timescale 1ns/1ps

// Vendor-independent synchronous ready/valid FIFO for signed int16 IQ.
// An upstream adapter must assert s_overflow_event when a sample is actually
// dropped. Backpressure alone is not counted as an overflow.
module iq_stream_fifo #(
    parameter integer DEPTH = 16,
    parameter integer COUNTER_WIDTH = 32,
    parameter integer PTR_WIDTH = (DEPTH <= 2) ? 1 : $clog2(DEPTH)
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire signed [15:0]           s_i,
    input  wire signed [15:0]           s_q,
    input  wire                         s_error,
    input  wire                         s_valid,
    output wire                         s_ready,
    input  wire                         s_overflow_event,
    output wire signed [15:0]           m_i,
    output wire signed [15:0]           m_q,
    output wire                         m_error,
    output wire                         m_valid,
    input  wire                         m_ready,
    output wire [$clog2(DEPTH+1)-1:0]   occupancy,
    output reg  [COUNTER_WIDTH-1:0]     overflow_count
);
    localparam integer COUNT_WIDTH = $clog2(DEPTH+1);
    localparam logic [COUNT_WIDTH-1:0] DEPTH_VALUE = COUNT_WIDTH'(DEPTH);
    localparam logic [PTR_WIDTH-1:0] LAST_POINTER = PTR_WIDTH'(DEPTH-1);

    reg signed [15:0] i_mem [0:DEPTH-1];
    reg signed [15:0] q_mem [0:DEPTH-1];
    reg               e_mem [0:DEPTH-1];
    reg [PTR_WIDTH-1:0] write_pointer;
    reg [PTR_WIDTH-1:0] read_pointer;
    reg [$clog2(DEPTH+1)-1:0] count;

    wire push = s_valid && s_ready;
    wire pop  = m_valid && m_ready;

    assign s_ready = (count < DEPTH_VALUE);
    assign m_valid = (count != 0);
    assign m_i = i_mem[read_pointer];
    assign m_q = q_mem[read_pointer];
    assign m_error = e_mem[read_pointer];
    assign occupancy = count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_pointer <= {PTR_WIDTH{1'b0}};
            read_pointer <= {PTR_WIDTH{1'b0}};
            count <= 0;
            overflow_count <= 0;
        end else begin
            if (s_overflow_event)
                overflow_count <= overflow_count + 1'b1;

            if (push) begin
                i_mem[write_pointer] <= s_i;
                q_mem[write_pointer] <= s_q;
                e_mem[write_pointer] <= s_error;
                if (write_pointer == LAST_POINTER)
                    write_pointer <= 0;
                else
                    write_pointer <= write_pointer + 1'b1;
            end

            if (pop) begin
                if (read_pointer == LAST_POINTER)
                    read_pointer <= 0;
                else
                    read_pointer <= read_pointer + 1'b1;
            end

            case ({push, pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end
endmodule
