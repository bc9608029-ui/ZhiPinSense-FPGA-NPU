`timescale 1ns/1ps
// Production OOC harness: instantiates `smart_scan_top` (framer + Hann ROM +
// migrated XFFT + u54 writer + double-buffer) and drives it with an LFSR IQ
// stream plus a PSD readback so the whole datapath survives P&R/STA on
// JFMQL30TAI676H. This is a P&R/STA smoke shell only, never a production top and
// never a board bitstream (the AXI-Lite/DMA PS glue is a separate wrapper).
module smart_scan_production_ooc_harness (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        enable,
    output reg  [31:0] digest,
    output wire [31:0] completed_frames,
    output wire        protocol_error,
    output wire        overflow,
    output wire        committed_valid,
    output wire        committed_bank
);
    reg [31:0] lfsr;
    reg [9:0]  sample_cnt;
    reg [9:0]  rd_addr;

    wire [31:0] s_axis_iq_tdata  = lfsr;
    wire        s_axis_iq_tvalid = enable;
    wire        s_axis_iq_tready;
    wire        s_axis_iq_tlast  = (sample_cnt == 10'd1023);

    wire [63:0] rd_data;
    wire [7:0]  version;
    wire [31:0] status_frame_id;
    wire        status_protocol_error, status_overflow;
    wire        committed_valid, committed_bank;

    smart_scan_top u_top (
        .clk(clk), .rst_n(rst_n),
        .s_axis_iq_tdata(s_axis_iq_tdata),
        .s_axis_iq_tvalid(s_axis_iq_tvalid),
        .s_axis_iq_tready(s_axis_iq_tready),
        .s_axis_iq_tlast(s_axis_iq_tlast),
        .rd_bank(committed_bank), .rd_addr(rd_addr), .rd_data(rd_data),
        .version(version), .status_frame_id(status_frame_id),
        .status_protocol_error(status_protocol_error),
        .status_overflow(status_overflow),
        .committed_valid(committed_valid), .committed_bank(committed_bank)
    );

    assign completed_frames = status_frame_id;
    assign protocol_error   = status_protocol_error;
    assign overflow         = status_overflow;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr <= 32'h1ace_b00c;
            sample_cnt <= 10'd0;
            rd_addr <= 10'd0;
            digest <= 32'd0;
        end else begin
            lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
            if (s_axis_iq_tvalid && s_axis_iq_tready)
                sample_cnt <= (sample_cnt == 10'd1023) ? 10'd0 : sample_cnt + 1'b1;
            if (enable)
                rd_addr <= rd_addr + 1'b1;
            digest <= digest
                ^ (rd_data[31:0] ^ {rd_data[63:32], rd_addr})
                ^ ({status_frame_id[15:0], version, overflow, protocol_error,
                    committed_valid, committed_bank});
        end
    end
endmodule
