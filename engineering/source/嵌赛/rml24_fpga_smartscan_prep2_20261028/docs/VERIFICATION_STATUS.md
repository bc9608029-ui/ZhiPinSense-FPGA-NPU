# Verification status

## Passed on the PC

- Golden/vector generation: four deterministic 1024-point cases.
- Fixed-point boundary self-test, including the unsigned-54-bit extreme value.
- Post-FFT writer reference: natural-order input to fftshift-addressed u54 PSD,
  four vector sets byte-for-byte equal.
- XSim 2018.3 was found at the explicit path
  `D:/Xilinx2018.3/Vivado/2018.3/bin` and re-run successfully.
- The primitive boundary test passed at 40 ns.
- The new post-FFT writer test passed 2048/2048 bins across two frames with
  periodic backpressure, fftshift addresses, u54 power, bank toggle, frame id,
  and `protocol_error=0`.
- Vivado 2018.3 with FMSH ip_patch 5.3.1.8 generated and synthesized XFFT 9.1.
  The generated configuration proves 16-bit complex input, 1024 points,
  unscaled natural-order output, XK_INDEX, and 27-bit complex output.
- Procise 2025.1.1 completed synthesis, placement, routing and STA for the
  post-FFT OOC harness on JFMQL30TAI676H. At 100 MHz the reported slack is
  +0.1784 ns; the harness uses 622 LUT, 152 slice registers, 6 CU and 0 RAMB.
- The migrated XFFT 9.1 netlist was linked with the window/writer in a single
  Procise project (`run_combined_ooc.tcl`). The Verilog `fft_vendor_ip_adapter`
  instantiates `smartscan_fft_1024` through a `(* black_box *)` declaration
  (`smartscan_fft_1024_blackbox.v`), and the migrated `smartscan_fft_1024.edif`
  provides the implementation (`read_edif` -> `bind_design` -> `uniquify`).
  Result: `SMARTSCAN_COMBINED_OOC_RESULT result=PASS device=JFMQL30TAI676H
  clock_ns=10 includes_fft=YES production_bitstream=NO`.
  - Resources: 3149 LUT, 4594 FF, 19 CU48E1 (13 FFT + 6 window), 8 RAMH18E1,
    4 RAMH36E1 (RAM/FIFO), 69 IO.
  - STA at 100 MHz: setup slack +0.497 ns, hold slack +0.100 ns (both MET).
    The critical path is in the window multiplier, not the FFT netlist.
- The full production datapath — Hann-window framer -> migrated XFFT 9.1 ->
  u54 magnitude-square -> fftshift-addressed writer -> ping-pong double buffer,
  instantiated by `smart_scan_top` — was synthesised, placed, routed and
  STA-timed as one Procise project (`run_production_ooc.tcl`) on
  JFMQL30TAI676H. Result:
  `SMARTSCAN_PRODUCTION_OOC_RESULT result=PASS device=JFMQL30TAI676H clock_ns=10
  includes_fft=YES includes_hann=YES includes_double_buffer=YES
  production_bitstream=NO`.
  - Resources: 3740 LUT, 4707 FF, 19 CU48E1, 8 RAMH18E1 / 4 RAMH36E1
    (RAM/FIFO); Slice LUTs 10.78 %, Slice Registers 2.95 %.
  - Both banks infer one-port 1024x64 block RAM (`Found a RAM 'mem0'/'mem1'`),
    confirming the two-1D-array fix (a single 2D `mem[0:1][...]` had flattened
    to ~110 k FF plus a 2048:1 read mux and failed placement).
  - STA at 100 MHz: setup slack +0.154 ns, hold slack +0.101 ns (both MET).
    Critical path is the window multiplier (`u_window`, 22 logic levels).
  - **Re-run 2026-10-29 09:30** (staging dir
    `%TEMP%\rml24_smartscan_production_ooc_20261029_093010`): the earlier
    00:26 run predated the forward-fix, so it could not cover the final
    `fft_vendor_ip_adapter` (`cfg_tdata[0]=FWD_INV=1` + config handshake + three
    fault classes). The re-run staged fresh `.v` copies from `rtl/*.sv` and
    confirmed `assign cfg_tdata = 8'd1;` in the staged adapter. Result:
    `SMARTSCAN_PRODUCTION_OOC_RESULT result=PASS device=JFMQL30TAI676H
    clock_ns=10 includes_fft=YES includes_hann=YES includes_double_buffer=YES
    production_bitstream=NO`; final setup worst slack +0.209 ns, hold worst
    slack +0.100 ns (both MET). This is the OOC coverage evidence for the final
    adapter (task 1), not the older 00:26 numbers.

- Real vendor XFFT 9.1 behavioural simulation (functional, not the migrated EDIF
  shell, not a self-written DFT): `scripts/simulate_real_fft.ps1` compiles the
  full production datapath (Hann framer -> `smartscan_fft_1024` behavioural sim
  netlist -> u54 magnitude-square -> fftshift double buffer) with xvlog/xelab/
  xsim in an independent ASCII temp working directory. It never opens the frozen
  `smartscan_fft_build.xpr` or the migrated EDIF.
  Result: `SMARTSCAN_REAL_FFT_SIM result=PASS tones=2`, TB token
  `TB_SMART_SCAN_REAL_FFT PASS tones=2 cases=12 faults=3`.
  - FFT direction contract (the bins that must NOT mirror): +37-bin tone ->
    natural bin 37 -> fftshift bin 549; -37-bin tone -> natural bin 987 ->
    fftshift bin 475. Both landed exactly, proving the transform runs FORWARD
    (`cfg_tdata[0]=FWD_INV=1`, matching the core's power-on default
    `fwd_inv_int_reg` FDSE INIT=1). A mirrored 549<->475 swap would mean inverse.
  - Clean cases (peak bin in fftshift storage order): tone_pos37=549,
    tone_neg37=475, tone_dc=512, tone_bin511=1023, dual_tone={549,475},
    random=835, multi_frame=3x549 (three back-to-back frames through one FFT
    instance, no reset between), zero (flat), pulse.
  - Fault cases (latched into `status_overflow` via `data_halt`):
    short_frame (early tlast -> `event_tlast_unexpected`, overflow=1),
    bubble (mid-frame valid drop -> `event_data_in_channel_halt`, i.e. INPUT
    starvation not "output too slow", overflow=1), reset_recovery (mid-frame
    reset then a clean frame still passes, peak=549).
  - NumPy cross-check of the dumped PSD against `reference/smart_scan_golden.py`
    (same frozen Hann window + rounding口径): `CHECK_REAL_FFT_NUMPY result=PASS
    cases=9 rel_tol=0.05` with peak-relative tolerance (5% of frame peak power
    plus a 4096-count absolute floor; a per-bin relative tolerance would falsely
    fail the fixed-point noise floor against near-zero sidelobes). Peak bins are
    exact in every case; the FFT output is NOT bit-identical to the float NumPy
    FFT (vendor fixed-point butterfly truncation), which is expected and is why
    the check is peak-relative.
  - Evidence: `evidence/real_fft_review_fix/psd_<case>.hex` (full PSD dump per
    case), `real_fft_xsim.log`, `real_fft_xelab.log`, `real_fft_xvlog_*.log`,
    plus `SHA256SUMS.txt` (all evidence files) and `frozen_inputs.sha256`
    (behavioural netlist + the SHA-locked window/power/writer/golden inputs).
    Behavioural netlist SHA256:
    `d899bd48dd120a82b5c8001964add985cbb70fd60cc8047c9fef122b3baa26d9`.

## PS/PL integration (in progress, task 2-4)

New deliverables for the FPGA actual-integration phase (B line). The datapath
(`smart_scan_top`) is unchanged and reuses the board's validated PS/PL blocks:

- `contract/pspl_register_map.md` — frozen `SS_` register map (contract §6
  backfill): data group (SS_IQ_BASE/SS_IQ_BYTES), control (SS_CTRL), status
  (SS_VERSION/SS_STATUS/SS_FRAME_ID/SS_IQ_ACCEPTED/SS_ERR_CODE), PSD readback
  (SS_RD_CTRL/SS_RD_DATA_LO/SS_RD_DATA_HI) with the anti-tear read protocol.
- `rtl/smart_scan_iq_frame_marker.sv` — inserts the per-frame `tlast` on sample
  1023 (the DDR reader/unpacker carries no frame boundary; the framer and the
  FFT writer both require it).
- `rtl/smart_scan_pspl_regs.sv` — SS_ register bank (gp_clk), speaking the
  platform User_Reg_* 32-bit protocol; START toggle, CLEAR, config validation
  (64B-aligned base + 4096-multiple byte count), PSD read request handshake.
- `rtl/smart_scan_pspl_engine.sv` — full engine: register bank + CDC (config
  2-FF, `job_domain_controller` per-domain reset/start, toggle handshakes for
  status/completion/readback) + `pl_ddr_iq_input_adapter` (DDR read -> async
  FIFO -> unpacker) + frame marker + `smart_scan_top` + PSD read bridge
  (registered bank/addr, 1-cycle BRAM latency wait, capture, done toggle) +
  completion detection (`input_done && frame_id >= bytes/4096`).
- `deps/adapters/` + `deps/rtl/` — read-only copies of the validated board
  blocks (`pl_ddr_iq_input_adapter`, `user_ddr_iq_reader`, `iq_beat_unpacker`,
  `async_fifo_gray`, `job_domain_controller`) with `deps/SHA256SUMS.txt`
  provenance. No board file was modified in place.
- `software/fpga_backend.hpp` — header-only C++ driver for the frozen
  `software|fpga|auto` backends; FPGA scan with anti-tear readback and `auto`
  fallback on any fault (version mismatch / timeout / protocol error / overflow
  / frame not committed / generation change / read timeout / sample-count
  mismatch). Register I/O is behind an abstract `RegIo` (board mmap or host
  mock).

Clock note: the engine is designed to run `smart_scan_top` on the board's
existing 50 MHz `core_clk` (no new clock wizard, no disturbance to the frozen
NPU core). 50 MHz (20 ns) is a strictly looser constraint than the OOC-verified
100 MHz (10 ns); the full-project STA must still be re-run at the real 50 MHz
clock before any `production_bitstream=YES` claim.

- **Engine PS/PL TB (2026-10-29)** — `scripts/simulate_pspl.ps1` re-run after the
  CDC reset-domain fix. Result: `SMARTSCAN_PSPL_SIM result=PASS cases=3 faults=2`,
  TB token `TB_SMART_SCAN_PSPL PASS cases=3 faults=2`.
  - Reset-domain split (the fix): gp-side status/completion latches reset only by
    the global `gp_rst_n` (no per-job reset); the core-side completion block
    `toggle`/`cap_*` reset by `core_global_rst_n`; the edge-detector `completion_d`
    resets by `core_job_rst_n`. This removes the spurious 1->0 completion edge at
    job start (previously status=0x82 committed_valid=0).
  - Cases: zero_1frame, tone_1frame (fftshift peak 549), tone_2frames (fid=2
    bank=1). Faults: bad_config (bytes=4000, BAD_CONFIG error), ddr_stall
    (stall_after=8 -> overflow).
  - The C++ driver selftest (three-backend `software|fpga|auto` + anti-tear
    readback + auto fallback) passed 8/8 in the pre-integration run.

- **FFT netlist for the board Vivado flow (2026-10-29)** — the migrated Procise
  EDIF `vivado_fft/latest_result/migrated_procise/smartscan_fft_1024.edif`
  carries FMSH primitive names (CU48E1/DRURE/DRUSE/LCARRY4/RAMH18E1/SHR16E/
  SHRC32E). A Vivado `read_edif`+`link_design` probe against `xc7z030ffg676-2`
  showed all of them as unresolved black boxes (4398 DRURE, 13 CU48E1, 8
  RAMH18E1, 372 LCARRY4, 1100 SHR16E, ...). That EDIF is Procise-only and must
  NOT be used in the board's Vivado m3/m4 P&R flow.
  - Fix: re-synthesise the same frozen XFFT 9.1 IP for the board part
    `xc7z030ffg676-2` (standard Unisim) via `build_xfft_z030.tcl`. Result:
    `XFFT_Z030_BUILD_RESULT result=PASS part=xc7z030ffg676-2
    ip=xilinx.com:ip:xfft:9.1 primitives=standard_unisim production_bitstream=NO`.
    Standard EDIF export `smartscan_fft_1024_z030.edif` (CARRY4/DSP48E1/FDRE/
    FDSE/INV/LUT1-6/RAM64X1S/RAMB18E1/SRL16E/SRLC32E/VCC), matching the board's
    own `AI_Mate.edif` pattern (EDIF + empty `_stub.v` black box).

- **Full-project synthesis, candidate copy (2026-10-29)** — `m3_synth_smartscan.tcl`
  (staging `F:/FPGA_Work/sdr_full_chain_12class_smartscan_candidate_v1/fpga`,
  ASCII path) opens a COPY of the frozen NPU base project, adds the 13 smart-scan
  RTL files + `smartscan_fft_1024_z030.edif` + black-box stub, switches the top to
  `pl_ddr_mandatory_core_top_combined_smartscan` (port list byte-identical to the
  board's frozen combined top), resets and relaunches `synth_1 -jobs 1`.
  Result: `==M3S_SYNTH_OK==`, `==M3S_SYNTH_STATUS=synth_design Complete!==`,
  `==M3S_SYNTH_PROGRESS=100%==`. Synthesis finished with 0 errors.
  - The 10 critical warnings are pre-existing board items, not smart-scan RTL:
    `Synth 8-4442` BlackBox `ZGolo` (the FMSH ZG330 NPU black box) unconnected
    `pl_exhs[7:0]`/`pl_exhs_vld`/`pl_buyi_error` pins, and two
    `set_clock_groups` no-valid-object warnings from the board's own
    `cdc_async_groups.xdc` (`clk_fpga_0`, `u_clk_wiz_core_50/inst/clk_in1`) that
    resolve at implementation time. No smart-scan RTL error or critical warning.
  - `production_bitstream` remains NO: this is a candidate-copy build only; the
    frozen bitstream `22fec95c…` is untouched and stays the delivery baseline.

## Not yet completed

- No complete smart-scan bitstream, PS-to-PL AXI data path, PS buffer readback,
  automatic fallback, board A/B or RF regression has been performed. The
  production OOC harness still drives the datapath with internal LFSR IQ and
  reads `committed_bank` directly; it verifies the framer/window/FFT/PSD/buffer
  datapath RTL in OOC but is not the production bitstream and does not exercise
  the real PS<->PL interface.
- The official FMSH migration flow was attempted after a real `synth_1` top
  build, but the IP patch repeatedly emitted `Unrecognized character` during
  `runEco0` while opening the XFFT DCP. It was stopped without a PASS token and
  superseded by the same-synthesis-session EDIF export; see
  `XFFT_MIGRATION_ATTEMPT.md`.

Status: `PRODUCTION_OOC_COMPLETE_PSPL_AND_BITSTREAM_PENDING`.
