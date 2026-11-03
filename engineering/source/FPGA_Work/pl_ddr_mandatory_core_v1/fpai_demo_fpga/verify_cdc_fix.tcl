# Fast check that the corrected cdc_async_groups.xdc (with
# -include_generated_clocks) actually cuts the cross-domain generated-clock
# paths.  Opens the placed.dcp, applies the corrected XDC, and re-reports the
# clock interaction matrix + worst hold paths.  Read-only.

set dcp {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_placed.dcp}
set xdc {F:/FPGA_Work/pl_ddr_mandatory_core_v1/pl_ddr_integration_v1/cdc_async_groups.xdc}
set outdir {F:/FPGA_Work/pl_ddr_mandatory_core_v1/fpai_demo_fpga/reports/pl_ddr_mandatory_core_v1/diag_cdc_effect}
file mkdir $outdir

open_checkpoint $dcp
read_xdc $xdc

report_clock_interaction -delay_type min -file [file join $outdir clock_interaction_hold_after_fix.rpt]
report_timing -delay_type min -max_paths 10 -nworst 1 -file [file join $outdir worst_hold_after_fix.rpt]

puts "VERIFY_CDC_FIX_DONE"
close_design
