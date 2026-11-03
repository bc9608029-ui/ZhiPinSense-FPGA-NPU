set_param general.maxThreads 2
file mkdir fifo_synthesis
foreach version {original fixed} {
    create_project -in_memory -part xc7z030ffg676-2
    if {$version eq "original"} {read_verilog -sv async_fifo_gray_original.sv} else {read_verilog -sv async_fifo_gray.sv}
    synth_design -top async_fifo_gray -part xc7z030ffg676-2 -mode out_of_context
    report_utilization -file fifo_synthesis/${version}_util.rpt
    set brams [get_cells -hier -filter {REF_NAME =~ RAMB*}]
    set f [open fifo_synthesis/${version}_cells.txt w]
    puts $f "BRAM_CELLS=[llength $brams]"
    foreach c $brams {puts $f "$c [get_property REF_NAME $c]"}
    close $f
    if {$version eq "fixed" && [llength $brams] == 0} {error "FIFO_BLOCK_RAM_INFERENCE_FAILED"}
    close_project
}
puts "FIFO_SYNTH_COMPARISON_PASS"
exit
