# FPGA takeover status — 2026-10-30

**Superseded by fix2:** the initial BRAM-only full build was deliberately stopped after discovery of an unreachable register decoder and optimized-away FFT datapath. Current authoritative status is [fix2/REVIEW_AND_STATUS.md](fix2/REVIEW_AND_STATUS.md). The independent project is now revision fix2; task `CodexSmartscanFix2_20261030` runs the guarded build. The remainder below preserves the earlier checkpoint of work, not current acceptance.

Independent project: `F:/FPGA_Work/smartscan_bram_fix1_20261030`.

The only functional RTL change is the PSD double-buffer synchronous BRAM read. Original and fixed module synthesis: LUT 3061 → 66, LUTRAM 2496 → 0, RAMB cells 0 → 4. This is module-level evidence, not full-design timing closure.

Complete PS/PL regression: `pspl_regression/xsim.log`, `TB_SMART_SCAN_PSPL PASS cases=3 faults=2`; version, zero input, tone bin 549, consecutive banks, invalid configuration and DDR stall tested.

Scheduled task `CodexSmartscanBramFix1_20261030` runs the independent synthesis then implementation through route_design. Status is recorded every 10 seconds in independent project `build/PIPELINE_STATUS.json`. At 13:55 it was running IP synthesis dependencies. Do not launch another full build concurrently.

The pipeline stops after routed reports. It does not generate/program a bitstream or modify the formal system. Required review includes route completeness, setup/hold, pulse-width/min-period checks, DRC, CDC and constraint coverage.

## Additional baseline issue requiring interpretation

Original `fpga/m1_baseline/reports/npu_timing_summary.rpt` already has WPWS=-0.409 ns, TPWS=-0.479 ns, 2 endpoints. One endpoint is AI_CORE_CLK_ST_1 at nominal 1 ns period, BUFG minimum period 1.409 ns (report lines around 5890–5910). This is in the frozen NPU branch, not the new FFT buffer. Do not describe the baseline as entirely timing-clean based solely on positive WNS/WHS. Inspect its vendor migration semantics and candidate reports before judging final acceptance; do not change frozen NPU clocks or waive this blindly.

Original project and bitstream preserved. All substantive new artifacts and temporary build directories are on F drive.
