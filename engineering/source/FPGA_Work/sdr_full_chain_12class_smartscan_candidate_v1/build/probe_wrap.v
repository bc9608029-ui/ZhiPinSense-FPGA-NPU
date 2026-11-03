module probe_wrap(input aclk, input aresetn);
  wire [31:0] s_tdata;
  wire s_tvalid, s_tready, s_tlast;
  wire [63:0] m_tdata;
  wire m_tvalid, m_tready, m_tlast;
  wire [7:0] cfg_tdata;
  wire cfg_tvalid, cfg_tready;
  wire [15:0] m_tuser;
  wire [0:0] m_status;
  smartscan_fft_1024 u_fft (
    .aclk(aclk), .aresetn(aresetn),
    .s_axis_config_tdata(cfg_tdata), .s_axis_config_tvalid(cfg_tvalid), .s_axis_config_tready(cfg_tready),
    .s_axis_data_tdata(s_tdata), .s_axis_data_tvalid(s_tvalid), .s_axis_data_tready(s_tready), .s_axis_data_tlast(s_tlast),
    .m_axis_data_tdata(m_tdata), .m_axis_data_tvalid(m_tvalid), .m_axis_data_tready(m_tready), .m_axis_data_tlast(m_tlast),
    .m_axis_data_tuser(m_tuser), .m_axis_status_tdata(m_status)
  );
endmodule
