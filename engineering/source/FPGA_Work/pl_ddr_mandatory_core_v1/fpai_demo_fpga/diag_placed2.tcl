# Second read-only diagnostic pass: congestion + hierarchical utilization +
# the specific inter-clock hold paths (100M/50M -> 200M clk_pll_i_1).  Still
# no XDC edits, no constraint additions, no bitstream.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_placed}
file mkdir $outdir

open_checkpoint $dcp

# Congestion.  2018.3 has report_design_analysis -congestion (report_congestion
# is a later command).  Use -file if supported, else -name + write_report.
if {[catch {report_design_analysis -congestion -file [file join $outdir congestion.rpt]} err]} {
    puts "WARN report_design_analysis -file unsupported; falling back to -name/write_report"
    report_design_analysis -congestion -name _cong
    write_report _cong -file [file join $outdir congestion.rpt]
}

# Hierarchical utilization to correlate congestion hotspots to module hierarchy.
report_utilization -hierarchical -file [file join $outdir utilization_hier.rpt]

# Inter-clock worst hold paths: 100M -> 200M (the dominant CDC hold source).
report_timing -delay_type min -from [get_clocks clk_out1_clk_wiz_0] -to [get_clocks clk_pll_i_1] -max_paths 5 -nworst 1 -path_type full_clock_expanded -file [file join $outdir inter_hold_100m_to_200m.rpt]
# Inter-clock worst hold paths: 50M -> 200M.
report_timing -delay_type min -from [get_clocks clk_out1_clk_wiz_core_50_1] -to [get_clocks clk_pll_i_1] -max_paths 5 -nworst 1 -path_type full_clock_expanded -file [file join $outdir inter_hold_50m_to_200m.rpt]

puts "DIAG_PLACED2_DONE"
close_design
