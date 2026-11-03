# Wujing Lite 200 MHz differential PL clock.
# Source: official FPAI Lite reference design and Lite hardware manual V1.0.
set_property PACKAGE_PIN C8 [get_ports sys_clk_p]
set_property PACKAGE_PIN C7 [get_ports sys_clk_n]
set_property IOSTANDARD DIFF_SSTL15 [get_ports {sys_clk_p sys_clk_n}]
create_clock -period 5.000 -name sys_clk_200m [get_ports sys_clk_p]

# Wujing Lite PL LEDs. The NDS331N LED drivers are active high.
set_property PACKAGE_PIN J1 [get_ports {led[0]}]
set_property PACKAGE_PIN M6 [get_ports {led[1]}]
set_property PACKAGE_PIN H7 [get_ports {led[2]}]
set_property PACKAGE_PIN J8 [get_ports {led[3]}]
set_property IOSTANDARD LVCMOS15 [get_ports {led[*]}]
