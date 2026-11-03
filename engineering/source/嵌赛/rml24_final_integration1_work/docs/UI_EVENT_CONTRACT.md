# Final UI event contract

`rml24-final-ui-v1` is the only new result-to-UI adapter in this integration
tree.  It keeps classification state separate from IQ and spectrum validity.

## Rules

- A recovery or inference failure has `prediction=null` and
  `state=RECOVERY_FAILED`; the UI must not retain a stale class as current.
- `LOW_CONFIDENCE` is a display state only.  It does not remove the frame from
  an accuracy denominator or change the predicted class.
- IQ points are shown only when `iq_valid=true`. They are 256 display points
  compactly encoded by `iq_i16_interleaved`; `iq_units_per_count` reconstructs
  recovered-IQ units.
- Spectrum is shown only when `spectrum_valid=true` with exactly 256 bins.
- Truth exists only in the optional `self_test` object built by an external
  test controller.  It is never an input to recovery or inference.
- The recorded RF evidence does not include PC-side IQ files for all 480
  frames, so the generated replay currently sets `iq_valid=false` and
  `spectrum_valid=false` rather than fabricating data.

This contract is intentionally independent of the old 23-class UI protocol.
An adapter to the board framebuffer UI will be added only after the final
24-class parser accepts this schema in host tests.

## Live display derivation

For a successfully recovered live frame, both visuals are derived from the
same frozen `[8,2,1024]` tensor sent to the NPU. The eight repeated payload
windows are point-wise averaged for display only; inference still runs all
eight independently and averages their logits.

The spectrum is a Hann-windowed 1024-point complex FFT, reduced to 256 power
bins and stored as `spectrum_db_rel_x4` (four integer counts per dB, peak at
0 dB). It is relative dB, deliberately not called dBFS.

