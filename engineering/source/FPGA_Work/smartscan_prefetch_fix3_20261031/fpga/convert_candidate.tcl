set_device JFMQL30TAI676H
set ROOT {E:/FPGA_Work/smartscan_prefetch_fix3_20261031/outputs/smartscan_fix2_candidate}
set INPUT [file join $ROOT smartscan_fix2_raw.bit]
set OUTPUT [file join $ROOT smartscan_fix2_disable_icap.bit.tmp]
if {[file exists $OUTPUT]} {error "CONVERSION_OUTPUT_EXISTS"}
increment_bit_cfg_v3 $INPUT $OUTPUT -disable_icap
if {![file exists $OUTPUT] || [file size $OUTPUT] < 1000000} {error "CONVERSION_OUTPUT_INVALID"}
puts "FIX2_EXPLICIT_CONVERSION_FINISHED"
exit
