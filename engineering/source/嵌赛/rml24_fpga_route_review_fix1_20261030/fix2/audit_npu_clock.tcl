set_param general.maxThreads 1
open_checkpoint {F:/FPGA_Work/smartscan_bram_fix1_20261030/reports_fix2/routed_fix2.dcp}
set f [open npu_clock_connectivity.txt w]
foreach suffix {AI_CORE_CLK/inst/plle2_adv_inst AI_CORE_CLK/inst/clkout1_buf} {
    set cell [get_cells -hier -filter "NAME =~ */clkrst_wrapper_u0/$suffix"]
    puts $f "CELL=$cell"
    foreach c $cell {
        puts $f "REF=[get_property REF_NAME $c]"
        foreach prop [list_property $c] {
            if {[regexp {CLK|DIV|MULT|PERIOD|FREQ} $prop]} {puts $f "$prop=[get_property $prop $c]"}
        }
        foreach pin [get_pins -of_objects $c -filter {DIRECTION == OUT}] {
            set nets [get_nets -segments -of_objects $pin]
            set loads [get_pins -of_objects $nets -filter {DIRECTION == IN}]
            puts $f "OUTPUT=$pin LOADS=[llength $loads]"
            foreach load [lrange $loads 0 59] {puts $f "  $load REF=[get_property REF_NAME [get_cells -of_objects $load]]"}
        }
    }
}
close $f
puts "NPU_CLOCK_CONNECTIVITY_AUDIT_COMPLETE"
close_design
exit
