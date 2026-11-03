set_param general.maxThreads 1
open_checkpoint {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/npu_base/fpai_demo_vivado.runs/impl_1/pl_ddr_mandatory_core_top_combined_smartscan_opt.dcp}
set f [open checkpoint_gate_probe.txt w]
foreach pattern {
 {u_smart_scan/u_scan/u_fft/*}
 {u_smart_scan/u_scan/u_buffers/*}
 {u_engine/input_adapter/cdc_fifo/*}
 {u_engine/output_adapter/cdc_fifo/*}
 {u_smart_scan/input_adapter/cdc_fifo/*}
} {
    set primitives 0;set bram 0
    foreach c [get_cells -hier -filter "IS_PRIMITIVE == 1 && NAME =~ $pattern"] {
        incr primitives
        if {[string match {RAMB*} [get_property REF_NAME $c]]} {incr bram}
    }
    puts $f "$pattern primitives=$primitives bram=$bram"
    puts "GATE_PROBE $pattern primitives=$primitives bram=$bram"
}
close $f
report_utilization -hierarchical -file checkpoint_utilization_hier.rpt
close_design
open_project {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/npu_base/fpai_demo_vivado.xpr}
help launch_runs
close_project
puts "CHECKPOINT_PROBE_COMPLETE"
exit
