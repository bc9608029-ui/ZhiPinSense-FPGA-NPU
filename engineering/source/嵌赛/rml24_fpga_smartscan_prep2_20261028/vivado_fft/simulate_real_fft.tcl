set root [file normalize [lindex $argv 0]]
set project_path [lindex $argv 1]
open_project $project_path
foreach name {window_mul_q15.sv fft_psd_stream_writer.sv hann_coeff_rom.v smart_scan_framer.sv smart_scan_psd_buffers.sv fft_vendor_ip_adapter.sv smart_scan_top.sv} {
 add_files -fileset sim_1 -norecurse [file join $root rtl $name]
}
add_files -fileset sim_1 -norecurse [file join $root tb tb_smart_scan_real_fft.sv]
set_property top tb_smart_scan_real_fft [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sim_1
launch_simulation -mode behavioral
close_sim
puts "REAL_FFT_SIM_FLOW_COMPLETE inspect_testbench_pass_token=REQUIRED"
close_project
exit 0
