read_verilog -sv fft_frame_prefetch.sv
read_verilog -sv fft_vendor_ip_adapter.sv
read_verilog E:/FPGA_Work/smartscan_bram_fix1_20261030/fpga/smartscan_integration/netlist/smartscan_fft_1024_blackbox.v
synth_design -mode out_of_context -top fft_vendor_ip_adapter -part xc7z030ffg676-2
create_clock -period 20 [get_ports clk]
report_utilization -file prefetch_bram_utilization.rpt
report_timing_summary -file prefetch_bram_timing.rpt
write_checkpoint -force prefetch_bram_ooc.dcp
puts PREFETCH_OOC_SYNTH_PASS_NOT_FULL_IMPLEMENTATION
exit
