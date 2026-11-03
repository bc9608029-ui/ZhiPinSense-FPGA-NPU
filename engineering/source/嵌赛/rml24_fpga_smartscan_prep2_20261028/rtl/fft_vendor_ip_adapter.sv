`timescale 1ns/1ps
// Adapter around the migrated Xilinx XFFT 9.1 core (module `smartscan_fft_1024`,
// delivered as a Procise-translated EDIF netlist). Converts the core's AXI-Stream
// ports to the clean smart-scan boundary:
//   16-bit signed I/Q in  ->  27-bit signed re/im out + 10-bit natural bin index.
//
// Frozen bit packing, taken from the generated .veo/.vho wrapper and the Xilinx
// demo testbench (tb_smartscan_fft_1024.vhd), not from guesswork:
//   s_axis_data_tdata[15:0]   = real input
//   s_axis_data_tdata[31:16]  = imag input
//   m_axis_data_tdata[26:0]   = real output (unscaled, signed)
//   m_axis_data_tdata[58:32]  = imag output (unscaled, signed)
//   m_axis_data_tuser[9:0]    = XK_INDEX natural bin 0..1023
//
// The core's M_AXIS_DATA has no TREADY (HAS_TREADY 0) in realtime-throttle mode:
// its output is push-only, so `m_ready` cannot backpressure the FFT. Production
// must guarantee the downstream writer/double-buffer keeps up every cycle.
module fft_vendor_ip_adapter (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire signed [15:0]   s_i,
    input  wire signed [15:0]   s_q,
    input  wire                 s_valid,
    output wire                 s_ready,
    input  wire                 s_last,

    output wire signed [26:0]   m_re,
    output wire signed [26:0]   m_im,
    output wire [9:0]           m_index,
    output wire                 m_valid,
    input  wire                 m_ready,
    output wire                 m_last,
    output wire                 data_halt
);
    wire [7:0]  cfg_tdata;
    wire        cfg_tvalid;
    wire        cfg_tready;
    wire [31:0] s_tdata;
    wire        s_tvalid;
    wire        s_tready;
    wire        s_tlast;
    wire [63:0] m_tdata;
    wire [15:0] m_tuser;
    wire        m_tvalid;
    wire        m_tlast;
    wire        ev_frame_started, ev_tlast_unexpected, ev_tlast_missing, ev_data_halt;

    // Input packing: {Q, I}, real in the low 16 bits.
    assign s_tdata  = {s_q, s_i};
    reg configured;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) configured <= 1'b0;
        else if (cfg_tvalid && cfg_tready) configured <= 1'b1;
    end
    assign s_tvalid = s_valid && configured;
    assign s_tlast  = s_last;
    assign s_ready  = s_tready && configured;

    // Fixed config channel: one beat, held valid until the core accepts it.
    //   cfg_tdata[0] = FWD_INV : 1'b1 => forward DFT (X_k = sum x[n] e^-j2pi kn/N).
    //                    A 0 here would run the inverse transform and mirror the
    //                    spectrum (bin k <-> bin N-k), so the direction is pinned.
    //   cfg_tdata[4:1] = SCALE_SCH : unused, C_HAS_SCALING=0 (unscaled).
    //   cfg_tdata[7:5] = reserved.
    // NFFT is frozen at 1024 at elaboration (C_HAS_NFFT=0), so no length field.
    // This matches the core's own power-on default (fwd_inv_int_reg FDSE INIT=1)
    // and the vendor demo (FWD_INV=1 is forward); it is explicit, not assumed.
    assign cfg_tdata  = 8'd1;
    assign cfg_tvalid = !configured;

    smartscan_fft_1024 u_fft (
        .aclk(clk),
        .aresetn(rst_n),
        .s_axis_config_tdata(cfg_tdata),
        .s_axis_config_tvalid(cfg_tvalid),
        .s_axis_config_tready(cfg_tready),
        .s_axis_data_tdata(s_tdata),
        .s_axis_data_tvalid(s_tvalid),
        .s_axis_data_tready(s_tready),
        .s_axis_data_tlast(s_tlast),
        .m_axis_data_tdata(m_tdata),
        .m_axis_data_tuser(m_tuser),
        .m_axis_data_tvalid(m_tvalid),
        .m_axis_data_tlast(m_tlast),
        .event_frame_started(ev_frame_started),
        .event_tlast_unexpected(ev_tlast_unexpected),
        .event_tlast_missing(ev_tlast_missing),
        .event_data_in_channel_halt(ev_data_halt)
    );

    // Output unpacking: natural-order real/imag, XK_INDEX from tuser.
    assign m_re    = m_tdata[26:0];
    assign m_im    = m_tdata[58:32];
    assign m_index = m_tuser[9:0];
    assign m_valid = m_tvalid;
    assign m_last  = m_tlast;

    // `m_ready` is unused: the migrated core cannot be backpressured on its
    // output channel (see header). Keep the port for boundary compatibility.
    // (`cfg_tready` IS used in the config handshake above; it is not unused.)
    wire unused_m_ready     = m_ready;
    // event_frame_started is informational only; it is not a fault.
    wire unused_ev0 = ev_frame_started;

    // data_halt = latched-frame-fault OR. Three distinct fault classes, all of
    // which invalidate the current frame and must trip status_overflow:
    //
    //   (1) tlast anomaly  : ev_tlast_unexpected || ev_tlast_missing
    //       The core flagged a frame-boundary protocol violation -- tlast seen
    //       off the 1024-sample boundary (unexpected / short frame) or absent
    //       when the boundary was reached (missing / over-long frame).
    //
    //   (2) input starvation : ev_data_halt (event_data_in_channel_halt)
    //       INPUT-side stall: in realtime-throttle mode the core asserts
    //       load_enable while waiting for the next input sample, and the
    //       producer did not deliver one (load_enable & ~new_data). This is the
    //       input being starved / halted, NOT "the output is too slow". Do not
    //       confuse it with the output-desync term below.
    //
    //   (3) output desync : m_tvalid && !m_ready
    //       The push-only M_AXIS_DATA (HAS_TREADY=0) cannot be backpressured;
    //       if the downstream deasserts m_ready while the core is asserting
    //       m_tvalid, an output beat is dropped and the PSD stream desyncs.
    //       Production ties m_ready to the writer's ready (always 1 today), so
    //       this is a defensive term, not a current false-positive source.
    assign data_halt = ev_data_halt || ev_tlast_unexpected || ev_tlast_missing
                       || (m_tvalid && !m_ready);
endmodule
