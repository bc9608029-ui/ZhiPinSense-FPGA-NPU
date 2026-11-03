# Frozen NPU clock review — unresolved acceptance item

> Historical review, supplemented after baseline investigation: `BASELINE_EXCEPTION_GATE.json` verifies the exact two negative minimum-period endpoints and values against the previously used baseline. Existing project policy permits controlled candidate generation with this inherited exception; it does not establish full STA PASS, a manufacturer waiver, production release, or board acceptance. Earlier text requiring a newly obtained waiver before any generation is superseded by this scoped historical-policy finding.

## Measured facts

- Current full routing: 97692/97692 routable nets routed, 0 routing errors.
- Global setup/hold: WNS +0.030 ns, TNS 0; WHS +0.008 ns, THS 0.
- The integrated feature/smartscan clock is **50 MHz**. Its clock-group table has WNS +6.363 ns and WHS +0.047 ns. The earlier 100 MHz OOC target is a separate test, not the integrated operating clock.
- Two remaining minimum-period failures are on `clk_out1_AI_CORE_CLK_ST_1`, nominal period 1.000 ns: BUFG/I requires 1.409 ns (slack -0.409 ns); PLLE2_ADV/CLKOUT0 requires 1.071 ns (reported -0.071 ns). Rounded cumulative TPWS is -0.479 ns. Neither is on the FFT clock.
- Timing summary before and after the unchanged vendor post-route hook is identical. No new timing exception was added to hide these failures.

## Provenance checks

1. Candidate `AI_Mate.edif` is byte-identical to the unpacked local vendor reference `tmp_official_fpga_audit/fpai_demo_fpga/rtl/edif/AI_Mate.edif`: SHA256 `38f14b4427244f49a1ff0edf9dcdfe4438d033807d76018c688aa218c491d49c`.
2. The vendor reference PLL itself has CLKIN1_PERIOD=5 ns, CLKFBOUT_MULT=5, DIVCLK_DIVIDE=1, CLKOUT0_DIVIDE=1. Thus 1 GHz is inherited from the supplied design, not introduced by smartscan.
3. Installed Vivado `xc7z030.paspd` matches the vendor `JFM_Kits.zip` member `ip_patch/030ai/xc7z030ai.paspd`: SHA256 `71e30a2e40fab8ef620249acbc94711444698cc384f2a05b5385d4a235c81cca`. It is not the generic Xilinx paspd from that kit. See `SPEED_LIBRARY_AUDIT.json`.
4. Local official ICraft header `D:/icraft39/include/icraft-xrt/dev/zg330_device.h:53` initializes `icore_clk_freq = 1000E6`; generated local API docs show the same default. A `setIcoreClkFreq()` declaration exists, but no examined implementation proves that this call reprograms hardware. It must not be presented as a verified clock fix.
5. Direct routed connectivity inspection (`npu_clock_connectivity.txt`) finds the PLL output → BUFG → `ai_core_clk_locked_reg/C` as the only explicit BUFG load. This is **not** proof the vendor branch is disposable: target-specific NPU/bitstream behavior is not fully represented by that observation.

## What was not done

No PLL divider, vendor EDIF, model, clock constraint, timing exception or DRC severity was changed to obtain a clean report. The 1 GHz branch was not removed. No new bitstream was generated or loaded. Existing formal board services/bitstream are untouched.

## Acceptance consequence

Current status: `ROUTED_SETUP_HOLD_PASS_CLOCK_MIN_PERIOD_REVIEW_PENDING`, not full STA PASS and not READY_FOR_BOARD_TEST.

The examined local board/tutorial/Procise documentation and public product information did not provide an explicit disposition for these exact minimum-period violations. Vendor default frequency and baseline equality explain provenance; they do not by themselves waive a physical timing requirement. Preserve the routed checkpoint and new working datapath; do not rerun synthesis/P&R merely to investigate this clock item.

## Concrete clarification needed for final signoff

For FMQL30TAI, Vivado 2018.3 with the supplied 030ai timing library, supplied `AI_Mate.edif` and static 1 GHz `AI_CORE_CLK_ST`:

1. Are these BUFG/PLLE2 minimum-period checks expected limitations of the target mapping, or an unsupported NPU clock configuration?
2. What documented target-specific signoff rule, updated IP/library, or supported clock configuration should be used?
3. If clock configuration must change, how are NPU configuration, initialization and profiler frequency kept consistent without changing the frozen classifier contract?

This file is a prepared technical question/evidence record. It has not been sent to anyone.
