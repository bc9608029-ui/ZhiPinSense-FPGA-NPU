set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
file mkdir [file join $project_dir ip]
open_project [file join $project_dir project_1.xpr]

if {[llength [get_ips -quiet clk_wiz_0]] == 0} {
    create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 \
        -module_name clk_wiz_0 -dir [file join $project_dir ip]
}

set_property -dict [list \
    CONFIG.PRIMITIVE {MMCM} \
    CONFIG.PRIM_IN_FREQ {200.000} \
    CONFIG.CLKIN1_JITTER_PS {50.0} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {50.000} \
    CONFIG.CLKOUT1_DRIVES {BUFG} \
    CONFIG.USE_RESET {true} \
    CONFIG.RESET_TYPE {ACTIVE_HIGH} \
    CONFIG.USE_LOCKED {true}] [get_ips clk_wiz_0]

generate_target all [get_ips clk_wiz_0]
report_property -all [get_ips clk_wiz_0] \
    -file [file join $project_dir reports clk_wiz_50_properties.rpt]
puts "CLK_WIZ_CONFIGURED_200_TO_50"
close_project
