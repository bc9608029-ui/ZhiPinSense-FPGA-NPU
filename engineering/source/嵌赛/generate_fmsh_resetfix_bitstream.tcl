set project_dir {F:/Project_vivado/mandatory_core_board_validation_50mhz}
set dcp [file join $project_dir reports ila_50mhz_resetfix_routed_eco mandatory_core_routed_ila_50mhz_resetfix.dcp]
set output_dir [file join $project_dir bitstreams_ila_50mhz_resetfix]
set raw_bit [file join $output_dir board_mandatory_core_test_top_ila_50mhz_resetfix.bit]
file mkdir $output_dir

open_checkpoint $dcp

set hook_run_dir [file join $project_dir project_1.runs impl_ila_resetfix]
file mkdir $hook_run_dir
cd $hook_run_dir
set ::env(JFM_PATH) $project_dir
source [file join $project_dir ip_patch run.tcl]
puts "FMSH_PATCH_VERSION=$::ip_patch::version"
puts "FMSH_PATCH_USER_ID=$::ip_patch::user_id"
pre_write_bitstream_patch

set current_user_id [get_property BITSTREAM.CONFIG.USERID [get_designs [current_design]]]
if {$current_user_id == ""} {
    set_property BITSTREAM.CONFIG.USERID 32'h$::ip_patch::user_id [get_designs [current_design]]
}
puts "BITSTREAM_USER_ID=[get_property BITSTREAM.CONFIG.USERID [get_designs [current_design]]]"

set device_part [get_property PART [current_design]]
if {[regexp {xc7z030} $device_part] || [regexp {xc7z100_jfmql} $device_part]} {
    foreach check_name {REQP-44 REQP-46 REQP-52 REQP-56} {
        set check_obj [get_drc_checks -quiet $check_name]
        if {[llength $check_obj] > 0} {
            set_property IS_ENABLED 0 $check_obj
        }
    }
}

write_checkpoint -force [file join $output_dir board_mandatory_core_test_top_ila_50mhz_resetfix_prebit.dcp]
write_bitstream -force $raw_bit
puts "RAW_BITSTREAM=$raw_bit"
puts "RAW_BITSTREAM_EXISTS=[file exists $raw_bit]"
puts "RAW_BITSTREAM_SIZE=[file size $raw_bit]"
puts "FMSH_RESETFIX_RAW_BITSTREAM_COMPLETE"
exit
