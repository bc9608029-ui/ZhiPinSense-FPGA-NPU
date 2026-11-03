module probe_wrap2(input aclk, input aresetn);
  wire [7:0]  s_cfg_tdata; wire s_cfg_tvalid, s_cfg_tready;
  wire [31:0] s_tdata; wire s_tvalid, s_tready, s_tlast;
  wire [63:0] m_tdata; wire [15:0] m_tuser; wire m_tvalid, m_tlast;
  wire ev_fs, ev_tu, ev_tm, ev_dh;
  smartscan_fft_1024 u_fft (
    .aclk(aclk), .aresetn(aresetn),
    .s_axis_config_tdata(s_cfg_tdata), .s_axis_config_tvalid(s_cfg_tvalid), .s_axis_config_tready(s_cfg_tready),
    .s_axis_data_tdata(s_tdata), .s_axis_data_tvalid(s_tvalid), .s_axis_data_tready(s_tready), .s_axis_data_tlast(s_tlast),
    .m_axis_data_tdata(m_tdata), .m_axis_data_tuser(m_tuser), .m_axis_data_tvalid(m_tvalid), .m_axis_data_tlast(m_tlast),
    .event_frame_started(ev_fs), .event_tlast_unexpected(ev_tu), .event_tlast_missing(ev_tm), .event_data_in_channel_halt(ev_dh)
  );
endmodule
