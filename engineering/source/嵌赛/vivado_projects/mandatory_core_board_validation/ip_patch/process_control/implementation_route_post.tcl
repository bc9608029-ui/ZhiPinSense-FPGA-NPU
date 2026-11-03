set ::env(JFM_PATH) [file join [pwd] "../.."]
set run_tcl_path [file join $::env(JFM_PATH) "ip_patch" "run.tcl"]
source $run_tcl_path
set cells [get_cells -hier -filter {NAME =~ "*_bh_mig_lut3"}]
if {[llength $cells] == 0} {
	
} else {
	foreach cell $cells {
		set LUT3_O [get_nets -of [get_pins $cell/O]]
		set pin [get_pins -leaf -of [get_nets $LUT3_O] -filter {DIRECTION == IN}]
		set oserdes [get_cells -of [get_pins [lindex $pin 0]]]
		set_property DATA_RATE_TQ BUF [get_cells $oserdes]
		set_property TRISTATE_WIDTH	1 [get_cells $oserdes]
	}
	set lut4_cells [get_cells -hier -filter {NAME =~ "*bh_mig_eco/oserdes_dqsts_internal_INST_0"}]
	set oddr_q_net_list [list]
	foreach lut4 $lut4_cells {
		set lut4_o_net [get_nets -of [get_pins $lut4/O]]
		set pin  [get_pins -leaf -of [get_nets -of [get_pins $lut4/O]] -filter {DIRECTION == IN}]
		set oddr [get_cells -of [get_pins [lindex $pin 0]]]
		set oddr_q_net [get_nets -of [get_pins $oddr/Q]]
		remove_cell $oddr
		disconnectNet $lut4_o_net $lut4/O
		connectNet $oddr_q_net $lut4/O
		route_design -nets [get_nets $oddr_q_net]
	}
	puts "FMSH--bh_mig_oserdes_property_change excuted successfully!"

	set plls [get_cells -hierarchical  -filter {REF_NAME == PLLE2_ADV && PRIMITIVE_LEVEL == LEAF && NAME =~  *u_ddr3_infrastructure/plle2_i}]
	foreach pll $plls {
		set_false_path -from [get_clocks -of_objects [get_pins $pll/CLKOUT5]]
		set cells [get_cells -of_objects  [get_nets -segments  -of_objects [get_pins $pll/CLKOUT0]] -filter {REF_NAME == "PHASER_OUT_PHY" && PRIMITIVE_LEVEL == "LEAF"}]
		foreach cell $cells {
			puts "Name:$cell"
			set CTSBUS_0 [get_nets -of [get_pins $cell/CTSBUS[0]]]
			set CTSBUS_1 [get_nets -of [get_pins $cell/CTSBUS[1]]]
			if {$CTSBUS_0 == ""} {
				puts "Skip this cell,the pin CTSBUS is nc!"
				continue
			}
			set_false_path -through [get_pins $cell/CTSBUS]
			set_false_path -through [get_pins $cell/DTSBUS]
		}
    }
}

