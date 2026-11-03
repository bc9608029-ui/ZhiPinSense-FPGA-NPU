`timescale 1ns/1ps
`default_nettype none

// Smart-scan PS/PL integration engine.
//
// Reuses the validated board PS/PL path: the User_Reg_* 32-bit register
// channel (gp_clk) and the User_Ddr_* 512-bit read channel (ddr_clk), plus the
// already-validated pl_ddr_iq_input_adapter / job_domain_controller / async FIFO
// blocks from pl_ddr_integration_v1/deps/adapters.  The datapath is the frozen
// smart_scan_top (Hann + migrated XFFT 9.1 + u54 + fftshift double buffer),
// clocked by the board's existing 50 MHz core_clk (a strictly looser timing
// constraint than the 100 MHz OOC pass).  PSD readback goes over the register
// channel (SS_RD_*), not DDR writes, per contract/pspl_register_map.md.
//
// CDC summary (all toggle/full-handshake; no raw multi-bit counters crossed):
//   - config (IQ base/bytes): 2-FF from gp_clk into ddr_clk and core_clk
//   - START:  job_domain_controller -> per-domain job reset + start pulse
//   - status (version/frame_id/proto/overflow/committed_*): snapshot on change
//     in core_clk + toggle handshake into gp_clk
//   - completion (done/error/counts/code): edge-detected in core_clk + toggle
//     handshake into gp_clk
//   - PSD readback: SS_RD_CTRL write toggles a request into core_clk; a small
//     read FSM presents the registered bank/addr, waits one core cycle for the
//     BRAM latency, captures rd_data, and toggles a done back into gp_clk.
module smart_scan_pspl_engine (
    input  wire         gp_clk,
    input  wire         gp_rst_n,
    input  wire         ddr_clk,
    input  wire         ddr_global_rst_n,
    input  wire         core_clk,
    input  wire         core_global_rst_n,

    input  wire [31:0]  User_Reg_awwaddr,
    input  wire [31:0]  User_Reg_awwdata,
    input  wire         User_Reg_awwvalid,
    output wire         User_Reg_awwready,
    input  wire [31:0]  User_Reg_araddr,
    input  wire         User_Reg_arvalid,
    output wire         User_Reg_arready,
    output wire [31:0]  User_Reg_rdata,
    output wire         User_Reg_rvalid,
    input  wire         User_Reg_rready,

    output wire [31:0]  User_Ddr_awwaddr,
    output wire [511:0] User_Ddr_awwdata,
    output wire [71:0]  User_Ddr_awwinfo,
    output wire         User_Ddr_awwvalid,
    input  wire         User_Ddr_awwready,
    output wire [31:0]  User_Ddr_araddr,
    output wire         User_Ddr_arvalid,
    output wire [31:0]  User_Ddr_arinfo,
    input  wire         User_Ddr_arready,
    input  wire [511:0] User_Ddr_rdata,
    input  wire         User_Ddr_rvalid,
    input  wire [31:0]  User_Ddr_rinfo,
    output wire         User_Ddr_rready
);
    // This engine only reads DDR (IQ input); PSD readback is over registers.
    assign User_Ddr_awwaddr  = 32'd0;
    assign User_Ddr_awwdata  = 512'd0;
    assign User_Ddr_awwinfo  = 72'd0;
    assign User_Ddr_awwvalid = 1'b0;

    // ------------------------------------------------------------------
    // Register bank (gp_clk)
    // ------------------------------------------------------------------
    wire [31:0] cfg_iq_base_gp;
    wire [31:0] cfg_iq_bytes_gp;
    wire        start_toggle_gp;
    wire        rd_req_toggle_gp;
    wire [10:0] rd_bank_addr_gp;
    wire [7:0]  version_gp;
    wire [31:0] status_frame_id_gp;
    wire        status_proto_gp;
    wire        status_overflow_gp;
    wire        committed_valid_gp;
    wire        committed_bank_gp;
    wire [63:0] rd_data_gp;

    smart_scan_pspl_regs regs (
        .clk(gp_clk),
        .rst_n(gp_rst_n),
        .User_Reg_awwaddr(User_Reg_awwaddr),
        .User_Reg_awwdata(User_Reg_awwdata),
        .User_Reg_awwvalid(User_Reg_awwvalid),
        .User_Reg_awwready(User_Reg_awwready),
        .User_Reg_araddr(User_Reg_araddr),
        .User_Reg_arvalid(User_Reg_arvalid),
        .User_Reg_arready(User_Reg_arready),
        .User_Reg_rdata(User_Reg_rdata),
        .User_Reg_rvalid(User_Reg_rvalid),
        .User_Reg_rready(User_Reg_rready),
        .iq_base_addr(cfg_iq_base_gp),
        .iq_byte_count(cfg_iq_bytes_gp),
        .start_toggle(start_toggle_gp),
        .rd_req_toggle(rd_req_toggle_gp),
        .rd_bank_addr(rd_bank_addr_gp),
        .completion_pulse(completion_pulse_gp),
        .completion_error(completion_error_gp),
        .completion_iq_accepted(completion_iq_gp),
        .completion_error_code(completion_code_gp),
        .version_gp(version_gp),
        .status_frame_id_gp(status_frame_id_gp),
        .status_protocol_error_gp(status_proto_gp),
        .status_overflow_gp(status_overflow_gp),
        .committed_valid_gp(committed_valid_gp),
        .committed_bank_gp(committed_bank_gp),
        .rd_ready_pulse(rd_ready_pulse_gp),
        .rd_data_gp(rd_data_gp)
    );

    // ------------------------------------------------------------------
    // Config CDC: gp_clk -> ddr_clk (IQ base/bytes) and -> core_clk (bytes)
    // ------------------------------------------------------------------
    reg [31:0] iq_base_ddr1, iq_base_ddr2;
    reg [31:0] iq_bytes_ddr1, iq_bytes_ddr2;
    reg [31:0] iq_bytes_core1, iq_bytes_core2;

    always @(posedge ddr_clk or negedge ddr_global_rst_n) begin
        if (!ddr_global_rst_n) begin
            iq_base_ddr1  <= 32'd0;
            iq_base_ddr2  <= 32'd0;
            iq_bytes_ddr1 <= 32'd0;
            iq_bytes_ddr2 <= 32'd0;
        end else begin
            iq_base_ddr1  <= cfg_iq_base_gp;
            iq_base_ddr2  <= iq_base_ddr1;
            iq_bytes_ddr1 <= cfg_iq_bytes_gp;
            iq_bytes_ddr2 <= iq_bytes_ddr1;
        end
    end

    always @(posedge core_clk or negedge core_global_rst_n) begin
        if (!core_global_rst_n) begin
            iq_bytes_core1 <= 32'd0;
            iq_bytes_core2 <= 32'd0;
        end else begin
            iq_bytes_core1 <= cfg_iq_bytes_gp;
            iq_bytes_core2 <= iq_bytes_core1;
        end
    end

    // ------------------------------------------------------------------
    // START CDC: one job-domain controller per destination domain.  Both
    // reset their local datapath then emit a start pulse, so neither side of
    // the async FIFOs can observe a stale pointer on repeated jobs.
    // ------------------------------------------------------------------
    wire ddr_job_rst_n;
    wire ddr_start;
    wire core_job_rst_n;
    wire core_start;

    job_domain_controller #(.RESET_CYCLES(64)) ddr_job_control (
        .clk(ddr_clk),
        .global_rst_n(ddr_global_rst_n),
        .request_toggle_async(start_toggle_gp),
        .job_rst_n(ddr_job_rst_n),
        .start_pulse(ddr_start)
    );
    job_domain_controller #(.RESET_CYCLES(8)) core_job_control (
        .clk(core_clk),
        .global_rst_n(core_global_rst_n),
        .request_toggle_async(start_toggle_gp),
        .job_rst_n(core_job_rst_n),
        .start_pulse(core_start)
    );

    // ------------------------------------------------------------------
    // IQ input: DDR read (ddr_clk) -> async FIFO -> unpacker -> core stream
    // ------------------------------------------------------------------
    wire signed [15:0] core_i;
    wire signed [15:0] core_q;
    wire               input_core_valid;
    wire               input_core_ready;
    wire               input_ddr_busy;
    wire               input_ddr_done;
    wire               input_ddr_error;
    wire [31:0]        input_accepted_samples;

    pl_ddr_iq_input_adapter #(.FIFO_ADDR_WIDTH(4)) input_adapter (
        .ddr_clk(ddr_clk),
        .ddr_rst_n(ddr_job_rst_n),
        .ddr_start(ddr_start),
        .iq_base_addr(iq_base_ddr2),
        .iq_byte_count(iq_bytes_ddr2),
        .ddr_busy(input_ddr_busy),
        .ddr_done(input_ddr_done),
        .ddr_error(input_ddr_error),
        .User_Ddr_araddr(User_Ddr_araddr),
        .User_Ddr_arvalid(User_Ddr_arvalid),
        .User_Ddr_arinfo(User_Ddr_arinfo),
        .User_Ddr_arready(User_Ddr_arready),
        .User_Ddr_rdata(User_Ddr_rdata),
        .User_Ddr_rvalid(User_Ddr_rvalid),
        .User_Ddr_rinfo(User_Ddr_rinfo),
        .User_Ddr_rready(User_Ddr_rready),
        .core_clk(core_clk),
        .core_rst_n(core_job_rst_n),
        .core_i(core_i),
        .core_q(core_q),
        .core_valid(input_core_valid),
        .core_ready(input_core_ready),
        .core_accepted_samples(input_accepted_samples)
    );

    // ------------------------------------------------------------------
    // Frame marker + frozen datapath (core_clk)
    // ------------------------------------------------------------------
    wire [31:0] marker_tdata;
    wire        marker_tvalid;
    wire        marker_tlast;
    wire        scan_tready;

    smart_scan_iq_frame_marker #(.FRAME_LENGTH(1024)) marker (
        .clk(core_clk),
        .rst_n(core_job_rst_n),
        .s_tdata({core_q, core_i}),
        .s_tvalid(input_core_valid),
        .s_tready(input_core_ready),
        .m_tdata(marker_tdata),
        .m_tvalid(marker_tvalid),
        .m_tlast(marker_tlast),
        .m_tready(scan_tready)
    );

    wire        rd_bank_core;
    wire [9:0]  rd_addr_core;
    wire [63:0] rd_data_core;
    wire [7:0]  version_core;
    wire [31:0] status_frame_id_core;
    wire        status_protocol_error_core;
    wire        status_overflow_core;
    wire        committed_valid_core;
    wire        committed_bank_core;

    smart_scan_top u_scan (
        .clk(core_clk),
        .rst_n(core_job_rst_n),
        .s_axis_iq_tdata(marker_tdata),
        .s_axis_iq_tvalid(marker_tvalid),
        .s_axis_iq_tready(scan_tready),
        .s_axis_iq_tlast(marker_tlast),
        .rd_bank(rd_bank_core),
        .rd_addr(rd_addr_core),
        .rd_data(rd_data_core),
        .version(version_core),
        .status_frame_id(status_frame_id_core),
        .status_protocol_error(status_protocol_error_core),
        .status_overflow(status_overflow_core),
        .committed_valid(committed_valid_core),
        .committed_bank(committed_bank_core)
    );

    // ------------------------------------------------------------------
    // PSD read bridge (core_clk): registered address -> 1-cycle BRAM wait ->
    // capture -> toggle done back to gp_clk.
    // ------------------------------------------------------------------
    localparam [1:0] RD_IDLE    = 2'd0;
    localparam [1:0] RD_WAIT    = 2'd1;
    localparam [1:0] RD_CAPTURE = 2'd2;

    (* ASYNC_REG = "TRUE" *) reg rd_req_s1;
    (* ASYNC_REG = "TRUE" *) reg rd_req_s2;
    (* ASYNC_REG = "TRUE" *) reg rd_req_s3;
    reg         rd_seen;
    reg [10:0]  rd_bank_addr_c1;
    reg [10:0]  rd_bank_addr_c2;
    reg [1:0]   rd_fsm;
    reg         rd_bank_reg;
    reg [9:0]   rd_addr_reg;
    reg [63:0]  rd_capture;
    reg         rd_done_toggle;

    assign rd_bank_core = rd_bank_reg;
    assign rd_addr_core = rd_addr_reg;

    always @(posedge core_clk or negedge core_job_rst_n) begin
        if (!core_job_rst_n) begin
            rd_req_s1       <= 1'b0;
            rd_req_s2       <= 1'b0;
            rd_req_s3       <= 1'b0;
            rd_seen         <= 1'b0;
            rd_bank_addr_c1 <= 11'd0;
            rd_bank_addr_c2 <= 11'd0;
            rd_fsm          <= RD_IDLE;
            rd_bank_reg     <= 1'b0;
            rd_addr_reg     <= 10'd0;
            rd_capture      <= 64'd0;
            rd_done_toggle  <= 1'b0;
        end else begin
            rd_req_s1       <= rd_req_toggle_gp;
            rd_req_s2       <= rd_req_s1;
            rd_req_s3       <= rd_req_s2;
            rd_bank_addr_c1 <= rd_bank_addr_gp;
            rd_bank_addr_c2 <= rd_bank_addr_c1;

            case (rd_fsm)
                RD_IDLE: begin
                    if (rd_req_s3 != rd_seen) begin
                        rd_seen     <= rd_req_s3;
                        rd_bank_reg <= rd_bank_addr_c2[10];
                        rd_addr_reg <= rd_bank_addr_c2[9:0];
                        rd_fsm      <= RD_WAIT;
                    end
                end
                RD_WAIT: begin
                    rd_fsm <= RD_CAPTURE;
                end
                RD_CAPTURE: begin
                    rd_capture     <= rd_data_core;
                    rd_done_toggle <= ~rd_done_toggle;
                    rd_fsm         <= RD_IDLE;
                end
                default: rd_fsm <= RD_IDLE;
            endcase
        end
    end

    // ------------------------------------------------------------------
    // Completion (core_clk): input done (synced from ddr) AND final frame
    // committed.  Captures counts/error code, then toggles into gp_clk.
    // ------------------------------------------------------------------
    reg input_done_latch_ddr;
    reg input_err_latch_ddr;
    always @(posedge ddr_clk or negedge ddr_job_rst_n) begin
        if (!ddr_job_rst_n) begin
            input_done_latch_ddr <= 1'b0;
            input_err_latch_ddr  <= 1'b0;
        end else begin
            input_done_latch_ddr <= input_ddr_done | input_done_latch_ddr;
            input_err_latch_ddr  <= input_ddr_error | input_err_latch_ddr;
        end
    end

    (* ASYNC_REG = "TRUE" *) reg input_done_s1;
    (* ASYNC_REG = "TRUE" *) reg input_done_s2;
    (* ASYNC_REG = "TRUE" *) reg input_err_s1;
    (* ASYNC_REG = "TRUE" *) reg input_err_s2;
    always @(posedge core_clk or negedge core_job_rst_n) begin
        if (!core_job_rst_n) begin
            input_done_s1 <= 1'b0;
            input_done_s2 <= 1'b0;
            input_err_s1  <= 1'b0;
            input_err_s2  <= 1'b0;
        end else begin
            input_done_s1 <= input_done_latch_ddr;
            input_done_s2 <= input_done_s1;
            input_err_s1  <= input_err_latch_ddr;
            input_err_s2  <= input_err_s1;
        end
    end

    wire [19:0] expected_frames  = iq_bytes_core2[31:12];
    wire [29:0] expected_samples = iq_bytes_core2[31:2];
    wire        sample_mismatch  = (input_accepted_samples != expected_samples);
    wire        completion_core  = input_done_s2 &&
                                   (status_frame_id_core >= expected_frames);

    reg         completion_d;
    reg         completion_toggle_core;
    reg [31:0]  cap_iq_accepted;
    reg [31:0]  cap_frame_id;
    reg [31:0]  cap_error_code;
    reg         cap_committed_valid;
    reg         cap_committed_bank;

    // Per-job completion edge detector: reset with the job so each scan's
    // completion is detected fresh.
    always @(posedge core_clk or negedge core_job_rst_n) begin
        if (!core_job_rst_n)
            completion_d <= 1'b0;
        else
            completion_d <= completion_core;
    end

    // Completion toggle + capture: global reset ONLY (mirrors
    // pl_ddr_mandatory_core_engine, whose completion_toggle_ddr is reset by
    // ddr_global_rst_n). Resetting the toggle per-job would emit a spurious
    // 1->0 edge at job start that the gp side misreads as a completion pulse.
    always @(posedge core_clk or negedge core_global_rst_n) begin
        if (!core_global_rst_n) begin
            completion_toggle_core <= 1'b0;
            cap_iq_accepted      <= 32'd0;
            cap_frame_id         <= 32'd0;
            cap_error_code       <= 32'd0;
            cap_committed_valid  <= 1'b0;
            cap_committed_bank   <= 1'b0;
        end else begin
            if (completion_core && !completion_d) begin
                completion_toggle_core <= ~completion_toggle_core;
                cap_iq_accepted  <= input_accepted_samples;
                cap_frame_id     <= status_frame_id_core;
                cap_committed_valid <= committed_valid_core;
                cap_committed_bank  <= committed_bank_core;
                cap_error_code   <= {27'd0, sample_mismatch,
                                     status_overflow_core,
                                     status_protocol_error_core,
                                     input_err_s2, 1'b0};
            end
        end
    end

    // ------------------------------------------------------------------
    // Status snapshot (core_clk): re-publish version/frame_id/proto/overflow/
    // committed_* whenever anything changes, with a toggle for the gp side.
    // ------------------------------------------------------------------
    reg [31:0] snap_frame_id;
    reg        snap_proto;
    reg        snap_overflow;
    reg        snap_committed_valid;
    reg        snap_committed_bank;
    reg        status_toggle_core;
    always @(posedge core_clk or negedge core_job_rst_n) begin
        if (!core_job_rst_n) begin
            snap_frame_id        <= 32'd0;
            snap_proto           <= 1'b0;
            snap_overflow        <= 1'b0;
            snap_committed_valid <= 1'b0;
            snap_committed_bank  <= 1'b0;
            status_toggle_core   <= 1'b0;
        end else begin
            if (status_frame_id_core  != snap_frame_id ||
                status_protocol_error_core != snap_proto ||
                status_overflow_core  != snap_overflow ||
                committed_valid_core  != snap_committed_valid ||
                committed_bank_core   != snap_committed_bank) begin
                snap_frame_id        <= status_frame_id_core;
                snap_proto           <= status_protocol_error_core;
                snap_overflow        <= status_overflow_core;
                snap_committed_valid <= committed_valid_core;
                snap_committed_bank  <= committed_bank_core;
                status_toggle_core   <= ~status_toggle_core;
            end
        end
    end

    // ------------------------------------------------------------------
    // gp_clk side: synchronize the core->gp handshakes into stable latches.
    // ------------------------------------------------------------------
    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp1;
    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp2;
    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp3;
    reg [31:0] completion_iq_gp1, completion_iq_gp2;
    reg [31:0] completion_code_gp1, completion_code_gp2;
    reg [31:0] completion_fid_gp1, completion_fid_gp2;
    reg        completion_cvalid_gp1, completion_cvalid_gp2;
    reg        completion_cbank_gp1, completion_cbank_gp2;
    wire completion_pulse_gp = completion_toggle_gp2 ^ completion_toggle_gp3;
    wire completion_error_gp = (completion_code_gp2 != 32'd0);
    wire [31:0] completion_iq_gp = completion_iq_gp2;
    wire [31:0] completion_code_gp = completion_code_gp2;

    (* ASYNC_REG = "TRUE" *) reg status_toggle_gp1;
    (* ASYNC_REG = "TRUE" *) reg status_toggle_gp2;
    (* ASYNC_REG = "TRUE" *) reg status_toggle_gp3;
    reg [31:0] snap_frame_id_gp1, snap_frame_id_gp2;
    reg        snap_proto_gp1, snap_proto_gp2;
    reg        snap_overflow_gp1, snap_overflow_gp2;
    reg        snap_valid_gp1, snap_valid_gp2;
    reg        snap_bank_gp1, snap_bank_gp2;
    wire status_pulse_gp = status_toggle_gp2 ^ status_toggle_gp3;

    (* ASYNC_REG = "TRUE" *) reg rd_done_gp1;
    (* ASYNC_REG = "TRUE" *) reg rd_done_gp2;
    (* ASYNC_REG = "TRUE" *) reg rd_done_gp3;
    reg [63:0] rd_capture_gp1, rd_capture_gp2;
    wire rd_ready_pulse_gp = rd_done_gp2 ^ rd_done_gp3;

    // The scan-core version is constant (8'h01 frozen), so it is safe to
    // continuously synchronize it; the driver must be able to read it before
    // the first frame commits.
    (* ASYNC_REG = "TRUE" *) reg [7:0] version_gp1;
    (* ASYNC_REG = "TRUE" *) reg [7:0] version_gp2;

    reg [31:0] status_frame_id_gp_r;
    reg        status_proto_gp_r;
    reg        status_overflow_gp_r;
    reg        committed_valid_gp_r;
    reg        committed_bank_gp_r;
    reg [63:0] rd_data_gp_r;

    assign version_gp         = version_gp2;
    assign status_frame_id_gp = status_frame_id_gp_r;
    assign status_proto_gp    = status_proto_gp_r;
    assign status_overflow_gp = status_overflow_gp_r;
    assign committed_valid_gp = committed_valid_gp_r;
    assign committed_bank_gp  = committed_bank_gp_r;
    assign rd_data_gp         = rd_data_gp_r;

    always @(posedge gp_clk or negedge gp_rst_n) begin
        if (!gp_rst_n) begin
            completion_toggle_gp1 <= 1'b0;
            completion_toggle_gp2 <= 1'b0;
            completion_toggle_gp3 <= 1'b0;
            completion_iq_gp1     <= 32'd0;
            completion_iq_gp2     <= 32'd0;
            completion_code_gp1   <= 32'd0;
            completion_code_gp2   <= 32'd0;
            completion_fid_gp1    <= 32'd0;
            completion_fid_gp2    <= 32'd0;
            completion_cvalid_gp1 <= 1'b0;
            completion_cvalid_gp2 <= 1'b0;
            completion_cbank_gp1  <= 1'b0;
            completion_cbank_gp2  <= 1'b0;

            status_toggle_gp1   <= 1'b0;
            status_toggle_gp2   <= 1'b0;
            status_toggle_gp3   <= 1'b0;
            snap_frame_id_gp1   <= 32'd0;
            snap_frame_id_gp2   <= 32'd0;
            snap_proto_gp1      <= 1'b0;
            snap_proto_gp2      <= 1'b0;
            snap_overflow_gp1   <= 1'b0;
            snap_overflow_gp2   <= 1'b0;
            snap_valid_gp1      <= 1'b0;
            snap_valid_gp2      <= 1'b0;
            snap_bank_gp1       <= 1'b0;
            snap_bank_gp2       <= 1'b0;

            rd_done_gp1     <= 1'b0;
            rd_done_gp2     <= 1'b0;
            rd_done_gp3     <= 1'b0;
            rd_capture_gp1  <= 64'd0;
            rd_capture_gp2  <= 64'd0;

            version_gp1         <= 8'd0;
            version_gp2         <= 8'd0;
            status_frame_id_gp_r <= 32'd0;
            status_proto_gp_r    <= 1'b0;
            status_overflow_gp_r <= 1'b0;
            committed_valid_gp_r <= 1'b0;
            committed_bank_gp_r  <= 1'b0;
            rd_data_gp_r         <= 64'd0;
        end else begin
            completion_toggle_gp1 <= completion_toggle_core;
            completion_toggle_gp2 <= completion_toggle_gp1;
            completion_toggle_gp3 <= completion_toggle_gp2;
            completion_iq_gp1     <= cap_iq_accepted;
            completion_iq_gp2     <= completion_iq_gp1;
            completion_code_gp1   <= cap_error_code;
            completion_code_gp2   <= completion_code_gp1;
            completion_fid_gp1    <= cap_frame_id;
            completion_fid_gp2    <= completion_fid_gp1;
            completion_cvalid_gp1 <= cap_committed_valid;
            completion_cvalid_gp2 <= completion_cvalid_gp1;
            completion_cbank_gp1  <= cap_committed_bank;
            completion_cbank_gp2  <= completion_cbank_gp1;

            status_toggle_gp1 <= status_toggle_core;
            status_toggle_gp2 <= status_toggle_gp1;
            status_toggle_gp3 <= status_toggle_gp2;
            snap_frame_id_gp1 <= snap_frame_id;
            snap_frame_id_gp2 <= snap_frame_id_gp1;
            snap_proto_gp1    <= snap_proto;
            snap_proto_gp2    <= snap_proto_gp1;
            snap_overflow_gp1 <= snap_overflow;
            snap_overflow_gp2 <= snap_overflow_gp1;
            snap_valid_gp1    <= snap_committed_valid;
            snap_valid_gp2    <= snap_valid_gp1;
            snap_bank_gp1     <= snap_committed_bank;
            snap_bank_gp2     <= snap_bank_gp1;
            if (status_pulse_gp) begin
                status_frame_id_gp_r <= snap_frame_id_gp2;
                status_proto_gp_r    <= snap_proto_gp2;
                status_overflow_gp_r <= snap_overflow_gp2;
                committed_valid_gp_r <= snap_valid_gp2;
                committed_bank_gp_r  <= snap_bank_gp2;
            end
            // On completion, atomically publish the FINAL frame state alongside
            // `done` (the regs bank asserts done on the same completion_pulse),
            // so a reader that sees done never observes a stale frame_id/bank.
            // Placed after the live-status latch: if both pulses land in the
            // same gp cycle, the completion (final) values win.
            if (completion_pulse_gp) begin
                status_frame_id_gp_r <= completion_fid_gp2;
                status_proto_gp_r    <= completion_code_gp2[2];
                status_overflow_gp_r <= completion_code_gp2[3];
                committed_valid_gp_r <= completion_cvalid_gp2;
                committed_bank_gp_r  <= completion_cbank_gp2;
            end

            version_gp1    <= version_core;
            version_gp2    <= version_gp1;

            rd_done_gp1    <= rd_done_toggle;
            rd_done_gp2    <= rd_done_gp1;
            rd_done_gp3    <= rd_done_gp2;
            rd_capture_gp1 <= rd_capture;
            rd_capture_gp2 <= rd_capture_gp1;
            if (rd_ready_pulse_gp)
                rd_data_gp_r <= rd_capture_gp2;
        end
    end

    // Keep the core-side start pulse visible to synthesis/lint without driving
    // it into the datapath (the datapath is gated by the job reset, matching
    // the frozen-core pattern).
    wire unused_status = input_ddr_busy ^ core_start ^ core_i[0] ^ core_q[0] ^
                         cap_frame_id[0] ^ version_core[1];
endmodule

`default_nettype wire
