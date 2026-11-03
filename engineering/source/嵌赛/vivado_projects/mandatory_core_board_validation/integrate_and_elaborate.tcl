set project_root [file normalize [file dirname [info script]]]
set source_root [file normalize [file join $project_root src]]
set xpr_path [file join $project_root project_1.xpr]
set vector_path [file normalize [file join $project_root iq_input.hex]]
set reset_xdc [file normalize [file join $project_root constraints mandatory_core_reset.xdc]]
set report_dir [file normalize [file join $project_root reports]]
file mkdir $report_dir

if {![file exists $xpr_path]} { error "Missing copied baseline project: $xpr_path" }
if {![file exists $vector_path]} { error "Missing frozen IQ vector: $vector_path" }
if {![file exists $reset_xdc]} { error "Missing reset constraint: $reset_xdc" }

open_project $xpr_path

if {[get_property PART [current_project]] ne "xc7z030ffg676-2"} {
    error "Unexpected part: [get_property PART [current_project]]"
}

set source_set [get_filesets sources_1]
set constraint_set [get_filesets constrs_1]

# Remove only the old LED top from the copied project.  Its physical source
# remains intact in this copied baseline and in the original project.
set old_led [get_files -quiet -of_objects $source_set */led_flow_top.v]
if {[llength $old_led] > 0} {
    remove_files -fileset $source_set $old_led
}

set rtl_files [list \
    [file join $source_root iq_stream_fifo.sv] \
    [file join $source_root iq_frame_controller.sv] \
    [file join $source_root qam_feature_pipeline.sv] \
    [file join $source_root feature_quantizer.sv] \
    [file join $source_root tensor_packer.sv] \
    [file join $source_root mandatory_core_path.sv] \
    [file join $source_root fixed_iq_rom.sv] \
    [file join $source_root iq_replay_controller.sv] \
    [file join $source_root board_mandatory_core_test_top.sv] \
]

foreach rtl $rtl_files {
    set rtl [file normalize $rtl]
    if {![file exists $rtl]} { error "Missing RTL source: $rtl" }
    if {[llength [get_files -quiet $rtl]] == 0} {
        add_files -fileset $source_set -norecurse $rtl
    }
    set_property FILE_TYPE SystemVerilog [get_files $rtl]
}

if {[llength [get_files -quiet $vector_path]] == 0} {
    add_files -fileset $source_set -norecurse $vector_path
}
set_property FILE_TYPE {Memory Initialization Files} [get_files $vector_path]

if {[llength [get_files -quiet $reset_xdc]] == 0} {
    add_files -fileset $constraint_set -norecurse $reset_xdc
}

set_property top board_mandatory_core_test_top $source_set
set_property generic {ROM_INIT_FILE=iq_input.hex} $source_set
update_compile_order -fileset $source_set

# The inherited LED XDC supplies the proven clock and LED constraints.
set baseline_xdc [get_files -quiet -of_objects $constraint_set */led_flow_lite.xdc]
if {[llength $baseline_xdc] != 1} {
    error "Expected exactly one inherited led_flow_lite.xdc, found [llength $baseline_xdc]"
}

report_compile_order -used_in synthesis -file [file join $report_dir elaboration_compile_order.rpt]

puts "ELAB_INFO part=[get_property PART [current_project]]"
puts "ELAB_INFO top=[get_property top $source_set]"
puts "ELAB_INFO generic=[get_property generic $source_set]"
puts "ELAB_INFO baseline_xdc=$baseline_xdc"
puts "ELAB_INFO reset_xdc=[get_files $reset_xdc]"

# Vivado's RTL elaboration flow; no technology synthesis or implementation.
synth_design -rtl -name rtl_1 -top board_mandatory_core_test_top -part xc7z030ffg676-2

set ports_file [open [file join $report_dir elaboration_ports.rpt] w]
foreach port [lsort [get_ports *]] {
    puts $ports_file "$port direction=[get_property DIRECTION $port] iostandard=[get_property IOSTANDARD $port] package_pin=[get_property PACKAGE_PIN $port]"
}
close $ports_file

set hierarchy_file [open [file join $report_dir elaboration_hierarchy.rpt] w]
foreach cell [lsort [get_cells -hierarchical -filter {IS_PRIMITIVE == 0}]] {
    puts $hierarchy_file "$cell [get_property REF_NAME $cell]"
}
close $hierarchy_file

report_drc -file [file join $report_dir elaboration_drc.rpt]

close_design
if {[llength [get_runs -quiet synth_1]] > 0} { reset_run synth_1 }
if {[llength [get_runs -quiet impl_1]] > 0} { reset_run impl_1 }
close_project
puts "ELABORATION_PASS"
