# PL_KEY1: external 10 kOhm pulldown, active high, Bank 34 at 1.5 V.
# Do not add an internal PULLUP/PULLDOWN. Async assertion timing exceptions,
# if any are required, will be derived from post-synthesis/implementation
# timing evidence rather than applied broadly here.
set_property PACKAGE_PIN F8 [get_ports pl_key1_reset]
set_property IOSTANDARD LVCMOS15 [get_ports pl_key1_reset]
