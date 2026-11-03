# report_clocks_post.tcl — after the main build, open the routed design and
# emit a dedicated clock report so the two-MMCM chain can be verified against
# the expected 74.25 MHz (pixel) + 371.25 MHz (5x TMDS).
#
# Usage (after build_hdmi_colorbar_720p.tcl has run):
#   vivado -mode batch -source report_clocks_post.tcl
set script_dir [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir vivado_prj]
set report_dir  [file join $script_dir reports]
set xpr [file join $project_dir hdmi_colorbar_720p.xpr]

if {![file exists $xpr]} {
    error "project not found: $xpr (run build_hdmi_colorbar_720p.tcl first)"
}

open_project $xpr
open_run impl_1
report_clocks         -file [file join $report_dir routed_clocks.rpt]
report_clock_networks -file [file join $report_dir routed_clock_networks.rpt]
report_clock_interaction -file [file join $report_dir routed_clock_interaction.rpt]
close_design
close_project
puts "CLOCK_REPORT_DONE"
