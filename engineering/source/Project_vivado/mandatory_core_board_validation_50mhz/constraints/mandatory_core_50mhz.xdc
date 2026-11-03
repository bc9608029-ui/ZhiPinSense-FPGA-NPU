# Explicitly constrain the MMCM output used by all board-validation logic.
# The input clock is the existing 200 MHz sys_clk_200m clock on C8/C7.
create_generated_clock -name core_clk_50m \
    -source [get_pins u_core_clk_mmcm/CLKIN1] \
    -divide_by 4 \
    [get_pins u_core_clk_mmcm/CLKOUT0]
