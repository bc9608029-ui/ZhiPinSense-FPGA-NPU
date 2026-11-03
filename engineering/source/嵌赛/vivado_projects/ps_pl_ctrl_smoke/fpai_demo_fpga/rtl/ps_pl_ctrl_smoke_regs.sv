`timescale 1ns/1ps

module ps_pl_ctrl_smoke_regs #(
    parameter integer ACTION_CYCLES = 16
) (
    input  wire        clk,
    input  wire        rst_n,

    input  wire [31:0] User_Reg_awwaddr,
    input  wire [31:0] User_Reg_awwdata,
    input  wire        User_Reg_awwvalid,
    output wire        User_Reg_awwready,

    input  wire [31:0] User_Reg_araddr,
    input  wire        User_Reg_arvalid,
    output wire        User_Reg_arready,
    output reg  [31:0] User_Reg_rdata,
    output reg         User_Reg_rvalid,
    input  wire        User_Reg_rready
);

    localparam [17:0] ADDR_VERSION   = 18'h00000;
    localparam [17:0] ADDR_SCRATCH   = 18'h00004;
    localparam [17:0] ADDR_CONTROL   = 18'h00008;
    localparam [17:0] ADDR_STATUS    = 18'h0000c;
    localparam [17:0] ADDR_RUN_COUNT = 18'h00010;
    localparam [31:0] VERSION_VALUE  = 32'h20260927;
    localparam integer COUNT_WIDTH   = (ACTION_CYCLES <= 2) ? 1 : $clog2(ACTION_CYCLES);

    reg [31:0] scratch;
    reg [31:0] run_count;
    reg [COUNT_WIDTH-1:0] action_count;
    reg busy;
    reg done;

    wire write_fire = User_Reg_awwvalid && User_Reg_awwready;
    wire start_fire = write_fire &&
                      (User_Reg_awwaddr[17:0] == ADDR_CONTROL) &&
                      User_Reg_awwdata[0] && !busy;

    assign User_Reg_awwready = 1'b1;
    assign User_Reg_arready  = !User_Reg_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            scratch      <= 32'h00000000;
            run_count    <= 32'h00000000;
            action_count <= {COUNT_WIDTH{1'b0}};
            busy         <= 1'b0;
            done         <= 1'b0;
        end else begin
            if (write_fire && (User_Reg_awwaddr[17:0] == ADDR_SCRATCH))
                scratch <= User_Reg_awwdata;

            if (start_fire) begin
                busy         <= 1'b1;
                done         <= 1'b0;
                action_count <= {COUNT_WIDTH{1'b0}};
            end else if (busy) begin
                if (action_count == ACTION_CYCLES - 1) begin
                    busy         <= 1'b0;
                    done         <= 1'b1;
                    run_count    <= run_count + 1'b1;
                    action_count <= {COUNT_WIDTH{1'b0}};
                end else begin
                    action_count <= action_count + 1'b1;
                end
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            User_Reg_rdata  <= 32'h00000000;
            User_Reg_rvalid <= 1'b0;
        end else begin
            if (User_Reg_arvalid && User_Reg_arready) begin
                User_Reg_rvalid <= 1'b1;
                case (User_Reg_araddr[17:0])
                    ADDR_VERSION:   User_Reg_rdata <= VERSION_VALUE;
                    ADDR_SCRATCH:   User_Reg_rdata <= scratch;
                    ADDR_CONTROL:   User_Reg_rdata <= 32'h00000000;
                    ADDR_STATUS:    User_Reg_rdata <= {30'h0, done, busy};
                    ADDR_RUN_COUNT: User_Reg_rdata <= run_count;
                    default:        User_Reg_rdata <= 32'hffffffff;
                endcase
            end else if (User_Reg_rvalid && User_Reg_rready) begin
                User_Reg_rvalid <= 1'b0;
            end
        end
    end

endmodule
