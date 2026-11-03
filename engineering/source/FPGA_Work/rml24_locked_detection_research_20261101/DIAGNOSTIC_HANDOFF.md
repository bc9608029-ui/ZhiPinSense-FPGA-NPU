# Targeted search-failure diagnosis

Formal result remains fixed239/240, search234/240, sweep23/24, wide13/13; candidate not promoted. No scores or thresholds changed.

## Evidence

- Three formal search rejects happened at the unchanged locked LO. Public detector scores/CFO caused rejection. Original formal IQ was not retained, so exact replay of those three original failures is unavailable.
- New six-waveform diagnostic retained 58 unaveraged raw captures on board. Twenty captures fall in the predeclared steady TX windows. Original detector accepted19, centered pilot detector accepted20; original recovery succeeded20. Outside TX windows27 captures were rejected by both.
- Frozen-model replay: added detection at capture23 classified18 correctly. Persistent QAM confusions14->16 and13->15 remain under the original TX precision.
- Clean-source NPU replay: all six targeted source IQs classify correctly. Simulated current quantization with pilot calibration reproduces14->16 and13->15. Removing pilot scale bias corrects13 but not14. This supports numerical quantization/calibration contribution; does not prove it is the sole RF cause.
- Measured recovered QAM gains are around1.007 to1.012; this is consistent with the calculated pilot rounding bias but also includes channel/recovery errors.

## Restrictions

- Centered detector is isolated research, only for verified locked LO. Do not replace wide-CFO acquisition. Existing recovery head/tail verification must remain.
- Six targeted waveforms are development data, not an independent accuracy benchmark.
- All NPU replays use one guarded owner and restore baseline after clean EOF. Model, bitstream, frame structure and autostart are unchanged.
- High-precision TX test chooses digital scale using component peak only, and compensates analog TX attenuation. Ideal pilot mismatch is recorded, not a calibrated RF power measurement.

## Files

DETECTION_COMPARISON.json; CLASSIFIED_COMPARISON.json; PURE_QUANT_SCORE.json; AMPLITUDE_DIAG.json; LOCKED_SCOPE_TEST.json.
Board unaveraged IQ: /root/rml24_locked_detection_research_20261101/raw_*.npy.
Next comparison outputs: E:/FPGA_Work/rml24_tx_precision_rf_20261101.
