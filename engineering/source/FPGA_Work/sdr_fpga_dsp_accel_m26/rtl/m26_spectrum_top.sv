// M26-B  spectrum chain top level.
//
//   IQ -> [hann] -> [fft_1024] -> [fftshift] -> [mag_sq] -> power spectrum
//                                                          |
//                       +----------------+-----------------+-----------------+
//                       |                |                                   |
//                 [noise_floor]        [cfar]                       [candidate_merge]
//                 median (Q0.30)    1024-bit mask               candidate list + 99% BW
//
// The power spectrum (Q0.30, one frame = 1024 bins) is fanned out to three
// frame-based consumers that each buffer the frame internally (distributed RAM) and
// then compute their statistic.  They are kept in lockstep by the shared tlast: all
// three leave their input phase on the same cycle, and the fan-out back-pressure is
// the AND of their ready signals, so the next frame cannot begin until the slowest
// consumer (candidate_merge) returns to its input phase.  This trades throughput for
// a single buffered frame and is the documented offline/pre-silicon behaviour; the
// production path uses BRAM + a multi-frame ring (see
// M26_RESOURCE_AND_TIMING_BUDGET.md).
//
// hann and fft are independently bypassable; fftshift/mag_sq are essential and have
// no bypass.  A CFAR parameter error (2*R + 2*G >= 1024) raises cfg_error and stalls
// the fan-out (fail-closed, contract §17).
module m26_spectrum_top (
    input  logic          clk,
    input  logic          rst_n,             // async, active-low
    // per-stage bypass
    input  logic          bypass_hann,
    input  logic          bypass_fft,
    // CFAR configuration
    input  logic [9:0]    cfar_guard,        // G guard cells each side
    input  logic [9:0]    cfar_ref,          // R reference cells each side
    input  logic [15:0]   cfar_threshold_scale_q214, // T in Q2.14
    // candidate-merge configuration
    input  logic [9:0]    merge_gap,         // max gap bridged between detections
    input  logic [4:0]    max_cand,          // candidate cap (legal 1..16)
    // AXI-Stream slave (IQ, one frame = 1024 samples)
    input  logic          s_axis_tvalid,
    output logic          s_axis_tready,
    input  logic [31:0]   s_axis_tdata,      // {I[15:0], Q[15:0]} Q1.15
    input  logic          s_axis_tlast,
    // frame statistics
    output logic          n0_valid,          // noise-floor median valid (pulse)
    output logic [31:0]   n0_data,           // median power Q0.30
    output logic          mask_valid,        // CFAR mask valid (pulse)
    output logic [1023:0] mask,              // 1 = detected
    output logic          cand_valid,        // candidate data valid (pulse)
    output logic [9:0]    cand_start,
    output logic [9:0]    cand_end,
    output logic [9:0]    cand_peak,
    output logic [10:0]   cand_bw,           // 99% power bandwidth (bins)
    output logic [41:0]   cand_power,        // Q0.30 candidate power sum
    output logic [51:0]   cand_wsum,         // sum p[k]*k (centroid numerator)
    output logic          cand_done,         // candidate list complete (pulse)
    output logic [4:0]    cand_count,        // valid with cand_done
    output logic          candidate_overflow,// valid with cand_done
    // fail-closed status
    output logic          cfg_error
);
  // ---- hann -> fft stream
  logic        hann_valid, hann_ready, hann_tlast;
  logic [31:0] hann_data;
  // ---- fft -> fftshift stream
  logic        fft_valid, fft_ready, fft_tlast;
  logic [31:0] fft_data;
  // ---- fftshift -> mag_sq stream
  logic        fs_valid, fs_ready, fs_tlast;
  logic [31:0] fs_data;
  // ---- mag_sq -> {noise_floor, cfar, candidate_merge} fan-out
  logic        ms_valid, ms_ready, ms_tlast;
  logic [31:0] ms_data;
  logic        nf_ready, cfar_ready, cm_ready;

  m26_hann u_hann (
    .clk, .rst_n,
    .bypass       (bypass_hann),
    .s_axis_tvalid(s_axis_tvalid),
    .s_axis_tready(s_axis_tready),
    .s_axis_tdata (s_axis_tdata),
    .s_axis_tlast (s_axis_tlast),
    .m_axis_tvalid(hann_valid),
    .m_axis_tready(hann_ready),
    .m_axis_tdata (hann_data),
    .m_axis_tlast (hann_tlast)
  );

  m26_fft_1024 u_fft (
    .clk, .rst_n,
    .bypass       (bypass_fft),
    .s_axis_tvalid(hann_valid),
    .s_axis_tready(hann_ready),
    .s_axis_tdata (hann_data),
    .s_axis_tlast (hann_tlast),
    .m_axis_tvalid(fft_valid),
    .m_axis_tready(fft_ready),
    .m_axis_tdata (fft_data),
    .m_axis_tlast (fft_tlast)
  );

  m26_fftshift u_fftshift (
    .clk, .rst_n,
    .s_axis_tvalid(fft_valid),
    .s_axis_tready(fft_ready),
    .s_axis_tdata (fft_data),
    .s_axis_tlast (fft_tlast),
    .m_axis_tvalid(fs_valid),
    .m_axis_tready(fs_ready),
    .m_axis_tdata (fs_data),
    .m_axis_tlast (fs_tlast)
  );

  m26_mag_sq u_mag_sq (
    .clk, .rst_n,
    .s_axis_tvalid(fs_valid),
    .s_axis_tready(fs_ready),
    .s_axis_tdata (fs_data),
    .s_axis_tlast (fs_tlast),
    .m_axis_tvalid(ms_valid),
    .m_axis_tready(ms_ready),
    .m_axis_tdata (ms_data),
    .m_axis_tlast (ms_tlast)
  );

  assign ms_ready = nf_ready && cfar_ready && cm_ready;

  m26_noise_floor u_noise_floor (
    .clk, .rst_n,
    .s_axis_tvalid(ms_valid),
    .s_axis_tready(nf_ready),
    .s_axis_tdata (ms_data),
    .s_axis_tlast (ms_tlast),
    .n0_valid     (n0_valid),
    .n0_data      (n0_data)
  );

  m26_cfar u_cfar (
    .clk, .rst_n,
    .guard               (cfar_guard),
    .ref                 (cfar_ref),
    .threshold_scale_q214(cfar_threshold_scale_q214),
    .s_axis_tvalid       (ms_valid),
    .s_axis_tready       (cfar_ready),
    .s_axis_tdata        (ms_data),
    .s_axis_tlast        (ms_tlast),
    .mask_valid          (mask_valid),
    .mask                (mask),
    .cfg_error           (cfg_error)
  );

  m26_candidate_merge u_candidate_merge (
    .clk, .rst_n,
    .merge_gap         (merge_gap),
    .max_cand          (max_cand),
    .s_axis_tvalid     (ms_valid),
    .s_axis_tready     (cm_ready),
    .s_axis_tdata      (ms_data),
    .s_axis_tlast      (ms_tlast),
    .mask_valid        (mask_valid),
    .mask              (mask),
    .cand_valid        (cand_valid),
    .cand_start        (cand_start),
    .cand_end          (cand_end),
    .cand_peak         (cand_peak),
    .cand_bw           (cand_bw),
    .cand_power        (cand_power),
    .cand_wsum         (cand_wsum),
    .cand_done         (cand_done),
    .cand_count        (cand_count),
    .candidate_overflow(candidate_overflow)
  );

endmodule
