module smartscan_fft_migration_top (
    input wire aclk, input wire aresetn,
    input wire [7:0] s_axis_config_tdata, input wire s_axis_config_tvalid,
    output wire s_axis_config_tready,
    input wire [31:0] s_axis_data_tdata, input wire s_axis_data_tvalid,
    output wire s_axis_data_tready, input wire s_axis_data_tlast,
    output wire [63:0] m_axis_data_tdata, output wire [15:0] m_axis_data_tuser,
    output wire m_axis_data_tvalid, output wire m_axis_data_tlast,
    output wire event_frame_started, output wire event_tlast_unexpected,
    output wire event_tlast_missing, output wire event_data_in_channel_halt
);
smartscan_fft_1024 u_fft (
    .aclk(aclk), .aresetn(aresetn),
    .s_axis_config_tdata(s_axis_config_tdata),
    .s_axis_config_tvalid(s_axis_config_tvalid),
    .s_axis_config_tready(s_axis_config_tready),
    .s_axis_data_tdata(s_axis_data_tdata),
    .s_axis_data_tvalid(s_axis_data_tvalid),
    .s_axis_data_tready(s_axis_data_tready),
    .s_axis_data_tlast(s_axis_data_tlast),
    .m_axis_data_tdata(m_axis_data_tdata),
    .m_axis_data_tuser(m_axis_data_tuser),
    .m_axis_data_tvalid(m_axis_data_tvalid),
    .m_axis_data_tlast(m_axis_data_tlast),
    .event_frame_started(event_frame_started),
    .event_tlast_unexpected(event_tlast_unexpected),
    .event_tlast_missing(event_tlast_missing),
    .event_data_in_channel_halt(event_data_in_channel_halt)
);
endmodule
