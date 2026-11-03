# FPGA auxiliary smartscan: fix2 review

> Latest continuation (2026-10-30 19:14): user resumed candidate generation from the SHA-verified routed checkpoint. Full implementation is complete. `BASELINE_EXCEPTION_GATE.json` matches the two inherited NPU min-period failures to the previously used baseline and permits the existing controlled-candidate generation path only. Full STA PASS and board acceptance remain unproven. Consult fresh `build/BITGEN_STATUS.json`; older build/pause descriptions below are retained as history.

2026-10-30. Offline candidate only. No board, RF, Flash, formal service or model change.

## Scope

Preserve the smartscan architecture: real IQ from PS/DDR → input CDC FIFO → symmetric Hann → real vendor 1024-point forward FFT → magnitude squared → fftshift double buffer → PS readback. CPU search policy and frozen NPU classifier remain separate. This work does not establish RF accuracy or deployment acceptance.

## Defects now evidenced and corrected

1. **Unreachable smartscan register bank.** Router default and top override used mask `0x0F000` against base `0x10000`. Selection was identically false. Both now use the 18-bit 4 KiB mask `0x3F000`. Full GP manager source passes the original 32-bit address; the user aperture starts at physical `0x400C0000`, hence smartscan bank is at `0x400D0000`. Software MMIO identity must be checked on board before operation. Low-18-bit routing retains the prior aperture contract.
2. **Functional datapath optimized away.** Old placed hierarchy had only 161 LUT/155 FF under `u_smart_scan`, no PSD RAM, and essentially no FFT arithmetic. Old placement/routing therefore cannot establish a working auxiliary feature. It was stopped deliberately, not classified as natural timing failure. Prior reports/checkpoint were preserved under `prior_build_evidence`.
3. **FIFO RAM inference failure at the congestion source.** Placed congestion windows were 122–150% and attributed 91–99% to `u_engine/input_adapter/cdc_fifo`. Original FIFO RAM ports shared asynchronously reset control blocks. Vivado explicitly reported RAM dissolved into registers because of async reset sensitivity. RAM accesses now use reset-free clocked processes with enables; valid/control/pointers retain async reset. Invalid `m_data` after reset is unspecified; valid data, valid latency and ready behavior are preserved.
4. **DDR response owner overwrite.** Prior arbiter could accept another engine's read before the first response. It now enforces one global outstanding single-beat read until response handshake, preserving NPU priority. The supported reader protocol is single-beat; this is not a general burst-ID arbiter.
5. Earlier PSD buffer sync-read BRAM fix remains in place; it was functionally correct but could not affect a branch later pruned by defect 1.

## Verification actually completed

- `tb_router.log`: all 262144 low-18-bit addresses, read/write decode, address remap, selection/backpressure, owner return; PASS.
- `tb_fifo.log`: old/new cycle and valid-data equivalence, 32/512/544-bit widths, two clock-rate ratios, random stalls, three reset/drain phases; ALL_FIFO_CASES_PASS.
- `tb_arbiter.log`: competing requests, delayed response, response backpressure, fixed priority, reset; DDR_ARBITER_PASS.
- `routed_pspl/xsim.log`: real FFT engine behind corrected register router, 3 clean / 2 faults; PASS.
- `shared_pspl/xsim_retry.log`: corrected router + corrected FIFO + corrected DDR arbiter + real FFT, 3 clean / 2 faults; PASS. NPU requester is idle in this integrated test; concurrent traffic is covered separately by arbiter test, not a full NPU co-execution test.
- Original 512-bit FIFO OOC: LUT 2119 / FF 8777 / BRAM Tile 0. Fixed: LUT 30 / FF 40 / BRAM Tile 7.5. Both real Vivado 2018.3 synthesis. This is module evidence, not final full-design utilization.
- Some first XSim launches failed to start the child executable; unchanged snapshots rerun successfully. Chinese-workdir synthesis crashed TclStackFree; successful comparison used existing ASCII F-drive scratch. Tool startup failures are retained and not described as RTL passes.

## Current full build

Independent candidate remains `F:/FPGA_Work/smartscan_bram_fix1_20261030`, now explicitly revision fix2 (`REVISION_FIX2.json`). Original external B project and formal system are unchanged. A partially applied source update due UTF-8 decoding was completed with preserved backups; no build was started from the partial update.

Initial scheduled task: `CodexSmartscanFix2_20261030`. Synthesis and opt_design completed, but the first implementation script stopped on an incorrectly assumed status string. Actual partial-run status is `Not started place_design`, progress 50%; it is not an opt_design failure. The successful end marker and fresh opt DCP were preserved. This script error was corrected, not treated as design closure evidence.

Current continuation task: `CodexSmartscanFix2Resume_20261030`. Status: `build/PIPELINE_STATUS.json`; continuation log: `build/implementation_resume_fix2.stdout.log`. `resume_fix2.tcl` verifies concrete begin/end/error stamps and checkpoint timestamps, loads the successful opt checkpoint, and requires retained FFT primitives plus real BRAM under FFT, PSD buffer, existing input/output FIFO and smartscan input FIFO before long P&R. No synthesis reset is done by the continuation. These structural gates do not replace board functional acceptance.

The first continuation also exposed that `open_run` cannot open this partial implementation state. It was replaced by the direct checkpoint flow (`direct_resume_guarded.tcl`, installed as `resume_fix2.tcl`). Both workflow errors are archived as `flow_status_mismatch.log` and `flow_partial_open_run.log`; neither is described as a natural design failure. Direct checkpoint read was independently executed successfully: `checkpoint_gate_probe.txt` confirms FFT 9778 primitives/8 BRAM, PSD buffer 4 BRAM, each of the three CDC FIFOs 8 BRAM. `checkpoint_utilization_hier.rpt` records full hierarchy after opt_design.

The direct continuation performs place_design, saves `reports_fix2/placed_fix2.dcp` and placed congestion/utilization/control-set/timing reports before route_design. It preserves a routed checkpoint and timing/exceptions **before** running the original unchanged vendor post-route hook, then produces final post-hook reports. Both sides must be reviewed so inherited vendor exceptions are visible. It generates no bitstream.

The pipeline stops at routed reports. No automatic bitstream generation/programming. Review setup/hold, pulse-width/min-period, routing, DRC, CDC, bus skew and constraints before generating a candidate bitstream.

## Remaining limitations

Full-design closure is pending; one-pass success is not promised. Frozen NPU baseline already had min-period/pulse-width failures on its 1 GHz AI clock (WPWS -0.409 ns), and current inherited constraints include internal primary-clock redefinition and DDR non-dedicated-clock warnings. These are not waived or silently relaxed; vendor target semantics and final reports must be reviewed. The resource repair is evidence-based but is not proof that all routing constraints are correct.

The DDR arbiter intentionally preserves NPU fixed priority, not round-robin fairness. An unbounded continuously pending NPU requester can starve smartscan; no bounded concurrent service guarantee is claimed. The old source comment claiming a one-cycle requester gap always prevents starvation is not a valid guarantee once global outstanding ownership is enforced. Board tests must cover real contention and timeout/software fallback.

After offline acceptance: target-specific candidate bitstream/Procise processing → board version/register readback → same-IQ software/FPGA A/B → auto fallback → RF regression. No RF_PASS / PROJECT_COMPLETE is claimed.

## Routed result (2026-10-30 18:10)

The guarded direct flow completed. Place time 9m39s; route time 6m07s. 97692/97692 routable nets are routed, 0 routing errors. Setup/hold pass (WNS +0.030 / WHS +0.008 ns). Complete report review is recorded in `FINAL_REPORT_REVIEW.json`; the vendor hook did not change timing summary values. All 6 reported bus-skew paths have positive slack (worst reported 3.645 ns).

Two inherited NPU minimum-period failures remain. Their exact provenance, target timing-library identity, local official SDK evidence, connectivity findings and signoff limitation are in `NPU_CLOCK_REVIEW.md`. No full timing PASS or new bitstream is claimed. The heavy implementation process has finished; no placement/routing job remains running.
