`timescale 1ns/1ps
`default_nettype none

module pl_ddr_mandatory_core_regs #(
    parameter [31:0] VERSION_VALUE = 32'h20260929,
    parameter [31:0] EXPECTED_IQ_BYTES = 32'd77824,
    parameter [31:0] EXPECTED_TENSOR_BYTES = 32'd97280,
    parameter [31:0] EXPECTED_FRAME_COUNT = 32'd19
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
    input  wire        User_Reg_rready,

    output reg  [31:0] iq_base_addr,
    output reg  [31:0] iq_byte_count,
    output reg  [31:0] tensor_base_addr,
    output reg  [31:0] tensor_byte_count,
    output reg  [31:0] frame_count,
    output reg         start_toggle,

    input  wire        completion_pulse,
    input  wire        completion_error,
    input  wire [31:0] completion_iq_accepted,
    input  wire [31:0] completion_tensor_accepted,
    input  wire [31:0] completion_error_code
);
    localparam [17:0] ADDR_VERSION         = 18'h00000;
    localparam [17:0] ADDR_CONTROL         = 18'h00004;
    localparam [17:0] ADDR_STATUS          = 18'h00008;
    localparam [17:0] ADDR_IQ_BASE         = 18'h0000c;
    localparam [17:0] ADDR_IQ_BYTES        = 18'h00010;
    localparam [17:0] ADDR_TENSOR_BASE     = 18'h00014;
    localparam [17:0] ADDR_TENSOR_BYTES    = 18'h00018;
    localparam [17:0] ADDR_FRAME_COUNT     = 18'h0001c;
    localparam [17:0] ADDR_IQ_ACCEPTED     = 18'h00020;
    localparam [17:0] ADDR_TENSOR_ACCEPTED = 18'h00024;
    localparam [17:0] ADDR_ERROR_CODE      = 18'h00028;

    localparam [31:0] ERROR_BAD_CONFIG = 32'h00000001;

    reg busy;
    reg done;
    reg error;
    reg [31:0] iq_accepted;
    reg [31:0] tensor_accepted;
    reg [31:0] error_code;

    wire write_fire = User_Reg_awwvalid && User_Reg_awwready;
    wire control_write = write_fire && (User_Reg_awwaddr[17:0] == ADDR_CONTROL);
    wire clear_request = control_write && User_Reg_awwdata[1];
    wire start_request = control_write && User_Reg_awwdata[0];
    wire config_valid = (iq_base_addr[5:0] == 0) &&
                        (tensor_base_addr[5:0] == 0) &&
                        (iq_base_addr != tensor_base_addr) &&
                        (iq_byte_count == EXPECTED_IQ_BYTES) &&
                        (tensor_byte_count == EXPECTED_TENSOR_BYTES) &&
                        (frame_count == EXPECTED_FRAME_COUNT);

    assign User_Reg_awwready = 1'b1;
    assign User_Reg_arready = !User_Reg_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            iq_base_addr       <= 32'd0;
            iq_byte_count      <= EXPECTED_IQ_BYTES;
            tensor_base_addr   <= 32'd0;
            tensor_byte_count  <= EXPECTED_TENSOR_BYTES;
            frame_count        <= EXPECTED_FRAME_COUNT;
            start_toggle       <= 1'b0;
            busy               <= 1'b0;
            done               <= 1'b0;
            error              <= 1'b0;
            iq_accepted        <= 32'd0;
            tensor_accepted    <= 32'd0;
            error_code         <= 32'd0;
        end else begin
            if (write_fire && !busy) begin
                case (User_Reg_awwaddr[17:0])
                    ADDR_IQ_BASE:      iq_base_addr      <= User_Reg_awwdata;
                    ADDR_IQ_BYTES:     iq_byte_count     <= User_Reg_awwdata;
                    ADDR_TENSOR_BASE:  tensor_base_addr  <= User_Reg_awwdata;
                    ADDR_TENSOR_BYTES: tensor_byte_count <= User_Reg_awwdata;
                    ADDR_FRAME_COUNT:  frame_count       <= User_Reg_awwdata;
                    default: ;
                endcase
            end

            if (clear_request && !busy) begin
                done            <= 1'b0;
                error           <= 1'b0;
                iq_accepted     <= 32'd0;
                tensor_accepted <= 32'd0;
                error_code      <= 32'd0;
            end

            if (start_request && !busy) begin
                done            <= 1'b0;
                error           <= 1'b0;
                iq_accepted     <= 32'd0;
                tensor_accepted <= 32'd0;
                error_code      <= 32'd0;
                if (config_valid) begin
                    busy         <= 1'b1;
                    start_toggle <= ~start_toggle;
                end else begin
                    busy       <= 1'b0;
                    done       <= 1'b1;
                    error      <= 1'b1;
                    error_code <= ERROR_BAD_CONFIG;
                end
            end

            if (completion_pulse && busy) begin
                busy            <= 1'b0;
                done            <= 1'b1;
                error           <= completion_error;
                iq_accepted     <= completion_iq_accepted;
                tensor_accepted <= completion_tensor_accepted;
                error_code      <= completion_error_code;
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            User_Reg_rdata  <= 32'd0;
            User_Reg_rvalid <= 1'b0;
        end else begin
            if (User_Reg_arvalid && User_Reg_arready) begin
                User_Reg_rvalid <= 1'b1;
                case (User_Reg_araddr[17:0])
                    ADDR_VERSION:         User_Reg_rdata <= VERSION_VALUE;
                    ADDR_CONTROL:         User_Reg_rdata <= 32'd0;
                    ADDR_STATUS:          User_Reg_rdata <= {29'd0, error, done, busy};
                    ADDR_IQ_BASE:         User_Reg_rdata <= iq_base_addr;
                    ADDR_IQ_BYTES:        User_Reg_rdata <= iq_byte_count;
                    ADDR_TENSOR_BASE:     User_Reg_rdata <= tensor_base_addr;
                    ADDR_TENSOR_BYTES:    User_Reg_rdata <= tensor_byte_count;
                    ADDR_FRAME_COUNT:     User_Reg_rdata <= frame_count;
                    ADDR_IQ_ACCEPTED:     User_Reg_rdata <= iq_accepted;
                    ADDR_TENSOR_ACCEPTED: User_Reg_rdata <= tensor_accepted;
                    ADDR_ERROR_CODE:      User_Reg_rdata <= error_code;
                    default:              User_Reg_rdata <= 32'hffffffff;
                endcase
            end else if (User_Reg_rvalid && User_Reg_rready) begin
                User_Reg_rvalid <= 1'b0;
            end
        end
    end
endmodule

`default_nettype wire
