`timescale 1ns/1ps
`default_nettype none

// SS_ register bank for the smart-scan PS/PL integration.  Runs entirely in
// gp_clk and speaks the platform's User_Reg_* 32-bit register protocol
// (awwready == 1; single outstanding read with rvalid handshake), matching
// pl_ddr_mandatory_core_regs.  The register map is frozen in
// contract/pspl_register_map.md; every address and bit assignment here must
// track that document exactly.
//
// Responsibilities:
//   - data group: SS_IQ_BASE / SS_IQ_BYTES (config, validated at START)
//   - control group: SS_CTRL (START toggle, CLEAR)
//   - status group: SS_VERSION / SS_STATUS / SS_FRAME_ID / SS_IQ_ACCEPTED /
//                   SS_ERR_CODE (fed by the engine's gp-domain latches)
//   - PSD readback group: SS_RD_CTRL / SS_RD_DATA_LO / SS_RD_DATA_HI with the
//     rd_req_toggle -> engine read bridge -> rd_ready_pulse handshake.
module smart_scan_pspl_regs (
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

    // config / control out (to engine)
    output reg  [31:0] iq_base_addr,
    output reg  [31:0] iq_byte_count,
    output reg         start_toggle,

    // PSD read request out (to engine read bridge, held stable until next write)
    output reg         rd_req_toggle,
    output reg  [10:0] rd_bank_addr,

    // completion in (already synchronized + edge-detected by the engine)
    input  wire        completion_pulse,
    input  wire        completion_error,
    input  wire [31:0] completion_iq_accepted,
    input  wire [31:0] completion_error_code,

    // live status in (stable latches in gp_clk, maintained by the engine)
    input  wire [7:0]  version_gp,
    input  wire [31:0] status_frame_id_gp,
    input  wire        status_protocol_error_gp,
    input  wire        status_overflow_gp,
    input  wire        committed_valid_gp,
    input  wire        committed_bank_gp,

    // PSD read response in (rd_data_gp stable; rd_ready_pulse is 1 cycle)
    input  wire        rd_ready_pulse,
    input  wire [63:0] rd_data_gp
);
    localparam [17:0] ADDR_IQ_BASE     = 18'h00000;
    localparam [17:0] ADDR_IQ_BYTES    = 18'h00004;
    localparam [17:0] ADDR_CTRL        = 18'h00008;
    localparam [17:0] ADDR_VERSION     = 18'h0000C;
    localparam [17:0] ADDR_STATUS      = 18'h00010;
    localparam [17:0] ADDR_FRAME_ID    = 18'h00014;
    localparam [17:0] ADDR_IQ_ACCEPTED = 18'h00018;
    localparam [17:0] ADDR_ERR_CODE    = 18'h0001C;
    localparam [17:0] ADDR_RD_CTRL     = 18'h00020;
    localparam [17:0] ADDR_RD_DATA_LO  = 18'h00024;
    localparam [17:0] ADDR_RD_DATA_HI  = 18'h00028;

    localparam [31:0] ERROR_BAD_CONFIG = 32'h00000001;

    reg busy;
    reg done;
    reg error;
    reg [31:0] iq_accepted;
    reg [31:0] error_code;
    reg rd_ready;

    wire write_fire      = User_Reg_awwvalid && User_Reg_awwready;
    wire control_write   = write_fire && (User_Reg_awwaddr[17:0] == ADDR_CTRL);
    wire clear_request   = control_write && User_Reg_awwdata[1];
    wire start_request   = control_write && User_Reg_awwdata[0];
    wire rd_ctrl_write   = write_fire && (User_Reg_awwaddr[17:0] == ADDR_RD_CTRL);
    wire config_valid    = (iq_base_addr[5:0] == 6'd0) &&
                           (iq_byte_count[11:0] == 12'd0) &&
                           (iq_byte_count != 32'd0);

    assign User_Reg_awwready = 1'b1;
    assign User_Reg_arready  = !User_Reg_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            iq_base_addr   <= 32'd0;
            iq_byte_count  <= 32'd0;
            start_toggle   <= 1'b0;
            busy           <= 1'b0;
            done           <= 1'b0;
            error          <= 1'b0;
            iq_accepted    <= 32'd0;
            error_code     <= 32'd0;
            rd_req_toggle  <= 1'b0;
            rd_bank_addr   <= 11'd0;
            rd_ready       <= 1'b0;
        end else begin
            if (write_fire && !busy) begin
                case (User_Reg_awwaddr[17:0])
                    ADDR_IQ_BASE:  iq_base_addr  <= User_Reg_awwdata;
                    ADDR_IQ_BYTES: iq_byte_count <= User_Reg_awwdata;
                    default: ;
                endcase
            end

            if (clear_request && !busy) begin
                done        <= 1'b0;
                error       <= 1'b0;
                iq_accepted <= 32'd0;
                error_code  <= 32'd0;
            end

            if (start_request && !busy) begin
                done        <= 1'b0;
                error       <= 1'b0;
                iq_accepted <= 32'd0;
                error_code  <= 32'd0;
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

            if (rd_ctrl_write) begin
                rd_bank_addr  <= User_Reg_awwdata[10:0];
                rd_req_toggle <= ~rd_req_toggle;
                rd_ready      <= 1'b0;
            end

            if (rd_ready_pulse)
                rd_ready <= 1'b1;

            if (completion_pulse && busy) begin
                busy        <= 1'b0;
                done        <= 1'b1;
                error       <= completion_error;
                iq_accepted <= completion_iq_accepted;
                error_code  <= completion_error_code;
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
                    ADDR_IQ_BASE:     User_Reg_rdata <= iq_base_addr;
                    ADDR_IQ_BYTES:    User_Reg_rdata <= iq_byte_count;
                    ADDR_CTRL:        User_Reg_rdata <= 32'd0;
                    ADDR_VERSION:     User_Reg_rdata <= {24'd0, version_gp};
                    ADDR_STATUS:      User_Reg_rdata <= {24'd0, rd_ready,
                                                         status_overflow_gp,
                                                         status_protocol_error_gp,
                                                         committed_bank_gp,
                                                         committed_valid_gp,
                                                         error, done, busy};
                    ADDR_FRAME_ID:    User_Reg_rdata <= status_frame_id_gp;
                    ADDR_IQ_ACCEPTED: User_Reg_rdata <= iq_accepted;
                    ADDR_ERR_CODE:    User_Reg_rdata <= error_code;
                    ADDR_RD_CTRL:     User_Reg_rdata <= {21'd0, rd_bank_addr};
                    ADDR_RD_DATA_LO:  User_Reg_rdata <= rd_data_gp[31:0];
                    ADDR_RD_DATA_HI:  User_Reg_rdata <= rd_data_gp[63:32];
                    default:          User_Reg_rdata <= 32'hffffffff;
                endcase
            end else if (User_Reg_rvalid && User_Reg_rready) begin
                User_Reg_rvalid <= 1'b0;
            end
        end
    end
endmodule

`default_nettype wire
