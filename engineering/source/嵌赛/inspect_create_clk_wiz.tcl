set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
file mkdir [file join $project_dir ip]
open_project [file join $project_dir project_1.xpr]

puts "CLK_WIZ_IPDEFS_BEGIN"
foreach d [get_ipdefs -all -filter {NAME == clk_wiz}] {
    puts "IPDEF=$d"
}
puts "CLK_WIZ_IPDEFS_END"

if {[llength [get_ips -quiet clk_wiz_0]] == 0} {
    create_ip -name clk_wiz -vendor xilinx.com -library ip -module_name clk_wiz_0 \
        -dir [file join $project_dir ip]
}

report_property -all [get_ips clk_wiz_0] \
    -file [file join $project_dir reports clk_wiz_default_properties.rpt]
puts "CLK_WIZ_XCI=[get_property IP_FILE [get_ips clk_wiz_0]]"
close_project
