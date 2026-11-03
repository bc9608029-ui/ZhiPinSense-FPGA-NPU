set PRJ       {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/npu_base/fpai_demo_vivado.xpr}
set SS        {F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga/smartscan_integration}
set SS_NET    [file join $SS netlist]
open_project $PRJ
foreach stale [get_files -quiet {*smartscan_fft_1024_z030.edif}] {
  remove_files -fileset sources_1 $stale
  puts "==DRYRUN_MISNAMED_EDIF_REMOVED== $stale"
}
add_files -norecurse [list \
  [file join $SS_NET smartscan_fft_1024_blackbox.v] \
  [file join $SS_NET smartscan_fft_1024.edif] \
]
set ss_edif [get_files {*smartscan_fft_1024.edif}]
set_property is_enabled true $ss_edif
set_property used_in_synthesis true $ss_edif
set_property used_in_implementation true $ss_edif
set ss_stub [get_files {*smartscan_fft_1024_blackbox.v}]
set_property is_enabled true $ss_stub
set_property used_in_synthesis true $ss_stub
update_compile_order -fileset sources_1
puts "==DRYRUN_EDIF auto_dis=[get_property is_auto_disabled $ss_edif] enabled=[get_property is_enabled $ss_edif] synth=[get_property used_in_synthesis $ss_edif]=="
puts "==DRYRUN_STUB enabled=[get_property is_enabled $ss_stub] synth=[get_property used_in_synthesis $ss_stub] file_type=[get_property file_type $ss_stub]=="
# Dump the generated synth run tcl read lines for the two files
set run_tcl [get_files -quiet {*.runs/synth_1/*.tcl}]
puts "==DRYRUN_RUNTCL=[get_property name [get_runs synth_1]]=="
# reset_run would regenerate the tcl; instead inspect current compile order
puts "==DRYRUN_COMPILE_ORDER=="
foreach f [get_files -of_objects [get_filesets sources_1] -filter {is_auto_disabled == 0}] {
  set bn [file tail $f]
  if {$bn eq "smartscan_fft_1024_blackbox.v" || $bn eq "smartscan_fft_1024.edif"} {
    puts "  in-order: $bn (type=[get_property file_type $f])"
  }
}
close_project
