# Preserve the FMSH project-local post-opt patch, then make the automatically
# inserted debug hub metadata match the real 100 MHz gp_clk.
set project_dir [file normalize [file dirname [info script]]]
source [file join $project_dir ip_patch process_control implementation_opt_post.tcl]

set dbg_hub_core [get_debug_cores -quiet dbg_hub]
if {[llength $dbg_hub_core] != 1} {
    error "Expected exactly one auto-inserted dbg_hub after opt_design, found [llength $dbg_hub_core]"
}
set_property C_CLK_INPUT_FREQ_HZ 100000000 $dbg_hub_core
set_property C_ENABLE_CLK_DIVIDER false $dbg_hub_core
puts "GP0_DEBUG_HUB_CONFIGURED INPUT_FREQ_HZ=[get_property C_CLK_INPUT_FREQ_HZ $dbg_hub_core] DIVIDER=[get_property C_ENABLE_CLK_DIVIDER $dbg_hub_core]"
