# Current adaptation research and formal run

User explicitly authorized four new formal RF rounds for gain-freeze plus locked-pilot fallback. Running sequentially under E:/FPGA_Work/rml24_lockpilot_formal_prep_20261101. Requirements: fixed>=235/240; search>=237/240; sweep24/24; coordinated13/13. Same frozen240 source waveforms and original TX quantization. Missing/reject/wrong count as failures. No automatic deployment.

## Read live state first

- Formal STATUS.json and RESULTS.json in the formal root.
- monitoring/FORMAL_MONITOR.json: process liveness and completed rounds.
- monitoring/PAIRED_PROGRESS_AUDIT.json: waveform-matched changes versus prior gain-freeze run.
- monitoring/PERFORMANCE_AUDIT_FINAL.json: generated after finish or controller exit.
- Each round TX.log, SCORE.json, EVIDENCE.json.gz and RESTORE.txt.
- monitoring/SLEEP_GUARD.json: temporary no-idle-sleep request; display may be off.

Do not change the frozen candidate, helpers, plan, model, thresholds, bitstream, autostart or truth set while running. Do not open another radio/NPU owner. UART is used at round transitions, clock calibration and wide13 tuning.

## Completed research, separate from formal

1. Locked-pilot fallback integrated search short smoke24/24, missing0, valid95 all FPGA display backend, NPU760 frames/apply1/reset759/discipline1, clean guard and baseline restoration. E:/FPGA_Work/rml24_lockpilot_integrated_smoke_20261101.
2. TX integer quantization and pilot rounding reproduce two persistent QAM confusions. Higher numerical precision with analog attenuation compensation improves targeted failures;24 existing source0 waveforms51/51 captures correct. E:/FPGA_Work/rml24_tx_precision_rf_20261101 and rml24_tx_precision_24rf_20261101. Not all240 RF tested with this TX change, not power-meter calibrated, not included in formal RX candidate.
3. Same unaveraged8-repeat captures prefix averaging:1=51/51,2=50/51,4=50/51,8=51/51. This is NOT actual shortened-frame RF. E:/FPGA_Work/rml24_repeat_precision_paired_20261101.
4. Actual1-repeat cyclic RF under higher-precision TX: first eligible per-source22/24; all steady-window captures32/35. Errors include128QAM,AM-SSB-WC,AM-DSB-SC. All35 recovered captures detected1 repeat. Not qualified to replace8. E:/FPGA_Work/rml24_single_repeat_precision_rf_20261101.
5. Compatibility recovery prototype tries unchanged frozen8 first, then strict known-tail1/2/4 only on primary failure. Synthetic24 original8 cases bit-exact;72 other-count cases correctly identified; small noise tests0 accepts. Not RF qualified. E:/FPGA_Work/rml24_repeat_compatibility_research_20261101.
6. Single-repeat full-frame-context equalization prototype:72 synthetic channel cases, median IQ error0.01243 ->0.00728, improved60/72. Some cases regress; no classification claim. E:/FPGA_Work/rml24_linear_equalization_research_20261101.

## Real automatic continuation

The formal controller runs four rounds, restores baseline each round, and records all errors. Independent local monitor and paired audit observe completion. A separate after_formal.py waits for ALL_ROUNDS_COMPLETE_NOT_DEPLOYED and verified final clean/restored evidence. Only then it runs a short frozen-NPU offline replay on the saved35 actual1-repeat captures comparing the linear-context EQ. It does not transmit RF, modify official files, retrain or deploy. It restores baseline and writes SCORE.json and CHAIN_STATUS.json. On formal early exit it writes BLOCKED and does not touch devices.

Further long RF experiments still require explicit consent. Preserve formal gate failures and do not silently substitute the optional TX precision or reduced-repeat research into those scores. Current official release remains /opt/rml24-integrated/releases/range_20261101.
