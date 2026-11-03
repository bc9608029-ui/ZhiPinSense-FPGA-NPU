# m3_synth_smartscan.tcl — smart-scan combined top synthesis (step 1 of 3).
#
# Integrates the smart-scan PS/PL engine + frozen datapath into the copied NPU
# base project.  The FFT core is a Vivado-synthesized EDIF for the BOARD part
# xc7z030ffg676-2 with STANDARD Unisim primitives (see build_xfft_z030.tcl), NOT
# the FMSH-migrated Procise EDIF (which Vivado cannot resolve — CU48E1/DRURE/...).
#
# Same shape as m3_synth_combined.tcl: append files, switch top, reset the PS7 OOC
# + synth_1 runs, launch synthesis.  Everything stays inside the candidate copy.
# Only heavy Vivado build runs at a time (queue).

set PRJ       {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/npu_base/fpai_demo_vivado.xpr}
set SS        {F:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/smartscan_integration}
set SS_RTL    [file join $SS rtl]
set SS_NET    [file join $SS netlist]

open_project $PRJ
puts "==M3S_OPEN_OK=="

# The EDIF file must be named to match its top module `smartscan_fft_1024`.
# Vivado's update_compile_order infers the module name from the file BASENAME, so
# a `smartscan_fft_1024_z030.edif` name makes it treat the netlist as a different
# (unreferenced) module and auto-disable it — the FFT then stays an unresolved
# black box at opt_design (DRC INBB-3).  The byte-identical copy is named
# `smartscan_fft_1024.edif` so basename == module name, exactly like the board's
# own `AI_Mate.edif`.
set net [file join $SS_NET smartscan_fft_1024.edif]
if {![file exists $net]} {
  puts "==M3S_NETLIST_MISSING== $net"
  close_project
  exit 1
}

# Datapath + engine + regs RTL + integration RTL.
add_files -norecurse [list \
  [file join $SS_RTL smart_scan_framer.sv] \
  [file join $SS_RTL hann_coeff_rom.v] \
  [file join $SS_RTL window_mul_q15.sv] \
  [file join $SS_RTL fft_vendor_ip_adapter.sv] \
  [file join $SS_RTL fft_psd_stream_writer.sv] \
  [file join $SS_RTL smart_scan_psd_buffers.sv] \
  [file join $SS_RTL smart_scan_top.sv] \
  [file join $SS_RTL smart_scan_iq_frame_marker.sv] \
  [file join $SS_RTL smart_scan_pspl_engine.sv] \
  [file join $SS_RTL smart_scan_pspl_regs.sv] \
  [file join $SS_RTL user_reg_router.sv] \
  [file join $SS_RTL user_ddr_read_arbiter.sv] \
  [file join $SS_RTL pl_ddr_mandatory_core_top_combined_smartscan.sv] \
]

# FFT core: BOTH the black-box stub .v AND the standard-primitive EDIF netlist,
# exactly mirroring the board's own AI_Mate flow (AI_Mate_stub.v + AI_Mate.edif,
# both is_enabled=1 / is_auto_disabled=0).  Vivado synthesis does NOT elaborate
# modules from EDIF netlists: without the stub .v it reports
# "module 'smartscan_fft_1024' not found" (Synth 8-439).  The stub (comment-form
# `synthesis syn_black_box`) lets synthesis infer a black box; the EDIF
# (read_edif) is stitched at implementation to resolve it (no DRC INBB-3).
# Do NOT use the Verilog `(* black_box *)` attribute here: in this project
# update_compile_order reacts to that attribute by auto-disabling the sibling
# EDIF.  The comment-form directive matches AI_Mate_stub.v and is safe.
#
# Self-heal: if a previous (broken) run left the mis-named
# `smartscan_fft_1024_z030.edif` in the project, remove it (its basename does
# not match the module name, which makes update_compile_order auto-disable it).
foreach stale [get_files -quiet {*smartscan_fft_1024_z030.edif}] {
  remove_files -fileset sources_1 $stale
  puts "==M3S_MISNAMED_EDIF_REMOVED== $stale"
}
add_files -norecurse [list \
  [file join $SS_NET smartscan_fft_1024_blackbox.v] \
  [file join $SS_NET smartscan_fft_1024.edif] \
]

set_property top pl_ddr_mandatory_core_top_combined_smartscan [current_fileset]
puts "==M3S_TOP=[get_property top [current_fileset]]=="

# Force-enable the EDIF netlist BEFORE the first update_compile_order, and set the
# three properties that make Vivado emit a `read_edif` line in the generated synth
# run tcl.  With no sibling stub defining the same module, update_compile_order
# keeps the EDIF in the compile order (AutoDisabled stays 0) and the FFT cell
# resolves at opt_design (no DRC INBB-3).  Fail closed if any property is off.
set ss_edif [get_files {*smartscan_fft_1024.edif}]
set_property is_enabled true $ss_edif
set_property used_in_synthesis true $ss_edif
set_property used_in_implementation true $ss_edif
update_compile_order -fileset sources_1

set edif_enabled      [get_property is_enabled $ss_edif]
set edif_used_synth   [get_property used_in_synthesis $ss_edif]
set edif_used_impl    [get_property used_in_implementation $ss_edif]
set edif_auto_dis     [get_property is_auto_disabled $ss_edif]
puts "==M3S_EDIF_ENABLED=${edif_enabled}=="
puts "==M3S_EDIF_USED_IN_SYNTHESIS=${edif_used_synth}=="
puts "==M3S_EDIF_USED_IN_IMPL=${edif_used_impl}=="
puts "==M3S_EDIF_AUTO_DISABLED=${edif_auto_dis}=="
if {($edif_enabled ne "1" && $edif_enabled ne "true") || \
    ($edif_used_synth ne "1" && $edif_used_synth ne "true") || \
    ($edif_used_impl ne "1" && $edif_used_impl ne "true") || \
    ($edif_auto_dis ne "0" && $edif_auto_dis ne "false")} {
  puts "==M3S_EDIF_NOT_READY== smartscan_fft_1024.edif enabled=${edif_enabled} used_in_synthesis=${edif_used_synth} used_in_impl=${edif_used_impl} auto_disabled=${edif_auto_dis}"
  close_project
  exit 1
}

# Fail closed on the black-box stub too: it must be present, enabled and used in
# synthesis, or the FFT instantiation will not elaborate (Synth 8-439).
set ss_stub [get_files {*smartscan_fft_1024_blackbox.v}]
set_property is_enabled true $ss_stub
set_property used_in_synthesis true $ss_stub
set stub_enabled    [get_property is_enabled $ss_stub]
set stub_used_synth [get_property used_in_synthesis $ss_stub]
puts "==M3S_STUB_ENABLED=${stub_enabled}=="
puts "==M3S_STUB_USED_IN_SYNTHESIS=${stub_used_synth}=="
if {($stub_enabled ne "1" && $stub_enabled ne "true") || \
    ($stub_used_synth ne "1" && $stub_used_synth ne "true")} {
  puts "==M3S_STUB_NOT_READY== smartscan_fft_1024_blackbox.v enabled=${stub_enabled} used_in_synthesis=${stub_used_synth}"
  close_project
  exit 1
}

foreach f [list \
  [file join $SS_RTL smart_scan_pspl_engine.sv] \
  [file join $SS_RTL smart_scan_pspl_regs.sv] \
  [file join $SS_RTL pl_ddr_mandatory_core_top_combined_smartscan.sv] \
  [file join $SS_NET smartscan_fft_1024_blackbox.v] \
  [file join $SS_NET smartscan_fft_1024.edif] \
] {
  puts "==M3S_SRC_EXISTS=[expr {[file exists $f] ? "YES" : "NO"}] $f=="
}

if {[get_runs -quiet ps_ai_processing_system7_0_0_synth_1] ne ""} {
  reset_run ps_ai_processing_system7_0_0_synth_1
  puts "==M3S_RESET_PS7_OOC=done=="
}
reset_run synth_1
puts "==M3S_RESET_SYNTH_1=done=="

# Fresh clone has no OOC run products: regenerate every IP, do not trust old statuses.
foreach ip_run [get_runs -quiet *_synth_1] {reset_run $ip_run}
launch_runs synth_1 -jobs 1
wait_on_run synth_1

set st [get_property STATUS   [get_runs synth_1]]
set pr [get_property PROGRESS [get_runs synth_1]]
puts "==M3S_SYNTH_STATUS=${st}=="
puts "==M3S_SYNTH_PROGRESS=${pr}=="
if {$pr ne "100%"} {
  puts "==M3S_SYNTH_FAILED== status=${st} see fpga/npu_base/fpai_demo_vivado.runs/synth_1/runme.log"
  close_project
  exit 1
}
puts "==M3S_SYNTH_OK=="
close_project
exit 0
