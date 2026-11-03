# FMQL30TAI Lite PL_KEY1, copied from the verified official Lite constraints.
# The key is idle-low and active-high. Do not add internal pulls.
set_property PACKAGE_PIN F8 [get_ports sys_rst]
set_property IOSTANDARD LVCMOS15 [get_ports sys_rst]

# The external reset request is synchronized before it drives GP logic.
set_false_path -from [get_ports sys_rst]
