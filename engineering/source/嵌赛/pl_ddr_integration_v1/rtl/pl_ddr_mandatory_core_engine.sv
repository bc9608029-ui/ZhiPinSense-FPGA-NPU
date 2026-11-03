`timescale 1ns/1ps
`default_nettype none

// UserCustomOp integration engine.  Register traffic is in gp_clk, the
// official PL-DDR interface is in ddr_clk, and the frozen Mandatory Core is
// kept in the already-validated 50 MHz core_clk domain.
module pl_ddr_mandatory_core_engine (
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
    localparam [31:0] TOTAL_SAMPLES = 32'd19456;
    localparam [31:0] EXPECTED_BEATS = 32'd1520;

    wire [31:0] cfg_iq_base_gp;
    wire [31:0] cfg_iq_bytes_gp;
    wire [31:0] cfg_tensor_base_gp;
    wire [31:0] cfg_tensor_bytes_gp;
    wire [31:0] cfg_frame_count_gp;
    wire start_toggle_gp;

    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp1;
    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp2;
    (* ASYNC_REG = "TRUE" *) reg completion_toggle_gp3;
    (* ASYNC_REG = "TRUE" *) reg completion_error_gp1;
    (* ASYNC_REG = "TRUE" *) reg completion_error_gp2;
    reg [31:0] completion_iq_gp1, completion_iq_gp2;
    reg [31:0] completion_tensor_gp1, completion_tensor_gp2;
    reg [31:0] completion_code_gp1, completion_code_gp2;
    wire completion_pulse_gp = completion_toggle_gp2 ^ completion_toggle_gp3;

    reg completion_toggle_ddr;
    reg completion_error_ddr;
    reg [31:0] completion_iq_ddr;
    reg [31:0] completion_tensor_ddr;
    reg [31:0] completion_code_ddr;
    reg job_started_ddr;

    pl_ddr_mandatory_core_regs regs (
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
        .tensor_base_addr(cfg_tensor_base_gp),
        .tensor_byte_count(cfg_tensor_bytes_gp),
        .frame_count(cfg_frame_count_gp),
        .start_toggle(start_toggle_gp),
        .completion_pulse(completion_pulse_gp),
        .completion_error(completion_error_gp2),
        .completion_iq_accepted(completion_iq_gp2),
        .completion_tensor_accepted(completion_tensor_gp2),
        .completion_error_code(completion_code_gp2)
    );

    always @(posedge gp_clk or negedge gp_rst_n) begin
        if (!gp_rst_n) begin
            completion_toggle_gp1 <= 1'b0;
            completion_toggle_gp2 <= 1'b0;
            completion_toggle_gp3 <= 1'b0;
            completion_error_gp1  <= 1'b0;
            completion_error_gp2  <= 1'b0;
            completion_iq_gp1     <= 32'd0;
            completion_iq_gp2     <= 32'd0;
            completion_tensor_gp1 <= 32'd0;
            completion_tensor_gp2 <= 32'd0;
            completion_code_gp1   <= 32'd0;
            completion_code_gp2   <= 32'd0;
        end else begin
            completion_toggle_gp1 <= completion_toggle_ddr;
            completion_toggle_gp2 <= completion_toggle_gp1;
            completion_toggle_gp3 <= completion_toggle_gp2;
            completion_error_gp1  <= completion_error_ddr;
            completion_error_gp2  <= completion_error_gp1;
            completion_iq_gp1     <= completion_iq_ddr;
            completion_iq_gp2     <= completion_iq_gp1;
            completion_tensor_gp1 <= completion_tensor_ddr;
            completion_tensor_gp2 <= completion_tensor_gp1;
            completion_code_gp1   <= completion_code_ddr;
            completion_code_gp2   <= completion_code_gp1;
        end
    end

    // Configuration is stable from before START until completion.  Two data
    // stages plus the three-stage request-toggle synchronizer ensure that the
    // destination sees settled values before its start pulse.
    reg [31:0] iq_base_ddr1, iq_base_ddr2;
    reg [31:0] iq_bytes_ddr1, iq_bytes_ddr2;
    reg [31:0] tensor_base_ddr1, tensor_base_ddr2;
    reg [31:0] tensor_base_core1, tensor_base_core2;
    always @(posedge ddr_clk or negedge ddr_global_rst_n) begin
        if (!ddr_global_rst_n) begin
            iq_base_ddr1     <= 32'd0;
            iq_base_ddr2     <= 32'd0;
            iq_bytes_ddr1    <= 32'd0;
            iq_bytes_ddr2    <= 32'd0;
            tensor_base_ddr1 <= 32'd0;
            tensor_base_ddr2 <= 32'd0;
        end else begin
            iq_base_ddr1     <= cfg_iq_base_gp;
            iq_base_ddr2     <= iq_base_ddr1;
            iq_bytes_ddr1    <= cfg_iq_bytes_gp;
            iq_bytes_ddr2    <= iq_bytes_ddr1;
            tensor_base_ddr1 <= cfg_tensor_base_gp;
            tensor_base_ddr2 <= tensor_base_ddr1;
        end
    end
    always @(posedge core_clk or negedge core_global_rst_n) begin
        if (!core_global_rst_n) begin
            tensor_base_core1 <= 32'd0;
            tensor_base_core2 <= 32'd0;
        end else begin
            tensor_base_core1 <= cfg_tensor_base_gp;
            tensor_base_core2 <= tensor_base_core1;
        end
    end

    wire ddr_job_rst_n;
    wire ddr_start;
    wire core_job_rst_n;
    wire core_start;
    // Hold the fast DDR side in reset until the slower core side has also
    // observed and applied the request.  This prevents either side of the
    // asynchronous FIFOs from sampling a stale pointer on repeated jobs.
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

    wire signed [15:0] core_i;
    wire signed [15:0] core_q;
    wire input_core_valid;
    wire input_core_ready;
    wire input_ddr_busy;
    wire input_ddr_done;
    wire input_ddr_error;
    wire [31:0] input_accepted_samples;

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

    wire core_write_valid;
    wire core_write_ready;
    wire core_buffer_id;
    wire [31:0] core_frame_id;
    wire [9:0] core_sample_index;
    wire [10:0] core_iq_i_addr, core_iq_q_addr;
    wire [11:0] core_power_addr, core_lag_re_addr, core_lag_im_addr;
    wire signed [7:0] core_iq_i_data, core_iq_q_data;
    wire signed [7:0] core_power_data, core_lag_re_data, core_lag_im_data;
    wire core_frame_valid, core_frame_start, core_frame_done, core_frame_error;
    wire core_irq;
    wire [1:0] core_buffer_busy;
    wire [1:0] core_buffer_release;
    wire [31:0] overflow_count;
    wire [31:0] saturation_count_i, saturation_count_q;
    wire [31:0] saturation_count_power, saturation_count_lag_re;
    wire [31:0] saturation_count_lag_im;

    mandatory_core_path #(.FRAME_LENGTH(1024), .FRAME_ID_WIDTH(32)) frozen_core (
        .clk(core_clk),
        .rst_n(core_job_rst_n),
        .s_i(core_i),
        .s_q(core_q),
        .s_error(1'b0),
        .s_valid(input_core_valid),
        .s_ready(input_core_ready),
        .s_overflow_event(1'b0),
        .cfg_iq_multiplier(32'd127),
        .cfg_iq_shift(8'd15),
        .cfg_power_multiplier(32'd127),
        .cfg_power_shift(8'd31),
        .cfg_lag_multiplier(32'd127),
        .cfg_lag_shift(8'd31),
        .clear_counters(1'b0),
        .buffer_release(core_buffer_release),
        .m_write_valid(core_write_valid),
        .m_write_ready(core_write_ready),
        .m_buffer_id(core_buffer_id),
        .m_frame_id(core_frame_id),
        .m_sample_index(core_sample_index),
        .m_iq_i_addr(core_iq_i_addr),
        .m_iq_q_addr(core_iq_q_addr),
        .m_power_addr(core_power_addr),
        .m_lag_re_addr(core_lag_re_addr),
        .m_lag_im_addr(core_lag_im_addr),
        .m_iq_i_data(core_iq_i_data),
        .m_iq_q_data(core_iq_q_data),
        .m_power_data(core_power_data),
        .m_lag_re_data(core_lag_re_data),
        .m_lag_im_data(core_lag_im_data),
        .m_frame_valid(core_frame_valid),
        .m_frame_start(core_frame_start),
        .m_frame_done(core_frame_done),
        .m_frame_error(core_frame_error),
        .m_irq(core_irq),
        .buffer_busy(core_buffer_busy),
        .overflow_count(overflow_count),
        .saturation_count_i(saturation_count_i),
        .saturation_count_q(saturation_count_q),
        .saturation_count_power(saturation_count_power),
        .saturation_count_lag_re(saturation_count_lag_re),
        .saturation_count_lag_im(saturation_count_lag_im)
    );

    wire output_core_active;
    wire output_all_frames_enqueued;
    wire output_core_protocol_error;
    wire [31:0] output_core_accepted_samples;
    wire [31:0] output_core_enqueued_beats;
    wire output_ddr_busy;
    wire output_ddr_done;
    wire output_ddr_error;
    wire [31:0] output_ddr_accepted_beats;

    pl_ddr_tensor_output_adapter #(
        .FRAME_LENGTH(1024),
        .FRAME_COUNT(19),
        .FIFO_ADDR_WIDTH(4)
    ) output_adapter (
        .core_clk(core_clk),
        .core_rst_n(core_job_rst_n),
        .core_start(core_start),
        .output_base_addr(tensor_base_core2),
        .core_write_valid(core_write_valid),
        .core_write_ready(core_write_ready),
        .core_buffer_id(core_buffer_id),
        .core_frame_id(core_frame_id),
        .core_sample_index(core_sample_index),
        .core_iq_i_addr(core_iq_i_addr),
        .core_iq_q_addr(core_iq_q_addr),
        .core_power_addr(core_power_addr),
        .core_lag_re_addr(core_lag_re_addr),
        .core_lag_im_addr(core_lag_im_addr),
        .core_iq_i_data(core_iq_i_data),
        .core_iq_q_data(core_iq_q_data),
        .core_power_data(core_power_data),
        .core_lag_re_data(core_lag_re_data),
        .core_lag_im_data(core_lag_im_data),
        .core_frame_start(core_frame_start),
        .core_frame_done(core_frame_done),
        .core_frame_error(core_frame_error),
        .core_buffer_release(core_buffer_release),
        .core_active(output_core_active),
        .core_all_frames_enqueued(output_all_frames_enqueued),
        .core_protocol_error(output_core_protocol_error),
        .core_accepted_samples(output_core_accepted_samples),
        .core_enqueued_beats(output_core_enqueued_beats),
        .ddr_clk(ddr_clk),
        .ddr_rst_n(ddr_job_rst_n),
        .ddr_start(ddr_start),
        .ddr_busy(output_ddr_busy),
        .ddr_done(output_ddr_done),
        .ddr_error(output_ddr_error),
        .ddr_accepted_beats(output_ddr_accepted_beats),
        .User_Ddr_awwaddr(User_Ddr_awwaddr),
        .User_Ddr_awwdata(User_Ddr_awwdata),
        .User_Ddr_awwinfo(User_Ddr_awwinfo),
        .User_Ddr_awwvalid(User_Ddr_awwvalid),
        .User_Ddr_awwready(User_Ddr_awwready)
    );

    // Stable job-result values cross to DDR before the completion toggle is
    // returned to GP.  DONE is created only after the final accepted DDR write.
    reg [31:0] input_samples_ddr1, input_samples_ddr2;
    reg [31:0] output_samples_ddr1, output_samples_ddr2;
    reg [31:0] overflow_ddr1, overflow_ddr2;
    reg core_protocol_ddr1, core_protocol_ddr2;
    reg output_done_d;
    wire [31:0] completion_code_now = {
        26'd0,
        (output_ddr_accepted_beats != EXPECTED_BEATS),
        (output_samples_ddr2 != TOTAL_SAMPLES),
        (input_samples_ddr2 != TOTAL_SAMPLES),
        (overflow_ddr2 != 0),
        core_protocol_ddr2,
        (input_ddr_error | output_ddr_error)
    };

    always @(posedge ddr_clk or negedge ddr_global_rst_n) begin
        if (!ddr_global_rst_n) begin
            input_samples_ddr1  <= 32'd0;
            input_samples_ddr2  <= 32'd0;
            output_samples_ddr1 <= 32'd0;
            output_samples_ddr2 <= 32'd0;
            overflow_ddr1       <= 32'd0;
            overflow_ddr2       <= 32'd0;
            core_protocol_ddr1  <= 1'b0;
            core_protocol_ddr2  <= 1'b0;
        end else begin
            input_samples_ddr1  <= input_accepted_samples;
            input_samples_ddr2  <= input_samples_ddr1;
            output_samples_ddr1 <= output_core_accepted_samples;
            output_samples_ddr2 <= output_samples_ddr1;
            overflow_ddr1       <= overflow_count;
            overflow_ddr2       <= overflow_ddr1;
            core_protocol_ddr1  <= output_core_protocol_error;
            core_protocol_ddr2  <= core_protocol_ddr1;
        end
    end

    always @(posedge ddr_clk or negedge ddr_job_rst_n) begin
        if (!ddr_job_rst_n)
            output_done_d <= 1'b0;
        else
            output_done_d <= output_ddr_done;
    end

    always @(posedge ddr_clk or negedge ddr_global_rst_n) begin
        if (!ddr_global_rst_n) begin
            completion_toggle_ddr <= 1'b0;
            completion_error_ddr  <= 1'b0;
            completion_iq_ddr     <= 32'd0;
            completion_tensor_ddr <= 32'd0;
            completion_code_ddr   <= 32'd0;
            job_started_ddr       <= 1'b0;
        end else begin
            if (ddr_start)
                job_started_ddr <= 1'b1;
            if (job_started_ddr && output_ddr_done && !output_done_d) begin
                job_started_ddr       <= 1'b0;
                completion_toggle_ddr <= ~completion_toggle_ddr;
                completion_error_ddr  <= (completion_code_now != 0);
                completion_iq_ddr     <= input_samples_ddr2;
                completion_tensor_ddr <= output_samples_ddr2;
                completion_code_ddr   <= completion_code_now;
            end
        end
    end

    // Keep currently unused status nets visible to synthesis/lint without
    // changing the frozen core or adapter behavior.
    wire unused_status = input_ddr_busy ^ input_ddr_done ^ output_ddr_busy ^
                         output_core_active ^ output_all_frames_enqueued ^
                         core_frame_valid ^ core_irq ^ core_buffer_busy[0] ^
                         saturation_count_i[0] ^ saturation_count_q[0] ^
                         saturation_count_power[0] ^ saturation_count_lag_re[0] ^
                         saturation_count_lag_im[0] ^ cfg_tensor_bytes_gp[0] ^
                         cfg_frame_count_gp[0] ^ tensor_base_ddr2[0] ^
                         output_core_enqueued_beats[0];
endmodule

`default_nettype wire
