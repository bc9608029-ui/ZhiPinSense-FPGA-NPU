set run_dir [file normalize [file dirname [info script]]]
set work_dir [file join $run_dir work_query]
file mkdir $work_dir
create_project -force smartscan_fft_query $work_dir -part xc7k325tffg900-2
source D:/FMSH/JFM_Kits/ip_patch/run.tcl
show_ip_patch_version
set hf [open [file join $run_dir add_hook_tcl_to_prj_body.txt] w]
puts $hf [info body add_hook_tcl_to_prj]
close $hf
create_ip -name xfft -vendor xilinx.com -library ip -version 9.1 \
          -module_name smartscan_fft_1024
set ip [get_ips smartscan_fft_1024]
set f [open [file join $run_dir xfft_default_properties.txt] w]
foreach p [lsort [list_property $ip]] {
    if {[string match "CONFIG.*" $p]} {
        puts $f "$p=[get_property $p $ip]"
    }
}
close $f
puts "XFFT_QUERY_RESULT result=PASS ip=[get_property IPDEF $ip]"
exit 0
