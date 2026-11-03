// M26-A  streaming frontend top level.
//
//   IQ -> [dc_removal] -> [nco] -> [fir] -> [decimator] -> IQ out
//               \-> [energy_rms] -> [signal_presence]  (observer, out of band)
//
// Every data-path stage is independently bypassable and fail-closed on illegal
// parameters (see M26_FIXED_POINT_CONTRACT.md §17).  The energy/RMS + signal-presence
// observer taps the dc_removal->nco *transfer beat* (the sample is counted exactly
// once per accepted sample, so back-pressure stalls cannot double-count), and its
// per-frame statistics feed the hysteretic presence detector.  Metadata (frame_id /
// timestamp / sample_count, §16) is added at the integration wrapper, not here.
module m26_stream_frontend_top (
    input  logic        clk,
    input  logic        rst_n,          // async, active-low
    // per-stage bypass
    input  logic        bypass_dc,
    input  logic        bypass_nco,
    input  logic        bypass_fir,
    input  logic        bypass_decim,
    // NCO + decimator config
    input  logic [31:0] nco_phase_inc,  // round(f/fs * 2^32)
    input  logic [3:0]  decim_factor,   // legal {2,4,8}
    // energy / presence config
    input  logic        energy_enable,
    input  logic [15:0] thr_enter,      // Q0.15
    input  logic [15:0] thr_exit,       // Q0.15
    input  logic [3:0]  enter_m,
    input  logic [3:0]  exit_n,
    // AXI-Stream slave
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic [31:0] s_axis_tdata,   // {I[15:0], Q[15:0]}
    input  logic        s_axis_tlast,
    // AXI-Stream master
    output logic        m_axis_tvalid,
    input  logic        m_axis_tready,
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tlast,
    // observer / statistics
    output logic [47:0] energy,         // Q0.30
    output logic [15:0] rms,            // Q0.15
    output logic [31:0] peak,           // Q0.30
    output logic        stats_valid,
    output logic [1:0]  presence,
    output logic        presence_changed,
    // fail-closed status
    output logic        cfg_error
);
  // ---- dc_removal -> nco stream
  logic        dc_valid, dc_ready, dc_tlast;
  logic [31:0] dc_data;
  // ---- nco -> fir stream
  logic        nco_valid, nco_ready, nco_tlast;
  logic [31:0] nco_data;
  // ---- fir -> decimator stream
  logic        fir_valid, fir_ready, fir_tlast;
  logic [31:0] fir_data;

  m26_dc_removal u_dc (
    .clk, .rst_n,
    .bypass       (bypass_dc),
    .s_axis_tvalid(s_axis_tvalid),
    .s_axis_tready(s_axis_tready),
    .s_axis_tdata (s_axis_tdata),
    .s_axis_tlast (s_axis_tlast),
    .m_axis_tvalid(dc_valid),
    .m_axis_tready(dc_ready),
    .m_axis_tdata (dc_data),
    .m_axis_tlast (dc_tlast)
  );

  m26_nco u_nco (
    .clk, .rst_n,
    .bypass       (bypass_nco),
    .phase_inc    (nco_phase_inc),
    .s_axis_tvalid(dc_valid),
    .s_axis_tready(dc_ready),
    .s_axis_tdata (dc_data),
    .s_axis_tlast (dc_tlast),
    .m_axis_tvalid(nco_valid),
    .m_axis_tready(nco_ready),
    .m_axis_tdata (nco_data),
    .m_axis_tlast (nco_tlast)
  );

  m26_fir u_fir (
    .clk, .rst_n,
    .bypass       (bypass_fir),
    .s_axis_tvalid(nco_valid),
    .s_axis_tready(nco_ready),
    .s_axis_tdata (nco_data),
    .s_axis_tlast (nco_tlast),
    .m_axis_tvalid(fir_valid),
    .m_axis_tready(fir_ready),
    .m_axis_tdata (fir_data),
    .m_axis_tlast (fir_tlast)
  );

  m26_decimator u_decim (
    .clk, .rst_n,
    .bypass       (bypass_decim),
    .decim        (decim_factor),
    .s_axis_tvalid(fir_valid),
    .s_axis_tready(fir_ready),
    .s_axis_tdata (fir_data),
    .s_axis_tlast (fir_tlast),
    .m_axis_tvalid(m_axis_tvalid),
    .m_axis_tready(m_axis_tready),
    .m_axis_tdata (m_axis_tdata),
    .m_axis_tlast (m_axis_tlast),
    .cfg_error    (cfg_error)
  );

  // ---- observer: energy/RMS on the dc_removal->nco transfer beat
  m26_energy_rms u_energy (
    .clk, .rst_n,
    .enable       (energy_enable),
    .s_axis_tvalid(dc_valid && dc_ready),
    .s_axis_tready(),
    .s_axis_tdata (dc_data),
    .s_axis_tlast (dc_tlast),
    .stats_valid  (stats_valid),
    .energy       (energy),
    .rms          (rms),
    .peak         (peak)
  );

  m26_signal_presence u_presence (
    .clk, .rst_n,
    .frame_valid      (stats_valid),
    .rms              (rms),
    .thr_enter        (thr_enter),
    .thr_exit         (thr_exit),
    .enter_m          (enter_m),
    .exit_n           (exit_n),
    .presence         (presence),
    .presence_changed (presence_changed)
  );

endmodule
