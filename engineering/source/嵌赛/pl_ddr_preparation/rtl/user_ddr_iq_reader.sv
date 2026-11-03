`timescale 1ns/1ps
`default_nettype none

// Conservative PL-DDR reader for the official User_Ddr_* interface.
// It deliberately keeps only one read outstanding until the platform's
// maximum outstanding-request contract is formally documented.
module user_ddr_iq_reader (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    input  wire [31:0]  base_addr,
    input  wire [31:0]  byte_count,
    output reg          busy,
    output reg          done,
    output reg          error,

    output wire [31:0]  User_Ddr_araddr,
    output wire         User_Ddr_arvalid,
    output wire [31:0]  User_Ddr_arinfo,
    input  wire         User_Ddr_arready,
    input  wire [511:0] User_Ddr_rdata,
    input  wire         User_Ddr_rvalid,
    input  wire [31:0]  User_Ddr_rinfo,
    output wire         User_Ddr_rready,

    output wire [511:0] beat_data,
    output wire         beat_valid,
    input  wire         beat_ready
);
    localparam [1:0] ST_IDLE = 2'd0;
    localparam [1:0] ST_AR   = 2'd1;
    localparam [1:0] ST_R    = 2'd2;

    reg [1:0] state;
    reg [31:0] current_addr;
    reg [25:0] beats_remaining;

    assign User_Ddr_araddr  = current_addr;
    assign User_Ddr_arvalid = (state == ST_AR);
    // Official single-beat request: info=0, last=1.
    assign User_Ddr_arinfo  = {25'h0, 6'b0, 1'b1};
    assign beat_data        = User_Ddr_rdata;
    assign beat_valid       = (state == ST_R) && User_Ddr_rvalid;
    assign User_Ddr_rready  = (state == ST_R) && beat_ready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= ST_IDLE;
            current_addr    <= 32'd0;
            beats_remaining <= 26'd0;
            busy            <= 1'b0;
            done            <= 1'b0;
            error           <= 1'b0;
        end else begin
            done <= 1'b0;

            if (start && state == ST_IDLE) begin
                error <= 1'b0;
                if (base_addr[5:0] != 6'd0 || byte_count[5:0] != 6'd0 || byte_count == 0) begin
                    error <= 1'b1;
                    done  <= 1'b1;
                    busy  <= 1'b0;
                end else begin
                    current_addr    <= base_addr;
                    beats_remaining <= byte_count[31:6];
                    busy            <= 1'b1;
                    state           <= ST_AR;
                end
            end

            case (state)
                ST_IDLE: begin
                    busy <= 1'b0;
                end
                ST_AR: begin
                    if (User_Ddr_arvalid && User_Ddr_arready)
                        state <= ST_R;
                end
                ST_R: begin
                    if (beat_valid && beat_ready) begin
                        // The official request is a complete single-beat read.
                        if (!User_Ddr_rinfo[0])
                            error <= 1'b1;
                        if (beats_remaining == 1) begin
                            beats_remaining <= 0;
                            busy            <= 1'b0;
                            done            <= 1'b1;
                            state           <= ST_IDLE;
                        end else begin
                            beats_remaining <= beats_remaining - 1'b1;
                            current_addr    <= current_addr + 32'd64;
                            state           <= ST_AR;
                        end
                    end
                end
                default: state <= ST_IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
