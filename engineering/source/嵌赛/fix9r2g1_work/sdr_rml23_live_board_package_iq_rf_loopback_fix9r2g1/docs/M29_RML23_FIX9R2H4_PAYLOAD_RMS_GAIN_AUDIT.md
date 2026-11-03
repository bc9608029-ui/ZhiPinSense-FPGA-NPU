# M29 RML23 fix9r2h4 — payload RMS magnitude audit

## Scope

This is the minimum amplitude-estimator correction after the fix9r2h3a R8 run.
It does not change the model, labels, preprocessing, frame layout, correlation or
residual thresholds, retry policy, TX ceiling, FPGA image, or NPU binary.

## Board evidence

For BPSK `quantized_d2_2p56m_000006.ci16`:

- TX component-RMS target: `2048`
- TX digital scale: `2.291509`
- raw aligned payload complex RMS: `43.969756`
- expected unscaled payload complex RMS (R8 audit only): `1263.930964`
- training-block LS magnitude: `0.016284`
- provisional recovered complex RMS: `1178.365575`
- active-region scale error: `0.068177`

`1178.365575 / 1263.930964 = 0.93218`, exactly matching the reported uniform
scale deficit.  Correlation remained `0.998811`, so this is magnitude bias rather
than waveform-shape distortion.

The public TX contract normalizes every final quantized payload to component RMS
2048.  Therefore the label-free RF magnitude is:

```
payload_rms_gain_mag = rx_payload_component_rms / tx_target_component_rms
```

For the recorded BPSK capture this is
`43.969756 / (sqrt(2) * 2048) = 0.015181`, which predicts the original payload
RMS after also undoing `tx_scale`.

## Runtime semantics

- ZC remains the timing/CFO/SRO reference.
- The common payload training block remains the phase reference and supplies the
  unchanged correlation/residual fidelity gates.
- Magnitude uses only the received payload energy and the public TX RMS contract.
- No label, class, frozen prediction, or expected-payload sample enters estimation.
- Expected payload remains diagnostic-only for the final R8 `<=5%` audit.
- Non-finite, zero, or out-of-bounds payload RMS estimation fails closed with
  `PAYLOAD_RMS_GAIN_NOT_FOUND`.
- A zero TX target preserves the previous training-block magnitude path for legacy
  callers; the board R8/R9 command uses the explicit positive target `2048`.

## Verification

The core host test synthesizes different gains for the common training block and
the payload.  It verifies that training-only magnitude exceeds the 5% scale-error
limit, while payload-RMS magnitude plus training-block phase restores the payload
within the unchanged limit.  The full host suite must remain green before board
delivery.

## Stop point

Deliver only a two-sample BPSK/4ASK R8 package.  Do not run the 46-sample regression
until R8 reports `scored=2`, `rf_excluded=0`, `prediction_agreement=2`, and
`payload_scale_error_max<=0.05`.
